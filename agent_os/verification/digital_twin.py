"""
digital_twin.py - التوأم الرقمي للمشروع (Project Digital Twin) — §46
====================================================================
خريطة حية لبنية المشروع: ملفات، وحدات، دوال، أصناف، تبعيات، اختبارات.
يعرف impact التعديل قبل تنفيذه (يبني على blast_radius).
"""

import os
import sys
import ast

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

try:
    from agent_os.evolution import blast_radius
except Exception:
    blast_radius = None


def _analyze_file(path):
    """يستخرج دوال/أصناف/سطور من ملف بايثون."""
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except Exception:
        return {"functions": [], "classes": [], "lines": 0, "parse_error": True}
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    lines = len(open(path, encoding="utf-8", errors="replace").read().splitlines())
    return {"functions": funcs, "classes": classes, "lines": lines}


def build(root=None):
    """يبني التوأم الرقمي: جرد كامل للبنية."""
    root = root or C.BASE_DIR
    twin = {"modules": {}, "totals": {"files": 0, "functions": 0,
                                      "classes": 0, "lines": 0, "tests": 0}}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(dirpath, f)
            rel = os.path.relpath(path, root)
            info = _analyze_file(path)
            twin["modules"][rel] = info
            twin["totals"]["files"] += 1
            twin["totals"]["functions"] += len(info.get("functions", []))
            twin["totals"]["classes"] += len(info.get("classes", []))
            twin["totals"]["lines"] += info.get("lines", 0)
            if f.startswith("test_"):
                twin["totals"]["tests"] += 1
    return twin


def impact_of(module_name, root=None):
    """ماذا يتأثر لو عدّلنا هذه الوحدة؟ (يستدعي blast_radius) — §81."""
    if blast_radius is None:
        return {"error": "blast_radius غير متاح"}
    return blast_radius.dependents_of(module_name, root)


def stats(root=None):
    """إحصائيات موجزة للتقرير/اللوحة."""
    t = build(root)["totals"]
    return t


if __name__ == "__main__":
    t = stats()
    print(f"ملفات:{t['files']} دوال:{t['functions']} أصناف:{t['classes']} "
          f"أسطر:{t['lines']} اختبارات:{t['tests']}")
    imp = impact_of("_common")
    print(f"تأثير تعديل _common: {imp.get('blast_size')} وحدة ({imp.get('risk')})")
