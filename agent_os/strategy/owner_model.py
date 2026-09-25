"""
owner_model.py - نموذج المالك طويل الأمد (Long-Term Owner Model) — §65
=======================================================================
يبني صورة عن أهداف المالك وأولوياته وما يفضّله/يتجنّبه، ويستخدمها لترتيب
المهام (§89) بدل FIFO. يتعلّم من قرارات المالك (موافقة/رفض) عبر الوقت.
"""

import os
import sys

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

OWNER_FILE = os.path.join(C.AGENT_OS_DIR, "owner_model.json")

DEFAULT = {
    "current_goals": [],
    "long_term_goals": [],
    "preferred_work": [],      # أنواع عمل يحبها المالك (وزن أعلى)
    "avoided_work": [],        # أنواع عمل يتجنّبها (وزن أدنى/رفض)
    "business_priorities": [],
    "learning_priorities": [],
    "approval_history": {"approved": 0, "rejected": 0},
}


def _load():
    return C.load_json(OWNER_FILE, dict(DEFAULT))


def _save(m):
    C.atomic_write(OWNER_FILE, m)


def set_goals(current=None, long_term=None):
    m = _load()
    if current is not None:
        m["current_goals"] = list(current)
    if long_term is not None:
        m["long_term_goals"] = list(long_term)
    _save(m)
    return m


def add_preference(work_type, preferred=True):
    """يسجّل تفضيل/تجنّب لنوع عمل."""
    m = _load()
    target = "preferred_work" if preferred else "avoided_work"
    other = "avoided_work" if preferred else "preferred_work"
    if work_type not in m[target]:
        m[target].append(work_type)
    if work_type in m[other]:
        m[other].remove(work_type)
    _save(m)
    return m


def learn_from_decision(work_type, approved):
    """يتعلّم من قرار المالك: الموافقة ترفع تفضيل النوع، الرفض يخفضه."""
    m = _load()
    if approved:
        m["approval_history"]["approved"] += 1
        if work_type and work_type not in m["preferred_work"]:
            m["preferred_work"].append(work_type)
    else:
        m["approval_history"]["rejected"] += 1
        if work_type and work_type not in m["avoided_work"]:
            m["avoided_work"].append(work_type)
    _save(m)
    return m


def score_task(task_type, base_value=0.5):
    """يعطي وزن أولوية لمهمة حسب توافقها مع نموذج المالك (§89).

    يعيد درجة 0..~1.3: ترتفع لو النوع مفضّل أو ضمن أهداف حالية،
    وتنخفض لو ضمن المتجنّب.
    """
    m = _load()
    score = float(base_value)
    if task_type in m["preferred_work"]:
        score += 0.3
    if task_type in m["avoided_work"]:
        score -= 0.4
    if any(task_type in g for g in m["current_goals"]):
        score += 0.25
    if any(task_type in g for g in m["business_priorities"]):
        score += 0.2
    return round(max(0.0, score), 3)


def rank_tasks(tasks):
    """يرتّب قائمة مهام [{"type","value"}] حسب نموذج المالك."""
    scored = [{**t, "priority": score_task(t.get("type", ""), t.get("value", 0.5))}
              for t in tasks]
    scored.sort(key=lambda x: x["priority"], reverse=True)
    return scored


def profile():
    """ملخّص نموذج المالك للتقرير/اللوحة."""
    m = _load()
    h = m["approval_history"]
    total = h["approved"] + h["rejected"]
    return {
        "current_goals": m["current_goals"],
        "preferred": m["preferred_work"],
        "avoided": m["avoided_work"],
        "approval_rate": round(h["approved"] / total, 3) if total else None,
    }


if __name__ == "__main__":
    set_goals(current=["بناء منتج SaaS", "تعلّم الأمن"])
    add_preference("coding", preferred=True)
    add_preference("manual_data_entry", preferred=False)
    ranked = rank_tasks([
        {"type": "coding", "value": 0.5},
        {"type": "manual_data_entry", "value": 0.5},
        {"type": "research", "value": 0.5},
    ])
    for t in ranked:
        print(f"{t['type']}: {t['priority']}")
