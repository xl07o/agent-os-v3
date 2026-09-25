"""
mission_generator.py - مولّد المهام الذاتية (ركن استقلالية/تعلم)
=================================================================
يؤلّف "مهمة ليلية" من مصادر محلية حقيقية — بلا ادعاء:

  - الهدف النشط ذو الأولوية العليا مع مهام قابلة للتنفيذ الآن
  - أولوية فرصة من عقل الفرص (opportunity_brain)
  - أضعف نطاق في المقاييس (benchmark.weakest_categories)
  - مهارات قليلة الاستعمال (تستحق الحرارة) — اختياري

ينتج missions.json ويقترح مهمة واحدة فقط للدورة (insert_anywhere حرة).
النواة تستهلكه عرضية: بلا تحويل لهدف دائم إجبارياً (لا فوضى أهداف).

الاستخدام:
  python agent_os/mission_generator.py compose
  python agent_os/mission_generator.py next
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

MISSIONS_FILE = os.path.join(C.AGENT_OS_DIR, "missions.json")


def _load():
    return C.load_json(MISSIONS_FILE, {"missions": [], "next_id": 1})


def _save(state):
    C.atomic_write(MISSIONS_FILE, state)


def compose():
    """ؤلّف مهمة واحدة قابلة للتنفيذ الآن حسب الأولوية — free فقط (بدون حرق رصيد)."""
    reason = ""
    seed = ""

    # المصدر 1: هدف نشط ذو أولوية عليا له مهام
    try:
        from agent_os import goal_manager
        for g in goal_manager.get_active_goals() or []:
            if g.get("priority") == "high" and (g.get("tasks") or []):
                actionable = [t for t in g["tasks"] if t.get("status") == "pending"
                              and not t.get("requires_approval")]
                if actionable:
                    seed = g["title"][:80]
                    reason = f"هدف نشط عالي الأولوية: {g['title'][:60]}"
                    break
    except Exception:
        pass

    # المصدر 2: أقوى فرصة محلية (لا إنفاق)
    if not seed:
        try:
            from agent_os import opportunity_brain
            opps = opportunity_brain.scan().get("opportunities", [])
            if opps:
                best = opps[0]
                seed = best["name"][:80]
                reason = "فرصة محلية من عقل الفرص"
        except Exception:
            pass

    # المصدر 3: أضعف نطاق مقاييس
    if not seed:
        try:
            from agent_os import benchmark
            weak = benchmark.weakest_categories(1)
            if weak:
                seed = f"تقوية: {weak[0][0]}"
                reason = "أضعف نطاق في المقاييس"
        except Exception:
            pass

    if not seed:
        return {"ok": False, "reason": "لا مصادر مهمة الآن"}

    state = _load()
    mid = state["next_id"]
    state["next_id"] += 1
    mission = {"id": mid, "title": seed, "reason": reason,
               "free": True, "status": "proposed",
               "created": C.now_iso()}
    state["missions"].append(mission)
    state["missions"] = state["missions"][-50:]
    _save(state)
    C.log(f"🚀 مهمة مقترحة #{mid}: {seed} ({reason})")
    return mission


def next_mission():
    """أقدم مهمة مقترحة جاهزة — تُجذب مرة واحدة ولا تتكرر."""
    state = _load()
    for m in state["missions"]:
        if m.get("status") == "proposed":
            m["status"] = "picked"
            _save(state)
            return m
    return None


if __name__ == "__main__":
    import json
    args = sys.argv[1:]
    if args and args[0] == "next":
        print(json.dumps(next_mission() or {"none": True}, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(compose(), ensure_ascii=False, indent=1))