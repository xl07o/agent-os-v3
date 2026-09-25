"""
daily_summary.py - ملخص الصباح الذكي (v2.0)
===========================================
تقرير تنفيذي يومي مع:
  - إحصائيات ذكية
  - رؤى عن الأداء
  - اقتراحات مبنية على البيانات
"""

import datetime
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")
SEARCH_DIR = os.path.join(BASE_DIR, "output", "searches")
SKILLS_DIR = os.path.join(BASE_DIR, "skills")
MEMORY_DIR = os.path.join(BASE_DIR, "memory")

SUMMARY_FILE = os.path.join(BASE_DIR, "output", "daily_summary.md")


def _recent(base, ext, hours):
    """الملفات الأحدث من مدة معينة."""
    cutoff = datetime.datetime.now().timestamp() - hours * 3600
    out = []
    if not os.path.isdir(base):
        return out
    for root, _, names in os.walk(base):
        for n in names:
            if n.startswith("_"):
                continue
            if ext and not n.endswith(ext):
                continue
            full = os.path.join(root, n)
            try:
                if os.path.getmtime(full) >= cutoff:
                    out.append(full)
            except OSError:
                continue
    out.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    return out


def _count_files(base, ext):
    if not os.path.isdir(base):
        return 0
    n = 0
    for root, _, names in os.walk(base):
        for f in names:
            if ext and f.endswith(ext):
                n += 1
    return n


def build_summary(hours=24):
    now = datetime.datetime.now()
    reports = _recent(REPORTS_DIR, ".md", hours)
    projects = _recent(PROJECTS_DIR, None, hours)
    searches = _recent(SEARCH_DIR, None, hours)
    skills = _recent(SKILLS_DIR, "SKILL.md", hours)

    # إحصائيات الذاكرة
    memory_stats = None
    try:
        import memory_bank
        memory_stats = memory_bank.stats()
    except Exception:
        pass

    # قراءة التقارير الأخيرة
    report_titles = []
    for r in reports[:5]:
        try:
            with open(r, "r", encoding="utf-8") as f:
                content = f.read()
            for line in content.splitlines():
                if line.startswith("**المهمة:**"):
                    report_titles.append(line.replace("**المهمة:**", "").strip())
                    break
        except Exception:
            pass

    lines = [
        "# 🌙 ملخص الصباح - موظف الليل",
        f"**الوقت:** {now:%Y-%m-%d %H:%M}",
        f"**الفترة:** آخر {hours} ساعة",
        "",
        "## 📊 المنجز",
        f"- عدد التقارير: **{len(reports)}**",
        f"- ملفات مشاريع: **{len(projects)}**",
        f"- عمليات بحث: **{len(searches)}**",
        f"- مهارات متعلمة: **{len(skills)}**",
    ]

    if memory_stats:
        lines += [
            f"- ذاكرة: **{memory_stats['total_items']}** معلومة",
            f"- متوسط الأهمية: **{memory_stats['avg_importance']}/1.0**",
        ]

    # أحدث المهام المنفذة
    if report_titles:
        lines += ["", "## ✅ أحدث المهام", ""]
        for t in report_titles:
            lines.append(f"- {t}")

    lines += ["", "## 📁 أحدث المشاريع"]
    for p in projects[:5]:
        lines.append(f"- {os.path.relpath(p, PROJECTS_DIR)}")
    if not projects:
        lines.append("- (لا توجد مشاريع جديدة)")

    lines += ["", "## 🧠 مهارات جديدة"]
    for s in skills[:5]:
        rel = os.path.relpath(s, SKILLS_DIR)
        name = rel.split(os.sep)[0]
        lines.append(f"- {name}")
    if not skills:
        lines.append("- (لا توجد مهارات جديدة)")

    # اقتراحات اليوم من نظام الاقتراح الذكي
    import json as _json
    suggest_file = os.path.join(BASE_DIR, "output", "suggestions.json")
    if os.path.exists(suggest_file):
        try:
            with open(suggest_file, "r", encoding="utf-8") as f:
                suggest_data = _json.load(f)
            sessions = suggest_data.get("sessions", [])
            today = datetime.date.today().isoformat()
            today_sessions = [s for s in sessions if s.get("date", "").startswith(today)]
            if today_sessions:
                last = today_sessions[-1]
                lines += ["", "## 💡 اقتراحات اليوم الذكية"]
                for i, s in enumerate(last.get("suggestions", [])[:3], 1):
                    lines.append(f"{i}. **{s.get('idea', '-')}** [{s.get('field', '-')}] - {s.get('profit', '-')}")
                lines.append("> للتفاصيل: `python suggest.py --today`")
        except Exception:
            pass

    lines += ["", "## 💡 الخطوات التالية"]
    lines.append("- راجع أحدث التقارير في مجلد reports/")
    lines.append("- اطلب مهمة جديدة: python selfrunner.py \"المهمة\"")
    lines.append("- افتح لوحة العرض: python selfrunner.py --dashboard")
    lines.append("- اقتراحات ذكية جديدة: python suggest.py")

    tmp = SUMMARY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(tmp, SUMMARY_FILE)

    print(f"\n✅ خلاصة الصباح محفوظة في: {SUMMARY_FILE}")
    return SUMMARY_FILE


if __name__ == "__main__":
    hours = 24
    if "--hours" in sys.argv:
        i = sys.argv.index("--hours")
        try:
            hours = int(sys.argv[i + 1])
        except (ValueError, IndexError):
            pass
    build_summary(hours)