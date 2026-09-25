"""
dashboard.py - لوحة تفاعلية فورية (مقترح كلاودي #7)
====================================================
يعرض حالة الوكيل آنياً عبر FastAPI إن توفر، وبخلاف ذلك يطبع الحالة نصياً.
FastAPI/uvicorn اختياريان نقيّان — لا تُستورد على مستوى الوحدة.

  GET /            صفحة HTML بسيطة.
  GET /state       كل الحالة مجمّعة.
  GET /finance     الميزانية اليومية + توفير المجاني.
  GET /goals       الأهداف النشطة + المحظورة.
  GET /approvals   الموافقات المعلقة.
  GET /notifications  آخر الإشعارات.
  GET /heartbeat   نبض النواة.

الاستخدام:
  python agent_os/dashboard.py              # يقلب uvicorn (أو يطبع الحالة)
  python agent_os/dashboard.py state        # حالة نصية فقط
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C


def state():
    """مجمّع الحالة الحتمي — يعمل بلا شبكة وبلا FastAPI."""
    data = {"time": C.now_iso(), "agent_os_dir": C.AGENT_OS_DIR}
    try:
        from agent_os import finance_intel
        data["finance"] = finance_intel.daily_report()
    except Exception as e:
        data["finance"] = {"error": str(e)[:100]}
    try:
        from agent_os import goal_manager
        data["goals"] = {
            "active": len(goal_manager.get_active_goals() or []),
            "blocked": [b.get("task", "")[:60] for b in (goal_manager.get_blocked_tasks() or [])[:5]],
        }
    except Exception as e:
        data["goals"] = {"error": str(e)[:100]}
    try:
        from agent_os import approval_center
        data["approvals_pending"] = approval_center.pending_count()
    except Exception as e:
        data["approvals_pending"] = {"error": str(e)[:100]}
    try:
        from agent_os import notifier
        data["notifications"] = [n["title"] for n in notifier.list_notifications()[-5:]]
    except Exception as e:
        data["notifications"] = {"error": str(e)[:100]}
    try:
        from agent_os import kernel
        data["heartbeat"] = kernel.read_heartbeat()
    except Exception as e:
        data["heartbeat"] = {"error": str(e)[:100]}
    return data


_PAGE = """<!DOCTYPE html><html lang="ar"><head><meta charset="utf-8">
<title>Agent OS — لوحة الحالة</title></head>
<body style="font-family:system-ui;background:#0f172a;color:#e2e8f0;padding:2rem">
<h1>🤖 Agent OS — لوحة الحالة</h1>
<p id="s"></p>
<script>fetch('state').then(r=>r.json()).then(d=>{{
document.getElementById('s').innerText=JSON.stringify(d,null,1);
}});</script></body></html>"""


def create_app():
    """FastAPI app — تتوفر فقط إن سُخّنت عند توفر المكتبة."""
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="Agent OS Dashboard", version="3.0")

    @app.get("/")
    def index():
        return HTMLResponse(_PAGE)

    @app.get("/state")
    def full_state():
        return state()

    @app.get("/finance")
    def finance_section():
        return state().get("finance")

    @app.get("/goals")
    def goals_section():
        return state().get("goals")

    @app.get("/approvals")
    def approvals_section():
        from agent_os import approval_center
        return {"pending": approval_center.pending_count()}

    @app.get("/notifications")
    def notifs():
        from agent_os import notifier
        return {"items": notifier.list_notifications()[-20:]}

    @app.get("/heartbeat")
    def heartbeat_section():
        from agent_os import kernel
        return kernel.read_heartbeat()

    return app


def serve(port=8787):
    """قلّب uvicorn إن وُجد؛ وإلا وجّه لاستخدام وضع النص."""
    try:
        import uvicorn
        uvicorn.run(create_app(), host="127.0.0.1", port=port)
    except ImportError:
        print("fastapi/uvicorn غير مثبتة — حالتك النصية:")
        import json
        print(json.dumps(state(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "state":
        import json
        print(json.dumps(state(), ensure_ascii=False, indent=1))
    else:
        serve()