"""
اختبار المساعد Hermes (البند 14) — بلا مزوّد عقل: يتدهور بصدق ويخزّن مشورته.
"""
import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "hermes_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import hermes


def test_ask_degrades_honestly_or_answers():
    h = hermes.Hermes()
    r = h.ask("كيف أبني أداة CLI؟")
    assert "ok" in r
    if not r["ok"]:
        assert r.get("reason")               # صدق: سبب صريح بلا مزوّد
    else:
        assert r["text"] and not r["text"].startswith("(")


def test_plan_and_review_shape():
    h = hermes.Hermes()
    for r in (h.plan("انشر موقعاً"), h.review("def f(): return 1")):
        assert "ok" in r
        assert r.get("text") or r.get("reason")


def test_shared_instance():
    assert hermes.get() is hermes.get()
