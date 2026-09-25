"""
اختبار الفحص الذاتي الشامل — يجب أن تعمل كل الأنظمة الأساسية معاً.
"""
import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "sc_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import selfcheck


def test_all_core_subsystems_pass():
    r = selfcheck.run()
    # الأنظمة التي لا تحتاج شبكة/أدوات خارجية يجب أن تعمل كلها.
    core = {"memory", "learn", "kernel", "honesty", "finance", "bounty_scope", "priorities", "voice", "brain"}
    by = {c["name"]: c for c in r["checks"]}
    for name in core:
        assert by[name]["ok"] is True, f"{name}: {by[name]['note']}"
    assert r["ok"] is True
