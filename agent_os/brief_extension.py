"""
brief_extension.py - ملحق التقرير الصباحي الموحّد — §74
========================================================
يجمع حالة كل الأنظمة الجديدة في قسم واحد للتقرير الصباحي واللوحة:
صحة النظام، فجوات القدرات، تعارضات الذاكرة، حجم المشروع، دروس الانحدار.

لا يستبدل morning_brief.py — يُغذّيه بقسم إضافي جاهز.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C


def _safe(fn, default=None):
    """يستدعي دالة بأمان — غياب نظام لا يكسر التقرير."""
    try:
        return fn()
    except Exception as e:
        C.log(f"⚠️ ملحق التقرير: {e}")
        return default


def collect():
    """يجمع مؤشرات كل الأنظمة الجديدة في dict واحد."""
    data = {}

    # صحة النظام (§58)
    def _health():
        from agent_os.verification import health_graph
        s = health_graph.snapshot()
        return {"overall": s["overall"], "pct": s["health_pct"],
                "degraded": list(health_graph.degraded().keys())}
    data["health"] = _safe(_health, {})

    # فجوات القدرات المفتوحة (§13)
    def _gaps():
        from agent_os.cognition import capability_gap
        return [g["capability"] for g in capability_gap.open_gaps()]
    data["capability_gaps"] = _safe(_gaps, [])

    # تعارضات الذاكرة المعلّقة (§28)
    def _conflicts():
        from agent_os.memory import conflict_resolver
        return len(conflict_resolver.disputed_items())
    data["disputed_memory"] = _safe(_conflicts, 0)

    # حجم المشروع / التوأم الرقمي (§46)
    def _twin():
        from agent_os.verification import digital_twin
        return digital_twin.stats()
    data["project"] = _safe(_twin, {})

    # دروس الانحدار المتراكمة (§60)
    def _regressions():
        from agent_os import golden_loop
        mem = C.load_json(golden_loop.REGRESSION_FILE, {"lessons": []})
        return len(mem["lessons"])
    data["regression_lessons"] = _safe(_regressions, 0)

    # معرفة متقادمة تحتاج مراجعة (§92)
    def _stale():
        from agent_os.memory import provenance
        return len(provenance.stale_keys())
    data["stale_knowledge"] = _safe(_stale, 0)

    # Bug Bounty — برامج وثغرات (§45)
    def _bounty():
        from agent_os import bounty_engine as be
        programs = be.list_programs()
        queue = be.submission_queue()
        return {"programs": len(programs),
                "pending_submissions": len(queue) if isinstance(queue, list) else 0}
    data["bounty"] = _safe(_bounty, {})

    # محفظة إعادة الاستثمار
    def _wallet():
        from agent_os.business import reinvestment_wallet as rw
        return rw.balance()
    data["wallet"] = _safe(_wallet, {})

    # الحارس الليلي
    def _night():
        from agent_os.orchestration import smart_scheduler as ss
        return ss.night_summary()
    data["night_guard"] = _safe(_night, "")

    # منحنى النمو
    def _growth():
        from agent_os.security import proactive_shield as ps
        return ps.compare_with_yesterday()
    data["growth"] = _safe(_growth, {})

    # دورة التطور اليومية
    def _evolution():
        from agent_os.evolution import daily_evolution as de
        return {"streak": de.streak(), "evolved_today": de.already_evolved_today()}
    data["evolution"] = _safe(_evolution, {})

    return data


def render():
    """يبني نص القسم الجاهز للإدراج في التقرير الصباحي."""
    d = collect()
    lines = ["", "═══ حالة النظام الموسّعة ═══"]

    h = d.get("health", {})
    if h:
        icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(h.get("overall"), "⚪")
        lines.append(f"{icon} الصحة الكلية: {h.get('pct')}%")
        if h.get("degraded"):
            lines.append(f"   ⚠ يحتاج انتباه: {'، '.join(h['degraded'])}")

    proj = d.get("project", {})
    if proj:
        lines.append(f"📦 المشروع: {proj.get('files')} ملف، "
                     f"{proj.get('functions')} دالة، {proj.get('tests')} اختبار")

    gaps = d.get("capability_gaps", [])
    lines.append(f"🧩 فجوات قدرات مفتوحة: {len(gaps)}"
                 + (f" ({'، '.join(gaps[:3])})" if gaps else ""))

    lines.append(f"🧠 دروس انحدار محفوظة: {d.get('regression_lessons', 0)}")
    lines.append(f"⚖️ تعارضات ذاكرة معلّقة: {d.get('disputed_memory', 0)}")
    lines.append(f"🕒 معرفة متقادمة للمراجعة: {d.get('stale_knowledge', 0)}")

    # Bug Bounty
    bounty = d.get("bounty", {})
    if bounty:
        lines.append(f"🎯 Bug Bounty: {bounty.get('programs', 0)} برنامج، "
                     f"{bounty.get('pending_submissions', 0)} تقرير معلّق")

    # المحفظة
    wallet = d.get("wallet", {})
    if wallet and wallet.get("balance") is not None:
        lines.append(f"💼 محفظة الوكيل: {wallet.get('balance', 0)} "
                     f"(إجمالي مكتسب: {wallet.get('total_earned', 0)})")

    # الحارس الليلي
    night = d.get("night_guard", "")
    if night:
        lines.append(night)

    # منحنى النمو
    growth = d.get("growth", {})
    if growth.get("available"):
        lines.append(f"{growth.get('trend', '➡️')} أداء اليوم مقابل الأمس")

    # دورة التطور
    evo = d.get("evolution", {})
    if evo:
        lines.append(f"🧬 سلسلة التطور: {evo.get('streak', 0)} يوم متتالي"
                     + (" ✅" if evo.get("evolved_today") else " (لم يتطور اليوم بعد)"))

    return "\n".join(lines)


if __name__ == "__main__":
    print(render())
