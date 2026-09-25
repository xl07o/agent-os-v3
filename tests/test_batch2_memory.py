"""اختبارات الدفعة 2: معمارية الذاكرة (conflict_resolver, provenance, strategy_memory)."""

import os
import sys
import datetime
import tempfile

# عزل ملفات البيانات في مجلد مؤقت قبل استيراد الوحدات
os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "batch2_data"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os.memory import conflict_resolver as cr
from agent_os.memory import provenance as prov
from agent_os.memory import strategy_memory as sm


# ===== Conflict Resolver =====

def test_conflict_higher_confidence_wins():
    r = cr.resolve(
        {"value": "A", "confidence": 0.5, "timestamp": "2026-01-01"},
        {"value": "B", "confidence": 0.9, "timestamp": "2026-01-01"},
    )
    assert r["resolved_value"] == "B"
    assert r["rule"] == "أعلى ثقة"


def test_conflict_newer_wins_when_close():
    r = cr.resolve(
        {"value": "قديم", "confidence": 0.7, "timestamp": "2026-01-01"},
        {"value": "جديد", "confidence": 0.72, "timestamp": "2026-09-01"},
    )
    assert r["resolved_value"] == "جديد"
    assert "الأحدث" in r["rule"]


def test_conflict_tie_flagged_for_human():
    r = cr.resolve(
        {"value": "A", "confidence": 0.7, "timestamp": "2026-01-01"},
        {"value": "B", "confidence": 0.7, "timestamp": "2026-01-01"},
    )
    assert r["disputed"] is True
    assert r["needs_human"] is True


# ===== Provenance =====

def test_provenance_record_and_get():
    prov.record("k1", "قيمة", source="test", confidence=0.8, kind="fact")
    item = prov.get("k1")
    assert item["value"] == "قيمة"
    assert item["source"] == "test"
    assert item["last_verified"]


def test_provenance_staleness():
    prov.record("fast", "x", source="s", kind="price")   # صلاحية يوم واحد
    # نزوّر آخر تحقق ليكون قديماً
    future = datetime.datetime.now() + datetime.timedelta(days=5)
    assert prov.is_stale("fast", now=future) is True


def test_provenance_mark_verified_refreshes():
    prov.record("v", "x", source="s", kind="price")
    assert prov.mark_verified("v") is True
    assert prov.is_stale("v") is False   # طازج الآن


# ===== Strategy Memory =====

def test_strategy_records_and_ranks():
    import uuid
    tt = f"research_{uuid.uuid4().hex[:8]}"
    for _ in range(3):
        sm.record_outcome(tt, "cross_check", True)
    sm.record_outcome(tt, "single_source", False)
    sm.record_outcome(tt, "single_source", False)
    best = sm.best_strategy(tt)
    assert best["strategy"] == "cross_check"
    assert best["success_rate"] == 1.0


def test_strategy_requires_min_samples():
    import uuid
    task = f"rare_task_{uuid.uuid4().hex[:8]}"   # فريد لكل تشغيل — عزل تام
    sm.record_outcome(task, "once", True)   # عيّنة واحدة فقط
    assert sm.best_strategy(task, min_samples=2) is None
