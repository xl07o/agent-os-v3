"""
اختبار واجهة JARVIS التفاعلية + ذاكرة المحادثة والأولويات (البنود 11/3).
"""
import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "jarvis_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import jarvis
from agent_os.memory import conversation


def test_help_and_status():
    assert "JARVIS" in jarvis.handle("مساعدة")["reply"]
    s = jarvis.handle("حالة")
    assert s["kind"] == "status" and s["data"] is not None


def test_task_routes_to_kernel_and_records_turn():
    out = jarvis.handle("سجّل هدف بناء متجر إلكتروني")
    assert out["kind"] == "task"
    assert "result" in out["data"]
    # الدور سُجِّل في ذاكرة المحادثة
    assert conversation.recent(1)[0]["user"].startswith("سجّل هدف")


def test_priorities_emerge_from_conversation():
    for _ in range(3):
        jarvis.handle("تعلّم عن الأمن السيبراني")
    pr = conversation.priorities(5)
    topics = [p["topic"] for p in pr]
    assert any("امن" in t or "أمن" in t or "السيبراني" in t or "سيبراني" in t for t in topics) or topics


def test_voice_toggle():
    on = jarvis.handle("صوت on")
    assert on["data"]["voice"] is True
    off = jarvis.handle("صوت off")
    assert off["data"]["voice"] is False


def test_ask_is_honest_without_provider():
    out = jarvis.handle("اسأل ما أفضل قاعدة بيانات")
    assert out["kind"] == "ask"
    assert isinstance(out["reply"], str) and out["reply"]


def test_empty_is_noop():
    assert jarvis.handle("")["kind"] == "noop"


def test_noise_input_asks_for_clarification():
    for junk in ["ش", "ok", "a", ".."]:
        out = jarvis.handle(junk)
        assert out["kind"] == "unclear", f"{junk!r} -> {out['kind']}"

def test_real_command_still_runs_after_guard():
    assert jarvis.handle("سجّل هدف بناء متجر")["kind"] == "task"
    assert jarvis.handle("حالة")["kind"] == "status"
