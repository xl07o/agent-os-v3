"""
hermes_server.py - جسر توافق Hermes: يجعل وكيلك عقلاً لواجهة JARVIS
==================================================================
تطبيق JARVIS (Flutter، MultiX0/jarvis) يتصل بوكيل Hermes عبر REST+SSE على
منفذ 8642. هذا الخادم يتكلّم نفس بروتوكول Hermes بالضبط (كما وُثّق في
docs/hermes-probe.md بالمستودع)، فتظنّه JARVIS خادم Hermes — بينما العقل
خلفه هو وكيلك (agent_os.jarvis.handle).

المسارات المنفّذة (المطابقة لما تتوقّعه JARVIS):
  GET  /health                    (بلا مصادقة)
  GET  /health/detailed
  GET  /v1/capabilities           (Bearer)
  GET  /v1/models
  GET  /v1/toolsets
  POST /v1/runs                   {"input": "..."} -> 202 {run_id, status:"started"}
  GET  /v1/runs/{id}
  GET  /v1/runs/{id}/events       (SSE: أسطر data: فقط، تنتهي بـ ": stream closed")
  GET  /api/sessions/{id}/messages

التشغيل على جهازك:
  python -m agent_os.hermes_server            # على 127.0.0.1:8642
ثم في JARVIS: host=127.0.0.1 (أو عبر نفق SSH كالمعتاد)، hermes_port=8642.
اضبط HERMES_API_KEY إن أردت مطابقة مفتاح، وإلا يقبل أي مفتاح.
"""

import json
import os
import secrets
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

VERSION = "0.20.6"          # يطابق ما فحصته JARVIS
MODEL = "hermes-agent"
HOST = os.getenv("HERMES_HOST", "127.0.0.1")
PORT = int(os.getenv("HERMES_PORT", "8642"))
API_KEY = os.getenv("HERMES_API_KEY", "")  # فارغ = يقبل أي مفتاح (وضع محلي)

_RUNS = {}  # run_id -> {status, input, output, kind, created, updated, messages}


# ===================== نواة التنفيذ (وكيلك) =====================
def _trim_reply(t, max_chars=900):
    t = " ".join(str(t).split())
    return t if len(t) <= max_chars else t[:max_chars].rsplit(" ", 1)[0] + "…"


def _agent_reply(prompt_text):
    """ردّ محادثة ذكي عبر العقل (Ollama) — هذا ما يفعله وكيل Hermes: يقرأ
    الطلب (مع تعليمات JARVIS المُرفقة) ويردّ كموظف بشري، لا يشغّل مُوجّه مهام
    بالكلمات المفتاحية (كان يخلط تعليمات JARVIS بمهمة «improve»)."""
    ctx = ""
    try:
        from agent_os.memory import conversation
        recent = [t for t in conversation.recent(6) if t.get("user")]
        ctx = "\n".join(f"User: {t['user']}\nJARVIS: {t.get('reply', '')}" for t in recent[-4:])
    except Exception:
        pass
    persona = ("You are JARVIS, a capable and friendly AI assistant and employee. "
               "Reply in English, natural and concise (2-5 sentences) like a smart human "
               "colleague. The message may include system notes/instructions — follow them "
               "but never repeat them back. If you don't know, say so plainly.")
    full = (f"Recent conversation:\n{ctx}\n\n" if ctx else "") + prompt_text
    # "fastest" = مزوّد واحد قوي مع تبديل تلقائي عند الفشل — أبسط وأثبت من الهجين
    # (الوضع الهجين كان يفشل أحياناً رغم أن مزوّداً منفرداً يعمل).
    raw, engine = C.call_brain(persona, full, mode="fastest")
    if not raw or engine in (None, "", "none") or raw.strip().startswith("("):
        reply = ("I'm online, but no thinking brain is reachable yet. Add a free API key "
                 "(e.g. GROQ_API_KEY) to .env or start Ollama, then RESTART me so I load it.")
    else:
        reply = _trim_reply(raw.strip())
    # نخزّن كلام المستخدم الأصلي (أول سطر) لا الطلب المُركّب كاملاً.
    try:
        from agent_os.memory import conversation
        conversation.record_turn(prompt_text.split("\n", 1)[0].strip()[:300], reply, intent="chat")
    except Exception:
        pass
    return reply


def create_run(input_text):
    """ينشئ تشغيلاً: وكيل تنفيذي (ينفّذ أوامر فعلاً) إن كان JARVIS_EXEC مفعّلاً،
    وإلا محادثة ذكية فقط. العقل يقرّر chat أو أوامر."""
    run_id = "run_" + secrets.token_hex(16)
    now = time.time()
    steps = []
    try:
        from agent_os import agent_loop
        if agent_loop.exec_enabled():
            r = agent_loop.run_agentic(input_text)
            reply, steps = r.get("reply", ""), r.get("steps", [])
        else:
            reply = _agent_reply(input_text)
    except Exception as e:
        reply = _agent_reply(input_text)  # fallback إلى المحادثة عند أي خلل
        C.log(f"agent_loop fallback: {str(e)[:120]}")
    # نخزّن المحادثة كمرجع
    try:
        from agent_os.memory import conversation
        conversation.record_turn(input_text.split("\n", 1)[0].strip()[:300], reply, intent="agent")
    except Exception:
        pass
    _RUNS[run_id] = {
        "run_id": run_id, "status": "completed", "input": input_text,
        "output": reply, "kind": "agent", "steps": [{"action": s["cmd"][:40], "done": s["ok"]} for s in steps],
        "created": now, "updated": time.time(), "session_id": run_id,
    }
    return run_id


def run_frames(run_id):
    """مولّد إطارات SSE لتشغيلٍ (بصيغة Hermes: أسطر data: فقط).
    يبثّ إطارات الأدوات من خطوات الوكيل الفعلية لتُضيء لوحات JARVIS، ثم النص."""
    run = _RUNS.get(run_id)
    if not run:
        yield _sse({"event": "error", "run_id": run_id,
                    "error": {"code": "run_not_found", "message": f"Run not found: {run_id}"}})
        yield ": stream closed\n"
        return

    # 1) خطوات الوكيل → إطارات tool.started / tool.completed (كصيغة Hermes الملتقَطة).
    for st in run.get("steps", []):
        action = st.get("action", "step")
        ts = time.time()
        yield _sse({"event": "tool.started", "run_id": run_id, "timestamp": ts,
                    "tool": action, "preview": st.get("target", action)})
        yield _sse({"event": "tool.completed", "run_id": run_id, "timestamp": time.time(),
                    "tool": action, "duration": 0.01, "error": not st.get("done", True)})

    # 2) الرد النصي على شكل message.delta (كلمة بكلمة).
    reply = run["output"] or ""
    for word in reply.split(" "):
        yield _sse({"event": "message.delta", "run_id": run_id,
                    "timestamp": time.time(), "delta": word + " "})

    # 3) الختام.
    yield _sse({"event": "run.completed", "run_id": run_id, "timestamp": time.time(),
                "output": reply, "usage": {"input_tokens": 0, "output_tokens": len(reply.split()),
                                           "total_tokens": len(reply.split())}})
    yield ": stream closed\n"


def _sse(obj):
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


# ===================== منطق REST (قابل للاختبار) =====================
def _authed(headers):
    if not API_KEY:
        return True  # وضع محلي: يقبل أي مفتاح/بلا مفتاح
    auth = (headers or {}).get("Authorization", "") if headers else ""
    return auth == f"Bearer {API_KEY}"


def handle_rest(method, path, query, headers, body):
    """كل المسارات غير SSE. يرجع (status, obj). SSE يُعالَج في المُعالِج مباشرة."""
    if path == "/health":
        return 200, {"status": "ok", "platform": "hermes-agent", "version": VERSION}

    # ما عدا /health يتطلّب مصادقة (كما في بروتوكول Hermes).
    if not _authed(headers):
        return 401, {"error": {"message": "Invalid gateway API key (API_SERVER_KEY)",
                               "type": "gateway_auth_error", "code": "gateway_auth_failed"}}

    if path == "/health/detailed":
        return 200, {"status": "ok",
                     "readiness": {"status": "ok", "checks": {
                         "state_db": {"status": "ok"}, "config": {"status": "ok"},
                         "model": {"status": "ok"},
                         "gateway": {"status": "ok", "state": "running", "connected_platforms": 1, "platforms": 1},
                         "background_queues": {"status": "ok", "active_api_runs": 0,
                                               "process_completions": 0, "active_delegations": 0}}},
                     "platform": "hermes-agent", "version": VERSION, "gateway_state": "running",
                     "active_agents": sum(1 for r in _RUNS.values() if r["status"] != "completed"),
                     "gateway_busy": False, "gateway_drainable": True, "exit_reason": None, "pid": os.getpid()}

    if path == "/v1/capabilities":
        feats = {k: True for k in ("run_submission", "run_status", "run_events_sse", "run_stop",
                                   "run_steer", "run_approval_response", "session_chat",
                                   "session_fork", "session_resources", "skills_api")}
        feats.update({k: False for k in ("audio_api", "realtime_voice", "cors", "admin_config_rw",
                                         "jobs_admin", "memory_write_api")})
        return 200, {"object": "capabilities", "features": feats,
                     "session_headers": {"id": "X-Hermes-Session-Id", "key": "X-Hermes-Session-Key"}}

    if path == "/v1/models":
        return 200, {"object": "list", "data": [{"id": MODEL, "object": "model",
                     "created": int(time.time()), "owned_by": "hermes", "permission": [],
                     "root": MODEL, "parent": None}]}

    if path == "/v1/toolsets":
        enabled = ["web", "terminal", "file", "code_execution", "skills", "todo", "memory", "delegation"]
        return 200, {"object": "list", "data": [
            {"name": n, "label": n, "description": "", "enabled": True, "configured": True, "tools": []}
            for n in enabled]}

    if path == "/v1/runs" and method == "POST":
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}
        inp = (data.get("input") or "").strip() if isinstance(data, dict) else ""
        if not inp:
            return 400, {"error": {"message": "Missing 'input' field",
                                   "type": "invalid_request_error", "code": "missing_input"}}
        run_id = create_run(inp)
        return 202, {"run_id": run_id, "status": "started"}

    # /v1/runs/{id}
    if path.startswith("/v1/runs/") and not path.endswith("/events"):
        rid = path.split("/v1/runs/", 1)[1].strip("/")
        run = _RUNS.get(rid)
        if not run:
            return 404, {"error": {"message": f"Run not found: {rid}",
                                   "type": "invalid_request_error", "code": "run_not_found"}}
        return 200, {"object": "hermes.run", "run_id": rid, "status": run["status"],
                     "updated_at": run["updated"], "created_at": run["created"],
                     "session_id": rid, "model": MODEL, "last_event": "run.completed",
                     "output": run["output"], "usage": {"input_tokens": 0,
                     "output_tokens": len(run["output"].split()), "total_tokens": len(run["output"].split())}}

    # /api/sessions/{id}/messages — النص الكامل (رد المساعد)
    if path.startswith("/api/sessions/") and path.endswith("/messages"):
        rid = path[len("/api/sessions/"):-len("/messages")].strip("/")
        run = _RUNS.get(rid)
        rows = []
        if run:
            rows.append({"id": 1, "role": "user", "content": run["input"], "timestamp": run["created"]})
            # صفوف الأدوات من خطوات الوكيل (تُغذّي لوحة الطرفية في JARVIS).
            for i, st in enumerate(run.get("steps", []), start=2):
                rows.append({"id": i, "role": "tool", "tool_name": st.get("action", "step"),
                             "tool_call_id": f"call_{i}",
                             "content": json.dumps({"output": st.get("target", ""),
                                                    "exit_code": 0 if st.get("done", True) else 1,
                                                    "error": None if st.get("done", True) else "لم تكتمل"},
                                                   ensure_ascii=False),
                             "timestamp": run["updated"]})
            rows.append({"id": len(rows) + 1, "role": "assistant", "content": run["output"],
                         "reasoning": "", "tool_calls": [], "timestamp": run["updated"]})
        return 200, {"object": "list", "session_id": rid, "data": rows,
                     "pagination": {"limit": 500, "offset": 0, "order": "latest", "returned": len(rows)}}

    return 404, {"error": {"message": "Not Found", "type": "invalid_request_error", "code": "not_found"}}


# ===================== خادم HTTP =====================
class _H(BaseHTTPRequestHandler):
    def _json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _headers(self):
        return {k: v for k, v in self.headers.items()}

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path.startswith("/v1/runs/") and p.path.endswith("/events"):
            return self._sse(p.path[len("/v1/runs/"):-len("/events")].strip("/"))
        status, obj = handle_rest("GET", p.path, p.query, self._headers(), None)
        self._json(status, obj)

    def _read_body(self):
        """يقرأ جسم الطلب سواء بـ Content-Length أو Transfer-Encoding: chunked
        (عملاء Dart/Flutter — ومنهم JARVIS — يرسلون chunked بلا طول، فكان
        الجسم يُقرأ فارغاً ويرجع 400)."""
        te = (self.headers.get("Transfer-Encoding", "") or "").lower()
        if "chunked" in te:
            data = b""
            while True:
                size_line = self.rfile.readline().strip()
                if not size_line:
                    break
                try:
                    size = int(size_line.split(b";")[0], 16)
                except ValueError:
                    break
                if size == 0:
                    self.rfile.readline()  # سطر CRLF الختامي
                    break
                data += self.rfile.read(size)
                self.rfile.read(2)  # CRLF بعد كل قطعة
            return data.decode("utf-8", "replace")
        n = int(self.headers.get("Content-Length", 0) or 0)
        return self.rfile.read(n).decode("utf-8", "replace") if n else ""

    def do_POST(self):
        p = urllib.parse.urlparse(self.path)
        body = self._read_body()
        status, obj = handle_rest("POST", p.path, p.query, self._headers(), body)
        self._json(status, obj)

    def _sse(self, run_id):
        if not _authed(self._headers()):
            return self._json(401, {"error": {"code": "gateway_auth_failed", "message": "Invalid key"}})
        # بثّ منتهٍ: نُغلق الاتصال بعد ": stream closed" حتى لا يتعلّق العميل
        # منتظراً المزيد (كان keep-alive يسبّب تعلّق JARVIS).
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for frame in run_frames(run_id):
                self.wfile.write(frame.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *a):
        pass


def serve(host=HOST, port=PORT):
    srv = ThreadingHTTPServer((host, port), _H)
    msg = f"🧠 Hermes-compat (وكيلك كعقل) على http://{host}:{port} — وجّه JARVIS إليه"
    C.log(msg)
    print(msg + "  (Ctrl-C للإيقاف)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nتوقّف الجسر.")
        srv.shutdown()


if __name__ == "__main__":
    serve()
