"""
chat_api.py - جسر محادثة محلي بين واجهة ويب وbrain.py (v1.0)
================================================================
سيرفر HTTP محلي بحت — الأساس اللي أي واجهة ويب (Next.js أو غيرها) تتكلم
معه بدل ما تتكلم مباشرة مع brain.py. لاحقاً يضاف له مسار sandbox محوسب
(Daytona) لمّا يتوفر المفتاح — هذا الملف يبقى صالح بدون أي تغيير.

  • يعمل محلياً فقط على 127.0.0.1 — لا يفتح أي منفذ للإنترنت الخارجي.
  • POST /api/chat فقط — يمرّر الرسالة لـbrain.Brain نفسه (نفس العقل
    اللي يستخدمه selfrunner.py/chat_cli.py، بنفس أوضاع hybrid/smart/...).
  • CORS مفتوح فقط لأصول localhost/127.0.0.1 (أي منفذ) — نفس قاعدة
    web_bridge.py.
  • جلسة واحدة بالذاكرة لكل chat_id — بسيطة، تُعاد تهيئتها عند إعادة التشغيل.

التشغيل:
  python agent_os/chat_api.py
"""

import json
import os
import re
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8788

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

_LOCALHOST_ORIGIN = re.compile(
    r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?)$"
)

_sessions = {}  # chat_id -> brain.Brain


def _get_session(chat_id):
    import brain
    if chat_id not in _sessions:
        _sessions[chat_id] = brain.Brain(
            "أنت وكيل agent-os-v3 — رد مختصر مفيد بالعربية. "
            "إذا احتجت فعل حقيقي (تصفح/تحكم جهاز)، قل إنك تحتاج صلاحية sandbox."
        )
    return _sessions[chat_id]


class Handler(BaseHTTPRequestHandler):
    def _cors_headers(self):
        origin = self.headers.get("Origin", "")
        if _LOCALHOST_ORIGIN.match(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_response(404)
            self._cors_headers()
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            message = str(body.get("message", "")).strip()
            chat_id = str(body.get("chat_id") or uuid.uuid4())
            if not message:
                raise ValueError("empty message")

            session = _get_session(chat_id)
            text, engine = session.ask(message)

            payload = {"chat_id": chat_id, "reply": text, "engine": engine}
            status = 200
        except Exception as e:
            payload = {"error": str(e)[:200]}
            status = 400

        out = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, fmt, *args):
        pass  # صامت — بدون طباعة كل طلب بالطرفية


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"chat_api.py يعمل على http://{HOST}:{PORT}/api/chat (POST)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
