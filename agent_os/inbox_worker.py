# -*- coding: utf-8 -*-
"""
inbox_worker.py - منفّذ صندوق الوارد (ربط اللوحة بالنواة)
==========================================================
يقرأ data/agent_os/ui_inbox.jsonl (الذي تكتبه اللوحة/الوصلة) وينفّذ طلبات
نوع "task" فعلياً عبر الحلقة الذهبية (فهم→خطة→تنفيذ→تحقق→تعلم→قرر).

- تعقّب الموضع: ملف cursor يحفظ آخر بايت قرأناه (التبديل عن الـ fan).
- لا يعيد تنفيذ أي طلب: append-only + cursor.
- كل طلب يُسجَّل نتيجةً في ui_inbox_results.jsonl + حدث.
- طلبات "chat" (المحادثة العادية) لا تُنفّذ — الجسر يرد عليها مباشرة.

الاستخدام:
  python -m agent_os.inbox_worker --once           # يوزع ما ينتظره الآن
  python -m agent_os.inbox_worker --minutes 120    # حلقة مستمرة بغلاف مدة آمنة
"""

import os
import re
import sys
import time
import json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
from agent_os import _common as C

INBOX_FILE  = os.path.join(C.AGENT_OS_DIR, "ui_inbox.jsonl")
RESULTS_FILE = os.path.join(C.AGENT_OS_DIR, "ui_inbox_results.jsonl")
CURSOR_FILE  = os.path.join(C.AGENT_OS_DIR, "ui_inbox_cursor.json")
POLL_SECONDS = 20
MAX_ITEMS_RUN = 3   # أقصى عمليات لكل جولة — حماية للتكلفة

STATUS_FILE = os.path.join(C.AGENT_OS_DIR, "worker.json")
CRASH_LOG = os.path.join(C.AGENT_OS_DIR, "worker_crash.log")


def _tick(extra=None):
    """نبضة العامل: دليل بقاء حي للمراقب الخارجي (الحارس/اللوحة)."""
    try:
        import json
        d = {"pid": os.getpid(), "at": C.now_iso(), "ts": time.time(), "extra": extra or {}}
        C.atomic_write(STATUS_FILE, d)
    except Exception:
        pass


def _crash(where, err):
    try:
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(C.now_iso() + " | " + where + " | " + str(err)[:300] + "\n")
    except Exception:
        pass


# ----------------------------------------------------------------------
def _read_cursor():
    """آخر موضع بايت قُرئ. أول تشغيل أبداً: يبدأ من نهاية الملف (يتجاهل القديم)."""
    try:
        d = C.load_json(CURSOR_FILE, {})
        off = d.get("offset")
        if off is not None:
            return int(off)
    except Exception:
        pass
    try:
        if os.path.exists(INBOX_FILE):
            return os.path.getsize(INBOX_FILE)
    except Exception:
        pass
    return 0


def _save_cursor(offset):
    try:
        C.atomic_write(CURSOR_FILE, {"offset": offset, "at": C.now_iso()})
    except Exception:
        pass


def _read_new_entries():
    """يرجع قائمة dict للطلبات الجديدة منذ آخر موضع، ويحدّث الموضع فور قراءتها."""
    if not os.path.exists(INBOX_FILE):
        return []
    off = _read_cursor()
    size = os.path.getsize(INBOX_FILE)
    out = []
    if size > off:
        try:
            with open(INBOX_FILE, "r", encoding="utf-8") as f:
                f.seek(off)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    out.append(e)
        except Exception:
            pass
    # الموضع يتقدَّم دائماً (حتى بصفر قراءة) — استئناف سليم عبر عمليات إعادة التشغيل
    _save_cursor(size)
    return out


def _append_result(entry, kind, detail, ok):
    line = json.dumps({
        "time": C.now_iso(),
        "type": entry.get("type"),
        "text": str(entry.get("text", ""))[:2000],
        "kind": kind,
        "ok": ok,
        "detail": str(detail)[:4000],
    }, ensure_ascii=False)
    try:
        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _notify(level, title, message):
    try:
        from agent_os import notifier
        notifier.notify(level=level, title=title, message=message[:500])
    except Exception:
        pass


def _run_one(entry):
    text = str(entry.get("text", "")).strip()
    if not text:
        return {"ran": False, "reason": "empty"}
    learn_trigger = str(entry.get("mode", "")) == "learn" or bool(
        re.match(r"^\s*(تعل[ّ]?م|علمني|علّمني)([\s،,:؛]|$)", text))
    if learn_trigger:
        try:
            from agent_os import teach
            res = teach.teach(text)
            _append_result(entry, "learned", res.get("path", "جاهز"), ok=True)
            _notify("info", "تعلّمت درساً أمامك", text[:60])
            return {"ran": True, "learned": str(res.get("path"))[:120], "ok": res.get("ok")}
        except Exception as e:
            _append_result(entry, "learn_failed", e, ok=False)
            _notify("critical", "تعذّر التعلم الآن", f"{text[:60]} — {e}")
            return {"ran": False, "reason": str(e)[:120]}
    try:
        from agent_os import kernel
        agent = kernel.AgentOS(use_brain=True)
        res = agent.run_goal(text)
        summary = res.get("summary") or res.get("result") or res
        _append_result(entry, "executed", summary, ok=True)
        _notify("info", "وفيّت بالطلب", text[:60])
        return {"ran": True, "result": str(summary)[:120]}
    except Exception as e:
        _append_result(entry, "failed", e, ok=False)
        _notify("critical", "طلب فشل تنفيذه", f"{text[:60]} — {e}")
        return {"ran": False, "reason": str(e)[:120]}


def worker_alive(max_age_sec=90):
    """هل العامل حي؟ (الحارس يتّخذ القرار بناءً على نضارة النبضة)."""
    try:
        d = C.load_json(STATUS_FILE, {})
        return (time.time() - float(d.get("ts", 0))) <= max_age_sec
    except Exception:
        return False


def run_once(max_items=MAX_ITEMS_RUN):
    """يوزّع ما يصل حديثاً (أحدث المطلوبين أولاً). يعيد قائمة النتائج."""
    entries = _read_new_entries()
    tasks = [e for e in entries if e.get("type") == "task" and str(e.get("text", "")).strip()]
    if not tasks:
        return []
    # نفضّل الأحدث عند تجاوز السقف (لا نتراكم خلف الطابور القديم)
    picked = tasks[-max_items:] if len(tasks) > max_items else tasks
    results = []
    for e in picked:
        _tick({"mode": "processing", "current": str(e.get("text", ""))[:70]})
        results.append(_run_one(e))
        _tick({"mode": "running", "current": None})
    return results


def run_loop(minutes, poll=POLL_SECONDS):
    """حلقة مستمرة بقِفْل مدة آمنة — تشقّق بهدوء كل بضع ثوانٍ.
    صلبة ضد الانهيار: أي خطأ يُسجَّل ولا يوقف الحلقة (النبضة ترصد الحارس)."""
    deadline = time.time() + float(minutes) * 60
    ran = 0
    _tick({"mode": "start", "minutes": minutes})
    while time.time() < deadline:
        try:
            ran += len(run_once())
        except SystemExit:
            raise
        except Exception as e:
            C.log(f"⚠️ جولة صندوق الوارد: {e}")
            _crash("run_once", e)
        _tick({"mode": "running", "ran": ran})
        time.sleep(poll)
    _tick({"mode": "ended", "ran": ran})
    return {"ran": ran, "stopped": C.now_iso()}


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--once" in argv:
        print(json.dumps(run_once(), ensure_ascii=False, indent=1))
    else:
        mins = 120.0
        if "--minutes" in argv:
            try:
                mins = float(argv[argv.index("--minutes") + 1])
            except Exception:
                mins = 120.0
        print(json.dumps(run_loop(mins), ensure_ascii=False, indent=1))