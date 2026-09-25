"""
checkpoint.py - نقاط حماية (Checkpoints + Canary) — ركن تنفيذ حقيقي/أمان
=========================================================================
قبل أي تعديل حرج أو تحسين ذاتي نلتقط "لقطة كاملة": نسخ ملفات مصدّقة وخاصة
(الأصول التي لا تُمسّ) في مجلد checkpoints/ مع تفريع للاضطراري.

القاعدة الذهبية:
  - اللقطة تُبقي الأصل سليماً؛ الاستعادة تُعيد الملفات الأصلية فقط وليس مصنوعات
    مؤقتة (لا نعيد المكتبات نصف-المكتوبة على حساب أصلٍ سليم).

الاستخدام:
  python agent_os/checkpoint.py snap [سبب]
  python agent_os/checkpoint.py list
  python agent_os/checkpoint.py restore <id> [سبب]
  python agent_os/checkpoint.py verify <id>
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

CH_DIR = os.path.join(C.AGENT_OS_DIR, "checkpoints")
INDEX_FILE = os.path.join(CH_DIR, "index.json")

# الملفات الأصولية السليمة: هذه تُحفظ وتُستعاد. لا نستعيد الملفات شبه-المصنوعة.
PROTECTED_CORE = ("kernel.py", "goal_manager.py", "goal_manager.py.bak",
                  "employ.py", "employ.pyc", "watchdog.py")


def _loaded():
    return C.load_json(INDEX_FILE, {"checkpoints": []})


def _save(state):
    C.atomic_write(INDEX_FILE, state)


def snap(reason="دوري", include_self_improve=False):
    """لقطة كاملة: ملفات نواة + (اختياري) دورات التحسين الذاتي المعلّمة."""
    os.makedirs(CH_DIR, exist_ok=True)
    cid = C.now_compact()
    folder = os.path.join(CH_DIR, cid)
    os.makedirs(folder, exist_ok=True)
    copied = []
    for fname in PROTECTED_CORE:
        src = os.path.join(C.AGENT_OS_DIR, fname)
        if os.path.exists(src) and os.path.isfile(src):
            try:
                shutil.copy2(src, os.path.join(folder, fname))
                copied.append(fname)
            except Exception:
                pass
    # المصدر الحقيقي للنواة هو مجلد الحزمة وليس مجلد البيانات
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    for fname in PROTECTED_CORE:
        if fname in copied:
            continue
        src = os.path.join(pkg_dir, fname)
        if os.path.exists(src) and os.path.isfile(src) and fname.endswith(".py"):
            try:
                shutil.copy2(src, os.path.join(folder, fname))
                copied.append(fname)
            except Exception:
                pass
    if include_self_improve:
        for extra in ("requests.json", "resolve.json"):
            src = os.path.join(C.AGENT_OS_DIR, extra)
            if os.path.exists(src):
                try:
                    shutil.copy2(src, os.path.join(folder, extra))
                    copied.append(extra)
                except Exception:
                    pass
    entry = {"id": cid, "when": C.now_iso(), "reason": reason[:100],
             "files": copied}
    state = _loaded()
    state["checkpoints"].append(entry)
    state["checkpoints"] = state["checkpoints"][-30:]
    _save(state)
    C.log(f"💾 لقطة #{cid}: {len(copied)} ملفاً محفوظاً ({reason})")
    return entry


def list_checkpoints():
    return [c for c in _loaded()["checkpoints"]]


def verify(cid):
    """تحقق أن اللقطة ملفاتها موجودة وسليمة الحجم — من دون فتح النواة."""
    folder = os.path.join(CH_DIR, cid)
    if not os.path.isdir(folder):
        return {"ok": False, "reason": "المجلد مفقود"}
    names = os.listdir(folder)
    return {"ok": bool(names), "files": len(names), "size_kb":
            round(sum(os.path.getsize(os.path.join(folder, n)) for n in names) / 1024, 1)}


def restore(cid, reason="استعادة يدوية"):
    """استعادة ملفات نواة أصلية سليمة من اللقطة — لا تمسّ مصنوعات فوضوية."""
    folder = os.path.join(CH_DIR, cid)
    if not os.path.isdir(folder):
        return {"ok": False, "reason": "لقطة غير موجودة"}
    only_expected = set(PROTECTED_CORE)
    restored, skipped = [], []
    for fname in only_expected:
        src = os.path.join(folder, fname)
        if not os.path.exists(src):
            continue
        dst = os.path.join(C.AGENT_OS_DIR, fname)
        try:
            shutil.copy2(src, dst)
            restored.append(fname)
        except Exception as e:
            skipped.append((fname, str(e)[:80]))
    # لا نحذف ملفات غريبة — مجرد إعادة أصل سليم فوقها
    C.log(f"🪤 استعادة #{cid}: {len(restored)} ملفاً أصلياً، تجاوز {len(skipped)} ضدياً")
    return {"ok": not skipped or bool(restored), "restored": restored,
            "skipped": skipped}


def canary_restore(cid, before, after):
    """طلاء كناري: إن بدا التعديل لوحة لا تقرأ فلا نستعيد الصمت — نعيد الأصل."""
    if not cid:
        return {"ok": True, "decision": "no_snapshot_needed"}
    rebuilt = verify(cid)
    if not rebuilt["ok"]:
        return {"ok": False, "decision": "cannot_restore_broken_snapshot",
                "why": rebuilt.get("reason")}
    # الاستعادة لا تُنفّذ تلقائياً؛ الطلب يُرسل للموافقة لأنه يلمس النواة
    try:
        from agent_os import approval_center
        approval_center.request(
            title=f"استعادة لقطة #{cid}",
            body=f"قبل: {before}\nبعد: {after}\nسبب: تطبيق تحديث كود حرج فشل في الحفظ.",
            kind="code_restore", by="canary", priority="high")
    except Exception:
        pass
    return {"ok": True, "decision": "restore_queued"}


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("snap", "snapshot"):
        print(snap(args[1] if len(args) > 1 else "دوري"))
    elif args[0] == "list":
        for c in list_checkpoints():
            print(f"#{c['id']}  {c['when'][:16]}  {c['reason'][:40]} ({len(c['files'])} ملف)")
    elif args[0] == "verify" and len(args) > 1:
        print(verify(args[1]))
    elif args[0] == "restore" and len(args) > 1:
        print(restore(args[1], args[2] if len(args) > 2 else "استعادة يدوية"))
    else:
        print("الاستعمال: snap [سبب] | list | verify <id> | restore <id> [سبب]")