"""
swarm.py - سرب الوكيلات (مقترح كلاودي #1)
==========================================
مدير سرب يوزع المهام على وكيلات متخصصة (كل وظيفة عبر نظام agent_os) ويجمع
النتائج في تقرير موحّد.

  - بدون شبكة وبدون دماغ: كل وكيل يستدعي نظامه الحتمي المضمون.
  - مع دماغ (اختياري): role="brain" فقط حين يتوفر رصيد مدفوع (بوابة مالية).

الأدوار المضمونة:
  finance / goals / approvals / build / devops / bounty / learning / research

الاستخدام:
  python agent_os/swarm.py run finance
  python agent_os/swarm.py run all
  python agent_os/swarm.py state
"""

import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

SWARM_FILE = os.path.join(C.AGENT_OS_DIR, "swarm_runs.json")
MAX_AGENTS = 8  # حد أمان هيكلي فقط — ليس سقفاً على الوكيلات، بل سقف الأدوار الموزعة


def _agent_for(role):
    """وكيل متخصص = استدعاء حتمي للنظام المعني — فعّال دائماً وبلا شبكة."""
    if role == "finance":
        from agent_os import finance_intel
        return finance_intel.daily_report()
    if role == "goals":
        from agent_os import goal_manager
        return {
            "active": len(goal_manager.get_active_goals() or []),
            "next": intent(goal_manager.next_actionable_task()),
            "blocked": len(goal_manager.get_blocked_tasks() or []),
        }
    if role == "approvals":
        from agent_os import approval_center
        return {"pending": approval_center.pending_count()}
    if role == "build":
        from agent_os import product_factory
        return {"products": [p["name"] for p in product_factory.list_products()][-10:]}
    if role == "devops":
        from agent_os import devops_agent
        root = C.BASE_DIR
        try:
            return devops_agent.health_check(root)
        except Exception as e:
            return {"ok": False, "reason": str(e)[:100]}
    if role == "bounty":
        from agent_os import bounty_engine
        try:
            return {"programs": len(bounty_engine.list_programs())}
        except Exception:
            return {"programs": 0}
    if role == "learning":
        from agent_os import skill_memory
        try:
            return skill_memory.summarize()
        except Exception:
            return {"count": 0}
    if role == "research":
        from agent_os import world_model
        try:
            w = world_model.daily_delta()
            return {"changes": w.get("changes", [])[:5]}
        except Exception:
            return {"changes": []}
    if role == "brain":
        from agent_os import finance_intel
        fin = finance_intel.daily_report()
        if fin["self_earned_usd"] <= 0.0 or fin["budget_remaining_today"] <= 0.0:
            return {"status": "skip", "reason": "لا رصيد مكتسب اليوم"}
        out, _ = C.call_brain("سرب: معاينة وضع الوكيلات", text_prompt="راجع ما يفعله الوكيل الآن")
        return {"status": "ok", "summary": (out or "")[:200]}
    return {"status": "unknown_role", "role": role}


def intent(task):
    """خلاصة المهمة القادمة (goal, task) من next_actionable_task."""
    if not task or not task[0] or not task[1]:
        return None
    return {"task": (task[1].get("task") or "")[:80], "id": task[1].get("id")}


def run_swarm(tasks, use_brain=False):
    """وزّع قائمة (role, request) على الوكيلات واجمع النتائج.
    tasks: قائمة أدوار أو [[role, الطلب]...] — لا يتجاوز MAX_AGENTS وكيلاً بالجولة."""
    from_ = (tasks or [])
    roles = []
    for t in from_:
        if isinstance(t, (list, tuple)) and t:
            roles.append(str(t[0]))
        elif isinstance(t, str) and t:
            roles.append(t)
    if not roles:
        roles = ["finance", "goals", "approvals", "build"]
    roles = roles[:MAX_AGENTS]
    results = []
    for role in roles:
        if role == "brain" and not use_brain:
            results.append({"role": role, "skipped": "use_brain=False"})
            continue
        try:
            out = _agent_for(role)
        except Exception as e:
            out = {"status": "error", "reason": str(e)[:120]}
        results.append({"role": role, "out": out, "time": C.now_iso()})
    record = {"run_id": C.now_iso(), "agents": results}
    state = C.load_json(SWARM_FILE, {"runs": []})
    state["runs"].append(record)
    state["runs"] = state["runs"][-50:]
    C.atomic_write(SWARM_FILE, state)
    return record


def state():
    return C.load_json(SWARM_FILE, {"runs": []})["runs"][-10:]


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "state":
        for r in reversed(state()):
            print(f"#{r['run_id']}: " + ", ".join(a["role"] for a in r["agents"]))
    elif args[0] == "run":
        if len(args) < 2:
            print("الاستعمال: run <role|all> [--brain]")
        else:
            use_brain = "--brain" in args or False
            roles = (["finance", "goals", "approvals", "build", "devops"] if args[1] == "all"
                     else [args[1]])
            rec = run_swarm(roles, use_brain=use_brain)
            for a in rec["agents"]:
                print(f"  [{a['role']}] {a['out']}")
    else:
        print("الاستعمال: run <role|all> | state")