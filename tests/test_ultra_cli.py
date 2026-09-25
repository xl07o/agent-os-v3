"""
اختبار نقطة الدخول الموحّدة ultra (الواجهة القابلة للاستخدام).
"""
import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "ultra_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import ultra


def test_status_reports_all_sections():
    st = ultra.cmd_status(None)
    assert "brain_providers_available" in st
    assert "voice" in st and "ready" in st["voice"]
    assert "memory" in st


def test_memory_snapshot_shape():
    m = ultra.cmd_memory(None)
    assert "knowledge_items" in m and "experiences" in m


def test_run_command_executes_kernel():
    res = ultra.cmd_run(["سجّل هدف اختبار"])
    assert "result" in res and "intent" in res


def test_ask_is_honest_without_provider():
    r = ultra.cmd_ask(["سؤال"])
    assert "ok" in r
    if not r["ok"]:
        assert r.get("reason")


def test_main_unknown_prints_help():
    assert ultra.main(["nope"]) == 0
    assert ultra.main([]) == 0
