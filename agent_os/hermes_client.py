"""
hermes_client.py - وكيلك يستخدم Hermes كمساعد (الاتجاه أ)
========================================================
يتيح لوكيلك أن يفوّض/يستشير مثيل Hermes حقيقياً (وكيل NousResearch) عبر
نفس بروتوكول Hermes: POST /v1/runs ثم قراءة خرجه. فيصبح Hermes مساعداً
قويّاً لوكيلك حين يتوفّر.

الإعداد (اختياري):
  HERMES_UPSTREAM_URL   (افتراضاً http://127.0.0.1:8642)
  HERMES_UPSTREAM_KEY   (مفتاح API_SERVER_KEY)

يتدهور بصدق: إن لم يتوفّر مثيل Hermes يُرجع ok=False بسبب صريح (البند 5).

  available()      -> هل مثيل Hermes حيّ؟
  ask(prompt)      -> يشغّل مهمة على Hermes ويعيد خرجها النهائي
"""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

URL = os.getenv("HERMES_UPSTREAM_URL", "http://127.0.0.1:8642").rstrip("/")
KEY = os.getenv("HERMES_UPSTREAM_KEY", "")
TIMEOUT = int(os.getenv("HERMES_UPSTREAM_TIMEOUT", "120"))


def _headers():
    h = {"Content-Type": "application/json"}
    if KEY:
        h["Authorization"] = f"Bearer {KEY}"
    return h


def _get(path, timeout=5):
    req = urllib.request.Request(URL + path, headers=_headers())
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def available():
    """هل مثيل Hermes حيّ (يجيب على /health)؟"""
    try:
        st, body = _get("/health", timeout=3)
        return st == 200 and '"ok"' in body
    except Exception:
        return False


def ask(prompt, timeout=None):
    """يشغّل مهمة على Hermes ويقرأ خرجها النهائي من بثّ SSE (أو من /v1/runs/{id})."""
    timeout = timeout or TIMEOUT
    if not (prompt or "").strip():
        return {"ok": False, "reason": "نص فارغ"}
    # 1) submit run
    try:
        body = json.dumps({"model": "hermes-agent", "input": prompt}).encode("utf-8")
        req = urllib.request.Request(URL + "/v1/runs", data=body, headers=_headers(), method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            sub = json.loads(r.read().decode("utf-8", "replace"))
        run_id = sub.get("run_id")
        if not run_id:
            return {"ok": False, "reason": f"لا run_id: {sub}"}
    except Exception as e:
        return {"ok": False, "reason": f"تعذّر الوصول لـ Hermes: {str(e)[:120]}"}

    # 2) اقرأ بثّ الأحداث حتى run.completed (أسطر data: فقط، صيغة Hermes)
    output = ""
    try:
        req = urllib.request.Request(URL + f"/v1/runs/{run_id}/events", headers=_headers())
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except Exception:
                    continue
                if ev.get("event") == "message.delta":
                    output += ev.get("delta", "")
                elif ev.get("event") == "run.completed":
                    output = ev.get("output") or output
                    break
    except Exception:
        pass

    # 3) احتياط: إن لم يصل خرج من البثّ، اقرأ حالة التشغيل النهائية
    if not output.strip():
        try:
            st, body = _get(f"/v1/runs/{run_id}", timeout=10)
            output = (json.loads(body) or {}).get("output", "") if st == 200 else ""
        except Exception:
            pass

    if not output.strip():
        return {"ok": False, "reason": "Hermes لم يُرجع خرجاً"}
    return {"ok": True, "text": output.strip(), "run_id": run_id, "via": "hermes"}


if __name__ == "__main__":
    import json as _j
    q = " ".join(sys.argv[1:]) or "ما نظام التشغيل على هذا الخادم؟"
    print(_j.dumps({"available": available(), "result": ask(q) if available() else "لا مثيل Hermes"},
                   ensure_ascii=False, indent=2))
