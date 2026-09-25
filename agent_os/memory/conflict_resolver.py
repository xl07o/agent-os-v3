"""
conflict_resolver.py - حسم تضارب المعرفة
==========================================
حين تتعارض معلومتان لنفس الأمر، لا يخمّن الوكيل: يطبّق قاعدة شفّافة.
  1) فارق ثقة معتبر (>= CONF_MARGIN) → الأعلى ثقة يفوز.
  2) ثقة متقاربة + تواريخ مختلفة       → الأحدث يفوز.
  3) تعادل تام (ثقة وتاريخ)             → يُعلَّم للحسم البشري (لا تخمين).

كل تعادل يُسجَّل في memory_conflicts.json ليعرضه التقرير اليومي.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import _common as C

CONF_MARGIN = 0.1  # أقل فارق ثقة يُعتبر حاسماً


def _file():
    return os.path.join(C.AGENT_OS_DIR, "memory_conflicts.json")


def _load():
    return C.load_json(_file(), {"disputes": []})


def _save(st):
    C.atomic_write(_file(), st)


def _parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(str(ts))
    except ValueError:
        try:
            return datetime.date.fromisoformat(str(ts).split("T")[0])
        except ValueError:
            return None


def resolve(a, b):
    """يحسم بين معلومتين {value, confidence, timestamp}. يرجع القرار وسببه."""
    ca = float(a.get("confidence", 0) or 0)
    cb = float(b.get("confidence", 0) or 0)

    if abs(ca - cb) >= CONF_MARGIN:
        winner = a if ca > cb else b
        return _decision(a, b, winner, "أعلى ثقة", disputed=False)

    ta, tb = _parse_ts(a.get("timestamp")), _parse_ts(b.get("timestamp"))
    if ta is not None and tb is not None and ta != tb:
        winner = a if ta > tb else b
        return _decision(a, b, winner, "الأحدث عند تقارب الثقة", disputed=False)

    # تعادل — لا تخمين، يُرفع للإنسان
    dec = _decision(a, b, None, "تعادل ثقةً وتاريخاً — يحتاج حسماً بشرياً", disputed=True)
    _record_dispute(dec)
    return dec


def _decision(a, b, winner, rule, disputed):
    return {
        "resolved_value": (winner or {}).get("value") if winner else None,
        "rule": rule,
        "disputed": disputed,
        "needs_human": disputed,
        "candidates": [a.get("value"), b.get("value")],
    }


def _record_dispute(dec):
    st = _load()
    st.setdefault("disputes", []).append({
        "time": C.now_iso(),
        "candidates": dec.get("candidates"),
        "resolved": False,
    })
    st["disputes"] = st["disputes"][-200:]
    _save(st)


def disputed_items():
    """التعارضات المعلّقة التي لم تُحسم بعد (يقرؤها التقرير اليومي)."""
    return [d for d in _load().get("disputes", []) if not d.get("resolved")]


def clear_dispute(index):
    """يعلّم تعارضاً كمحسوم بعد قرار المالك."""
    st = _load()
    disp = st.get("disputes", [])
    if 0 <= index < len(disp):
        disp[index]["resolved"] = True
        _save(st)
        return True
    return False


if __name__ == "__main__":
    import json
    print(json.dumps({"pending": len(disputed_items())}, ensure_ascii=False, indent=2))
