"""
strategy_memory.py - الذاكرة الاستراتيجية (تعلّم فوقي)
======================================================
يتعلّم الوكيل — عبر التكرار — أي استراتيجية تنجح لأي نوع مهمة، فيوصي
بها لاحقاً بدل التخمين. لا يوصي قبل تجميع عيّنات كافية (min_samples)
حتى لا يبني ثقة على حظّ عيّنة واحدة.

  record_outcome(task_type, strategy, success) -> يسجّل محاولة ونتيجتها
  best_strategy(task_type, min_samples=3)       -> أفضل استراتيجية أو None
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import _common as C


def _file():
    return os.path.join(C.AGENT_OS_DIR, "strategy_memory.json")


def _load():
    return C.load_json(_file(), {"records": {}})


def _save(st):
    C.atomic_write(_file(), st)


def record_outcome(task_type, strategy, success):
    """يسجّل نتيجة استخدام استراتيجية لنوع مهمة."""
    st = _load()
    rec = st.setdefault("records", {}).setdefault(str(task_type), {})
    s = rec.setdefault(str(strategy), {"attempts": 0, "successes": 0})
    s["attempts"] += 1
    if success:
        s["successes"] += 1
    _save(st)
    return dict(s)


def best_strategy(task_type, min_samples=3):
    """أفضل استراتيجية لنوع المهمة حسب معدّل النجاح؛ None قبل بلوغ العيّنات."""
    rec = _load().get("records", {}).get(str(task_type), {})
    total = sum(s.get("attempts", 0) for s in rec.values())
    if total < min_samples:
        return None
    best = None
    for strat, s in rec.items():
        att = s.get("attempts", 0)
        if att == 0:
            continue
        rate = s.get("successes", 0) / att
        cand = {"strategy": strat, "success_rate": round(rate, 3), "attempts": att}
        if best is None or cand["success_rate"] > best["success_rate"] or (
                cand["success_rate"] == best["success_rate"] and att > best["attempts"]):
            best = cand
    return best


def stats(task_type=None):
    """لمحة: عدد الأنواع/العيّنات المتراكمة (للتقارير)."""
    rec = _load().get("records", {})
    if task_type is not None:
        return rec.get(str(task_type), {})
    return {"task_types": len(rec),
            "total_samples": sum(s.get("attempts", 0)
                                 for t in rec.values() for s in t.values())}


if __name__ == "__main__":
    import json
    print(json.dumps(stats(), ensure_ascii=False, indent=2))
