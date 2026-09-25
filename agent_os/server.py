"""
server.py - خادم JARVIS المحلي (نواة الوكيل خلف الوجه) — البند 13
================================================================
خادم خفيف (مكتبة قياسية فقط، بلا أي تثبيت) يربط:
  المتصفح (وجه JARVIS + سماع الاسم + صوت) ⇆ هذا الخادم ⇆ نواة الوكيل.

  python -m agent_os.server        # ثم افتح http://127.0.0.1:8770 في Chrome
  قل «جارفيس» فيستيقظ، تكلّم، ينفّذ عبر الوكيل، ويردّ بصوته.

نقاط النهاية:
  GET  /                → واجهة JARVIS
  GET  /api/status      → جاهزية النظام (JSON)
  POST /api/ask {q}     → jarvis.handle(q) → {reply, kind} (JSON)

يُربط على 127.0.0.1 فقط (محلي وآمن)، ولا يخدم إلا ملفات مجلد web/.
"""

import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
HOST = os.getenv("JARVIS_HOST", "127.0.0.1")
PORT = int(os.getenv("JARVIS_PORT", "8770"))


def handle_api(path, query, body):
    """منطق الـ API قابل للاختبار بلا سوكِت. يرجع (status, content_type, bytes)."""
    if path == "/api/status":
        from agent_os import ultra
        return 200, "application/json", _j(ultra.cmd_status(None))

    if path == "/api/ask":
        q = ""
        if body:
            try:
                q = (json.loads(body) or {}).get("q", "")
            except Exception:
                q = ""
        if not q and query:
            q = urllib.parse.parse_qs(query).get("q", [""])[0]
        q = (q or "").strip()
        if not q:
            return 400, "application/json", _j({"error": "لا يوجد نص"})
        from agent_os import jarvis
        out = jarvis.handle(q)
        return 200, "application/json", _j({"reply": out.get("reply"), "kind": out.get("kind")})

    return 404, "application/json", _j({"error": "not found"})


def _j(obj):
    return json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    def _send(self, status, ctype, data):
        self.send_response(status)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "html" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            return self._serve_file("jarvis.html", "text/html")
        if parsed.path.startswith("/api/"):
            status, ctype, data = handle_api(parsed.path, parsed.query, None)
            return self._send(status, ctype, data)
        # ملفات ثابتة من web/ فقط (بلا عبور مسارات).
        name = os.path.basename(parsed.path)
        return self._serve_file(name, self._ctype(name))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        status, ctype, data = handle_api(parsed.path, parsed.query, body)
        self._send(status, ctype, data)

    def _serve_file(self, name, ctype):
        full = os.path.join(WEB_DIR, name)
        if not os.path.isfile(full) or os.path.commonpath([WEB_DIR, os.path.abspath(full)]) != WEB_DIR:
            return self._send(404, "text/plain", b"not found")
        with open(full, "rb") as f:
            self._send(200, ctype, f.read())

    @staticmethod
    def _ctype(name):
        return {".html": "text/html", ".js": "application/javascript",
                ".css": "text/css", ".json": "application/json"}.get(
            os.path.splitext(name)[1].lower(), "text/plain")

    def log_message(self, *a):
        pass  # صامت — لا نلوّث المخرجات


def serve(host=HOST, port=PORT):
    srv = ThreadingHTTPServer((host, port), _Handler)
    C.log(f"🤖 JARVIS على http://{host}:{port} — افتحه في Chrome وقل «جارفيس»")
    print(f"🤖 JARVIS يعمل: http://{host}:{port}  (Ctrl-C للإيقاف)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nتوقّف JARVIS.")
        srv.shutdown()


if __name__ == "__main__":
    serve()
