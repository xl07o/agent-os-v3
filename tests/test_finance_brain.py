"""
اختبار الفكر المالي (البند 7) — حتمي بلا شبكة.
"""
import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "fin_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import finance_brain as fb


def test_good_opportunity_is_go():
    r = fb.evaluate("أداة مربحة", cost_usd=0, monthly_revenue_usd=300, effort_days=2, confidence=0.8)
    assert r["verdict"] == "go"
    assert r["payback_days"] is not None


def test_no_revenue_is_no_go():
    r = fb.evaluate("فكرة بلا دخل", cost_usd=100, monthly_revenue_usd=0, effort_days=5)
    assert r["verdict"] == "no-go"
    assert any("لا إيراد" in x for x in r["reasons"])


def test_slow_payback_is_no_go():
    # تكلفة عالية وإيراد ضئيل → استرداد بطيء
    r = fb.evaluate("مشروع بطيء", cost_usd=5000, monthly_revenue_usd=50, effort_days=1, confidence=0.9)
    assert r["verdict"] == "no-go"


def test_rank_orders_by_score():
    opps = [
        {"idea": "ضعيف", "cost_usd": 1000, "monthly_revenue_usd": 40, "effort_days": 5},
        {"idea": "قوي", "cost_usd": 0, "monthly_revenue_usd": 400, "effort_days": 1, "confidence": 0.9},
    ]
    ranked = fb.rank(opps)
    assert ranked[0]["idea"] == "قوي"


def test_fund_plan_respects_budget():
    opps = [
        {"idea": "أ", "cost_usd": 100, "monthly_revenue_usd": 300, "effort_days": 0, "confidence": 0.9},
        {"idea": "ب", "cost_usd": 100000, "monthly_revenue_usd": 300, "effort_days": 0, "confidence": 0.9},
    ]
    plan = fb.fund_plan(500, opps)
    assert plan["spent_usd"] <= 500
