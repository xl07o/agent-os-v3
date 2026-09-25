"""
اختبار مُستوعِب التعلّم (البند 1) — النواة تُختبر بلا شبكة.
"""
import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "learn_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os.learn import ingest
from agent_os.memory import contextual_memory as cm
from agent_os.memory import provenance as prov


def test_ingest_text_stores_and_is_recallable():
    topic = f"لغة بايثون {uuid.uuid4().hex[:6]}"
    res = ingest.ingest_text("test-source", "بايثون لغة برمجة عالية المستوى تُستخدم في الذكاء الاصطناعي وتحليل البيانات على نطاق واسع.", topic=topic)
    assert res["ok"] is True
    assert res["chars"] > 40
    # صار قابلاً للاستدعاء من الذاكرة السياقية
    hits = cm.recall(topic)
    assert any(h.get("outcome") == "learned" for h in hits)
    # وله نَسَب في provenance
    assert prov.get(res["key"]) is not None


def test_ingest_rejects_empty_and_errors():
    assert ingest.ingest_text("s", "")["ok"] is False
    assert ingest.ingest_text("s", "قصير")["ok"] is False          # أقصر من الحد
    assert ingest.ingest_text("s", "(تعذر جلب الصفحة: timeout)")["ok"] is False  # رسالة خطأ


def test_ingest_github_bad_format():
    assert ingest.ingest_github("not-a-repo")["ok"] is False


def test_ingest_youtube_missing_lib_is_honest():
    # في بيئة بلا المكتبة: يخبر بصراحة، لا يفبرك نجاحاً (البند 5)
    r = ingest.ingest_youtube("https://youtu.be/dQw4w9WgXcQ")
    assert "ok" in r  # إمّا نجاح فعلي أو سبب صريح
    if not r["ok"]:
        assert "reason" in r
