"""اختبارات الدفعة الكبيرة: كل أنظمة فكرة المالك الموسّعة."""

import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "vision_data"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===== Daily Evolution =====

def test_daily_evolution_discovers_weaknesses():
    from agent_os.evolution import daily_evolution as de
    w = de.discover_weakness()
    assert len(w) >= 1
    assert "type" in w[0]


def test_daily_evolution_cycle_runs():
    from agent_os.evolution import daily_evolution as de
    cycle = de.run_cycle()
    assert cycle["phase"] in ("discovered_only", "done", "failed", "improve")
    assert cycle["weaknesses_found"] >= 1


def test_daily_evolution_streak():
    from agent_os.evolution import daily_evolution as de
    de.run_cycle()   # يضمن تطور اليوم
    assert de.streak() >= 1


# ===== Hypothesis Lab =====

def test_hypothesis_sandbox_success():
    from agent_os.evolution import hypothesis_lab as hl
    def good_experiment(sandbox):
        open(os.path.join(sandbox, "t.txt"), "w").write("x")
        return {"success": True, "metrics": {"files": 1}}
    r = hl.create("اختبار sandbox", "ملف يُنشأ", good_experiment)
    assert r["status"] == "passed"
    assert r["sandbox_result"]["success"] is True


def test_hypothesis_sandbox_failure():
    from agent_os.evolution import hypothesis_lab as hl
    def bad_experiment(sandbox):
        return {"success": False}
    r = hl.create("فكرة فاشلة", "لا شيء", bad_experiment)
    assert r["status"] == "failed"


def test_hypothesis_promote_only_passed():
    from agent_os.evolution import hypothesis_lab as hl
    r = hl.create("فكرة بلا تجربة", "أي شي")
    assert r["status"] == "created"
    pr = hl.promote(r["id"])
    assert "error" in pr   # لا يمكن ترقية ما لم يُختبر


def test_hypothesis_stats():
    from agent_os.evolution import hypothesis_lab as hl
    s = hl.stats()
    assert "total" in s and "promoted" in s


# ===== Self Consultation =====

def test_consultation_graceful_no_provider():
    from agent_os.evolution import self_consultation as sc
    r = sc.consult("tool_discovery")
    assert "suggestions" in r or "note" in r   # لا يكسر


def test_consultation_invalid_type():
    from agent_os.evolution import self_consultation as sc
    r = sc.consult("invalid_type_zzz")
    assert "error" in r


# ===== Self Healer =====

def test_self_healer_diagnoses():
    from agent_os.recovery import self_healer as sh
    problems = sh.diagnose()
    # النظام سليم حالياً → لا مشاكل حرجة
    critical = [p for p in problems if p["severity"] == "critical"]
    assert len(critical) == 0, f"مشاكل حرجة غير متوقعة: {critical}"


def test_self_healer_full_cycle():
    from agent_os.recovery import self_healer as sh
    r = sh.check_and_heal()
    # قد يكتشف مشاكل غير حرجة (مثل اختبار بطيء) — المهم لا حرج
    critical = [d for d in r.get("details", [])
                if d["problem"].get("severity") == "critical"]
    assert len(critical) == 0, f"مشاكل حرجة: {critical}"


# ===== Reinvestment Wallet =====

def test_wallet_revenue_and_share():
    from agent_os.business import reinvestment_wallet as rw
    rw.set_share_rate(0.2)
    r = rw.record_revenue(1000, "test")
    assert r["share"] == 200.0
    b = rw.balance()
    assert b["balance"] >= 200.0


def test_wallet_spend_insufficient():
    from agent_os.business import reinvestment_wallet as rw
    r = rw.spend(999999, "شراء مستحيل")
    assert r["ok"] is False
    assert "رصيد غير كافٍ" in r["reason"]


def test_wallet_share_rate_capped():
    from agent_os.business import reinvestment_wallet as rw
    rate = rw.set_share_rate(0.99)   # يُقيّد عند 0.5
    assert rate <= 0.5


# ===== Human Requests =====

def test_request_creates_and_sorts():
    from agent_os.interface import human_requests as hr
    hr.request("اشتري API", ["سجّل"], priority="low")
    hr.request("طوارئ!", ["أصلح"], priority="critical")
    p = hr.pending()
    assert p[0]["priority"] == "critical"   # الأعلى أولوية أولاً


def test_request_complete():
    from agent_os.interface import human_requests as hr
    r = hr.request(f"طلب {uuid.uuid4().hex[:6]}", ["سوّ شي"], priority="medium")
    c = hr.complete(r["id"], notes="خلص")
    assert c["status"] == "completed"


def test_request_summary():
    from agent_os.interface import human_requests as hr
    s = hr.summary()
    assert "pending" in s and "completed_total" in s


# ===== Learning Engine =====

def test_learning_plan_nonempty():
    from agent_os.cognition import learning_engine as le
    plan = le.plan_learning(owner_goals=["بناء متجر"])
    assert len(plan) >= 1
    assert plan[0]["roi"] >= 0


def test_learning_stores_knowledge():
    from agent_os.cognition import learning_engine as le
    r = le.learn("Python async", "async/await للتنفيذ المتوازي", source="docs")
    assert r is True


def test_learning_stats():
    from agent_os.cognition import learning_engine as le
    s = le.stats()
    assert s["total_learned"] >= 1
