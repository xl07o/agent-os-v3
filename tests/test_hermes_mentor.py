"""اختبار حلقة Hermes المُرشِد (التطوّر المزدوج)."""
import os, sys, tempfile, uuid
os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "mentor_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os.evolution import hermes_mentor as M

def test_parse_fix():
    v, lesson, better = M._parse("VERDICT: FIX\nLESSON: 2+2=4 لا 5\nBETTER: الجواب 4")
    assert v == "FIX" and "4" in lesson and "4" in better

def test_parse_correct():
    v, _, _ = M._parse("VERDICT: CORRECT\nكل شيء سليم")
    assert v == "CORRECT"

def test_mentor_without_provider_is_honest():
    # بلا Hermes ولا عقل: لا تصحيح مُلفّق
    if not M.available():
        r = M.mentor("اجمع 2 و2", "الجواب 5")
        assert r["reviewed"] is False and r.get("reason")

def test_store_lesson_writes_memory():
    from agent_os.memory import provenance, contextual_memory as cm
    ok = M._store_lesson("مهمة اختبار", "task", "الدرس: تحقّق من الحساب", "الجواب الصحيح 4")
    assert ok is True
    assert provenance.get("mentor:task:مهمة اختبار") is not None
    # صار قابلاً للاستدعاء كتجربة «مصحّحة»
    hits = cm.recall("مهمة اختبار")
    assert any(h.get("outcome") == "corrected" for h in hits)
