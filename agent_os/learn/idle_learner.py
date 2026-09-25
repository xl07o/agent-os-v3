"""
idle_learner.py - التعلّم الذاتي وقت السكون (البند 2)
=====================================================
«يوم أكون ساكت، يتعلم بنفسه». يختار مواضيع ذات قيمة (فجوات قدرات، معرفة
متقادمة، أهداف المالك) ثم يتعلّمها ويخزّنها بالذاكرة.

مسارا التعلّم — والأهم أنه يعمل مجاناً:
  1) العقل (Claude/DeepSeek/Gemini) إن توفّر مزوّد.
  2) وإلا: بحث الويب + استيعاب أعلى النتائج (agent_os.learn.ingest) — مجاناً.

لا تلفيق (البند 5): موضوع «تُعُلِّم» فقط إن خُزِّن شيء فعلاً؛ وإلا يُسجَّل
سبب صريح ودرس في الذاكرة يمنع تكرار المحاولة العقيمة نفسها.

  idle_learn_cycle(owner_goals, max_topics, topics=None) -> ملخّص ما تعلّمه
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import _common as C


def _pick_topics(owner_goals, max_topics):
    try:
        from agent_os.cognition import learning_engine
        plan = learning_engine.plan_learning(owner_goals, max_items=max_topics)
        return [p["topic"] for p in plan[:max_topics]]
    except Exception:
        return (owner_goals or [])[:max_topics] or ["استكشاف أدوات/APIs مفتوحة جديدة"]


def _learn_via_brain(topic):
    text, engine = C.call_brain(
        "أنت معلّم خبير. علّمني هذا الموضوع بإيجاز وعملية.",
        f"علّمني: {topic}", mode="smart",
    )
    if not text or engine in (None, "", "none") or text.strip().startswith("("):
        return None
    try:
        from agent_os.cognition import learning_engine
        learning_engine.learn(topic, text, source=engine or "brain", confidence=0.7)
    except Exception:
        pass
    return {"path": "brain", "engine": engine, "chars": len(text)}


def _learn_via_web(topic):
    try:
        from agent_os.learn import ingest
        res = ingest.learn_query(topic, max_sources=2)
        if res.get("ok"):
            return {"path": "web", "sources": res.get("ingested", [])}
    except Exception:
        pass
    return None


def idle_learn_cycle(owner_goals=None, max_topics=3, topics=None):
    """دورة تعلّم ذاتي واحدة وقت السكون. تعمل مجاناً عبر الويب إن غاب العقل."""
    topics = topics or _pick_topics(owner_goals, max_topics)
    results = []
    for topic in topics[:max_topics]:
        got = _learn_via_brain(topic) or _learn_via_web(topic)
        if got:
            results.append({"topic": topic, "learned": True, **got})
            C.log(f"🎓 تعلّم وقت السكون: {topic} عبر {got['path']}")
        else:
            reason = "لا مزوّد عقل ولا نتائج ويب (غالباً لا شبكة)"
            results.append({"topic": topic, "learned": False, "reason": reason})
            # درس دائم: لا تُعِد المحاولة العقيمة نفسها دون تغيّر الظرف.
            try:
                from agent_os.memory import provenance
                prov_key = f"idle_fail:{topic[:50]}"
                provenance.record(prov_key, reason, source="idle_learner",
                                  confidence=0.5, kind="fact")
            except Exception:
                pass
    return {"topics": topics, "results": results,
            "learned_count": sum(1 for r in results if r.get("learned"))}


if __name__ == "__main__":
    import json
    goals = sys.argv[1:] or None
    print(json.dumps(idle_learn_cycle(goals), ensure_ascii=False, indent=2))
