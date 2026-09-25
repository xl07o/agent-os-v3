"""اختبارات الدفعة 4: تكامل الحلقة الذهبية مع الذاكرة (preflight + meta-learning)."""

import os
import sys
import tempfile

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "batch4_data"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import golden_loop as gl


def _ok_exec(step):
    p = os.path.join(tempfile.gettempdir(), "b4_ok.txt")
    open(p, "w").write("x")
    return {"ran": True, "output": "ok",
            "expected": {"type": "file_exists", "target": p}}


def test_preflight_phase_present():
    rec = gl.run("مهمة بحث فريدة b4", _ok_exec)
    assert "preflight" in rec["phases"]
    assert "prior_failure" in rec["phases"]["preflight"]


def test_meta_learning_accumulates_strategy():
    """بعد عدة تشغيلات ناجحة لنفس النية، تُوصى استراتيجية (min_samples=2)."""
    goal = "ابنِ شيئاً meta b4"
    for _ in range(3):
        gl.run(goal, _ok_exec)
    rec = gl.run(goal, _ok_exec)
    # بعد 3+ عيّنات ناجحة يجب أن تظهر توصية استراتيجية
    assert rec["phases"]["preflight"]["recommended_strategy"] == "golden_loop_default"


def test_prior_failure_recalled():
    """فشل سابق لهدف يُستدعى في preflight الطلعة التالية."""
    def fail_exec(step):
        fake = os.path.join(tempfile.gettempdir(), "b4_missing_zzz.txt")
        os.path.exists(fake) and os.remove(fake)
        return {"ran": True, "output": "زعم",
                "expected": {"type": "file_exists", "target": fake}}

    goal = "هدف يفشل b4 unique-xyz"
    gl.run(goal, fail_exec)          # ينتج failure ويُسجَّل
    rec = gl.run(goal, fail_exec)    # الطلعة التالية تستدعي الفشل
    assert rec["phases"]["preflight"]["prior_failure"] is not None


def _cleanup():
    p = os.path.join(tempfile.gettempdir(), "b4_ok.txt")
    os.path.exists(p) and os.remove(p)
