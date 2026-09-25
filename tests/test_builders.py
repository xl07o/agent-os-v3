"""اختبارات builders.py (الحقن في HTML/Python/Lua).

تشغيل: python -m pytest tests/ -v
"""

import os
import sys
import html as html_mod

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_builders_html_escape():
    """منع حقن HTML في أسماء المشاريع المولّدة."""
    import builders
    evil = "<script>alert(1)</script>"
    paths = builders.make_web_project(evil)
    index = os.path.join(paths["site"], "index.html")
    with open(index, "r", encoding="utf-8") as f:
        content = f.read()
    assert "<script>" not in content.split("<body>")[0]
    assert html_mod.escape(evil) in content


def test_builders_python_escape():
    """منع كسر صيغة بايثون عند اسم ضار (لا يُنفَّذ كود في الاسم)."""
    import builders
    evil = 'x"\nimport os; os.system("1")\n'
    paths = builders.make_python_project(evil)
    main = os.path.join(paths["project"], "main.py")
    with open(main, "r", encoding="utf-8") as f:
        for line in f.read().splitlines():
            # لا سطر مستقل يبدأ بـ import أُدرج من الاسم الضار
            assert not (line.strip().startswith("import") and "os.system" in line)


def test_builders_lua_no_injection():
    """اسم خريطة Roblox لا يفلت من السلسلة النصية (لا حقن كود)."""
    import builders
    evil = "x') os.execute(\"rm -rf /\") -- '"
    result = builders.make_roblox_place(evil)
    with open(result["server_script"], "r", encoding="utf-8") as f:
        lua = f.read()
    # تسلسل الإغلاق الخطير (' ) المقطع بعد اقتباس) يجب أن يختفي من الاسم
    assert "x')" not in lua
    assert "') os.execute" not in lua
    # سطر الطباعة يبقى مغلقاً على سطر واحد صالح
    line = [ln for ln in lua.splitlines() if ln.lstrip().startswith("print(")][0]
    assert line.endswith("جاهزة!')") or line.endswith("جاهزة!\")")