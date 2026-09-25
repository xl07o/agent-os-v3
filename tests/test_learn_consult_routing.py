"""
اختبار ربط التعلّم والاستشارة بالنواة (البندان 1 و 17).
"""
import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "lcr_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import agent_os as A


def test_learn_intent_routes_to_learn_topic():
    r = A.router("تعلّم عن لغة rust")
    assert r["intent"] == "learn"
    assert r["subsystems"] == ["learn_topic"]
    steps = A.plan("تعلّم عن لغة rust", r["intent"], r["subsystems"])
    assert any(s["action"] == "learn_topic" for s in steps)


def test_consult_without_provider_is_honest():
    """بلا مزوّد عقل: استشارة تُرجع ok=False وسبباً — لا تلفيق (البند 5)."""
    c = A._consult_brain("مهمة يعجز عنها الوكيل")
    # قد يوجد مزوّد فعلي في بعض البيئات؛ إن لم يوجد يجب أن يكون صادقاً.
    assert "ok" in c
    if not c["ok"]:
        assert c.get("reason")
    else:
        assert c.get("suggestion") and not c["suggestion"].startswith("(")


def test_unknown_action_holds_not_fake_success():
    step = A.execute_step({"action": "totally_unknown_action", "target": "t",
                           "done": False, "output": None}, "افعل شيئاً غريباً جداً", {})
    assert step["done"] is False
    assert step["output"].get("held") is True
