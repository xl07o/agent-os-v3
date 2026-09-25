"""اختبارات الدفعة 7: الاسترداد (loop_guard, attention_budget)."""

import os
import sys
import tempfile

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "batch7_data"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os.recovery import loop_guard as lg
from agent_os.recovery import attention_budget as ab


# ===== Loop Guard =====

def test_detects_same_action_repeat():
    g = lg.LoopGuard(repeat_limit=3)
    for _ in range(3):
        g.record("retry", outcome="fail")
    r = g.check()
    assert r["stuck"] is True
    assert "تكرار نفس الفعل" in r["problems"]


def test_detects_oscillation():
    g = lg.LoopGuard()
    for a in ["A", "B", "A", "B"]:
        g.record(a)
    r = g.check()
    assert "تذبذب" in r["problems"]


def test_detects_no_progress():
    g = lg.LoopGuard(window=8)
    for i in range(8):
        g.record(f"action_{i}", progressed=False)
    r = g.check()
    assert "لا تقدّم" in r["problems"]


def test_healthy_loop_not_stuck():
    g = lg.LoopGuard()
    g.record("a", progressed=True)
    g.record("b", progressed=True)
    r = g.check()
    assert r["stuck"] is False


def test_reset_clears():
    g = lg.LoopGuard()
    g.record("x")
    g.reset()
    assert g.check()["actions_seen"] == 0


# ===== Attention Budget =====

def test_valuable_task_gets_more():
    b = ab.AttentionBudget(total_steps=100)
    big = b.allocate("مهم", 0.9)
    small = b.allocate("تافه", 0.1)
    assert big > small


def test_budget_exhaustion():
    b = ab.AttentionBudget(total_steps=100)
    b.allocate("t", 0.1)          # حصة صغيرة
    # استهلك حتى النفاد
    while b.can_spend("t"):
        b.spend("t")
    assert b.exhausted("t") is True
    assert b.can_spend("t") is False


def test_cannot_spend_unallocated():
    b = ab.AttentionBudget()
    assert b.spend("unknown") is False


def test_learning_roi():
    assert ab.worth_learning(0.9, 0.2)["worth_it"] is True
    assert ab.worth_learning(0.3, 0.3)["worth_it"] is False


def test_budget_report():
    b = ab.AttentionBudget(total_steps=50)
    b.allocate("a", 0.5)
    b.spend("a", 2)
    rep = b.report()
    assert rep["spent"] == 2
    assert rep["remaining"] == 48
