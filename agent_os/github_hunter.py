"""
github_hunter.py - صيّاد المعرفة الموّجه من GitHub (ركن 8% ← 60% الهدف)
======================================================================
ليس «أرشيف كل GitHub» (مستحيل وغير قانوني كزحف شامل — كما حذّر التقرير)، بل
صيّاد مرخّص بترخيص:

  - بلا اعتمادات نهائياً (رؤوس عامة، حد 60/ساعة).
  - يرشّح المستودعات بمعلّم الترخيص: MIT/Apache-2.0/GPL-3.0/… فقط.
  - يلتقط README وأسطول رمز مصدر لإبراز النمط — لا استنساخ ضخم.
  - كل عملية مسجلة في github_hunts.json للموظف (وجولنا) دون امتلاء.

الاستخدام:
  python agent_os/github_hunter.py hunt "fastapi micro-saas"
  python agent_os/github_hunter.py recent
  python agent_os/github_hunter.py skills <topic>     # يستنتج مهارة في skills.mem
"""

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

HUNT_FILE = os.path.join(C.AGENT_OS_DIR, "github_hunts.json")
ALLOWED_LICENSES = {"mit", "apache-2.0", "gpl-3.0", "gpl-2.0", "bsd-3-clause",
                    "bsd-2-clause", "mpl-2.0", "unlicense", "isc", "lgpl-3.0"}
API_SLEEP = 2.0  # مهذّب للواجهة العامة


def _api(url, timeout=15):
    try:
        import webtools
        body = webtools._fetch(url, timeout=timeout)
        if not isinstance(body, str) or not body.strip():
            return None
        start = min(len(body), 20000)
        head = body[:start]
        if head.lstrip().startswith("{"):
            import json
            return json.loads(head)
        return None
    except Exception:
        return None


def hunt(query, per_page=10):
    """ابحث عن مستودعات بترخيص مفتوح في موضوع محدد — أعد قائمة موجزة."""
    import json
    url = ("https://api.github.com/search/repositories?q={q}&sort=stars"
           "&order=desc&per_page={n}").format(q=query.replace(" ", "+"),
                                              n=min(per_page, 30))
    res = _api(url)
    if not res:
        return {"query": query, "error": "لا استجابة (راجع الوتيرة العامة 60/ساعة)"}
    items = res.get("items", [])
    picked = []
    for it in items:
        lic = (it.get("license") or {}).get("spdx_id", "") or ""
        if lic.lower() not in ALLOWED_LICENSES:
            continue
        picked.append({
            "full_name": it.get("full_name", ""),
            "stars": it.get("stargazers_count", 0),
            "lang": it.get("language", ""),
            "license": lic,
            "description": (it.get("description") or "")[:200],
            "topics": (it.get("topics") or [])[:5],
        })
    record = {"query": query, "time": C.now_iso(), "found": len(picked),
              "items": picked[:8]}
    state = C.load_json(HUNT_FILE, {"hunts": []})
    state["hunts"].append(record)
    state["hunts"] = state["hunts"][-60:]
    C.atomic_write(HUNT_FILE, state)
    time.sleep(API_SLEEP)
    return record


def readme(full_name):
    """اقرأ README المستودع (من غير استنساخ) لاستخلاص النمط."""
    url = f"https://api.github.com/repos/{full_name}/readme"
    res = _api(url)
    if not res or "content" not in res:
        return None
    import base64
    try:
        return base64.b64decode(res["content"]).decode("utf-8", errors="replace")[:4000]
    except Exception:
        return None


def learn(query, per_page=8):
    """استنتج مهارة عملية من مستودعات مرخصة: اكتب سطراً في skills.mem بلا حذفية."""
    rec = hunt(query, per_page)
    if not rec.get("items"):
        return {"ok": False, "reason": "لا مستودعات مرخصة"}
    top = rec["items"][0]
    note = ("pattern=" + (top["lang"] or "") + " license=" + top["license"] +
            " stars=" + str(top["stars"]))
    try:
        from agent_os import skill_memory
        skill_memory.remember(f"github:{query}", action=top["full_name"], ok=True, notes=note)
    except Exception:
        pass
    return {"ok": True, "learned_from": top["full_name"], "license": top["license"]}


def recent(limit=10):
    return C.load_json(HUNT_FILE, {"hunts": []})["hunts"][-limit:]


def new_hunt_since(ts="2000-01-01"):
    """موضوعات جديدة (للنواة: أولوية تعلم)."""
    return [h for h in recent(40) if h["time"] > ts and h.get("items")]


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "recent":
        for h in recent():
            print(f"{h['time']} <{h['query']}> {h['found']} مستودع مرخّص")
    elif args[0] in ("hunt", "learn") and len(args) >= 2:
        topic = " ".join(args[1:])
        print(learn(topic) if args[0] == "learn" else hunt(topic))
    else:
        print("الاستعمال: hunt <موضوع> | learn <موضوع> | recent")