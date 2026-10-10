"""
error_tracker.py - مركز تتبّع الأخطاء المركزي (v1.0)
=======================================================
بديل `except Exception: pass` الصامت — يحفظ الخطأ ومصدره في errors.jsonl
ليصير مرئياً بالواجهة والسجلات بدل أن يضيع.

الاستخدام (في أي وحدة):
  from agent_os import error_tracker
  try:
      do_something()
  except Exception as e:
      error_tracker.capture(e, source="module_name")

أو كـone-liner يرجع None دائماً:
  except Exception as e:
      error_tracker.capture(e, "my_module") or fallback_value
"""

import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

ERRORS_FILE = os.path.join(C.AGENT_OS_DIR, "errors.jsonl")


def capture(exc, source="unknown", ctx=None):
    """سجّل استثناءً. آمن دائماً — لا يُعيد الإطراح أبداً. يرجع None."""
    try:
        tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        entry = {
            "ts": C.now_iso(),
            "source": str(source)[:80],
            "type": type(exc).__name__,
            "msg": str(exc)[:300],
            "tb": "".join(tb_lines)[-600:],
            "ctx": {str(k)[:40]: str(v)[:200] for k, v in (ctx or {}).items()},
        }
        with open(ERRORS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return None  # يرجع None دائماً ليسهل الاستخدام في except


def recent(n=50):
    """آخر n خطأ مسجّل — للواجهة والمشرف. الأحدث أولاً."""
    if not os.path.exists(ERRORS_FILE):
        return []
    out = []
    try:
        with open(ERRORS_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for ln in lines[-n:]:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    except Exception:
        pass
    return list(reversed(out))


def count_today():
    """عدد الأخطاء اليوم — مؤشر صحة سريع للمشرف."""
    today = C.now_iso()[:10]
    return sum(1 for e in recent(200) if e.get("ts", "").startswith(today))


if __name__ == "__main__":
    for err in recent(20):
        print(f"{err['ts'][:19]} [{err['source']}] {err['type']}: {err['msg'][:80]}")
