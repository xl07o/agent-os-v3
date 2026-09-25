"""
regression_writer.py - كاتب اختبارات الانحدار (Self-Generated Tests) — §21, §60
===============================================================================
عند اكتشاف bug: أصلحه ثم أنشئ اختبار انحدار دائم حتى لا يعود.
هذا الملف يولّد ملف pytest حقيقياً من وصف فشل، مع تحقق صياغي.
"""

import os
import sys
import ast
import re

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

GEN_DIR = os.path.join(C.BASE_DIR, "tests", "generated")


def _safe_name(text):
    """يحوّل وصفاً إلى اسم دالة اختبار صالح."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")[:40]
    return slug or "regression"


def generate(bug_id, description, module, callable_name, args, expected,
             comparison="=="):
    """يولّد كود اختبار انحدار (كنص) — لا يكتب ملفاً بعد.

    module/callable_name: الدالة موضع الاختبار (مثل 'agent_os._common', 'now_iso').
    args: قائمة وسائط تُمرَّر.
    expected: القيمة المتوقعة.
    comparison: '==' أو 'is' أو 'in' أو 'truthy'.
    """
    fn = f"test_regression_{_safe_name(bug_id + '_' + description)}"
    args_repr = ", ".join(repr(a) for a in (args or []))

    if comparison == "truthy":
        assertion = f"    assert result, {repr(description)}"
    elif comparison == "in":
        assertion = f"    assert {repr(expected)} in result"
    elif comparison == "is":
        assertion = f"    assert result is {repr(expected)}"
    else:
        assertion = f"    assert result == {repr(expected)}"

    code = f'''"""اختبار انحدار مولّد تلقائياً — bug: {bug_id}
{description}
لا تحذفه: يمنع عودة هذا الخطأ (المواصفة §60, §62).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from {module} import {callable_name}


def {fn}():
    result = {callable_name}({args_repr})
{assertion}
'''
    return {"function": fn, "code": code}


def write(bug_id, description, module, callable_name, args, expected,
          comparison="=="):
    """يولّد ويكتب ملف اختبار انحدار فعلياً (بعد تحقق صياغي)."""
    gen = generate(bug_id, description, module, callable_name, args, expected, comparison)
    # تحقق صياغي قبل الكتابة — لا نكتب اختباراً مكسوراً
    try:
        ast.parse(gen["code"])
    except SyntaxError as e:
        return {"ok": False, "reason": f"صياغة مولّدة خاطئة: {e}"}

    os.makedirs(GEN_DIR, exist_ok=True)
    fname = f"test_gen_{_safe_name(bug_id)}.py"
    path = os.path.join(GEN_DIR, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write(gen["code"])
    C.log(f"🧪 اختبار انحدار مولّد: {path} :: {gen['function']}")
    return {"ok": True, "path": path, "function": gen["function"]}


if __name__ == "__main__":
    r = write("BUG-001", "now_iso يجب أن يعيد نصاً غير فارغ",
              "agent_os._common", "now_iso", [], None, comparison="truthy")
    print(r)
