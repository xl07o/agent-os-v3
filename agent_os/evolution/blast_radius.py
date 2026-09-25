"""
blast_radius.py - محلل نصف قطر التأثير (Blast Radius) — §81-82
==============================================================
قبل أي تعديل ذاتي: "ماذا يمكن أن يكسر هذا التغيير؟"
يبني خريطة استيراد فعلية للمشروع (من AST) ويحسب أي الوحدات تعتمد
على الملف المُراد تعديله — مباشرةً وعبر السلسلة (transitive).
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


def _module_name(path, root):
    """يحوّل مسار ملف إلى اسم موديول نقطي نسبةً للجذر."""
    rel = os.path.relpath(path, root)
    rel = rel[:-3] if rel.endswith(".py") else rel
    return rel.replace(os.sep, ".")


def build_import_graph(root=None):
    """يبني خريطة: موديول → مجموعة الموديولات التي يستوردها (داخل المشروع فقط)."""
    root = root or C.BASE_DIR
    graph = {}
    local_mods = set()

    py_files = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "tests")]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(dirpath, f))

    for path in py_files:
        local_mods.add(_module_name(path, root))

    for path in py_files:
        mod = _module_name(path, root)
        imports = set()
        try:
            tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
        except Exception:
            graph[mod] = imports
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.add(n.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # from agent_os.x import y  →  agent_os.x  و  agent_os.x.y
                    imports.add(node.module)
                    for n in node.names:
                        imports.add(f"{node.module}.{n.name}")
        # نُبقي فقط ما يشير لموديولات المشروع
        graph[mod] = {i for i in imports if any(i == m or i.startswith(m + ".") or m.startswith(i + ".") or m.endswith("." + i.split(".")[-1]) for m in local_mods)}
    return graph, local_mods


def dependents_of(target_module, root=None):
    """يعيد كل الموديولات التي تعتمد على الهدف (مباشرة + عبر السلسلة)."""
    graph, local = build_import_graph(root)

    # اعكس الخريطة: هدف → من يستورده
    reverse = {m: set() for m in graph}
    for mod, imports in graph.items():
        for imp in imports:
            for m in graph:
                if imp == m or imp.endswith("." + m.split(".")[-1]):
                    reverse.setdefault(m, set()).add(mod)

    # ابحث عن الهدف بمرونة (اسم قصير أو كامل)
    matches = [m for m in graph if m == target_module or m.endswith("." + target_module)
               or m.split(".")[-1] == target_module.replace(".py", "")]
    if not matches:
        return {"target": target_module, "found": False, "direct": [], "transitive": []}

    direct = set()
    for m in matches:
        direct |= reverse.get(m, set())

    # الانتشار عبر السلسلة (BFS)
    transitive = set(direct)
    frontier = list(direct)
    while frontier:
        cur = frontier.pop()
        for dep in reverse.get(cur, set()):
            if dep not in transitive:
                transitive.add(dep)
                frontier.append(dep)

    return {
        "target": target_module,
        "found": True,
        "direct": sorted(direct),
        "transitive": sorted(transitive),
        "blast_size": len(transitive),
        "risk": "high" if len(transitive) >= 5 else "medium" if transitive else "low",
    }


if __name__ == "__main__":
    r = dependents_of("_common")
    print(f"الهدف: {r['target']} | حجم التأثير: {r.get('blast_size')} | مخاطرة: {r.get('risk')}")
    print(f"يعتمد عليه مباشرة: {r['direct'][:8]}")
