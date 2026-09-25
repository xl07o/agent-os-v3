"""اختبارات الدفعة 3: التطور (blast_radius, regression_writer)."""

import os
import sys
import ast
import tempfile

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "batch3_data"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os.evolution import blast_radius as br
from agent_os.evolution import regression_writer as rw


# ===== Blast Radius =====

def test_blast_radius_finds_dependents_of_common():
    """_common يُستورد من كثير من الوحدات → تأثير غير صفري."""
    r = br.dependents_of("_common")
    assert r["found"] is True
    assert r["blast_size"] >= 1


def test_blast_radius_unknown_module():
    r = br.dependents_of("module_that_does_not_exist_zzz")
    assert r["found"] is False


def test_blast_radius_graph_builds():
    graph, local = br.build_import_graph()
    assert len(graph) > 10          # المشروع فيه وحدات كثيرة
    assert any("agent_os" in m for m in local)


# ===== Regression Writer =====

def test_regression_generate_valid_syntax():
    gen = rw.generate("BUG-X", "وصف", "agent_os._common", "now_iso",
                      [], None, comparison="truthy")
    # الكود المولّد يجب أن يكون بايثون صالحاً
    ast.parse(gen["code"])
    assert gen["function"].startswith("test_regression_")


def test_regression_write_creates_runnable_file():
    r = rw.write("BUG-TESTGEN", "now_iso غير فارغ",
                 "agent_os._common", "now_iso", [], None, comparison="truthy")
    assert r["ok"] is True
    assert os.path.exists(r["path"])
    # الملف المكتوب صالح صياغياً
    ast.parse(open(r["path"], encoding="utf-8").read())
    os.remove(r["path"])   # تنظيف


def test_regression_equals_comparison():
    gen = rw.generate("BUG-Y", "مساواة", "agent_os._common", "now_compact",
                      [], "x", comparison="==")
    assert "== 'x'" in gen["code"]
