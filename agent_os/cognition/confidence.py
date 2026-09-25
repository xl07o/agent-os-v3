"""
confidence.py - محرك الثقة (Confidence Engine) — المواصفة §6
=============================================================
يعطي درجة ثقة معايَرة لأي قرار/نتيجة، بناءً على أدلة ملموسة لا شعور.

الثقة ترتفع بـ: تعدد المصادر المتفقة، وجود دليل تحقق، سجل نجاح سابق.
الثقة تنخفض بـ: التعارض، غياب الدليل، حداثة المهمة، سجل فشل.
"""

import os
import sys

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C


def assess(evidence):
    """يحسب ثقة (0..1) من قرائن ملموسة.

    evidence: dict اختياري المفاتيح:
        sources_agree   عدد المصادر المتفقة (int)
        sources_total   إجمالي المصادر المستشارة (int)
        has_verification هل هناك تحقق واقعي؟ (bool)
        past_success_rate معدل نجاح سابق لمهمة مشابهة (0..1)
        contradictions  عدد التعارضات المكتشفة (int)
        is_novel        هل المهمة جديدة كلياً؟ (bool)
    """
    ev = evidence or {}
    score = 0.5  # نقطة انطلاق محايدة

    total = ev.get("sources_total", 0)
    agree = ev.get("sources_agree", 0)
    if total > 0:
        # اتفاق المصادر يرفع الثقة نسبياً لعددها
        agreement = agree / total
        score += (agreement - 0.5) * 0.4

    if ev.get("has_verification"):
        score += 0.2   # دليل واقعي = أقوى رافع للثقة

    if "past_success_rate" in ev:
        score += (float(ev["past_success_rate"]) - 0.5) * 0.3

    contradictions = ev.get("contradictions", 0)
    score -= min(contradictions * 0.15, 0.45)   # كل تعارض يخصم

    if ev.get("is_novel"):
        score -= 0.15   # الجدّة تعني عدم يقين

    score = max(0.0, min(1.0, round(score, 3)))
    return {
        "confidence": score,
        "level": _label(score),
        "actionable": score >= 0.6,   # دون ذلك: اطلب دليلاً أو تحققاً بشرياً
        "basis": {k: ev.get(k) for k in ev},
    }


def _label(score):
    if score >= 0.85:
        return "عالية"
    if score >= 0.6:
        return "متوسطة"
    if score >= 0.35:
        return "منخفضة"
    return "ضعيفة جداً"


def should_escalate(score, risk=0.0):
    """قرار التصعيد للإنسان: ثقة منخفضة + مخاطرة عالية = صعّد (المواصفة §39)."""
    return score < 0.5 or (risk >= 0.7 and score < 0.75)


if __name__ == "__main__":
    cases = [
        {"sources_total": 3, "sources_agree": 3, "has_verification": True, "past_success_rate": 0.8},
        {"sources_total": 3, "sources_agree": 1, "contradictions": 2, "is_novel": True},
    ]
    for c in cases:
        r = assess(c)
        print(f"ثقة={r['confidence']} ({r['level']}) قابل للتنفيذ={r['actionable']}")
