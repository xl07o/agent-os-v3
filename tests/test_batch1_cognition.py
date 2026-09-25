"""اختبارات الدفعة 1: محرّكات الإدراك (counterfactual, confidence, capability_gap)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os.cognition import counterfactual as cf
from agent_os.cognition import confidence as conf
from agent_os.cognition import capability_gap as cg


# ===== Counterfactual =====

def test_counterfactual_prefers_high_ev_low_risk():
    opts = [
        {"name": "آمن", "value": 0.5, "probability": 0.9, "risk": 0.1, "cost": 0.1},
        {"name": "متهور", "value": 0.9, "probability": 0.3, "risk": 0.9, "cost": 0.5, "reversible": False},
    ]
    r = cf.compare(opts, include_noop=False)
    assert r["recommended"] == "آمن"


def test_counterfactual_adds_noop_baseline():
    r = cf.compare([{"name": "خيار سيئ", "value": 0.1, "probability": 0.2, "risk": 0.9}])
    names = [x["name"] for x in r["ranking"]]
    assert "noop" in names
    # خيار سيئ جداً يجب ألا يتفوق على عدم الفعل
    assert r["recommended"] == "noop"


def test_counterfactual_detects_close_call():
    opts = [
        {"name": "A", "value": 0.5, "probability": 0.8, "risk": 0.2},
        {"name": "B", "value": 0.5, "probability": 0.79, "risk": 0.2},
    ]
    r = cf.compare(opts, include_noop=False)
    assert r["confident"] is False   # فارق ضيق = غير حاسم


def test_what_if_expected_value():
    r = cf.what_if("أطلق", value=0.8, probability=0.5)
    assert r["expected_value"] == 0.4


# ===== Confidence =====

def test_confidence_high_with_agreement_and_verification():
    r = conf.assess({"sources_total": 4, "sources_agree": 4,
                     "has_verification": True, "past_success_rate": 0.9})
    assert r["confidence"] >= 0.85
    assert r["actionable"] is True


def test_confidence_low_with_contradictions():
    r = conf.assess({"sources_total": 3, "sources_agree": 1,
                     "contradictions": 2, "is_novel": True})
    assert r["confidence"] < 0.5
    assert r["actionable"] is False


def test_confidence_escalation():
    assert conf.should_escalate(0.4) is True
    assert conf.should_escalate(0.7, risk=0.8) is True
    assert conf.should_escalate(0.9, risk=0.1) is False


# ===== Capability Gap =====

def test_capability_detects_available():
    # requests مثبّت في بيئة المشروع
    ok, via = cg.check_capability("http_requests")
    assert ok is True


def test_capability_detects_missing():
    r = cg.analyze(["quantum_teleport"])
    assert r["ready"] is False
    assert len(r["missing"]) == 1
    assert r["missing"][0]["acquisition_path"]   # يوجد مسار سدّ


def test_capability_coverage_mixed():
    r = cg.analyze(["http_requests", "quantum_teleport"])
    assert 0 < r["coverage"] < 1
