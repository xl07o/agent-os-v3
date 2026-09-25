"""اختبارات الحلقة الذهبية (agent_os/golden_loop.py).

تركز على مبدأي المواصفة: No Fake Completion (§106) و Partial Success (§31).
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import golden_loop as gl


def _exec_writes_file(step):
    """منفّذ يكتب ملفاً ويُرفق دليل تحقق حقيقياً."""
    path = os.path.join(tempfile.gettempdir(), "gl_test_real.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("done")
    return {"ran": True, "output": "wrote",
            "expected": {"type": "file_exists", "target": path}}


def _exec_claims_but_no_evidence(step):
    """منفّذ يدّعي النجاح لكن بلا أي دليل قابل للفحص."""
    return {"ran": True, "output": "تم! (بدون دليل)"}


def _exec_fake_file(step):
    """منفّذ يدّعي كتابة ملف لكنه لا يكتبه فعلاً — يجب أن يكشفه التحقق."""
    fake = os.path.join(tempfile.gettempdir(), "gl_does_not_exist_zzz.txt")
    if os.path.exists(fake):
        os.remove(fake)
    return {"ran": True, "output": "زعمت الكتابة",
            "expected": {"type": "file_exists", "target": fake}}


def _exec_fails(step):
    return {"ran": False, "output": "فشل التنفيذ"}


def test_real_success_with_evidence():
    """تنفيذ حقيقي مع دليل → success."""
    rec = gl.run("اكتب ملفاً", _exec_writes_file)
    assert rec["outcome"] == gl.OUTCOME_SUCCESS
    assert rec["next"] == "advance"
    # تنظيف
    p = os.path.join(tempfile.gettempdir(), "gl_test_real.txt")
    os.path.exists(p) and os.remove(p)


def test_no_fake_completion():
    """ادّعاء نجاح بلا دليل يجب ألا يُحسب success (المواصفة §106)."""
    rec = gl.run("مهمة بلا دليل", _exec_claims_but_no_evidence)
    assert rec["outcome"] == gl.OUTCOME_UNVERIFIED
    assert rec["outcome"] != gl.OUTCOME_SUCCESS
    assert rec["next"] == "seek_evidence"


def test_false_success_detected():
    """ادّعاء كتابة ملف غير موجود فعلاً → التحقق يكشفه كفشل (المواصفة §30)."""
    rec = gl.run("زعم كتابة ملف", _exec_fake_file)
    assert rec["outcome"] == gl.OUTCOME_FAILURE
    assert rec["next"] == "diagnose"


def test_execution_failure():
    """فشل التنفيذ الصريح → failure."""
    rec = gl.run("مهمة تفشل", _exec_fails)
    assert rec["outcome"] == gl.OUTCOME_FAILURE


def test_partial_success():
    """بعض الخطوات تنجح وبعضها لا → partial (المواصفة §31)."""
    calls = {"n": 0}

    def mixed(step):
        calls["n"] += 1
        if calls["n"] == 1:
            path = os.path.join(tempfile.gettempdir(), "gl_partial_ok.txt")
            open(path, "w").write("x")
            return {"ran": True, "output": "ok",
                    "expected": {"type": "file_exists", "target": path}}
        return {"ran": False, "output": "فشل"}

    # نبني خطوتين يدوياً لأن plan() ينتج خطوة واحدة افتراضياً
    steps = [{"action": "execute", "detail": "a"},
             {"action": "execute", "detail": "b"}]
    results = gl.execute(steps, mixed)
    verified = gl.verify(results)
    m = gl.measure(verified)
    assert m["outcome"] == gl.OUTCOME_PARTIAL
    assert 0 < m["score"] < 1
    p = os.path.join(tempfile.gettempdir(), "gl_partial_ok.txt")
    os.path.exists(p) and os.remove(p)


def test_record_is_auditable():
    """السجل يحتوي كل المراحل — قابلية التدقيق (المواصفة §32 Black Box)."""
    rec = gl.run("مهمة", _exec_claims_but_no_evidence)
    for phase in ("understand", "plan", "execute", "verify", "measure"):
        assert phase in rec["phases"], f"مرحلة ناقصة: {phase}"
    assert "elapsed_sec" in rec and "started" in rec and "finished" in rec


def test_measure_empty():
    """قياس بلا نتائج → failure لا استثناء."""
    m = gl.measure([])
    assert m["outcome"] == gl.OUTCOME_FAILURE
    assert m["score"] == 0.0


def test_regression_memory_records_failure():
    """كل فشل يُسجَّل كدرس انحدار دائم يمكن استرجاعه (المواصفة §60-62)."""
    import agent_os.golden_loop as g
    goal = "مهمة فريدة للاختبار zzz-regression-unique"
    g.run(goal, _exec_fake_file)   # ينتج failure
    lesson = g.known_failure(goal)
    assert lesson is not None, "لم يُسجَّل درس الانحدار"
    assert lesson["outcome"] == g.OUTCOME_FAILURE


def test_known_failure_absent_for_new_goal():
    """هدف جديد لم يفشل سابقاً → لا درس انحدار."""
    import agent_os.golden_loop as g
    assert g.known_failure("هدف لم يُجرَّب إطلاقاً qqq-never-seen") is None
