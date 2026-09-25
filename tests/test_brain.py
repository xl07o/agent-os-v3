"""اختبارات brain.py.

تشغيل: python -m pytest tests/ -v
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_brain_status():
    """التحقق من فحص العقول."""
    import brain
    report = brain.status_report()
    assert "available" in report
    assert "total_engines" in report


def test_brain_estimate_tokens():
    """التحقق من تقدير الـ tokens."""
    import brain
    tokens = brain._estimate_tokens("هذا نص تجريبي بالعربيه hello world test")
    assert tokens > 0


def test_brain_choose():
    """التحقق من اختيار المزود المناسب."""
    import brain
    # يجب أن لا يكسر بدون مزودين
    avail = brain.available_engines()
    assert isinstance(avail, list)


def test_brain_budget():
    """سقف التكلفة لا يمنع المزودين المجانيين أبداً."""
    import brain
    free_engines = [e for e in brain.ENGINES_ALL if e["free"]]
    for e in free_engines:
        assert brain._over_budget(e) is False
    rep = brain._budget_report()
    assert rep["max_cost_usd"] > 0


def test_brain_save_perf_atomic_and_judge_disabled():
    """كتابة الأداء ذرية + الحكم الدلالي معطّل افتراضياً (صفر استدعاءات شبكة)."""
    import json as _json
    import tempfile
    import brain
    b = brain.Brain("أنت مساعد اختباري")
    # ملف أداء مؤقت — لا نلوّث سجل الأداء الحقيقي
    tmp_dir = tempfile.mkdtemp(prefix="sr_perf_")
    b._perf_file = os.path.join(tmp_dir, "brain_perf.json")
    b._perf = {"test": {"n": 1, "ok": 1, "t": 0.5, "tokens": 10}}
    b._save_perf()
    with open(b._perf_file, "r", encoding="utf-8") as f:
        data = _json.load(f)
    assert data["test"]["n"] == 1
    assert not os.path.exists(b._perf_file + ".tmp")
    # الحكم الدلالي: معطّل افتراضياً فلا يحاول التواصل مع أي مزود
    os.environ["SELFRUNNER_HYBRID_JUDGE"] = "0"
    verdict = b._judge_response("سؤال؟", [("رد أ", "a", "ok", 1), ("رد ب", "b", "ok", 1)])
    assert verdict is None


def test_brain_daily_budget_reset():
    """الميزانية تتصفّر تلقائياً بتاريخ يختلف عن اليوم."""
    import brain
    stale = {"anthropic": {"n": 5, "ok": 5, "t": 9.0, "tokens": 1000000}, "_date": "2000-01-01"}
    totals = brain._perf_total(stale)
    assert totals == {}
    fresh_date = brain._today()
    fresh = {"anthropic": {"n": 2, "ok": 2, "t": 3.0, "tokens": 1000000}, "_date": fresh_date}
    totals2 = brain._perf_total(fresh)
    assert totals2.get("anthropic", 0) > 0.0