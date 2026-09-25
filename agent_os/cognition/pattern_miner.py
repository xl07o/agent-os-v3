"""
pattern_miner.py - تقليد الخبراء (Expert Pattern Miner)
========================================================
يحلل مشاريع ناجحة (هيكلها، أدواتها، أنماطها) ويستخلص **وصفات**
قابلة لإعادة الاستخدام. مو نسخ — فهم الأنماط وتطبيقها.
"""
import os, sys, ast
def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

PATTERNS_FILE = os.path.join(C.AGENT_OS_DIR, "expert_patterns.json")

def analyze_project(project_dir):
    """يحلل مشروع بايثون ويستخلص أنماطه."""
    if not os.path.isdir(project_dir):
        return {"error": "مجلد غير موجود"}
    patterns = {"frameworks": set(), "patterns": [], "structure": {},
                "test_style": None, "entry_points": []}

    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules")]
        for f in files:
            if not f.endswith(".py"): continue
            path = os.path.join(root, f)
            try:
                code = open(path, encoding="utf-8", errors="replace").read()
                tree = ast.parse(code)
            except Exception:
                continue
            # اكتشاف الأنماط
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        patterns["frameworks"].add(n.name.split(".")[0])
                if isinstance(node, ast.ImportFrom) and node.module:
                    patterns["frameworks"].add(node.module.split(".")[0])
            if f == "main.py" or f == "app.py" or f == "__main__.py":
                patterns["entry_points"].append(os.path.relpath(path, project_dir))
            if f.startswith("test_"):
                patterns["test_style"] = "pytest"

    patterns["frameworks"] = sorted(patterns["frameworks"])[:20]
    return patterns

def extract_recipe(project_dir, project_name=""):
    """يستخلص وصفة قابلة للتكرار من مشروع ناجح."""
    analysis = analyze_project(project_dir)
    if "error" in analysis:
        return analysis
    recipe = {
        "name": project_name or os.path.basename(project_dir),
        "frameworks": analysis["frameworks"],
        "has_tests": analysis["test_style"] is not None,
        "entry_points": analysis["entry_points"],
        "extracted_at": C.now_iso(),
    }
    # حفظ الوصفة
    pats = C.load_json(PATTERNS_FILE, {"recipes": []})
    pats["recipes"].append(recipe)
    pats["recipes"] = pats["recipes"][-100:]
    C.atomic_write(PATTERNS_FILE, pats)
    return recipe

def best_recipe_for(task_type):
    """يعيد أنسب وصفة محفوظة لنوع مهمة."""
    pats = C.load_json(PATTERNS_FILE, {"recipes": []})
    # بحث بسيط بالكلمات المشتركة
    for r in reversed(pats["recipes"]):
        if task_type.lower() in r.get("name", "").lower():
            return r
    return pats["recipes"][-1] if pats["recipes"] else None

def analyze_self():
    """يحلل المشروع نفسه — ماذا يستخدم؟"""
    return analyze_project(C.BASE_DIR)
