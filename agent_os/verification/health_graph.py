"""
health_graph.py - رسم الصحة الموحّد (Health Graph) — §58
========================================================
يجمع حالة كل الأنظمة الفرعية في رؤية واحدة: أخضر/أصفر/أحمر لكل مكوّن،
مع صحة كلية. يفحص فعلياً توفّر الوحدات وقابلية استيرادها + إشارات المشرف.
"""

import os
import sys
import importlib

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

# الأنظمة الفرعية التي نراقب صحتها (اسم عرض → موديول)
SUBSYSTEMS = {
    "العقل": "brain",
    "الأهداف": "agent_os.goal_manager",
    "التحقق": "agent_os.verification.reality",
    "الذاكرة": "agent_os.skill_memory",
    "الأدوات": "agent_os.tool_registry",
    "الأحداث": "agent_os.event_bus",
    "المشرف": "agent_os.supervisor",
    "التحسين": "agent_os.self_improve_engine",
    "الأمان": "agent_os.security.prompt_injection",
    "الحلقة_الذهبية": "agent_os.golden_loop",
    "الإجماع": "agent_os.models.consensus",
    "القرار": "agent_os.cognition.counterfactual",
}

GREEN, YELLOW, RED = "green", "yellow", "red"


def _probe(module_path):
    """يفحص وحدة: أخضر لو استوردت، أحمر لو فشلت، أصفر لو مفقودة."""
    try:
        importlib.import_module(module_path)
        return GREEN, "متاح ويُحمّل"
    except ModuleNotFoundError:
        return YELLOW, "غير مثبّت/مفقود"
    except Exception as e:
        return RED, f"خطأ تحميل: {str(e)[:60]}"


def snapshot():
    """يبني لقطة صحة كاملة لكل الأنظمة الفرعية + الحالة الكلية."""
    components = {}
    counts = {GREEN: 0, YELLOW: 0, RED: 0}
    for name, mod in SUBSYSTEMS.items():
        status, detail = _probe(mod)
        components[name] = {"status": status, "detail": detail, "module": mod}
        counts[status] += 1

    # إشارات المشرف (لو متاح) تخفّض الصحة الكلية
    supervisor_action = None
    try:
        from agent_os import supervisor
        verdict = supervisor.check()
        supervisor_action = verdict.get("action")
    except Exception:
        pass

    total = sum(counts.values())
    health_pct = round((counts[GREEN] + counts[YELLOW] * 0.5) / max(total, 1) * 100, 1)

    if counts[RED] > 0 or supervisor_action == "stop":
        overall = RED
    elif counts[YELLOW] > 0 or supervisor_action in ("slow", "cooldown"):
        overall = YELLOW
    else:
        overall = GREEN

    return {
        "overall": overall,
        "health_pct": health_pct,
        "counts": counts,
        "supervisor": supervisor_action,
        "components": components,
        "at": C.now_iso(),
    }


def degraded():
    """يعيد المكوّنات غير الخضراء فقط — لتقرير سريع بما يحتاج انتباهاً."""
    snap = snapshot()
    return {name: c for name, c in snap["components"].items()
            if c["status"] != GREEN}


def summary_line():
    """سطر ملخّص للتقرير الصباحي/اللوحة."""
    s = snapshot()
    icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[s["overall"]]
    return f"{icon} صحة النظام {s['health_pct']}% " \
           f"(🟢{s['counts']['green']} 🟡{s['counts']['yellow']} 🔴{s['counts']['red']})"


if __name__ == "__main__":
    print(summary_line())
    for name, c in degraded().items():
        print(f"  ⚠ {name}: {c['detail']}")
