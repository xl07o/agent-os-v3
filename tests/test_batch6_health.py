"""اختبارات الدفعة 6: الصحة والتوأم (health_graph, digital_twin)."""

import os
import sys
import tempfile

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "batch6_data"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os.verification import health_graph as hg
from agent_os.verification import digital_twin as dt


# ===== Health Graph =====

def test_health_snapshot_structure():
    s = hg.snapshot()
    assert s["overall"] in (hg.GREEN, hg.YELLOW, hg.RED)
    assert 0 <= s["health_pct"] <= 100
    assert "components" in s and len(s["components"]) >= 8


def test_health_core_modules_green():
    """الوحدات الأساسية (الأحداث، الأمان، الحلقة الذهبية) يجب أن تُحمّل."""
    s = hg.snapshot()
    assert s["components"]["الأحداث"]["status"] == hg.GREEN
    assert s["components"]["الحلقة_الذهبية"]["status"] == hg.GREEN
    assert s["components"]["الإجماع"]["status"] == hg.GREEN


def test_health_summary_line():
    line = hg.summary_line()
    assert "صحة النظام" in line
    assert "%" in line


# ===== Digital Twin =====

def test_twin_build_totals():
    t = dt.stats()
    assert t["files"] > 50        # المشروع كبير
    assert t["functions"] > 100
    assert t["tests"] >= 10


def test_twin_impact_uses_blast_radius():
    imp = dt.impact_of("_common")
    assert imp.get("found") is True
    assert imp.get("blast_size", 0) >= 1


def test_twin_analyzes_module_content():
    t = dt.build()
    # نتأكد أن ملفاً معروفاً يحوي دواله
    gl = next((v for k, v in t["modules"].items()
               if k.endswith("agent_os/golden_loop.py") or k.endswith("agent_os\\golden_loop.py")), None)
    assert gl is not None
    assert "run" in gl["functions"]
