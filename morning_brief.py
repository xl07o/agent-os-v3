"""
morning_brief.py - التقرير الصباحي الذكي (v1.0)
================================================
كل صباح:
  ╔══════════════════════════════════╗
  ║       AGENT MORNING REPORT       ║
  ╚══════════════════════════════════╝

  Completed: 37
  Failed: 3
  Recovered: 3

  💰 Value generated: ...
  📈 Best opportunity: ...
  🧠 What I learned: ...
  ⚠️ Problems: ...
  🎯 Today's highest-value actions: ...
  👤 Decisions needed from you: ...
  🔮 What I expect next: ...

التشغيل:
  python morning_brief.py
  python morning_brief.py --save
"""

import datetime
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

BRIEF_DIR = os.path.join(BASE_DIR, "output", "briefs")
os.makedirs(BRIEF_DIR, exist_ok=True)


def _load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def generate_brief() -> str:
    """يولد التقرير الصباحي الكامل."""
    now = datetime.datetime.now()

    # جمع البيانات من كل الأنظمة
    stats = _collect_stats()

    lines = [
        "╔══════════════════════════════════════════╗",
        "║         🌅 AGENT MORNING REPORT          ║",
        f"║  {now:%Y-%m-%d %H:%M}                        ║",
        "╚══════════════════════════════════════════╝",
        "",
        f"✅ **مكتمل:** {stats['completed']}",
        f"❌ **فشل:** {stats['failed']}",
        f"🔄 **تعافى تلقائياً:** {stats['recovered']}",
        "",
    ]

    # القيمة المولدة
    if stats.get("value_generated"):
        lines.append(f"💰 **القيمة المولدة:** ${stats['value_generated']:.2f}")
        lines.append("")

    # أفضل فرصة
    if stats.get("best_opportunity"):
        lines.append(f"📈 **أفضل فرصة:** {stats['best_opportunity']}")
        lines.append("")

    # ما تعلمه
    if stats.get("learned"):
        lines.append("🧠 **ما تعلمته:**")
        for item in stats["learned"][:3]:
            lines.append(f"  - {item}")
        lines.append("")

    # المشاكل
    if stats.get("problems"):
        lines.append("⚠️ **مشاكل:**")
        for p in stats["problems"][:3]:
            lines.append(f"  - {p}")
        lines.append("")

    # أفضل مهام اليوم
    if stats.get("top_tasks"):
        lines.append("🎯 **أفضل مهام اليوم:**")
        for i, t in enumerate(stats["top_tasks"][:3], 1):
            lines.append(f"  {i}. {t}")
        lines.append("")

    # قرارات تحتاجك
    if stats.get("pending_decisions"):
        lines.append(f"👤 **قرارات تحتاج منك ({len(stats['pending_decisions'])}):**")
        for d in stats["pending_decisions"][:3]:
            lines.append(f"  - {d}")
        lines.append("")

    # Dream Mode report
    if stats.get("dream_report"):
        lines.append("🌙 **تقرير الليل:**")
        lines.append(stats["dream_report"][:300])
        lines.append("")

    lines.append("---")
    lines.append(f"*تقرير تلقائي - {now:%Y-%m-%d %H:%M}*")

    return "\n".join(lines)


def _collect_stats() -> dict:
    """يجمع إحصائيات من كل الأنظمة."""
    stats = {
        "completed": 0,
        "failed": 0,
        "recovered": 0,
        "value_generated": 0.0,
        "best_opportunity": None,
        "learned": [],
        "problems": [],
        "top_tasks": [],
        "pending_decisions": [],
        "dream_report": None,
    }

    # من failure_learning
    try:
        from failure_learning import _load
        db = _load(os.path.join(BASE_DIR, "data", "failures", "failure_db.json"), {"failures": []})
        today = datetime.date.today().isoformat()
        today_failures = [f for f in db["failures"] if f.get("recorded_at", "")[:10] == today]
        stats["failed"] = len(today_failures)
        for f in today_failures[:3]:
            stats["problems"].append(f"{f['task']}: {f['error'][:60]}")
    except Exception:
        pass

    # من ROI Brain
    try:
        from roi_brain import get_ranked_tasks, _roi
        report = _roi.report()
        stats["completed"] = report.get("done", 0)
        stats["value_generated"] = report.get("total_value_generated", 0)
        top = get_ranked_tasks(3)
        stats["top_tasks"] = [f"{t['name']} (ROI: {t['roi_score']:.1f})" for t in top]
        best = report.get("best_pending")
        if best:
            stats["best_opportunity"] = f"{best['name']} - قيمة متوقعة: ${best['value']}"
    except Exception:
        pass

    # من mastery
    try:
        import mastery
        st = mastery._load_state()
        today_demos = [
            d for track in st.get("tracks", {}).values()
            for d in track.get("demos", [])
            if d.get("date", "")[:10] == datetime.date.today().isoformat()
        ]
        for d in today_demos[:3]:
            stats["learned"].append(d.get("topic", "")[:60])
    except Exception:
        pass

    # من Dream Mode
    try:
        from dream_mode import get_last_report
        report_text = get_last_report()
        if "OVERNIGHT" in report_text:
            stats["dream_report"] = report_text[:400]
    except Exception:
        pass

    # من approval_center
    try:
        from agent_os import approval_center
        pending = approval_center.list_pending() if hasattr(approval_center, "list_pending") else []
        stats["pending_decisions"] = [p.get("task", "")[:60] for p in pending[:3]]
    except Exception:
        pass

    return stats


def save_brief(brief: str) -> str:
    """يحفظ التقرير في ملف."""
    now = datetime.datetime.now()
    filename = f"brief_{now:%Y%m%d_%H%M}.md"
    path = os.path.join(BRIEF_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(brief)
    return path


if __name__ == "__main__":
    brief = generate_brief()
    print(brief)
    if "--save" in sys.argv:
        path = save_brief(brief)
        print(f"\n💾 محفوظ في: {path}")
