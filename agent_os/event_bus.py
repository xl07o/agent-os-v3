"""
event_bus.py - حافلة الأحداث الداخلية (ركن استقلالية)
========================================================
نقل أحداث منظمة بين الأنظمة دون ربط مباشر (فصل + قابلية مراقبة):

  - publish(type, data): يُسجّل الحدث في events.jsonl (ينمو بلا سقف) ويوصل للمشتركين
    الحاليين داخل العملية.
  - subscribe(callback): يسجّل معالِجاً ببلغة Python (لا إعادة وصل دمية).
  - kernel ينشر أحداثاً (task_done, goal_created, approval_requested, product_built)
    ويقرأها المشرف/اللوحة/السجلات.

الاستخدام:
  python agent_os/event_bus.py publish task_done "name=fix|ok=1"
  python agent_os/event_bus.py recent <نوع>
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

EVENTS_FILE = os.path.join(C.AGENT_OS_DIR, "events.jsonl")
_subscribers = []


def subscribe(fn):
    """سجّل معالِج: fn(event_dict). يبقى فعلياً طوال العملية الجارية."""
    if callable(fn) and fn not in _subscribers:
        _subscribers.append(fn)


def publish(event_type, data=None, source="kernel"):
    """انشر حدثاً وسجّله — بلا سقف حذف (القرار: يبقى كل شيء لأغراض السجلات)."""
    ev = {"type": event_type, "data": data or {}, "source": source,
          "ts": C.now_iso()}
    try:
        with open(EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except Exception:
        pass
    for fn in list(_subscribers):
        try:
            fn(ev)
        except Exception:
            pass
    return ev


def recent(event_type=None, limit=100):
    """آخر الأحداث من السجل النصي (بلا مكتبات سحرية)."""
    if not os.path.exists(EVENTS_FILE):
        return []
    out = []
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for ln in lines[-limit:]:
            ln = ln.strip()
            if not ln:
                continue
            try:
                ev = json.loads(ln)
            except Exception:
                continue
            if event_type and ev.get("type") != event_type:
                continue
            out.append(ev)
    except Exception:
        pass
    return out


def counts():
    """توزيع أنواع الأحداث — للوحة والمشرف."""
    agg = {}
    for ev in recent(None, 2000):
        t = ev.get("type", "?")
        agg[t] = agg.get(t, 0) + 1
    return agg


if __name__ == "__main__":
    import json as _j
    args = sys.argv[1:]
    if not args or args[0] == "recent":
        et = args[1] if len(args) > 1 else None
        for ev in recent(et, 30):
            print(f"{ev['ts'][:19]} [{ev['type']}] {_j.dumps(ev['data'], ensure_ascii=False)[:80]}")
    elif args[0] == "counts":
        print(counts())
    elif args[0] == "publish" and len(args) >= 3:
        try:
            data = _j.loads(args[2])
        except Exception:
            data = {"note": " ".join(args[2:])}
        print(publish(args[1], data, source="cli"))
    else:
        print("الاستعمال: publish <نوع> <json> | recent [نوع] | counts")