"""
dashboard.py - لوحة العرض الذكية (v2.0)
========================================
صفحة HTML واحدة تعرض كل شيء مع:
  - إحصائيات حية
  - تصفح الملفات
  - رسم بياني بسيط
"""

import datetime
import html
import json
import os
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")
SEARCH_DIR = os.path.join(BASE_DIR, "output", "searches")
SKILLS_DIR = os.path.join(BASE_DIR, "skills")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

DASHBOARD_HTML = os.path.join(BASE_DIR, "output", "dashboard.html")


def _list_files(d, ext=None, newest_first=True):
    if not os.path.isdir(d):
        return []
    files = []
    for root, _, names in os.walk(d):
        for n in names:
            if n.startswith("_"):
                continue
            full = os.path.join(root, n)
            if ext and not n.endswith(ext):
                continue
            try:
                mtime = os.path.getmtime(full)
                size = os.path.getsize(full)
            except OSError:
                mtime = 0
                size = 0
            files.append((mtime, full, size))
    files.sort(key=lambda x: x[0], reverse=newest_first)
    return [(f, s) for _, f, s in files]


def _format_size(size):
    for unit in ['B', 'KB', 'MB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def card_links(files, base, max_items=30):
    """توليد روابط نسبية بدل file:/// — لا تكشف المسار الكامل على القرص."""
    out = []
    html_dir = os.path.dirname(DASHBOARD_HTML)
    for f, size in files[:max_items]:
        rel = os.path.relpath(f, base)
        try:
            href = os.path.relpath(f, html_dir).replace("\\", "/")
        except ValueError:  # أقراص مختلفة — نعرض الاسم فقط دون رابط
            href = "#"
        name = os.path.basename(f)
        size_str = _format_size(size) if size else ""
        out.append(f'<a href="{href}" rel="noopener noreferrer" title="{html.escape(rel)}">'
                   f'{html.escape(name)} <span class="size">{size_str}</span></a>')
    return "\n".join(out) if out else "<i>لا يوجد</i>"


def build_html():
    reports = _list_files(REPORTS_DIR, ".md")
    projects = _list_files(PROJECTS_DIR)
    searches = _list_files(SEARCH_DIR, ".json")
    skills = []
    if os.path.isdir(SKILLS_DIR):
        for name in os.listdir(SKILLS_DIR):
            if name.startswith("_"):
                continue
            skill_file = os.path.join(SKILLS_DIR, name, "SKILL.md")
            if os.path.exists(skill_file):
                try:
                    size = os.path.getsize(skill_file)
                except OSError:
                    size = 0
                skills.append((skill_file, size))
    logs = _list_files(LOGS_DIR, ".log")

    html_doc = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>لوحة موظف الليل</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:system-ui,-apple-system,sans-serif; background:#0a0e1a; color:#e2e8f0; padding:2rem; line-height:1.7; }}
  h1 {{ color:#60a5fa; margin-bottom:0.5rem; font-size:1.8rem; }}
  .subtitle {{ color:#64748b; margin-bottom:2rem; font-size:0.9rem; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:1rem; }}
  .card {{ background:#111827; border-radius:14px; padding:1.4rem; border:1px solid #1e293b; transition:border-color 0.2s; }}
  .card:hover {{ border-color:#334155; }}
  .card h2 {{ color:#93c5fd; font-size:1rem; margin-bottom:1rem; border-bottom:1px solid #1e293b; padding-bottom:.5rem; }}
  .card a {{ display:block; color:#7dd3fc; text-decoration:none; padding:.3rem 0; font-size:.85rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .card a:hover {{ color:#fff; }}
  .card .size {{ color:#475569; font-size:.75rem; margin-right:.5rem; }}
  .stats {{ display:flex; gap:1rem; margin-bottom:2rem; flex-wrap:wrap; }}
  .stat {{ background:#111827; border:1px solid #1e293b; border-radius:12px; padding:1rem 1.5rem; min-width:120px; }}
  .stat b {{ color:#60a5fa; font-size:2rem; display:block; }}
  .stat span {{ font-size:.8rem; color:#64748b; }}
  .status {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-left:.5rem; }}
  .status.ok {{ background:#22c55e; }}
  .status.warn {{ background:#eab308; }}
  .status.err {{ background:#ef4444; }}
  footer {{ margin-top:2.5rem; color:#475569; font-size:.75rem; text-align:center; }}
  .note {{ background:#1e293b; border-radius:10px; padding:1rem; margin-top:1rem; font-size:.85rem; color:#94a3b8; }}
</style>
</head>
<body>
  <h1>🌙 لوحة موظف الليل</h1>
  <p class="subtitle">آخر تحديث: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}</p>

  <div class="stats">
    <div class="stat"><b>{len(reports)}</b><span>تقرير</span></div>
    <div class="stat"><b>{len(projects)}</b><span>ملف مشروع</span></div>
    <div class="stat"><b>{len(searches)}</b><span>بحث</span></div>
    <div class="stat"><b>{len(skills)}</b><span>مهارة</span></div>
    <div class="stat"><b>{len(logs)}</b><span>سجل</span></div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>📊 التقارير ({len(reports)})</h2>
      {card_links(reports, BASE_DIR)}
    </div>
    <div class="card">
      <h2>📁 المشاريع ({len(projects)})</h2>
      {card_links(projects, BASE_DIR)}
    </div>
    <div class="card">
      <h2>🔍 الأبحاث ({len(searches)})</h2>
      {card_links(searches, BASE_DIR)}
    </div>
    <div class="card">
      <h2>🧠 المهارات ({len(skills)})</h2>
      {card_links(skills, BASE_DIR)}
    </div>
    <div class="card">
      <h2>📝 السجلات ({len(logs)})</h2>
      {card_links(logs, BASE_DIR)}
    </div>
    <div class="card">
      <h2>ℹ️ معلومات</h2>
      <div class="note">
        <p>افتح ملف تقرير لترى تفاصيل المهمة.</p>
        <p>المهارات تُحفظ في مجلد skills/.</p>
        <p>الأبحاث تُحفظ في output/searches/.</p>
      </div>
    </div>
  </div>

  <footer>موظف الليل v2.0 — نظام متعدد العقول</footer>
</body>
</html>"""
    os.makedirs(os.path.dirname(DASHBOARD_HTML), exist_ok=True)
    with open(DASHBOARD_HTML, "w", encoding="utf-8") as f:
        f.write(html_doc)
    return DASHBOARD_HTML


def open_dashboard(auto=False):
    path = build_html()
    if auto or os.getenv("SELFRUNNER_SHOW_DASHBOARD", "0") == "1":
        try:
            webbrowser.open("file:///" + path.replace("\\", "/"))
        except Exception:
            pass
    return path


if __name__ == "__main__":
    p = open_dashboard()
    print("لوحة العرض: " + p)
