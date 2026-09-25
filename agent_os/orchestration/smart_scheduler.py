"""
smart_scheduler.py - الجدول الذكي + الحارس الليلي
===================================================
يعرف الوقت ويوزّع المهام: ثقيل بالليل (جهاز فاضي)، خفيف بالنهار.
بالليل يتحوّل لحارس: يراقب المشاريع، يصلح البسيط، يسجّل الكبير.
"""
import os, sys, datetime
def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

SCHEDULE_FILE = os.path.join(C.AGENT_OS_DIR, "smart_schedule.json")

# أوقات الجدول الافتراضية
NIGHT_START = 23   # 11 مساءً
NIGHT_END = 6      # 6 صباحاً
OWNER_ACTIVE = (8, 22)  # 8 صباحاً - 10 مساءً

def current_period():
    """يحدد الفترة الحالية: night/morning/active/evening."""
    hour = datetime.datetime.now().hour
    if hour >= NIGHT_START or hour < NIGHT_END:
        return "night"
    if NIGHT_END <= hour < 8:
        return "morning"
    if 8 <= hour < 18:
        return "active"
    return "evening"

def should_run_heavy():
    """هل الوقت مناسب لمهمة ثقيلة؟ (بالليل = نعم)."""
    return current_period() in ("night", "morning")

def should_be_quiet():
    """هل يجب أن يكون هادئاً؟ (المالك قد يكون نايم)."""
    return current_period() == "night"

def prioritize_for_now(tasks):
    """يرتّب المهام حسب الوقت الحالي.
    tasks: [{"name", "weight": light/heavy, "value"}]
    """
    period = current_period()
    def sort_key(t):
        weight = t.get("weight", "light")
        value = float(t.get("value", 0.5))
        if period == "night" and weight == "heavy":
            return value + 0.5  # الليل يرفع أولوية الثقيل
        if period in ("active", "evening") and weight == "light":
            return value + 0.3  # النهار يرفع أولوية الخفيف
        return value
    return sorted(tasks, key=sort_key, reverse=True)

# ===== الحارس الليلي =====

GUARD_LOG = os.path.join(C.AGENT_OS_DIR, "night_guard_log.json")

def night_patrol():
    """جولة حراسة ليلية: يفحص صحة النظام والمشاريع."""
    report = {"at": C.now_iso(), "period": current_period(), "checks": []}

    # 1) صحة النظام
    try:
        from agent_os.verification import health_graph
        snap = health_graph.snapshot()
        report["system_health"] = snap["health_pct"]
        if snap["overall"] != "green":
            report["checks"].append({
                "type": "system_degraded",
                "detail": f"صحة {snap['health_pct']}% — {list(health_graph.degraded().keys())}",
                "severity": "high" if snap["overall"] == "red" else "medium",
            })
    except Exception:
        pass

    # 2) طلبات بشرية معلّقة
    try:
        from agent_os.interface import human_requests as hr
        pending = hr.pending_count()
        if pending > 0:
            report["checks"].append({
                "type": "pending_requests", "detail": f"{pending} طلب معلّق",
                "severity": "low",
            })
    except Exception:
        pass

    # 3) فرضيات جاهزة للترقية
    try:
        from agent_os.evolution import hypothesis_lab as hl
        active_hyps = hl.active()
        passed = [h for h in active_hyps if h["status"] == "passed"]
        if passed:
            report["checks"].append({
                "type": "hypothesis_ready", "detail": f"{len(passed)} فرضية ناجحة تنتظر الترقية",
                "severity": "low",
            })
    except Exception:
        pass

    # تسجيل الجولة
    log = C.load_json(GUARD_LOG, {"patrols": []})
    log["patrols"].append(report)
    log["patrols"] = log["patrols"][-100:]
    C.atomic_write(GUARD_LOG, log)
    return report

def night_summary():
    """ملخّص الحراسة الليلية للتقرير الصباحي."""
    log = C.load_json(GUARD_LOG, {"patrols": []})
    if not log["patrols"]:
        return "لم تُجرَ حراسة ليلية بعد."
    last = log["patrols"][-1]
    issues = [c for c in last.get("checks", []) if c["severity"] != "low"]
    if not issues:
        return f"🌙 الحراسة الليلية: كل شيء هادئ (صحة {last.get('system_health', '?')}%)"
    return f"🌙 الحراسة الليلية: {len(issues)} مشكلة تحتاج انتباه"
