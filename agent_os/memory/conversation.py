"""
conversation.py - ذاكرة المحادثة واستخلاص الأولويات (البند 11)
=============================================================
«يحدد الأولوية بناءً على محادثاتنا». يسجّل كل دور حوار، ويستخلص المواضيع
المتكرّرة كأولويات مرتّبة — فما تسأل عنه كثيراً يصير مهماً تلقائياً.

  record_turn(user_text, agent_reply, intent) -> يخزّن دوراً
  priorities(top)                             -> مواضيع مرتّبة بالتكرار الحديث
  recent(n)                                   -> آخر n دور للسياق
"""

import os
import re
import sys
import math
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import _common as C

# كلمات وقف عربية/إنجليزية شائعة — لا تصلح كأولويات.
_STOP = set("""
من في على الى إلى عن مع هذا هذه ذلك التي الذي ما لا نعم يا كل بعض هو هي و او أو ثم
اذا إذا كان كانت لي لك له لها كيف متى اين أين لماذا هل قد سو سوي اعمل اعملي افعل
the a an of to in on for and or is are was were this that it be do how what why when
""".split())


def _file():
    return os.path.join(C.AGENT_OS_DIR, "conversation.json")


def _load():
    return C.load_json(_file(), {"turns": []})


def _save(st):
    C.atomic_write(_file(), st)


def _keywords(text):
    words = re.findall(r"[A-Za-z؀-ۿ]{3,}", str(text or "").lower())
    return [w for w in words if w not in _STOP]


def record_turn(user_text, agent_reply="", intent=""):
    """يسجّل دور حوار واحداً مع طابع زمني."""
    st = _load()
    st.setdefault("turns", []).append({
        "t": time.time(),
        "time": C.now_iso(),
        "user": str(user_text)[:500],
        "reply": str(agent_reply)[:300],
        "intent": intent,
        "keywords": _keywords(user_text)[:20],
    })
    st["turns"] = st["turns"][-500:]
    _save(st)
    return st["turns"][-1]


def priorities(top=5, half_life_days=7.0):
    """أولويات المالك = المواضيع الأكثر تكراراً حديثاً (تكرار موزون بالحداثة).
    الأحدث أثقل: وزن كل ذكر يتضاءل نصفياً كل half_life_days."""
    st = _load()
    now = time.time()
    scores = {}
    for turn in st.get("turns", []):
        age_days = max(0.0, (now - turn.get("t", now)) / 86400.0)
        weight = math.pow(0.5, age_days / half_life_days)
        for kw in turn.get("keywords", []):
            scores[kw] = scores.get(kw, 0.0) + weight
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [{"topic": k, "score": round(v, 3)} for k, v in ranked[:top]]


def recent(n=5):
    return _load().get("turns", [])[-n:]


def stats():
    turns = _load().get("turns", [])
    return {"turns": len(turns), "top_priorities": priorities(3)}


if __name__ == "__main__":
    import json
    print(json.dumps(stats(), ensure_ascii=False, indent=2))
