"""
selfcheck.py - فحص ذاتي شامل لتكامل النظام (Doctor)
===================================================
يستورد كل نظام فرعي ويشغّل عليه لمسة حقيقية خفيفة، ثم يبلّغ بصدق: يعمل /
معطّل / يحتاج شيئاً خارجياً (عقل، أدوات صوت). أداة صيانة تُظهر الحقيقة لا
تلفّقها (البند 5)، وتُستخدم قبل الاعتماد على أي مسار.

  run() -> {ok, checks:[{name, ok, note}], summary}
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C


def _probe(name, fn):
    try:
        note = fn()
        return {"name": name, "ok": True, "note": note}
    except Exception as e:
        return {"name": name, "ok": False, "note": f"خطأ: {str(e)[:120]}"}


def run():
    """يفحص كل الأنظمة الفرعية بلمسة حقيقية. لا يتطلب شبكة ولا مفاتيح."""
    checks = []

    def mem():
        from agent_os.memory import provenance, contextual_memory, strategy_memory, conflict_resolver
        provenance.record("selfcheck", "قيمة", source="selfcheck", kind="fact")
        assert provenance.get("selfcheck")["value"] == "قيمة"
        contextual_memory.save_experience("فحص", "لمسة", ["x"], "", "", "learned")
        strategy_memory.record_outcome("selfcheck", "s", True)
        r = conflict_resolver.resolve({"value": "A", "confidence": 0.9, "timestamp": "2026-01-01"},
                                      {"value": "B", "confidence": 0.5, "timestamp": "2026-01-01"})
        assert r["resolved_value"] == "A"
        return "الذاكرة: قراءة/كتابة/حسم تعمل"

    def learn():
        from agent_os.learn import ingest
        r = ingest.ingest_text("selfcheck", "نص معرفي حقيقي كافٍ الطول للاختبار الذاتي للنظام.")
        assert r["ok"]
        assert ingest.ingest_text("x", "")["ok"] is False  # يرفض الفارغ بصدق
        return "التعلّم: استيعاب + رفض صادق للفارغ"

    def kernel():
        from agent_os import agent_os as A
        res = A.run_task("سجّل هدف فحص ذاتي")
        assert "result" in res and "recalled" in res
        return f"النواة: مهمة نُفّذت (حالة {res['result']['status']})"

    def honesty():
        from agent_os import agent_os as A
        v = A.critic("t", [{"action": "x", "done": True, "output": {"c": "shell=True"}}], intent="code")
        assert any("shell=True" in i for i in v["issues"])
        return "الصدق: قاعدة shell=True حيّة، لا نجاح وهمي"

    def finance():
        from agent_os import finance_brain
        assert finance_brain.evaluate("x", monthly_revenue_usd=300, effort_days=1, confidence=0.8)["verdict"] == "go"
        return "المالية: تحليل الجدوى يعمل"

    def voice():
        from agent_os.voice import assistant
        s = assistant.status()
        need = [k for k, v in s.items() if v is False and k != "ready"]
        return "الصوت: جاهز" if s["ready"] else f"الصوت: يحتاج تثبيت ({', '.join(need)}) على جهازك"

    def brain():
        import brain
        av = brain.available_engines()
        return f"العقل: {len(av)} مزوّد متاح" if av else "العقل: لا مزوّد (شغّل Ollama أو ضع مفتاحاً)"

    def bounty():
        from agent_os import bounty_engine as be
        assert be.in_scope({"scope": ["example.com"]}, "evil.org")[0] is False
        return "الأمن: بوابة النطاق تحجب الخارج"

    def priorities():
        from agent_os.memory import conversation
        conversation.record_turn("فحص أولويات النظام", "", "selfcheck")
        return f"الأولويات: {len(conversation.priorities(3))} موضوع"

    checks.append(_probe("memory", mem))
    checks.append(_probe("learn", learn))
    checks.append(_probe("kernel", kernel))
    checks.append(_probe("honesty", honesty))
    checks.append(_probe("finance", finance))
    checks.append(_probe("voice", voice))
    checks.append(_probe("brain", brain))
    checks.append(_probe("bounty_scope", bounty))
    checks.append(_probe("priorities", priorities))

    failed = [c for c in checks if not c["ok"]]
    return {
        "ok": not failed,
        "checks": checks,
        "summary": f"{len(checks) - len(failed)}/{len(checks)} أنظمة تعمل" +
                   (f" · معطّل: {', '.join(c['name'] for c in failed)}" if failed else " · كلها سليمة"),
    }


if __name__ == "__main__":
    import json
    r = run()
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    sys.exit(0 if r["ok"] else 1)
