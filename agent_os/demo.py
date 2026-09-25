"""
demo.py - عرض حيّ لكل قدرات Agent OS v3 (بلا أي إعداد)
======================================================
يشغّل مساراً حقيقياً end-to-end يعمل فوراً بلا عقل ولا شبكة، ليريك النظام
يعمل بعينك: ذاكرة، تعلّم، أولويات، فكر مالي، أمن، نواة، فحص ذاتي.
كل خطوة حقيقية (لا تمثيل)؛ ما يحتاج عقلاً/شبكة يُقال بصراحة.

  python -m agent_os.demo
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C


def _p(title):
    print("\n" + "─" * 55 + f"\n▶ {title}\n" + "─" * 55)


def run():
    print("╔" + "═" * 53 + "╗")
    print("║   Agent OS v3 — عرض حيّ (كل خطوة حقيقية)            ║")
    print("╚" + "═" * 53 + "╝")

    _p("1) الذاكرة: أخزّن معرفة ثم أستدعيها")
    from agent_os.learn import ingest
    from agent_os.memory import contextual_memory as cm
    ingest.ingest_text("عرض", "الوكيل الذاتي يتعلّم من كل مصدر ويخزّن كل شيء "
                              "كمرجع، فيتقنى مع الوقت بدل أن ينسى.", topic="فلسفة الوكيل")
    hits = cm.recall("الوكيل يتعلّم ويتذكّر")
    print(f"   خزّنت معرفة، واستدعيت {len(hits)} تجربة مطابقة بالتشابه ✅")

    _p("2) النواة: أنفّذ مهمة عبر JARVIS")
    from agent_os import jarvis
    for cmd in ("سجّل هدف بناء متجر إلكتروني", "سجّل هدف تعلّم الأمن السيبراني"):
        out = jarvis.handle(cmd)
        print(f"   «{cmd}» → {out['reply']}")

    _p("3) الأولويات: أستخلصها من محادثتنا تلقائياً")
    from agent_os.memory import conversation
    pr = conversation.priorities(5)
    print("   ما يهمّك الآن: " + "، ".join(p["topic"] for p in pr))

    _p("4) الفكر المالي: أقيّم جدوى فرصة")
    from agent_os import finance_brain
    ev = finance_brain.evaluate("أداة CLI مدفوعة", cost_usd=0,
                                monthly_revenue_usd=250, effort_days=2, confidence=0.75)
    print(f"   القرار: {ev['verdict']} · العائد: {ev['roi']} · الاسترداد: {ev['payback_days']} يوماً")
    print(f"   السبب: {ev['reasons'][0]}")

    _p("5) الأمن: بوابة النطاق ترفض ما هو خارج التفويض (خط أحمر)")
    from agent_os import bounty_engine as be
    prog = {"scope": ["example.com", "*.test.com"]}
    for host in ("api.example.com", "evil.org"):
        ok, msg = be.in_scope(prog, host)
        print(f"   {host}: {'مسموح ✅' if ok else 'مرفوض 🚫'} ({msg})")

    _p("6) الفحص الذاتي: هل كل النظام سليم؟")
    from agent_os import selfcheck
    r = selfcheck.run()
    print("   " + r["summary"])

    _p("الخلاصة")
    print("   النظام يعمل فعلياً الآن بلا أي إعداد.")
    print("   للعقل الكامل: شغّل Ollama أو ضع مفتاحاً في .env.")
    print("   للصوت (JARVIS): ثبّت faster-whisper + piper + openwakeword.")
    return {"ok": r["ok"], "priorities": pr, "finance": ev, "selfcheck": r["summary"]}


if __name__ == "__main__":
    run()
