"""
اختبار ربط الذاكرة بحلقة التنفيذ (البنود 3/11/12).
يثبت أن run_task يقرأ الذاكرة قبل المحاولة ويكتب فيها بعدها — «الذاكرة أقوى من التوازي».
"""
import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "memloop_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import agent_os as A
from agent_os.memory import contextual_memory as cm
from agent_os.memory import strategy_memory as sm


def test_remember_then_recall():
    """بعد تشغيل مهمة تُحفظ التجربة، وتُستدعى في مهمة مشابهة."""
    task = f"حلّل ملف بيانات {uuid.uuid4().hex[:6]}"
    res = A.run_task(task, why="اختبار")
    assert "recalled" in res  # الحلقة تُرجع ما استُدعي من الذاكرة

    # التجربة حُفظت فعلاً في الذاكرة السياقية
    hits = cm.recall(task)
    assert len(hits) >= 1
    assert hits[0]["task"].startswith("حلّل ملف بيانات")

    # نتيجة الاستراتيجية سُجّلت لنوع المهمة
    stats = sm.stats(res["intent"])
    assert sum(s["attempts"] for s in stats.values()) >= 1


def test_failed_run_becomes_recalled_lesson():
    """فشل مهمة إنتاجية (سقالة بلا محتوى) يُسجَّل كدرس يظهر في محاولة تالية مشابهة."""
    from agent_os.memory import provenance as prov
    task = f"اكتب تقرير بحث فريد {uuid.uuid4().hex[:6]}"
    # بلا عقل/أدوات، المخرَج سقالة → غير verified → درس يُسجَّل
    res1 = A.run_task(task)
    # محاولة مشابهة: يجب أن تحمل دروساً مستدعاة أو تجربة سابقة
    res2 = A.run_task(task + " مرة ثانية")
    recalled = res2["recalled"]
    assert recalled["similar"] >= 1 or recalled["lessons"]
