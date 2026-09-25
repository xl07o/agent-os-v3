"""
daemon.py - حلقة الوكيل الدائمة «يشتغل وأنت ساكت» (البنود 2/9/10/16)
==================================================================
حلقة خلفية تعمل باستمرار وتنفّذ، كل دورة، عملاً منتِجاً بلا إشراف:
  1) تعلّم ذاتي موجَّه بأولوياتك (idle_learner ← أولويات المحادثة).
  2) دورة تحسين ذاتي واحدة في sandbox (self_improve_engine) — تُطبَّق فقط
     إن عبرت كل بوابات الاختبار.
  3) نبضة صحّة + حفظ checkpoint حتى لا يضيع التقدّم عند الانقطاع.

مصمّمة لتكون آمنة: كل خطوة معزولة (try/except)، بحدّ دورات اختياري،
وبفاصل زمني قابل للضبط. لا تتطلب شبكة ولا مفاتيح لتبدأ.

  tick()                      -> دورة واحدة، تُرجع ملخّصاً
  run(max_cycles, interval)   -> الحلقة الدائمة (Ctrl-C للإيقاف)
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

STATE_FILE = os.path.join(C.AGENT_OS_DIR, "daemon_state.json")


def _priorities():
    try:
        from agent_os.memory import conversation
        return [p["topic"] for p in conversation.priorities(3)] or None
    except Exception:
        return None


def _do_idle_learning():
    try:
        from agent_os.learn import idle_learner
        r = idle_learner.idle_learn_cycle(owner_goals=_priorities(), max_topics=2)
        return {"learned": r.get("learned_count", 0), "topics": r.get("topics", [])}
    except Exception as e:
        return {"error": str(e)[:120]}


def _do_self_improve():
    try:
        from agent_os import self_improve_engine as sic
        r = sic.improve_once(quiet=True)
        return {"status": r.get("status"), "applied": r.get("ok", False)}
    except Exception as e:
        return {"error": str(e)[:120]}


def _save_state(cycle, summary):
    try:
        st = C.load_json(STATE_FILE, {"cycles": 0, "history": []})
        st["cycles"] = cycle
        st["last"] = {"time": C.now_iso(), **summary}
        st["history"] = (st.get("history", []) + [st["last"]])[-100:]
        C.atomic_write(STATE_FILE, st)
    except Exception:
        pass


def _load_state():
    return C.load_json(STATE_FILE, {"cycles": 0, "history": []})


def tick(cycle=None, do_improve=True):
    """دورة عمل واحدة: تعلّم ذاتي + (تحسين ذاتي) + حفظ الحالة."""
    cycle = cycle if cycle is not None else _load_state().get("cycles", 0) + 1
    summary = {"cycle": cycle, "learning": _do_idle_learning()}
    if do_improve:
        summary["improve"] = _do_self_improve()
    _save_state(cycle, summary)
    C.log(f"🔁 دورة ديمون #{cycle}: تعلّم={summary['learning'].get('learned', 0)} "
          f"تحسين={summary.get('improve', {}).get('status', '—')}")
    return summary


def run(max_cycles=None, interval=1800, do_improve=True):
    """الحلقة الدائمة: كل `interval` ثانية دورة عمل. resume من حالة سابقة."""
    start = _load_state().get("cycles", 0)
    C.log(f"🟢 بدء الديمون من الدورة {start + 1} (فاصل {interval}s)")
    cycle = start
    try:
        while max_cycles is None or (cycle - start) < max_cycles:
            cycle += 1
            tick(cycle, do_improve=do_improve)
            if max_cycles is not None and (cycle - start) >= max_cycles:
                break
            time.sleep(max(1, interval))
    except KeyboardInterrupt:
        C.log("🔴 أُوقف الديمون يدوياً — الحالة محفوظة، يكمل لاحقاً من نفس النقطة")
    return {"ran_cycles": cycle - start, "total_cycles": cycle}


if __name__ == "__main__":
    import json
    if len(sys.argv) >= 2 and sys.argv[1] == "tick":
        print(json.dumps(tick(do_improve="--no-improve" not in sys.argv),
                         ensure_ascii=False, indent=2, default=str))
    elif len(sys.argv) >= 2 and sys.argv[1] == "run":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else None
        iv = int(os.getenv("DAEMON_INTERVAL", "1800"))
        print(json.dumps(run(max_cycles=n, interval=iv), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(_load_state(), ensure_ascii=False, indent=2, default=str))
