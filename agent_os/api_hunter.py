"""
api_hunter.py - مستكشف نقاط نهاية API العامة (مقترح كلاودي #3)
==============================================================
يبحث عن endpoints عامة ويختبرها بأمان تام:

  - بلا كلمات مرور/أوراق اعتماد إطلاقاً (find-only، لا auth).
  - يمرر كل مسبار عبر فحص SSRF/خاص (webtools._is_safe_url).
  - يحترم robots.txt ويحدّد الوتيرة (browser_agent guards).
  - أي فشل شبكة = نتيجتان هادئتان وليس انهياراً.

الاستخدام:
  python agent_os/api_hunter.py hunt example.com
  python agent_os/api_hunter.py recent
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

HUNT_FILE = os.path.join(C.AGENT_OS_DIR, "api_hunter.json")

# مسارات عامة شائعة تفتح واجهة مُستكشفة بدون أماكن اعتماد
DEFAULT_PATHS = [
    "/api", "/v1", "/v2", "/health", "/api/v1/health", "/api/health",
    "/openapi.json", "/swagger.json", "/swagger-ui.html", "/api/docs",
    "/docs", "/redoc", "/graphql", "/metrics", "/status",
]


def _is_public_host(host):
    """مضيفات العامة فقط: http(s)، لا عناوين خاصة/محلية، لا موانئ مشبوهة."""
    m = re.fullmatch(r"(https?)://([A-Za-z0-9.\-]+)(:\d{1,5})?(/.*)?", host or "")
    if not m:
        return False
    return True


def hunt(host, paths=None):
    """جرّب المسارات العامة بأمان على مضيف عام.
    يعيد {host, findings, time}; لا يرسل أي اعتماد أبداً."""
    host = (host or "").strip()
    if not _is_public_host(host):
        return {"host": host, "error": "مضيف غير عام أو غير مؤمَّن — نرفض المسح"}
    try:
        import webtools
    except Exception:
        return {"host": host, "error": "webtools غير متاح"}
    from agent_os import browser_agent

    if not webtools._is_safe_url(host):
        return {"host": host, "error": "مُحجوب أمنياً (SSRF/خاص)"}
    limiter = browser_agent._RateLimiter()
    findings = []
    base = host.rstrip("/")
    for path in (paths or DEFAULT_PATHS):
        url = base + path
        if not _robots_ok(host, webtools):
            break
        try:
            limiter.wait(re.sub(r"^https?://", "", host).split(":")[0])
            body = webtools._fetch(url, timeout=8)
            status = 200 if body is not None and body != "" else 0
            note = body.strip()[:80] if isinstance(body, str) else "غير نصّي"
            if status:
                findings.append({"path": path, "status": status, "note": note})
        except Exception:
            continue
    record = {"host": host, "time": C.now_iso(), "findings": findings}
    state = C.load_json(HUNT_FILE, {"hunts": []})
    state["hunts"].append(record)
    state["hunts"] = state["hunts"][-100:]
    C.atomic_write(HUNT_FILE, state)
    return record


def _robots_ok(url, webtools):
    try:
        from agent_os import browser_agent
        return browser_agent._robots_allows(url, webtools._fetch)
    except Exception:
        return True


def recent(limit=10):
    """آخر عمليات المسح المحفوظة."""
    return C.load_json(HUNT_FILE, {"hunts": []})["hunts"][-limit:]


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "recent":
        for r in recent():
            print(f"{r['time']} {r['host']} → {len(r.get('findings', []))} نقاط")
    elif args[0] == "hunt" and len(args) >= 2:
        res = hunt(args[1])
        if "error" in res:
            print("رفض:", res["error"])
        else:
            print(f"{res['host']}: {len(res['findings'])} نافذة")
            for f in res["findings"]:
                print(f"  [{f['status']}] {f['path']} — {f['note'][:60]}")
    else:
        print("الاستعمال: hunt <http(s)://host> | recent")