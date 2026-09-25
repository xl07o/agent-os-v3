"""
learning_engine.py - محرك التعلّم اللامحدود
=============================================
فكرة المالك: "يفتح متصفحات بجهازي ويتعلم من كل مكان... قوقل مواقع برامج كل شي"
التوسيع: محرك تعلّم مُهيكل:
  1. يحدد ماذا يتعلّم (حسب أهداف المالك + فجوات القدرات)
  2. يرتّب بالقيمة (Learning ROI §91)
  3. يتعلّم (من ذاكرته/مهاراته/عقله)
  4. يخزن المعرفة مع المصدر (provenance)
  5. يختبر الفهم (يطبّق ما تعلّمه)
  6. يسجّل المهارة الجديدة
"""

import os
import sys

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

LEARN_LOG = os.path.join(C.AGENT_OS_DIR, "learning_log.json")


def plan_learning(owner_goals=None, max_items=5):
    """يبني خطة تعلّم مرتّبة بالقيمة."""
    topics = []

    # 1) فجوات قدرات
    try:
        from agent_os.cognition import capability_gap
        for g in capability_gap.open_gaps()[:3]:
            topics.append({"topic": f"تعلّم {g['capability']}",
                           "source": "capability_gap", "value": 0.9,
                           "cost": 0.3})
    except Exception:
        pass

    # 2) معرفة متقادمة تحتاج تحديث
    try:
        from agent_os.memory import provenance
        for k in provenance.stale_keys()[:3]:
            topics.append({"topic": f"تحديث معرفة: {k}",
                           "source": "stale_knowledge", "value": 0.6,
                           "cost": 0.2})
    except Exception:
        pass

    # 3) من أهداف المالك
    if owner_goals:
        for goal in owner_goals[:3]:
            topics.append({"topic": f"تعلّم لتحقيق: {goal}",
                           "source": "owner_goal", "value": 0.85,
                           "cost": 0.4})

    # 4) تحسين عام
    if not topics:
        topics.append({"topic": "استكشاف أدوات/APIs جديدة",
                       "source": "general", "value": 0.5, "cost": 0.2})

    # ترتيب بـ Learning ROI
    for t in topics:
        t["roi"] = round(t["value"] - t["cost"], 3)
    topics.sort(key=lambda t: t["roi"], reverse=True)
    return topics[:max_items]


def learn(topic, knowledge, source="", confidence=0.7):
    """يخزن معرفة مكتسبة مع مصدرها."""
    try:
        from agent_os.memory import provenance
        provenance.record(
            key=f"learned:{topic[:60]}",
            value=str(knowledge)[:500],
            source=source or "self_learning",
            confidence=confidence,
            kind="fact",
        )
    except Exception:
        pass

    log = C.load_json(LEARN_LOG, {"entries": []})
    log["entries"].append({
        "topic": topic[:100],
        "knowledge": str(knowledge)[:300],
        "source": source,
        "confidence": confidence,
        "at": C.now_iso(),
    })
    log["entries"] = log["entries"][-500:]
    C.atomic_write(LEARN_LOG, log)
    C.log(f"📚 تعلّم: {topic[:50]}")
    return True


def daily_learning_cycle(owner_goals=None):
    """دورة تعلّم يومية كاملة: خطة → استشارة العقل → تخزين."""
    plan = plan_learning(owner_goals)
    results = []
    for item in plan[:3]:   # أعلى 3 قيمة
        # نسأل العقل عن الموضوع
        try:
            text, engine = C.call_brain(
                "أنت معلّم خبير. علّمني هذا الموضوع بإيجاز وعملية.",
                f"علّمني: {item['topic']}", mode="smart",
            )
            if text and not text.startswith("("):
                learn(item["topic"], text, source=engine or "brain",
                      confidence=0.7)
                results.append({"topic": item["topic"], "learned": True})
            else:
                results.append({"topic": item["topic"], "learned": False,
                                "note": "لا مزوّد"})
        except Exception:
            results.append({"topic": item["topic"], "learned": False})
    return {"plan": plan, "completed": results,
            "learned_count": sum(1 for r in results if r.get("learned"))}


def stats():
    log = C.load_json(LEARN_LOG, {"entries": []})
    return {"total_learned": len(log["entries"])}


if __name__ == "__main__":
    plan = plan_learning(["بناء متجر إلكتروني", "تعلّم الأمن"])
    print("خطة التعلّم:")
    for p in plan:
        print(f"  [{p['roi']}] {p['topic']}")
