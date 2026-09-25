"""
contextual_memory.py - ذاكرة التجارب (استدعاء بالتشابه)
=======================================================
يخزّن الوكيل كل تجربة (مهمة، نهج، أدوات، مشكلة، حل، نتيجة) ويستدعي
الأقرب منها حين تشبه مهمة جديدة تجربةً سابقة — فيبني على خبرته بدل
البدء من الصفر. التشابه = تقاطع الكلمات (Jaccard) بلا شبكة ولا نموذج.

  save_experience(task, approach, tools, problem, solution, outcome)
  recall(query, limit=5) -> التجارب الأقرب، الأعلى تشابهاً أولاً
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import _common as C


def _file():
    return os.path.join(C.AGENT_OS_DIR, "contextual_memory.json")


def _load():
    return C.load_json(_file(), {"experiences": []})


def _save(st):
    C.atomic_write(_file(), st)


def _tokens(text):
    """كلمات مطبّعة (يدعم العربية والإنجليزية عبر \\w في يونيكود)."""
    return set(re.findall(r"\w+", str(text).lower()))


def save_experience(task, approach, tools, problem, solution, outcome):
    """يحفظ تجربة كاملة قابلة للاستدعاء لاحقاً."""
    st = _load()
    exp = {
        "task": task,
        "approach": approach,
        "tools": tools if isinstance(tools, list) else [tools],
        "problem": problem,
        "solution": solution,
        "outcome": outcome,
        "time": C.now_iso(),
    }
    st.setdefault("experiences", []).append(exp)
    st["experiences"] = st["experiences"][-1000:]
    _save(st)
    return exp


def recall(query, limit=5):
    """يرجع التجارب الأشبه بالاستعلام (تقاطع كلمات > 0)، الأعلى أولاً."""
    q = _tokens(query)
    if not q:
        return []
    scored = []
    for e in _load().get("experiences", []):
        base = _tokens(e.get("task", "")) | _tokens(e.get("approach", "")) | _tokens(e.get("problem", ""))
        overlap = len(q & base)
        if overlap > 0:
            jaccard = overlap / (len(q | base) or 1)
            scored.append((jaccard, overlap, e))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [e for _, _, e in scored[:limit]]


if __name__ == "__main__":
    import json
    print(json.dumps({"experiences": len(_load().get("experiences", []))},
                     ensure_ascii=False, indent=2))
