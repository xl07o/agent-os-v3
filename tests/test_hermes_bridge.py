"""اختبار جسر Hermes (وكيلك كعقل لـ JARVIS) + عميل Hermes (كمساعد لوكيلك)."""
import os, sys, tempfile, uuid, json
os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "hb_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import hermes_server as H
from agent_os import hermes_client as HC


# ===== الجسر: بروتوكول Hermes الذي تتوقّعه JARVIS =====
def test_health_no_auth():
    s, o = H.handle_rest("GET", "/health", "", {}, None)
    assert s == 200 and o["platform"] == "hermes-agent"

def test_capabilities_need_auth_when_key_set():
    old = H.API_KEY
    H.API_KEY = "k"
    try:
        assert H.handle_rest("GET", "/v1/capabilities", "", {}, None)[0] == 401
        assert H.handle_rest("GET", "/v1/capabilities", "", {"Authorization": "Bearer k"}, None)[0] == 200
    finally:
        H.API_KEY = old

def test_submit_run_202_and_events():
    s, o = H.handle_rest("POST", "/v1/runs", "", {}, json.dumps({"input": "حالة"}))
    assert s == 202 and o["run_id"].startswith("run_") and o["status"] == "started"
    frames = list(H.run_frames(o["run_id"]))
    assert frames[-1] == ": stream closed\n"
    assert any('"run.completed"' in f for f in frames)
    assert any('"message.delta"' in f for f in frames)

def test_missing_input_400():
    assert H.handle_rest("POST", "/v1/runs", "", {}, "{}")[0] == 400

def test_run_status_and_transcript():
    _, o = H.handle_rest("POST", "/v1/runs", "", {}, json.dumps({"input": "سجّل هدف متجر"}))
    rid = o["run_id"]
    s, run = H.handle_rest("GET", f"/v1/runs/{rid}", "", {}, None)
    assert s == 200 and run["status"] == "completed" and run["output"]
    s2, msgs = H.handle_rest("GET", f"/api/sessions/{rid}/messages", "", {}, None)
    assert s2 == 200 and len(msgs["data"]) >= 2
    assert msgs["data"][0]["role"] == "user" and msgs["data"][-1]["role"] == "assistant"

def test_unknown_run_404():
    assert H.handle_rest("GET", "/v1/runs/run_nope", "", {}, None)[0] == 404


# ===== العميل: Hermes كمساعد (بلا مثيل حيّ = صدق) =====
def test_client_unavailable_is_honest():
    # لا مثيل Hermes في الاختبار → available False و ask يرجع سبباً
    if not HC.available():
        r = HC.ask("مرحبا")
        assert r["ok"] is False and r.get("reason")

def test_client_empty_prompt():
    assert HC.ask("")["ok"] is False


# ===== إطارات الأدوات تُضيء لوحات JARVIS =====
def test_events_include_tool_frames_from_steps():
    _, o = H.handle_rest("POST", "/v1/runs", "", {}, json.dumps({"input": "سجّل هدف بناء متجر"}))
    frames = list(H.run_frames(o["run_id"]))
    events = [json.loads(f[5:])["event"] for f in frames if f.startswith("data:")]
    assert "tool.started" in events and "tool.completed" in events
    assert events.index("tool.started") < events.index("run.completed")

def test_session_messages_have_tool_rows():
    _, o = H.handle_rest("POST", "/v1/runs", "", {}, json.dumps({"input": "سجّل هدف متجر"}))
    _, msgs = H.handle_rest("GET", f"/api/sessions/{o['run_id']}/messages", "", {}, None)
    roles = [m["role"] for m in msgs["data"]]
    assert "tool" in roles and roles[0] == "user" and roles[-1] == "assistant"


# ===== قراءة الجسم المُقطّع (سبب خطأ 400 مع JARVIS/Dart) =====
def test_read_body_chunked():
    import io
    fake = type("F", (), {})()
    fake.headers = {"Transfer-Encoding": "chunked"}
    body = '{"model":"hermes-agent","input":"سجل هدف"}'
    b = body.encode("utf-8")
    chunk = (format(len(b), "x") + "\r\n").encode() + b + b"\r\n0\r\n\r\n"
    fake.rfile = io.BytesIO(chunk)
    assert H._H._read_body(fake) == body

def test_read_body_content_length():
    import io
    fake = type("F", (), {})()
    fake.headers = {"Content-Length": "5"}
    fake.rfile = io.BytesIO(b"hello")
    assert H._H._read_body(fake) == "hello"
