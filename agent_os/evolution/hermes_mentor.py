"""
hermes_mentor.py - Hermes مُرشِداً: تصحيح + تطوّر مزدوج (رؤية المالك)
===================================================================
بعد أن ينفّذ وكيلك مهمة، يعرض عمله على Hermes (أو العقل) ليصحّح الأخطاء،
ثم يحوّل كل تصحيح إلى **درس دائم في ذاكرة وكيلك** — فيتراكم مصدر تطوّر ثانٍ
إلى جانب التحسين الذاتي: «تطوّر مزدوج».

  available()                       -> هل يوجد مُرشِد (Hermes أو عقل)؟
  mentor(task, output, kind)        -> يراجع، يصحّح، يخزّن الدرس، ويعيد الأفضل

مُفعَّل حين HERMES_MENTOR=1 (أو استدعاء مباشر). بلا مُرشِد يتدهور بصدق: لا
تصحيح مُلفّق (البند 5).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import _common as C

_MENTOR_PERSONA = (
    "أنت Hermes، مُرشِد خبير يراجع عمل وكيل آخر. صحّح الأخطاء بدقّة. "
    "ابدأ ردّك بسطر: VERDICT: CORRECT إن كان العمل سليماً، أو VERDICT: FIX إن به خطأ. "
    "ثم إن كان FIX: سطر LESSON: <الدرس المستفاد بإيجاز> وسطر BETTER: <النسخة المصحّحة>."
)


def available():
    """هل يوجد مُرشِد: مثيل Hermes حيّ أو عقل متعدد المزودين؟"""
    try:
        from agent_os import hermes_client
        if hermes_client.available():
            return True
    except Exception:
        pass
    try:
        import brain
        return bool(brain.available_engines())
    except Exception:
        return False


def _ask_mentor(prompt):
    """يسأل المُرشِد: Hermes الحقيقي أولاً ثم العقل. يرجع النص أو None."""
    try:
        from agent_os import hermes_client
        if hermes_client.available():
            r = hermes_client.ask(f"{_MENTOR_PERSONA}\n\n{prompt}")
            if r.get("ok"):
                return r["text"], "hermes"
    except Exception:
        pass
    raw, engine = C.call_brain(_MENTOR_PERSONA, prompt, mode="smart")
    if raw and engine not in (None, "", "none") and not raw.strip().startswith("("):
        return raw.strip(), engine
    return None, None


def _parse(review):
    """يفكّك رد المُرشِد إلى (verdict, lesson, better)."""
    verdict, lesson, better = "CORRECT", "", ""
    for line in review.splitlines():
        s = line.strip()
        up = s.upper()
        if up.startswith("VERDICT:"):
            verdict = "FIX" if "FIX" in up else "CORRECT"
        elif up.startswith("LESSON:"):
            lesson = s.split(":", 1)[1].strip()
        elif up.startswith("BETTER:"):
            better = s.split(":", 1)[1].strip()
    return verdict, lesson, better


def _store_lesson(task, kind, lesson, better):
    """يحوّل تصحيح المُرشِد إلى ذاكرة دائمة لوكيلك (التطوّر الثاني)."""
    text = lesson or better
    if not text:
        return False
    stored = False
    try:
        from agent_os.memory import provenance
        provenance.record(f"mentor:{kind}:{task[:50]}", text,
                          source="hermes_mentor", confidence=0.75, kind="fact")
        stored = True
    except Exception:
        pass
    try:
        from agent_os.memory import contextual_memory as cm
        cm.save_experience(task=task[:200], approach=kind, tools=["hermes_mentor"],
                           problem=lesson, solution=better, outcome="corrected")
        stored = True
    except Exception:
        pass
    try:
        from agent_os.memory import strategy_memory as sm
        sm.record_outcome(kind, "hermes_mentored", success=True)
    except Exception:
        pass
    return stored


def mentor(task, output, kind="task"):
    """يراجع عمل الوكيل عبر المُرشِد، يخزّن الدرس، ويعيد النتيجة."""
    if not available():
        return {"reviewed": False, "reason": "لا مُرشِد متاح (لا Hermes ولا عقل)"}
    review, engine = _ask_mentor(
        f"المهمة: «{task}»\nإجابة الوكيل:\n{str(output)[:1500]}\n\nراجِعها وصحّح إن لزم.")
    if not review:
        return {"reviewed": False, "reason": "المُرشِد لم يردّ"}
    verdict, lesson, better = _parse(review)
    if verdict == "CORRECT":
        return {"reviewed": True, "verdict": "correct", "engine": engine, "lesson_stored": False}
    stored = _store_lesson(task, kind, lesson, better)
    C.log(f"🧑‍🏫 Hermes صحّح [{kind}] → درس مُخزَّن={stored}")
    return {"reviewed": True, "verdict": "fix", "engine": engine,
            "lesson": lesson, "better": better or None, "lesson_stored": stored}


if __name__ == "__main__":
    import json
    print(json.dumps(mentor("اجمع 2 و2", "الجواب 5"), ensure_ascii=False, indent=2))
