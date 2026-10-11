"""
فحص سريع للإعداد: python -m agent_os4.doctor          (بدون أي صرف)
                  python -m agent_os4.doctor --live   (+ سؤال قصير حقيقي لـClaude)

ما يطبع المفتاح أبداً — بس هل هو موجود، وهل شكله صحيح، وطوله.
"""

import os
import sqlite3
import sys

from . import env, spend


def _line(ok: bool | None, text: str) -> None:
    mark = {True: "✓", False: "✗", None: "•"}[ok]
    print(f"{mark} {text}")


def main() -> int:
    problems = 0
    _line(os.path.exists(env._ENV_PATH) or None, f"ملف الإعدادات: {env._ENV_PATH}"
          + ("" if os.path.exists(env._ENV_PATH) else " (مو موجود — انسخ .env.example إلى .env)"))

    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        _line(False, "ANTHROPIC_API_KEY مو موجود بملف .env")
        problems += 1
    elif not key.startswith("sk-ant-"):
        _line(False, f"ANTHROPIC_API_KEY موجود بس شكله غلط (مفاتيح Claude تبدأ بـ sk-ant-) — طوله {len(key)} حرف")
        problems += 1
    else:
        _line(True, f"ANTHROPIC_API_KEY موجود وشكله صحيح (طوله {len(key)} حرف — ما ينطبع)")

    try:
        import anthropic
        _line(True, f"حزمة anthropic مثبّتة ({anthropic.__version__})")
    except ImportError:
        _line(False, "حزمة anthropic مو مثبّتة — python -m pip install -r agent_os4/requirements.txt")
        problems += 1

    model = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
    _line(model in spend.PRICES or None, f"الموديل: {model}" + ("" if model in spend.PRICES else " (مو بجدول الأسعار — يُحسب بأغلى سعر)"))

    s = spend.summary()
    _line(s["remaining_usd"] > 0, f"سقف الصرف: ${s['spent_usd']:.2f} من ${s['budget_usd']:.2f} هالشهر ({s['calls']} استدعاء)")

    try:
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        _line(True, "البحث بالمحادثات (SQLite FTS5) متاح")
    except sqlite3.OperationalError:
        _line(False, "SQLite عندك بدون FTS5 — البحث بالمحادثات القديمة ما بيشتغل (الباقي عادي)")

    if os.getenv("TELEGRAM_BOT_TOKEN"):
        owner = os.getenv("TELEGRAM_OWNER_ID", "").strip()
        _line(bool(owner) or None, "تيليجرام: التوكن موجود" + ("، ورقم حسابك مضبوط" if owner else "، بس TELEGRAM_OWNER_ID فاضي — راسل البوت يعطيك رقمك"))
    else:
        _line(None, "تيليجرام: مو مفعّل (اختياري)")

    if "--live" in sys.argv:
        if problems:
            _line(False, "ما جرّبت Claude — صلّح اللي فوق أول")
        else:
            from . import brain
            before = spend.summary()["spent_usd"]
            print("… أسأل Claude سؤال قصير (ممكن ياخذ لين دقيقة)")
            try:
                reply = brain.ask("رد بجملة وحدة قصيرة بالعربي: إيش اسمك؟")
                cost = spend.summary()["spent_usd"] - before
                _line(True, f"Claude رد: {reply.strip()[:200]}")
                _line(True, f"تكلفة هالتجربة: ${cost:.4f}")
            except Exception as e:  # noqa: BLE001 — نعرض السبب بصدق
                _line(False, f"Claude ما رد: {e}")
                problems += 1
    else:
        _line(None, "لتجربة Claude فعلياً: python -m agent_os4.doctor --live")

    print("\nكل شي تمام." if not problems else f"\nفيه {problems} شي يحتاج تصليح (✗ فوق).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
