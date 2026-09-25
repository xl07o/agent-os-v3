"""اختبار خادم JARVIS — منطق الـ API بلا سوكِت + خدمة الواجهة."""
import os, sys, tempfile, uuid
os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "srv_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from agent_os import server

def test_status_endpoint():
    s, ctype, data = server.handle_api("/api/status", "", None)
    assert s == 200 and "json" in ctype
    d = json.loads(data)
    assert "voice" in d and "memory" in d

def test_ask_endpoint_executes_agent():
    s, ctype, data = server.handle_api("/api/ask", "", json.dumps({"q": "سجّل هدف بناء متجر"}))
    assert s == 200
    d = json.loads(data)
    assert d["reply"] and d["kind"]

def test_ask_empty_is_400():
    s, _, _ = server.handle_api("/api/ask", "", json.dumps({"q": ""}))
    assert s == 400

def test_ask_via_query_string():
    import urllib.parse
    s, _, data = server.handle_api("/api/ask", "q=" + urllib.parse.quote("حالة"), None)
    assert s == 200

def test_unknown_api_404():
    s, _, _ = server.handle_api("/api/nope", "", None)
    assert s == 404

def test_ui_file_exists():
    assert os.path.isfile(os.path.join(server.WEB_DIR, "jarvis.html"))


# ===== النقاط العالمية للربط بواجهات JARVIS خارجية =====
def test_chat_accepts_various_input_keys():
    for key in ("message", "text", "prompt", "input", "q"):
        s, _, data = server.handle_api("/chat", "", json.dumps({key: "حالة"}))
        assert s == 200
        d = json.loads(data)
        # يردّ بكل المفاتيح الشائعة
        for out in ("reply", "response", "text", "answer"):
            assert d.get(out)

def test_chat_alias_api_chat():
    s, _, _ = server.handle_api("/api/chat", "", json.dumps({"message": "حالة"}))
    assert s == 200

def test_chat_empty_400_with_reply():
    s, _, data = server.handle_api("/chat", "", json.dumps({"message": ""}))
    assert s == 400 and json.loads(data).get("reply")
