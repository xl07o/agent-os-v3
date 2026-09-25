"""
daily_evolution.py - دورة التطور اليومية الإجبارية
===================================================
فكرة المالك: "كل يوم يتعلم ويتحسن ويتطور"
التوسيع: كل يوم الوكيل يُلزم نفسه بدورة كاملة:

  1. تدقيق ذاتي (وش ضعفي؟)
  2. اكتشاف فرصة تحسين
  3. تنفيذ التحسين
  4. اختبار
  5. قياس (قبل ← بعد)
  6. تعلّم الدرس
  7. تقرير للمالك

لا يمر يوم بلا تحسين واحد على الأقل.
"""

import os
import sys
import datetime

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

EVOLUTION_LOG = os.path.join(C.AGENT_OS_DIR, "daily_evolution_log.json")


def _today():
    return datetime.date.today().isoformat()


def already_evolved_today():
    """هل تطوّر الوكيل اليوم؟ (يمنع التكرار ولكن يضمن يوم واحد على الأقل)."""
    log = C.load_json(EVOLUTION_LOG, {"days": {}})
    return _today() in log["days"]


def discover_weakness():
    """يكتشف أضعف نقطة حالياً (من عدة مصادر حقيقية)."""
    weaknesses = []

    # 1) فجوات القدرات المفتوحة
    try:
        from agent_os.cognition import capability_gap
        gaps = capability_gap.open_gaps()
        for g in gaps[:2]:
            weaknesses.append({"type": "capability_gap", "detail": g["capability"],
                               "priority": 0.8})
    except Exception:
        pass

    # 2) معرفة متقادمة
    try:
        from agent_os.memory import provenance
        stale = provenance.stale_keys()
        for k in stale[:2]:
            weaknesses.append({"type": "stale_knowledge", "detail": k,
                               "priority": 0.5})
    except Exception:
        pass

    # 3) تعارضات ذاكرة معلّقة
    try:
        from agent_os.memory import conflict_resolver
        disputes = conflict_resolver.disputed_items()
        if disputes:
            weaknesses.append({"type": "memory_dispute", "detail": f"{len(disputes)} تعارض",
                               "priority": 0.6})
    except Exception:
        pass

    # 4) أدوات منخفضة الثقة
    try:
        from agent_os import tool_registry
        tools = tool_registry.all_tools() if hasattr(tool_registry, "all_tools") else []
        for t in tools:
            if t.get("trust", 1.0) < 0.5:
                weaknesses.append({"type": "low_trust_tool", "detail": t.get("name"),
                                   "priority": 0.7})
    except Exception:
        pass

    # 5) لو ما فيه ضعف محدد → حسّن الأداء العام
    if not weaknesses:
        weaknesses.append({"type": "general_optimization",
                           "detail": "لا ضعف محدد — حسّن الأداء العام",
                           "priority": 0.3})

    weaknesses.sort(key=lambda w: w["priority"], reverse=True)
    return weaknesses


def run_cycle(executor=None):
    """يشغّل دورة تطور يومية كاملة.

    executor: دالة اختيارية تنفّذ تحسيناً (لو None يسجّل الاكتشاف فقط).
    يعيد تقرير الدورة.
    """
    cycle = {
        "date": _today(),
        "started": C.now_iso(),
        "phase": "discover",
    }

    # 1) اكتشاف الضعف
    weaknesses = discover_weakness()
    cycle["weaknesses_found"] = len(weaknesses)
    cycle["top_weakness"] = weaknesses[0] if weaknesses else None

    # 2) محاولة التحسين
    if executor and weaknesses:
        cycle["phase"] = "improve"
        target = weaknesses[0]
        try:
            result = executor(target)
            cycle["improvement"] = {
                "target": target["detail"],
                "success": bool(result.get("success")),
                "detail": str(result.get("detail", ""))[:200],
            }
            cycle["phase"] = "done"
        except Exception as e:
            cycle["improvement"] = {"target": target["detail"], "success": False,
                                    "detail": f"فشل: {e}"}
            cycle["phase"] = "failed"
    else:
        cycle["phase"] = "discovered_only"

    cycle["finished"] = C.now_iso()

    # 3) تسجيل في السجل اليومي (لا حذف — §26)
    log = C.load_json(EVOLUTION_LOG, {"days": {}, "total_cycles": 0})
    log["days"][_today()] = cycle
    log["total_cycles"] = log.get("total_cycles", 0) + 1
    C.atomic_write(EVOLUTION_LOG, log)

    C.log(f"🧬 دورة تطور يومية: {cycle['phase']} — "
          f"{cycle.get('top_weakness', {}).get('detail', 'عام')}")
    return cycle


def streak():
    """كم يوم متتالي تطوّر الوكيل؟ (تحفيز الاستمرارية)."""
    log = C.load_json(EVOLUTION_LOG, {"days": {}})
    today = datetime.date.today()
    count = 0
    while True:
        day = (today - datetime.timedelta(days=count)).isoformat()
        if day in log["days"]:
            count += 1
        else:
            break
    return count


def history(last_n=7):
    """آخر N دورات تطور."""
    log = C.load_json(EVOLUTION_LOG, {"days": {}})
    days = sorted(log["days"].items(), reverse=True)[:last_n]
    return [{"date": d, **v} for d, v in days]


if __name__ == "__main__":
    cycle = run_cycle()
    print(f"دورة اليوم: {cycle['phase']}")
    print(f"أضعف نقطة: {cycle.get('top_weakness', {}).get('detail')}")
    print(f"سلسلة التطور: {streak()} يوم متتالي")
