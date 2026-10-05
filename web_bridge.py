"""
web_bridge.py - جسر قراءة محلي بين وكيلك الحقيقي وموقع Live Agency (v1.0)
============================================================================
سيرفر HTTP محلي بحت يعرض بيانات حقيقية من هذا المشروع كـJSON، بلا أي كتابة
أو تنفيذ أوامر — مخصص خصيصاً لموقع التسويق (agency-site/) حتى يعرض أرقاماً
وأسماء حقيقية بدل الثابتة المكتوبة يدوياً فيه.

  • يعمل محلياً فقط على 127.0.0.1 — لا يفتح أي منفذ للإنترنت الخارجي.
  • قراءة فقط: ثلاث نقاط نهاية، كلها GET، لا كتابة ولا تنفيذ أوامر إطلاقاً.
  • CORS مفتوح فقط لأصول localhost/127.0.0.1 (أي منفذ) — لا شيء آخر.

التشغيل:
  python web_bridge.py
  ثم شغّل موقع agency-site بجنبه (npm run dev) — يقرأ منه تلقائياً.

نقاط النهاية:
  GET /api/specialists   قائمة الخبراء (id, name, description, emoji)
  GET /api/approvals     طلبات الموافقة المعلّقة فقط (id, what, why, risk, created)
  GET /api/stats         أرقام مجمّعة حقيقية للموقع
"""

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8787

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

_LOCALHOST_ORIGIN = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$")


def _specialists_payload():
    import specialists
    items = specialists.list_specialists()
    return [
        {"id": s["id"], "name": s["name"], "description": s["description"], "emoji": s["emoji"]}
        for s in items
    ]


def _approvals_payload():
    from agent_os import approval_center
    pending = approval_center.list_requests("pending")
    return [
        {"id": r["id"], "what": r["what"], "why": r["why"], "risk": r["risk"], "created": r["created"]}
        for r in pending
    ]


def _stats_payload():
    specialists_total = 0
    pending_approvals = 0
    tasks_tracked = 0
    notify_configured = 0

    try:
        import specialists
        specialists_total = len(specialists.list_specialists())
    except Exception:
        pass

    try:
        from agent_os import approval_center
        pending_approvals = len(approval_center.list_requests("pending"))
    except Exception:
        pass

    try:
        import roi_brain
        tasks_tracked = roi_brain._roi.report().get("total_tasks", 0)
    except Exception:
        pass

    try:
        import notifier
        status = notifier.status()
        notify_configured = sum(1 for v in status.values() if v)
    except Exception:
        pass

    return {
        "specialists_total": specialists_total,
        "pending_approvals": pending_approvals,
        "tasks_tracked": tasks_tracked,
        "notify_channels_configured": notify_configured,
    }


ROUTES = {
    "/api/specialists": _specialists_payload,
    "/api/approvals": _approvals_payload,
    "/api/stats": _stats_payload,
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[web_bridge] " + (fmt % args))

    def _cors_origin(self):
        origin = self.headers.get("Origin", "")
        return origin if _LOCALHOST_ORIGIN.match(origin) else ""

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        handler = ROUTES.get(path)
        if not handler:
            self._send_json(404, {"error": "unknown endpoint", "path": path})
            return
        try:
            self._send_json(200, handler())
        except Exception as e:
            self._send_json(500, {"error": str(e)[:200]})


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[web_bridge] يستمع على http://{HOST}:{PORT} — قراءة فقط، محلي بحت.")
    print("[web_bridge] نقاط النهاية: /api/specialists  /api/approvals  /api/stats")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
