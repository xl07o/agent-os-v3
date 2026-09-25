"""
incident_commander.py - قائد الحوادث (Incident Commander) — ركن أمان/تعافٍ
===========================================================================
عند خللٍ حرج (فشل فحص المشرف، استهلاك ميزانية، لقطة منهارة) يفتح "ملف حادثة"
مع مالك ومسار تعافٍ واضح، ثم يُغلق التقرير بتعليم مُستخلَص — لا صفرات مغطّاة.

القواعد:
  - الحادثة تُفتح بأدلة حقيقية (المسار/الخطأ) لا بظن.
  - الإغلاق يتطلب ملخصاً + نتيجة؛ لا نغلق بالصمت.
  - كل حادثة تُستخلص منها "درس" يُحقن في ذاكرة المهارات (تعلّم من الأخطاء).

الاستخدام:
  python agent_os/incident_commander.py open chat_loop_error "نواة انحشرت في حلقة"
  python agent_os/incident_commander.py list
  python agent_os/incident_commander.py close <id> <ملخص> [قرار]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

INCIDENTS_FILE = os.path.join(C.AGENT_OS_DIR, "incidents.json")
MAX_ID = 1


def _loaded():
    return C.load_json(INCIDENTS_FILE, {"incidents": [], "next_id": 1})


def _save(state):
    C.atomic_write(INCIDENTS_FILE, state)


def open_incident(kind, description, severity="medium"):
    """افتح حادثة بأدلة (وصف موجز، أدلة مكتسبة إن وُجدت)."""
    state = _loaded()
    iid = state["next_id"]
    state["next_id"] += 1
    inc = {"id": iid, "kind": kind[:50], "severity": severity,
           "status": "open", "when": C.now_iso(),
           "description": description[:400],
           "resolution": "", "lesson": "", "closed_at": None}
    state["incidents"].insert(0, inc)
    state["incidents"] = state["incidents"][-60:]
    _save(state)
    C.log(f"🚨 حادثة #{iid} مفتوحة: {kind[:50]} ({severity})")
    return inc


def close_incident(iid, resolution, decision="تعلّم"):
    """إغلاق بأثر: ملخص + درس يُحقن في ذاكرة المهارات."""
    state = _loaded()
    inc = next((x for x in state["incidents"] if x["id"] == iid), None)
    if not inc:
        return {"ok": False, "reason": "حادثة غير موجودة"}
    inc["status"] = "closed"
    inc["resolution"] = resolution[:400]
    inc["closed_at"] = C.now_iso()
    try:
        from agent_os import skill_memory
        lesson = f"حادثة #{iid} [{inc['kind'][:30]}]: {resolution[:200]}"
        skill_memory.remember("الدرس من حادثة " + inc["kind"][:30],
                              action="incident:close",
                              ok=(decision.lower() != "فشل"))
        inc["lesson"] = lesson[:250]
    except Exception as e:
        inc["lesson"] = f"تعذّر التعلم: {str(e)[:80]}"
    _save(state)
    C.log(f"✅ حادثة #{iid} أُغلقت: {resolution[:80]}")
    return {"ok": True, "id": iid, "lesson_saved": bool(inc["lesson"])}


def list_open():
    return [i for i in _loaded()["incidents"] if i["status"] == "open"]


def count_open():
    return len(list_open())


def report():
    state = _loaded()
    return {"open": count_open(),
            "total": len(state["incidents"]),
            "learned": sum(1 for i in state["incidents"]
                           if i.get("lesson") and i["status"] == "closed")}


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(report())
    elif args[0] == "open" and len(args) >= 2:
        print(open_incident(args[1], " ".join(args[2:]) or "بلا وصف"))
    elif args[0] == "close" and len(args) >= 2:
        print(close_incident(int(args[1]), " ".join(args[2:]) or "أُغلق بعد مراجعة"))
    else:
        print(report())