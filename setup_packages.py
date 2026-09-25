"""
setup_packages.py - تثبيت الأدوات والمكتبات
==============================================
يثبّت المكتبات والأدوات الأساسية التي يحتاجها "موظف الليل"
للعمل (بحث، بناء، أتمتة). يشغّل تلقائياً من عبر `pip`.

عند إضافة حزم جديدة، أضفها إلى القوائم أدناه ثم أعد التشغيل.

الاستخدام:
  python setup_packages.py
  python setup_packages.py --select python http web
"""

import subprocess
import sys

# مجموعات الحزم: كل مجموعة = قائمة حزم pip
PACKAGE_GROUPS = {
    # أساسيات موظف الليل الأساسية
    "core": [
        "python-dotenv",
        "beautifulsoup4",
        "duckduckgo-search",
    ],
    # HTTPS / APIs / بحث
    "http": [
        "httpx",
        "aiohttp",
        "requests-html",
    ],
    # بناء مشاريع Python
    "build": [
        "click",
        "typer",
        "pydantic",
        "pytest",
    ],
    # معالجة بيانات وملفات
    "data": [
        "pandas",
        "numpy",
        "openpyxl",
    ],
    # علوم حاسوب وآلة (اختياري، قد تكون ثقيلة)
    "ai": [
        "scikit-learn",
    ],
}

ALL_GROUPS = list(PACKAGE_GROUPS.keys())


def install(packages):
    if not packages:
        return
    print(f"\nتثبيت: {', '.join(packages)}")
    res = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", *packages],
    )
    if res.returncode == 0:
        return True
    # فشل التثبيت العام (غالباً صلاحيات) — نحاول للمستخدم فقط بدل ما نقف
    print("المحاولة العامة لم تنجح — نحاول التثبيت للمستخدم (--user)...")
    res2 = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--user", *packages],
    )
    return res2.returncode == 0


def main():
    args = sys.argv[1:]
    groups = ALL_GROUPS
    if "--select" in args:
        i = args.index("--select")
        selected = [a for a in args[i + 1 :] if not a.startswith("--")]
        groups = [g for g in selected if g in PACKAGE_GROUPS]
        if not groups:
            print("لم يتم التعرف على المجموعات. اختر من: " + ", ".join(ALL_GROUPS))
            return

    print("تثبيت مكتبات موظف الليل...")
    ok, fail = 0, 0
    for g in groups:
        if install(PACKAGE_GROUPS[g]):
            ok += 1
        else:
            fail += 1
    print(f"\nانتهى: {ok} مجموعة اكتملت, {fail} مجموعات بها أخطاء.")
    print("تحقق: python -c \"import bs4\"")


if __name__ == "__main__":
    main()
