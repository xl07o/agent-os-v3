"""
builders.py - منشئات مشاريع عامة
==================================
محرك توليد مخرجات تقنية قابل للتوسع لأي مجال.
أضف أي منشئ جديد هنا وستصبح مهارة يستخدمها الوكيل.

النمط: كل دالة ترجع dict من المسارات -> الملفات.
"""

import html
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")


def make_web_project(name, lang="ar", template="landing"):
    """يبني مشروع موقع ويب كامل (HTML/CSS/JS)."""
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_") or "WebApp"
    proj = os.path.join(PROJECTS_DIR, safe)
    os.makedirs(proj, exist_ok=True)

    dir_attr = "rtl" if lang == "ar" else "ltr"
    name_html = html.escape(name, quote=True)  # يمنع حقن HTML/JS في اسم الموقع
    html_doc = f"""<!DOCTYPE html>
<html lang="{html.escape(lang, quote=True)}" dir="{dir_attr}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name_html}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>{name_html}</h1>
    <nav>
      <a href="#home">الرئيسية</a>
      <a href="#about">من نحن</a>
      <a href="#contact">تواصل</a>
    </nav>
  </header>
  <main>
    <section id="home">
      <h2>مرحباً</h2>
      <p>هذا موقع مبني بواسطة موظف الليل.</p>
    </section>
    <section id="about">
      <h2>من نحن</h2>
      <p>وصف مشروعك هنا.</p>
    </section>
    <section id="contact">
      <h2>تواصل</h2>
      <form>
        <input type="email" placeholder="بريدك">
        <button>إرسال</button>
      </form>
    </section>
  </main>
  <script src="script.js"></script>
</body>
</html>"""

    css = """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: system-ui, sans-serif; line-height:1.7; color:#1f2937; }
header { background:#111827; color:#fff; padding:1rem 2rem; display:flex; justify-content:space-between; align-items:center; }
nav a { color:#9ca3af; margin-left:1rem; text-decoration:none; }
nav a:hover { color:#fff; }
main { max-width:900px; margin:0 auto; padding:2rem; }
section { margin-bottom:3rem; }
h2 { color:#2563eb; margin-bottom:.5rem; }
input, button { padding:.6rem 1rem; font-size:1rem; }
button { background:#2563eb; color:#fff; border:0; border-radius:6px; cursor:pointer; }
"""

    js = """document.querySelector('form').addEventListener('submit', (e) => {
  e.preventDefault();
  alert('تم إرسال! (ستربط هذا بنظام فعل لاحقاً)');
});
"""

    paths = {}
    with open(os.path.join(proj, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_doc)
    with open(os.path.join(proj, "style.css"), "w", encoding="utf-8") as f:
        f.write(css)
    with open(os.path.join(proj, "script.js"), "w", encoding="utf-8") as f:
        f.write(js)
    paths["site"] = proj
    return paths


def make_python_project(name, desc="وصف المشروع"):
    """يبني مشروع Python أساسي ببنية نظيفة."""
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_") or "python_app"
    proj = os.path.join(PROJECTS_DIR, safe)
    os.makedirs(proj, exist_ok=True)

    # تعقيم الاسم والوصف ضد فواصل الأسطر وعلامات الاقتباس (يمنع حقن تعليمات/كود)
    name_safe_txt = name.replace("\r", " ").replace("\n", " ").replace('"', "'").strip()
    desc_safe = desc.replace("\r", " ").replace("\n", " ").replace('"', "'").strip()
    main = f'''"""\n{name_safe_txt}\n========\n{desc_safe}\n"""\n\n\ndef main():\n    print("أهلاً من {name_safe_txt}!")\n\n\nif __name__ == "__main__":\n    main()\n'''
    paths = {}
    with open(os.path.join(proj, "main.py"), "w", encoding="utf-8") as f:
        f.write(main)
    with open(os.path.join(proj, "README.md"), "w", encoding="utf-8") as f:
        f.write(f"# {html.escape(name_safe_txt)}\n\n{desc_safe}\n")
    paths["project"] = proj
    return paths


def make_roblox_place(name, theme="أساسي"):
    """يبني خريطة Roblox: سكربت Lua جاهز للصق في Roblox Studio."""
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_") or "MyPlace"
    proj = os.path.join(PROJECTS_DIR, safe)
    os.makedirs(proj, exist_ok=True)

    theme_tiles = {
        "صحراء": ("BrickColor.new('Bright red')", "Grass"),
        "غابة": ("BrickColor.new('Bright green')", "Grass"),
        "جبل": ("BrickColor.new('Stone')", "Rock"),
        "مستقبلي": ("BrickColor.new('Institutional white')", "Concrete"),
    }
    color, material = theme_tiles.get(theme, ("BrickColor.new('White')", "Plastic"))

    # تعقيم الاسم لبيئة Lua: إزالة الاقتتباسات والشرطة المائلة وفواصل الأسطر —
    # يمنع كسر السلسلة النصية وحقن كود (تقليد os.execute) داخل السكربت
    name_lua = (
        name.replace("'", "")
        .replace('"', "")
        .replace("\\", "/")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    ) or "MyPlace"

    server = f"""-- {name_lua} - سكربت الخادم
local SpawnLocation = Instance.new("SpawnLocation")
SpawnLocation.Name = "Spawn"
SpawnLocation.Size = Vector3.new(8, 1, 8)
SpawnLocation.TopSurface = Enum.SurfaceType.Smooth
SpawnLocation.BottomSurface = Enum.SurfaceType.Smooth
SpawnLocation.Material = Enum.Material.{material}
SpawnLocation.Anchored = true
SpawnLocation.Parent = workspace

local floor = Instance.new("Part")
floor.Name = "Floor"
floor.Size = Vector3.new(200, 1, 200)
floor.Position = Vector3.new(0, -1, 0)
floor.BrickColor = {color}
floor.Material = Enum.Material.{material}
floor.Anchored = true
floor.Parent = workspace

local light = Instance.new("PointLight")
light.Range = 30
light.Brightness = 3
light.Parent = SpawnLocation

print("الخريطة '{name_lua}' جاهزة!")
"""

    with open(os.path.join(proj, "ServerScript.lua"), "w", encoding="utf-8") as f:
        f.write(server)
    with open(os.path.join(proj, "README.txt"), "w", encoding="utf-8") as f:
        f.write(
            f"خريطة Roblox: {name}\nوضع: {theme}\n\n"
            "انسخ محتوى ServerScript.lua داخل ServerScriptService في Roblox Studio ثم شغّل.\n"
        )
    return {"server_script": os.path.join(proj, "ServerScript.lua")}


def make_dashboard_project(name, sections, lang="ar"):
    """يبني شاشة/لوحة مخصّصة (HTML) من قائمة أقسام — أي طلب نوعه
    «سوِّ لي شاشة فيها X ويمين Y ويسار Z» يترجم لعنصر بـ sections.

    sections: قائمة dict لكل قسم: {"title": عنوان, "items": [أسطر نصية]}
    يرجع {"dashboard": مسار index.html}.
    """
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_") or "Dashboard"
    proj = os.path.join(PROJECTS_DIR, safe)
    os.makedirs(proj, exist_ok=True)

    dir_attr = "rtl" if lang == "ar" else "ltr"
    name_html = html.escape(name, quote=True)

    cards = []
    for sec in sections:
        title = html.escape(str(sec.get("title", "قسم")), quote=True)
        items = sec.get("items") or ["بيانات تجريبية — اربطها بمصدرك الحقيقي لاحقاً"]
        rows = "\n".join(
            f'        <div class="row"><span>{html.escape(str(it), quote=True)}</span></div>'
            for it in items
        )
        cards.append(f"""      <section class="card">
        <h2>{title}</h2>
{rows}
      </section>""")
    cards_html = "\n".join(cards)

    html_doc = f"""<!DOCTYPE html>
<html lang="{html.escape(lang, quote=True)}" dir="{dir_attr}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name_html}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>{name_html}</h1>
    <span class="clock" id="clock"></span>
  </header>
  <main class="grid">
{cards_html}
  </main>
  <script src="script.js"></script>
</body>
</html>"""

    css = """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: system-ui, sans-serif; background:#0b0f17; color:#e5e7eb; }
header { background:#11161f; padding:1rem 2rem; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1f2937; }
header h1 { font-size:1.25rem; }
.clock { color:#9ca3af; font-variant-numeric: tabular-nums; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:1.25rem; padding:1.5rem; max-width:1400px; margin:0 auto; }
.card { background:#141a24; border:1px solid #1f2937; border-radius:12px; padding:1.25rem; }
.card h2 { color:#60a5fa; font-size:1rem; margin-bottom:.9rem; border-bottom:1px solid #1f2937; padding-bottom:.5rem; }
.row { padding:.4rem 0; color:#d1d5db; font-size:.92rem; border-bottom:1px dashed #1f2937; }
.row:last-child { border-bottom:0; }
"""

    js = """function tick(){ document.getElementById('clock').textContent = new Date().toLocaleTimeString(); }
tick(); setInterval(tick, 1000);
"""

    with open(os.path.join(proj, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_doc)
    with open(os.path.join(proj, "style.css"), "w", encoding="utf-8") as f:
        f.write(css)
    with open(os.path.join(proj, "script.js"), "w", encoding="utf-8") as f:
        f.write(js)
    return {"dashboard": os.path.join(proj, "index.html")}


if __name__ == "__main__":
    import sys
    kind = sys.argv[1] if len(sys.argv) > 1 else "web"
    name = sys.argv[2] if len(sys.argv) > 2 else "MyProject"
    if kind == "web":
        print(make_web_project(name))
    elif kind == "py":
        print(make_python_project(name))
    elif kind == "dashboard":
        print(make_dashboard_project(name, [{"title": "تجربة", "items": ["عنصر 1", "عنصر 2"]}]))
    else:
        print(make_roblox_place(name))
