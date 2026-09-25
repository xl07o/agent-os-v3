"""
kernel_guard.py - زر الإيقاف الاضطراري (Kill Switch) + إجازة تشغيل الأصول
========================================================================
ركن التنفيذ الحقيقي لا يملك "حق استمرار أعمى": إذا طلب الإنسان إيقافاً،
أو فرغت الميزانية المكتسبة، أو استُهلكت الجولة الليلية — تفتح النواة مفتاح
الأمان قبل أي عمل.

الدرجات (بلا سكّر):
  - armed   : عمليّ، الميزانية ممتلئة أو العمل مجاني
  - warn    : الميزانية شبه-فارغة (يومنا الأخير المدفوع) — نعمل لكن بحذر
  - blocked : توقف كامل حتى يرد الإنسان (إيقاف عن عمليات مدفوعة أو جوهرية)
  - restore : أمر استعادة نواة من الإنسان مسجّل وينتظر التنفيذ عند إذن

CLI:
  python agent_os/kernel_guard.py state
  python agent_os/kernel_guard.py block <سبب>
  python agent_os/kernel_guard.py arm <سبب>
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

GUARD_FILE = os.path.join(C.AGENT_OS_DIR, "kernel_guard.json")


def _loaded():
    return C.load_json(GUARD_FILE, {"mode": "armed", "blocked_reason": "",
                                    "blocked_at": None, "last_state": None})


def _save(state):
    C.atomic_write(GUARD_FILE, state)


def current_state():
    """احسب حالة الأمان الفعلية الآن — لا نقرأ إعداداً قديماً فحسب."""
    st = _loaded()
    mode = st.get("mode", "armed")
    # قاعدة 1: إيقاف صريح من الإنسان يتغلب دائماً
    if mode == "blocked":
        return {"mode": "blocked", "reason": st.get("blocked_reason") or "طلب الإنسان",
                "since": st.get("blocked_at"), "needs_human": True}
    # قاعدة 2: ميزانية مكتسبة فارغة + عمل مدفوع قادم → افحص إن استطاعت الإنفاق
    try:
        from agent_os import revenue_engine
        rid = revenue_engine.daily_report()
        budget = rid.get("budget_remaining_today", 0)
        if budget <= 0 and rid.get("paid_pending_tasks", 0) > 0:
            return {"mode": "warn", "reason": "ميزانية اليوم نافذت والعمل مدفوع",
                    "budget": budget, "needs_human": False}
        if mode == "warn" and budget > 0:
            mode = "armed"  # الميزانية امتلأت من جديد (إيراد حقيقي)
    except Exception:
        pass
    # قاعدة 3: جولة ليلية منتهية بلا أمر جديد
    try:
        from agent_os import mission_scheduler
        sch = mission_scheduler.load()
        now_day = C.now_iso()[:10]
        if sch.get("schedule") and sch["last_run"] and sch["last_run"][:10] == now_day:
            return {"mode": "sleep", "reason": "أُنجز جدول اليوم — ننتظر موعد الليل",
                    "needs_human": False}
    except Exception:
        pass
    st["last_state"] = mode
    _save(st)
    return {"mode": mode, "reason": "كل شيء مستقر", "needs_human": False}


def block(reason="طلب بشريّ"):
    st = _loaded()
    st["mode"] = "blocked"
    st["blocked_reason"] = str(reason)[:200]
    st["blocked_at"] = C.now_iso()
    _save(st)
    C.log(f"🛑 إيقاف اضطراري مختوم: {reason[:80]}")
    return {"ok": True, "mode": "blocked", "reason": reason[:200]}


def arm(reason="تم فكُّ الإيقاف"):
    st = _loaded()
    old = st.get("mode")
    st["mode"] = "armed"
    st["blocked_reason"] = ""
    st["blocked_at"] = None
    _save(st)
    C.log(f"🔓 عادت تشغيل الملفات: {reason[:80]} (كانت: {old})")
    return {"ok": True, "mode": "armed", "previous": old}


def needs_human():
    st = current_state()
    return {"needs_human": st.get("needs_human", False),
            "mode": st.get("mode"), "reason": st.get("reason","")[:120]}


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("state", "status"):
        st = current_state()
        print(f"الحالة: {st['mode']} | سبب: {st.get('reason','')[:50]}")
        print(f"يحتاج إنساناً؟ {'نعم' if st.get('needs_human') else 'لا'}")
    elif args[0] == "block":
        print(block(" ".join(args[1:]) if len(args) > 1 else "طلب بشريّ"))
    elif args[0] == "arm":
        print(arm(" ".join(args[1:]) if len(args) > 1 else "عودة تشغيل"))