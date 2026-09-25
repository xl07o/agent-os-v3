"""
skill_memory.py - ذاكرة المهارات (مقترح كلاودي #2)
==================================================
مهارات تُتعلَّم وتُخزَّن استدلالياً في ملف نصي مجازي  data/agent_os/skills.mem
(سجل تطوّري يتنامى بلا حدود ولا سقف ولا حذف — أي مهمة ناجحة تُحفظ كلمة مفتاحية).

  remember(context, action, ok, notes)  -> يُدرج سطراً جديداً
  recall(context, top)                  -> يبحث استدلالياً بتشابه الرموز
  summarize()                           -> عدّ + نسبة النجاح

الاستخدام:
  python agent_os/skill_memory.py remember <context> <action>
  python agent_os/skill_memory.py recall <context>
  python agent_os/skill_memory.py summarize
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

SKILL_MEM = os.path.join(C.AGENT_OS_DIR, "skills.mem")
FIELDS = 5


def _line(entry):
    return "|".join(str(entry.get(k, "")) for k in ("time", "context", "action", "ok", "notes"))


def remember(context, action, ok=True, notes=""):
    """تعلم مهارة: سطر في skills.mem. الملف ينمو بلا حدود — لا سقف ولا حذف."""
    entry = {
        "time": C.now_iso(),
        "context": (context or "").strip()[:300],
        "action": (action or "").strip()[:300],
        "ok": "1" if ok else "0",
        "notes": (notes or "").strip()[:200],
    }
    os.makedirs(os.path.dirname(SKILL_MEM), exist_ok=True)
    try:
        with open(SKILL_MEM, "a", encoding="utf-8") as f:
            f.write(_line(entry) + "\n")
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120]}
    return {"ok": True, "line": _line(entry)}


def _load_lines():
    if not os.path.exists(SKILL_MEM):
        return []
    try:
        with open(SKILL_MEM, "r", encoding="utf-8", errors="replace") as f:
            return [ln.rstrip("\n") for ln in f if ln.strip()]
    except Exception:
        return []


def _tokens(text):
    return set(re.findall(r"[a-zA-Z\u0600-\u06FF0-9_]{2,}", (text or "").lower()))


def recall(context, top=5):
    """استدعاء استدلالي: تشابه رموز السياق في الذاكرة — أعلى التقارير أولاً."""
    q = _tokens(context)
    scored = []
    for ln in _load_lines():
        parts = ln.split("|", FIELDS - 1)
        if len(parts) < FIELDS:
            continue
        ctxt = parts[1] if len(parts) > 1 else ""
        tt = _tokens(ctxt)
        score = len(q & tt)
        if score:
            scored.append({"similarity": score, "line": ln, "parts": parts})
    scored.sort(key=lambda r: (-r["similarity"], r["line"]))
    return scored[:top]


def summarize():
    """ملخص الذاكرة: أعداد + نسبة النجاح — للوكيل والإنسان."""
    lines = _load_lines()
    ok = sum(1 for ln in lines if ln.split("|", FIELDS - 1)[3] == "1") if lines else 0
    return {
        "count": len(lines),
        "ok": ok,
        "ok_ratio": round(ok / len(lines), 3) if lines else 0.0,
        "mem_file": SKILL_MEM,
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("summarize", "state"):
        print(summarize())
    elif args[0] == "remember" and len(args) >= 3:
        ok = not (len(args) > 3 and args[3].lower() == "fail")
        print(remember(" ".join(args[1:-1]), args[-1], ok=ok))
    elif args[0] == "recall" and len(args) >= 2:
        for r in recall(" ".join(args[1:])):
            print(f"  [{r['similarity']}] {r['parts'][1][:60]} | {r['parts'][2][:60]}")
    else:
        print("الاستعمال: remember <سياق> <فعل> | recall <سياق> | summarize")