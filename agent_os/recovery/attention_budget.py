"""
attention_budget.py - ميزانية الانتباه (Attention Budget) — §90-91
===================================================================
لا يستهلك كل الموارد على مهمة تافهة. يوزّع "انتباهاً" محدوداً حسب قيمة
المهمة، ويقطع المهام التي تجاوزت حصّتها دون عائد (Learning ROI §91).
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


class AttentionBudget:
    """يدير حصص انتباه (خطوات/محاولات) لكل مهمة حسب قيمتها."""

    def __init__(self, total_steps=100):
        self.total = total_steps
        self.spent = 0
        self.allocations = {}   # task_id → {"budget", "spent", "value"}

    def allocate(self, task_id, value):
        """يخصّص حصّة متناسبة مع قيمة المهمة (0..1)."""
        value = max(0.0, min(1.0, float(value)))
        # مهمة قيمتها 1.0 تأخذ حتى 30% من الإجمالي، والتافهة حداً أدنى
        budget = max(2, int(self.total * (0.05 + value * 0.25)))
        self.allocations[task_id] = {"budget": budget, "spent": 0, "value": value}
        return budget

    def can_spend(self, task_id):
        """هل بقي للمهمة رصيد انتباه؟"""
        a = self.allocations.get(task_id)
        if a is None:
            return False
        return a["spent"] < a["budget"] and self.spent < self.total

    def spend(self, task_id, steps=1):
        """يستهلك خطوات من حصّة المهمة. يعيد True لو نجح، False لو نفدت."""
        a = self.allocations.get(task_id)
        if a is None or not self.can_spend(task_id):
            return False
        a["spent"] += steps
        self.spent += steps
        return True

    def exhausted(self, task_id):
        """هل تجاوزت المهمة حصّتها؟ (يجب إيقافها أو تصعيدها)."""
        a = self.allocations.get(task_id)
        return a is not None and a["spent"] >= a["budget"]

    def report(self):
        return {
            "total": self.total,
            "spent": self.spent,
            "remaining": self.total - self.spent,
            "tasks": len(self.allocations),
            "exhausted": [t for t in self.allocations if self.exhausted(t)],
        }


def worth_learning(value, cost, threshold=0.3):
    """Learning ROI (§91): هل قيمة المعرفة تستحق كلفتها؟"""
    value = max(0.0, min(1.0, float(value)))
    cost = max(0.0, min(1.0, float(cost)))
    roi = value - cost
    return {"worth_it": roi >= threshold, "roi": round(roi, 3)}


if __name__ == "__main__":
    b = AttentionBudget(total_steps=100)
    b.allocate("مهمة_مهمة", value=0.9)
    b.allocate("مهمة_تافهة", value=0.1)
    print("حصة المهمة المهمة:", b.allocations["مهمة_مهمة"]["budget"])
    print("حصة التافهة:", b.allocations["مهمة_تافهة"]["budget"])
    print("يستحق التعلّم (قيمة 0.8 كلفة 0.2):", worth_learning(0.8, 0.2))
