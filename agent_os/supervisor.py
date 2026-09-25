"""
supervisor.py - المشرف الذي يراقب صحّة الموظف (ركن استقلالية/أمان)
===================================================================
يراقب مؤشرات لا تُعرف مؤشرات تقليدياً:

  - استنفاد الميزانية المكتسبة (لا حرق للمدفوع)
  - تكرار نفس المهمة في اليوم (حماية الحلقات اللانهائية)
  - تصاعد الفشل المعرفي الزمني (الملف المعرفي أسرع نمواً من النجاح)
  - صحة الأهداف: لا أهداف بلا خطوات، لا مهام تنتظر موافقة للأبد
  - نبض طازج

يعيد {ok: bool, action: continue|slow|stop|cooldown, reasons: [...]}.
النواة تتعامل معه: continue فقط متابعة؛ slow يُقلّص الخطوات؛ cooldown يوقف
التحسين الذاتي ليلة واحدة؛ stop يوقف الحلقة بلا ذعر (أمان بلا شلل).

الاستخدام:
  python agent_os/supervisor.py check
  python agent_os/supervisor.py alarms
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

ALARM_FILE = os.path.join(C.AGENT_OS_DIR, "supervisor_alarms.json")
MAX_SAME_TASK_DAY = 4
COOLDOWN_AFTER_FAILURES = 6


def _raise(level, kind, msg):
    state = C.load_json(ALARM_FILE, {"alarms": []})
    state["alarms"].append({"level": level, "kind": kind, "msg": str(msg)[:200],
                            "at": C.now_iso()})
    state["alarms"] = state["alarms"][-100:]
    C.atomic_write(ALARM_FILE, state)
    try:
        from agent_os import notifier
        notifier.notify(level, "مشرف: " + kind, msg)
    except Exception:
        pass


def _same_task_repeat():
    """عدّد مرات تكرار مهام nucleus اليوم من ذكرى المهارات (skills.mem) — بلا سكر إضافي."""
    try:
        import re
        from agent_os import skill_memory
        today = datetime.date.today().isoformat()
        seen = {}
        with open(skill_memory.SKILL_MEM, "r", encoding="utf-8", errors="replace") as f:
            for ln in f:
                parts = ln.rstrip("\n").split("|", 4)
                if len(parts) < 5:
                    continue
                time_part, ctx, act = parts[0], parts[1], parts[2]
                if not time_part.startswith(today):
                    continue
                if act.startswith("nucleus:"):
                    key = ctx[:60]
                    seen[key] = seen.get(key, 0) + 1
        return [(k, n) for k, n in seen.items() if n >= MAX_SAME_TASK_DAY]
    except Exception:
        return [("", 0)]


def _rotation_failures():
    """عدد النقاط الساخنة في الدوران المعرفي (فشل متتابع ≥ العتبة) — إشارة برودتنز لا إيقاف."""
    try:
        from agent_os import self_improve_engine as si
        failures = C.load_json(si.FAILURES_FILE, {})
        threshold = getattr(si, "_ROTATION_THRESHOLD", 3)
        return sum(1 for n in failures.values() if n >= threshold)
    except Exception:
        return 0


def check():
    """فحص واحدة: يعيد حكم المشرف — continue/slow/cooldown/stop."""
    alarms = []
    action = "continue"

    # 1) ميزانية مكتسبة مُنفَّقة
    try:
        from agent_os import finance_intel
        fin = finance_intel.daily_report()
        if fin.get("spent_today_usd", 0) > 0 and fin.get("self_earned_usd", 0) <= 0:
            alarms.append(("warn", "مدفوع نُفِّق بدون رصيد مكتسب اليوم"))
    except Exception:
        pass

    # 2) تكرار مهمة (حلقة لانهائية)
    repeats = _same_task_repeat()
    if repeats:
        alarms.append(("warn", "تكرار مهام: " + ", ".join(f"{k}×{n}" for k, n in repeats)))
        action = "slow"

    # 3) فشل دوران معرفي متصاعد
    fails = _rotation_failures()
    if fails >= COOLDOWN_AFTER_FAILURES:
        alarms.append(("info", "فشل دوران معرفي متتالٍ — برودتنز ليلة واحدة"))
        action = "cooldown" if action == "continue" else action

    # 4) أهداف بلا خطوات
    try:
        from agent_os import goal_manager
        bad = 0
        for g in goal_manager.get_active_goals() or []:
            steps = g.get("steps") or []
            if not steps:
                bad += 1
        if bad:
            alarms.append(("warn", f"{bad} هدفاً نشطاً بلا خطوات"))
    except Exception:
        pass

    # 5) مهام في طابور تنتظر الموافقة منذ أيام
    try:
        from agent_os import approval_center
        old = 0
        for r in approval_center.list_requests("pending"):
            created = r.get("created", "")
            if created and created[:10] < (datetime.date.today() - datetime.timedelta(days=3)).isoformat():
                old += 1
        if old:
            alarms.append(("info", f"{old} طلباً بشرياً معلّقاً منذ 3+ أيام — ذكّر الإنسان"))
    except Exception:
        pass

    emergency = any(a[0] == "critical" for a in alarms)
    for lvl, msg in alarms:
        _raise(lvl, "مؤشر", msg)
    result = {"ok": not emergency, "action": "stop" if emergency else action,
              "reasons": [m for _, m in alarms]}
    C.atomic_write(os.path.join(C.AGENT_OS_DIR, "supervisor_latest.json"), result)
    return result


if __name__ == "__main__":
    import json
    args = sys.argv[1:]
    if args and args[0] == "alarms":
        st = C.load_json(ALARM_FILE, {"alarms": []})
        for a in st["alarms"][-15:]:
            print(f"{a['at'][:19]} [{a['level']}] {a['msg']}")
    else:
        r = check()
        print(json.dumps(r, ensure_ascii=False, indent=1))