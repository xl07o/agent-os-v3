"""
autoproviders.py - محرك اكتشاف المزودات المجانية (v2.0)
========================================================
اكتشاف وفحص مزودات AI المجانية بشكل آمن وموثوق.
"""

import datetime
import json
import os

import webtools

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "output", "searches")
ENV_FILE = os.path.join(BASE_DIR, ".env")
os.makedirs(OUT_DIR, exist_ok=True)

# قائمة المزودين المعروفين والموثوقين فقط
PROVIDER_INDEX = [
    {
        "id": "gemini",
        "name": "Google Gemini",
        "url": "https://aistudio.google.com",
        "env": "GEMINI_API_KEY",
        "free": True,
        "note": "Gemini Flash مجاني مع free tier واسع",
        "key_page": "https://aistudio.google.com/apikey",
    },
    {
        "id": "groq",
        "name": "Groq",
        "url": "https://console.groq.com",
        "env": "GROQ_API_KEY",
        "free": True,
        "note": "نماذج قوية وسريعة جداً مع free tier",
        "key_page": "https://console.groq.com/keys",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "url": "https://openrouter.ai",
        "env": "OPENROUTER_API_KEY",
        "free": True,
        "note": "بوابة لنماذج كثيرة منها مجانية",
        "key_page": "https://openrouter.ai/settings/keys",
    },
    {
        "id": "nvidia",
        "name": "NVIDIA NIM",
        "url": "https://build.nvidia.com",
        "env": "NVIDIA_API_KEY",
        "free": True,
        "note": "منصة NVIDIA لنماذج مفتوحة",
        "key_page": "https://build.nvidia.com",
    },
    {
        "id": "mistral",
        "name": "Mistral",
        "url": "https://console.mistral.ai",
        "env": "MISTRAL_API_KEY",
        "free": True,
        "note": "Mistral free tier",
        "key_page": "https://console.mistral.ai/api-keys",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "url": "https://platform.deepseek.com",
        "env": "DEEPSEEK_API_KEY",
        "free": False,
        "note": "رخيص جداً وقوي بالمنطق",
        "key_page": "https://platform.deepseek.com/api_keys",
    },
]


def scan():
    """فحص المزودين المعروفين."""
    lines = ["# تقرير مزودات AI المجانية", f"**التاريخ:** {datetime.datetime.now():%Y-%m-%d %H:%M}", ""]
    found = {}
    for p in PROVIDER_INDEX:
        print(f"فحص: {p['name']}...")
        env_val = os.getenv(p["env"], "")
        status = "مفعل" if env_val else "غير مفعل"
        found[p["id"]] = {**p, "status": status}
        lines.append(f"## {p['name']}")
        lines.append(f"- الحالة: {status}")
        lines.append(f"- مجاني: {'نعم' if p['free'] else 'لا'}")
        lines.append(f"- الوصف: {p['note']}")
        lines.append(f"- صفحة المفتاح: {p['key_page']}")
        lines.append(f"- متغير البيئة: `{p['env']}`")
        lines.append("")

    _save("providers_known.md", lines)
    return found


def discover():
    """بحث عن مزودات جديدة."""
    print("بحث عن مزودات AI مجانية جديدة...")
    lines = ["# بحث عن مزودات AI مجانية", f"**التاريخ:** {datetime.datetime.now():%Y-%m-%d %H:%M}", ""]
    queries = [
        "free AI API providers 2025 no credit card required",
        "best free LLM API services free tier",
    ]
    seen = set()
    found = []
    for q in queries:
        res = webtools.search(q, save=False, num=5)
        for r in res.get("results", []):
            if not isinstance(r, dict):
                continue
            u = r.get("url", "")
            t = r.get("title", "")
            if u and u not in seen:
                seen.add(u)
                found.append({"url": u, "title": t})
                lines.append(f"- [{t}]({u})")

    _save("providers_discovered.md", lines)
    return found


def _save(name, lines):
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def add_env(var, value):
    """إضافة مفتاح إلى .env بشكل آمن."""
    # التحقق من صحة اسم المتغير
    if not var.isupper() or not var.replace("_", "").isalnum():
        return "اسم المتغير غير صالح"

    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.read().splitlines(keepends=True)

    if not any(l.startswith(var + "=") for l in lines):
        lines.append(f"{var}={value}\n")
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return f"تم إضافة {var} إلى .env"
    return f"{var} موجود مسبقاً"


def report():
    """عرض التقرير المتراكم."""
    out = []
    for name in ["providers_known.md", "providers_discovered.md"]:
        p = os.path.join(OUT_DIR, name)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                out.append(f.read())
    return "\n\n".join(out) if out else "(لا يوجد بعد - شغّل scan أو discover)"


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "scan":
        scan()
        print("تم: راجع output/searches/providers_known.md")
    elif cmd == "discover":
        discover()
        print("تم: راجع output/searches/providers_discovered.md")
    elif cmd == "report":
        print(report())
    elif cmd == "all":
        scan()
        discover()
        print("تم كل شيء.")
    elif cmd == "add" and len(sys.argv) == 4:
        print(add_env(sys.argv[2], sys.argv[3]))
    else:
        print("استخدام: scan | discover | all | report | add <VAR> <value>")
