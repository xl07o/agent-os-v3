"""
consensus.py - محرك الإجماع بين النماذج (Consensus Engine) — §8
================================================================
يأخذ إجابات عدة نماذج على نفس السؤال ويقرر الأفضل/الأكثر اتفاقاً.
منطق خالص وقابل للاختبار (لا يستدعي نماذج بنفسه) — يُغذّى بالإجابات.

طرق الحسم:
  - majority: أكثر إجابة متكررة (بعد تطبيع) — للأسئلة ذات إجابة قصيرة/واقعية.
  - similarity: أعلى تشابه متبادل مع البقية — للإجابات النصية الطويلة.
  - confidence_weighted: ترجيح بثقة كل نموذج.
"""

import os
import sys
import re
from collections import Counter

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C


def _normalize(text):
    """تطبيع للمقارنة: حروف صغيرة، إزالة تشكيل/فراغات زائدة/ترقيم."""
    t = str(text).lower().strip()
    t = re.sub(r"[\u064b-\u065f\u0640]", "", t)      # تشكيل عربي وتطويل
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _tokens(text):
    return set(_normalize(text).split())


def _jaccard(a, b):
    """تشابه جاكارد بين نصين (0..1)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def majority_vote(answers):
    """أكثر إجابة تكراراً بعد التطبيع (للأسئلة الواقعية القصيرة)."""
    if not answers:
        return {"winner": None, "agreement": 0.0, "votes": {}}
    norm = [_normalize(a) for a in answers]
    counts = Counter(norm)
    top_norm, top_n = counts.most_common(1)[0]
    # نعيد النص الأصلي المطابق لأكثر صيغة مطبّعة
    winner = next(a for a in answers if _normalize(a) == top_norm)
    return {
        "winner": winner,
        "agreement": round(top_n / len(answers), 3),
        "votes": dict(counts),
        "unanimous": top_n == len(answers),
    }


def similarity_consensus(answers):
    """يختار الإجابة الأعلى تشابهاً متوسطاً مع البقية (للنصوص الطويلة)."""
    if not answers:
        return {"winner": None, "cohesion": 0.0}
    if len(answers) == 1:
        return {"winner": answers[0], "cohesion": 1.0}
    scores = []
    for i, a in enumerate(answers):
        others = [answers[j] for j in range(len(answers)) if j != i]
        avg_sim = sum(_jaccard(a, o) for o in others) / len(others)
        scores.append((avg_sim, i))
    scores.sort(reverse=True)
    best_sim, best_i = scores[0]
    # التماسك الكلي = متوسط كل التشابهات الزوجية
    pairs = [_jaccard(answers[i], answers[j])
             for i in range(len(answers)) for j in range(i + 1, len(answers))]
    cohesion = round(sum(pairs) / len(pairs), 3) if pairs else 1.0
    return {
        "winner": answers[best_i],
        "winner_index": best_i,
        "representativeness": round(best_sim, 3),
        "cohesion": cohesion,
        "divergent": cohesion < 0.3,   # النماذج متباعدة → عدم يقين
    }


def confidence_weighted(responses):
    """responses: [{"answer","confidence"}] — يرجّح بالثقة."""
    if not responses:
        return {"winner": None, "score": 0.0}
    best = max(responses, key=lambda r: float(r.get("confidence", 0.5)))
    total_conf = sum(float(r.get("confidence", 0.5)) for r in responses)
    return {
        "winner": best["answer"],
        "confidence": float(best.get("confidence", 0.5)),
        "avg_confidence": round(total_conf / len(responses), 3),
    }


def decide(answers, method="auto"):
    """واجهة موحّدة: تختار الطريقة تلقائياً حسب طبيعة الإجابات.

    auto: إجابات قصيرة متشابهة الطول → majority؛ نصوص طويلة → similarity.
    """
    if not answers:
        return {"winner": None, "method": method, "note": "لا إجابات"}
    if method == "majority":
        r = majority_vote(answers); r["method"] = "majority"; return r
    if method == "similarity":
        r = similarity_consensus(answers); r["method"] = "similarity"; return r

    avg_len = sum(len(str(a)) for a in answers) / len(answers)
    if avg_len <= 60:
        r = majority_vote(answers); r["method"] = "majority"
    else:
        r = similarity_consensus(answers); r["method"] = "similarity"
    return r


def live_consensus(question, n=3, mode="smart"):
    """إجماع حيّ: يسأل العقل الحقيقي عدة مرات/مزودين ويُجمع النتائج (§8).

    يستدعي brain عبر _common.call_brain؛ لو تعذّر العقل يعيد نتيجة فارغة
    بدل أن يكسر. الحسم يتم بـ decide() على الإجابات الفعلية.
    """
    answers = []
    try:
        from agent_os import _common as _C
        for _ in range(max(1, n)):
            text, engine = _C.call_brain(
                "أجب باختصار ودقة. أنت أحد عدة نماذج في تصويت إجماع.",
                question, mode=mode,
            )
            if text and not text.startswith("("):
                answers.append(text)
    except Exception as e:
        C.log(f"⚠️ إجماع حيّ تعذّر: {e}")

    if not answers:
        return {"winner": None, "answers": 0, "note": "لا مزوّد متاح — أضف مفتاحاً أو شغّل Ollama"}
    result = decide(answers)
    result["answers"] = len(answers)
    return result


if __name__ == "__main__":
    print(decide(["نعم", "نعم", "لا"]))
    print(decide(["الحل هو استخدام قائمة بيضاء للأوامر مع تحقق المسار",
                  "استخدم قائمة أوامر بيضاء وتحقق من المسارات الحساسة",
                  "افتح كل الصلاحيات بلا قيود"]))
