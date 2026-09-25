"""اختبارات الدفعة 8: ملحق التقرير الصباحي (brief_extension)."""

import os
import sys
import tempfile

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "batch8_data"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import brief_extension as bx


def test_collect_returns_all_sections():
    d = bx.collect()
    for key in ("health", "capability_gaps", "disputed_memory",
                "project", "regression_lessons", "stale_knowledge"):
        assert key in d, f"قسم ناقص: {key}"


def test_health_section_populated():
    d = bx.collect()
    assert d["health"].get("pct") is not None


def test_project_stats_present():
    d = bx.collect()
    assert d["project"].get("files", 0) > 0


def test_render_produces_text():
    text = bx.render()
    assert "حالة النظام الموسّعة" in text
    assert "الصحة الكلية" in text
    assert "المشروع" in text


def test_render_resilient_to_missing():
    """render يجب ألا يرمي استثناءً حتى لو غاب نظام."""
    text = bx.render()
    assert isinstance(text, str) and len(text) > 20
