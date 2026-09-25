"""
اختبارات صدق النواة (البند 5: ممنوع النجاح الوهمي).
كل اختبار هنا يثبّت إصلاحاً لعيب حقيقي كان يبلّغ نجاحاً كاذباً — حتى لا يعود.
"""
import os
import sys
import tempfile

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "honesty_test"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import agent_os as A


# ===== 1) قاعدة shell=True كانت ميتة (النص كان يُصغَّر فلا يطابق T الكبيرة) =====
def test_shell_true_rule_fires():
    v = A.critic("t", [{"action": "x", "done": True,
                        "output": {"cmd": "subprocess.run(x, shell=True)"}}], intent="code")
    assert any("shell=True" in i for i in v["issues"])


def test_security_rule_case_insensitive():
    v = A.critic("t", [{"action": "x", "done": True,
                        "output": {"code": "EVAL( danger )"}}], intent="code")
    assert any("eval" in i.lower() for i in v["issues"])


# ===== 2) سقالة فارغة لا تُمنح verified/A =====
def test_stub_python_not_verified():
    scaf = tempfile.mktemp(suffix=".py")
    with open(scaf, "w", encoding="utf-8") as f:
        f.write("def main():\n    print('تم تنفيذ المهمة')\n")
    assert A._is_scaffold_deliverable(scaf) is True
    v = A.critic("اكتب أداة", [{"action": "produce_artifact", "done": True,
                                "output": {"path": scaf, "kind": "artifact"}}], intent="code")
    assert A.verifier("t", v)["status"] != "verified"


def test_placeholder_markdown_not_verified():
    scaf = tempfile.mktemp(suffix=".md")
    with open(scaf, "w", encoding="utf-8") as f:
        f.write("# مهمة\n\nتم توليد هذا المخرَج تلقائياً بواسطة نواة Agent OS.\n"
                "\n## الخلاصة\n\n- عرض المخرجات هنا.\n")
    assert A._is_scaffold_deliverable(scaf) is True


# ===== 3) كود حقيقي بمحتوى فعلي = دليل مقبول =====
def test_real_code_is_evidence():
    real = tempfile.mktemp(suffix=".py")
    with open(real, "w", encoding="utf-8") as f:
        f.write("def add(a, b):\n    total = a + b\n    return total\n\n"
                "class Calc:\n    def run(self):\n        return add(1, 2)\n")
    assert A._is_scaffold_deliverable(real) is False
    v = A.critic("t", [{"action": "produce_artifact", "done": True,
                        "output": {"path": real, "kind": "artifact"}}], intent="code")
    assert A.verifier("t", v)["status"] == "verified"


# ===== 4) تحليل وسائط CLI: لا إسقاط لـ --why ولا تعليق على -- منفرد =====
def test_cli_kwargs_parsed():
    assert A._parse_cli_kwargs(["--why", "سبب", "--host", "example.com"]) == \
        {"why": "سبب", "host": "example.com"}


def test_cli_kwargs_bare_dash_no_hang():
    # كان "--" يسبب حلقة لا نهائية؛ الآن يُعالَج ويعود.
    assert A._parse_cli_kwargs(["--", "--flag"]) == {"flag": True}


def test_cli_kwargs_flag_without_value():
    assert A._parse_cli_kwargs(["--verbose"]) == {"verbose": True}


# ===== 5) tool_registry بلا رقم ملفّق «+1» =====
def test_tool_registry_count_not_inflated():
    from agent_os import tool_registry
    step = A.execute_step({"action": "tool_registry"}, "t", {})
    assert step["output"]["tools"] == len(tool_registry.list_tools())


# ===== 6) توليد المخرجات بالعقل مع احتياط صادق (البند 4) =====
def test_strip_fences():
    assert A._strip_fences("```python\nprint(1)\n```") == "print(1)"
    assert A._strip_fences("```\nx\n```") == "x"
    assert A._strip_fences("بلا سور") == "بلا سور"


def test_brain_deliverable_none_without_provider():
    # بلا مزوّد عقل: يرجع None ليُستعمل الاحتياط الصادق — لا تلفيق محتوى.
    import brain
    if not brain.available_engines():
        assert A._brain_deliverable("اكتب أداة CLI", "code", ".py") is None
        assert A._brain_deliverable("تقرير", "report", ".md") is None


def test_json_csv_stay_deterministic():
    # الأنواع المنظّمة لا تمرّ عبر العقل (تبقى حتمية).
    assert A._brain_deliverable("بيانات", "data", ".json") is None
    assert A._brain_deliverable("بيانات", "data", ".csv") is None
