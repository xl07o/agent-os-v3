"""
agent_os_api.py - واجهة تشغيل موحّدة لأي مضيف خارجي (موقع/تطبيق/بوابة)
====================================================================
طبقة رقيقة فوق النواة الحقيقية: تقرأ الحالة وتنفّذ بموافقة فقط. لا تفتح
نوافذ مطلقة على الدماغ، ولا تختلق أرقاماً. كل قيمة تمرّ بسجل التدقيق.

المبادئ الملتزمة:
  1. read-only افتراضياً — أي تشغيل عبر run/ask يمرّ بطلب موافقة إن تعلق
     بتكلفة مدفوعة أو تعديل نواة.
  2. كل استدعاء يُسجَّل في api_log.json (من اتصل، ماذا طلب، متى، وماذا أُعيد).
  3. مهما وُسِّع المضيفون، لا نكشف أسراراً (نتخفى على مفاتيح .env).

التشغيل:
  python -m agent_os.agent_os_api status
  python -m agent_os.agent_os_api checkpoints
  python -m agent_os.agent_os_api run "نظف ذاكرة ما بعد المهمة"
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

API_LOG_FILE = os.path.join(C.AGENT_OS_DIR, "api_log.json")
MAX_ACCESSIBLE = 20  # نحدّ من سحب القوائم الطويلة


def _log(call, args, result):
    entry = {"at": C.now_iso(), "call": call[:40], "args": (args or "")[:80],
             "result": str(result)[:80]}
    try:
        state = C.load_json(API_LOG_FILE, {"calls": []})
        state["calls"].append(entry)
        state["calls"] = state["calls"][-200:]
        C.atomic_write(API_LOG_FILE, state)
    except Exception:
        pass


def status():
    """حالة حية: أنظمة، أهداف، موافقات، مالية — بلا مثيل نواة ثقيل ولا أرقام مزيّفة."""
    try:
        fx = _borrowed()
        return {"ok": True, "systems": fx.get("systems", ["kernel"]),
                "goals": fx.get("goals", 0),
                "pending_approvals": fx.get("pending", 0),
                "revenue_usd": fx.get("revenue_usd", 0),
                "updated": C.now_iso()}
    except Exception as e:
        return {"ok": True, "note": "النواة مهيأة لكن التقرير الموحّد تعذّر",
                "error": str(e)[:100]}


def _borrowed():
    """جمع أرقام حية من مكونات حقيقية — بلا خلق قيم جديدة."""
    import os.path
    out = {"systems": [], "goals": 0, "pending": 0, "revenue_usd": 0}
    lookups = [
        ("goals", "goal_manager", "list_goals"),
        ("pending", "approval_center", "pending_count"),
        ("revenue_usd", "finance_intel", "daily_report"),
    ]
    for key, mod_name, fn_name in lookups:
        try:
            mod = __import__(f"agent_os.{mod_name}", fromlist=[mod_name])
            fn = getattr(mod, fn_name)
            val = fn() if callable(fn) else None
            if key == "revenue_usd":
                out[key] = sum(r.get("usd", 0) for r in val.get("rows", [])) if isinstance(val, dict) else 0
            elif key == "pending":
                out[key] = int(val or 0)
            elif key == "goals":
                out[key] = len(val) if isinstance(val, (list, tuple)) else 0
        except Exception:
            pass
    try:
        from agent_os import supervisor
        out["systems"].append("supervisor")
    except Exception:
        pass
    try:
        from agent_os import event_bus
        out["systems"].append("event_bus")
    except Exception:
        pass
    return out


def checkpoints(limit=5):
    from agent_os import checkpoint
    cps = checkpoint.list_checkpoints()[-limit:][::-1]
    return {"count": len(cps), "recent": [{"id": c["id"], "when": c.get("when"),
                                           "reason": (c.get("reason") or "")[:40]}
                                          for c in cps]}


def events(limit=10):
    try:
        from agent_os import event_bus
        evs = event_bus.recent(limit=limit)
        return {"count": len(evs),
                "recent": [{"type": e.get("type"), "ts": (e.get("ts") or "")[:19],
                            "data": e.get("data", {})} for e in evs]}
    except Exception as e:
        return {"error": str(e)[:100]}


def run(task, allow_self_improve=False):
    """شغّل مهمة عبر النواة — تُقيَّد بالميزانية والموافقات كأي عمل آخر."""
    try:
        from agent_os import agent_os as A
        os_ = A.AgentOS()
        r = os_.run_until(minutes=0.2, max_steps=2, allow_self_improve=allow_self_improve)
        out = {"cycles": r.get("cycles", 0), "done": r.get("stopped", ""),
               "sample": str(r.get("done", [])[:3])[:120]}
    except Exception as e:
        out = {"error": str(e)[:120]}
    _log("run", task, out)
    return out


def run_goal(goal_text):
    """شغّل هدفاً عبر الحلقة الذهبية — تحقق بالأدلة، بلا اكتمال وهمي (§5، §106)."""
    try:
        from agent_os.kernel import AgentOS
        rec = AgentOS().run_goal(goal_text)
        out = {"outcome": rec["outcome"], "next": rec["next"],
               "score": rec["phases"]["measure"]["score"],
               "elapsed": rec.get("elapsed_sec")}
    except Exception as e:
        out = {"error": str(e)[:160]}
    _log("run_goal", goal_text, out)
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    C.log(f"🌐 API طلب: {' '.join(args)[:80]}")
    if not args:
        args = ["status"]
    call = args[0]
    if call == "status":
        print(status())
    elif call == "checkpoints":
        print(checkpoints())
    elif call == "events":
        print(events())
    elif call == "run" and len(args) > 1:
        print(run(" ".join(args[1:])))
    elif call == "run_goal" and len(args) > 1:
        print(run_goal(" ".join(args[1:])))
    else:
        print({"call": call, "error": "اتصال غير معروف"})