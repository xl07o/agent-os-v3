"""
اختبار التعلّم الذاتي وقت السكون (البند 2).
"""
import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "idle_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os.learn import idle_learner as il


def test_cycle_returns_wellformed_and_honest():
    res = il.idle_learn_cycle(topics=["موضوع اختبار فريد لا نتائج له"], max_topics=1)
    assert res["learned_count"] in (0, 1)
    r = res["results"][0]
    # صدق: إن لم يتعلّم يجب أن يذكر سبباً، لا يدّعي التعلّم (البند 5)
    if not r["learned"]:
        assert r.get("reason")
    else:
        assert r.get("path") in ("brain", "web")


def test_picks_topics_from_goals_when_no_engine():
    res = il.idle_learn_cycle(owner_goals=["تعلّم أمن التطبيقات"], max_topics=2)
    assert isinstance(res["topics"], list) and res["topics"]


def test_failure_recorded_as_lesson():
    """فشل التعلّم يُسجَّل درساً في provenance لمنع تكراره العقيم."""
    from agent_os.memory import provenance as prov
    topic = f"موضوع بلا شبكة {uuid.uuid4().hex[:6]}"
    res = il.idle_learn_cycle(topics=[topic], max_topics=1)
    if not res["results"][0]["learned"]:
        assert prov.get(f"idle_fail:{topic[:50]}") is not None
