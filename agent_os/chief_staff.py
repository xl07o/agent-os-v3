"""
chief_staff.py - النظام 12: رئيس الأركان / جدولة الصباح (v3.0)
================================================================
متى تصحى:

  1. بصمة (world model) → ما الذي يجري اليوم؟
  2. فلتر (filter) → ما الذي يستحق التركيز؟
  3. رتب (prioritize) → ماذا نفعل أولاً؟
  4. خطة (plan) → ما هي الخطوات الفعلية؟
  5. احمِ (guard) → ما الذي سيتوقف على الموافقة البشرية؟
  6. نفّذ (run) → ادفعها إلى نواة التنفيذ.

الاستخدام:
  python agent_os/chief_staff.py wake
  python agent_os/chief_staff.py plan
  python agent_os/chief_staff.py brief
"""

import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C
from agent_os import world_model, benchmark, finance_intel, approval_center, goal_manager

DECISION_FILE = os.path.join(C.AGENT_OS_DIR, "morning_plan.json")


def wake():
    """البصمة الصباحية المدمجة."""
    wm = world_model.daily_delta()
    bench = benchmark.summary()
    fin = finance_intel.morning_brief()
    pending = approval_center.pending_summary()
    goals = [g for g in goal_manager.list_goals() if g.get("status") == "active"] if hasattr(goal_manager, "list_goals") else []
    brief = {
        "day": datetime.date.today().isoformat(),
        "world_delta": wm,
        "weakest_areas": bench.get("weakest", []),
        "finance": fin,
        "pending_human": pending,
        "active_goals": [g.get("title", "") for g in goals[:3]],
    }
    C.atomic_write(DECISION_FILE, brief)
    C.log(f"☀️ إيقاظ: {brief['day']}")
    return brief


def plan(max_actions=3):
    """رتب أولويات اليوم بحسب World Model."""
    w = C.load_json(DECISION_FILE) or wake()
    context = {
        "weak": w.get("weakest_areas", []),
        "active_goals": w.get("active_goals", []),
        "pending": w.get("pending_human"),
    }
    raw, _ = C.call_brain(
        "أنت رئيس أركان.",
        f"البيئة: {context}\nأعطِ خطة اليوم: على أسطر تبدأ بـ ACTION: و HOLD: إن تطلب موافقة.",
    )
    actions, holds = [], []
    for line in (raw or "").splitlines():
        if line.startswith("ACTION:"):
            actions.append(line.replace("ACTION:", "").strip()[:100])
        elif line.startswith("HOLD:"):
            holds.append(line.replace("HOLD:", "").strip()[:100])
    plan_rec = {"day": w.get("day"), "actions": actions[:max_actions], "holds": holds[:max_actions]}
    C.atomic_write(os.path.join(C.AGENT_OS_DIR, "morning_plan.json"), plan_rec)
    return plan_rec


def run_action(action_text):
    """دفع إجراء نصي إلى نواة التنفيذ (عبر agent_os.nucleus إن توفر)."""
    try:
        from agent_os import nucleus
        return nucleus.execute(action_text)
    except Exception as e:
        return {"ok": False, "reason": f"نواة غير متاحة: {str(e)[:80]}"}


def brief():
    """الملخص الصباحي للإنسان."""
    w = C.load_json(DECISION_FILE, None) or wake()
    text = []
    text.append(f"☀️ يوم {w.get('day')}")
    if w.get("world_delta", {}).get("changes"):
        text.append("التغييرات: " + "; ".join(w["world_delta"]["changes"][:4]))
    if w.get("weakest_areas"):
        text.append(f"أضعف مجالات الوكيل: {', '.join(w['weakest_areas'])}")
    if w.get("pending_human"):
        text.append(f"يحتاجك: {w['pending_human']}")
    if w.get("finance"):
        text.append(w["finance"])
    # المهام المحظورة (عيب 7): تُعرض للإنسان — هي بانتظار فكّ حِصارها
    try:
        from agent_os import goal_manager
        blocked = goal_manager.get_blocked_tasks() or []
        if blocked:
            lines = [f"  ⛔ {b.get('task', '')[:60]} (مانع: {b.get('blocker', '؟')})" for b in blocked[:5]]
            text.append("مهام محظورة تنتظرك:\n" + "\n".join(lines))
    except Exception:
        pass
    return "\n".join(text)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "wake":
        print(wake())
    elif args[0] == "plan":
        print(plan())
    elif args[0] == "brief":
        print(brief())
    elif args[0] == "run" and len(args) > 1:
        print(run_action(" ".join(args[1:])))