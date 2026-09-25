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
