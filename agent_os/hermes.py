"""
hermes.py - المساعد Hermes (البند 14)
======================================
عقل ثانٍ *مساعد* للوكيل الرئيسي، لا بديل عنه. دوره: رأيٌ ثانٍ، تخطيط
أعمق، ومراجعة نقدية. له شخصية وذاكرة مشورة خاصة، ويستفيد من دروس الذاكرة
الطويلة قبل أن يجيب. يعمل عبر brain (Claude/DeepSeek/Gemini) ويتدهور بصدق
حين لا مزوّد — لا يفبرك نصاً (البند 5).

  h = Hermes()
  h.ask(question)        -> إجابة/رأي
  h.plan(task)           -> خطوات مقترحة لمهمة عجز عنها الرئيسي
  h.review(text)         -> مراجعة نقدية مقتضبة
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

PERSONA = ("أنت Hermes، مساعد تقني ثانٍ للوكيل. تفكّر بعمق، تعطي رأياً "
           "نقدياً صريحاً، وتقترح خطوات وأدوات مفتوحة/مجانية محدّدة. "
           "لو لا تعرف، قل لا أعرف بوضوح.")


def _advice_file():
    return os.path.join(C.AGENT_OS_DIR, "hermes_advice.json")


class Hermes:
    """مساعد ذو ذاكرة مشورة خاصة."""

    def __init__(self, persona=None):
        self.persona = persona or PERSONA

    # ---- المشورة الأساسية ----
    def _ask_brain(self, prompt, mode="smart"):
        # (أ) إن توفّر مثيل Hermes حقيقي، نستخدمه كمساعد أقوى أولاً.
        try:
            from agent_os import hermes_client
            if hermes_client.available():
                r = hermes_client.ask(f"{self.persona}\n\n{prompt}")
                if r.get("ok"):
                    return {"ok": True, "text": r["text"][:2000], "engine": "hermes"}
        except Exception:
            pass
        # (ب) وإلا العقل متعدد المزودين (brain).
        raw, engine = C.call_brain(self.persona, prompt, mode=mode)
        if not raw or engine in (None, "", "none") or raw.strip().startswith("("):
            return {"ok": False, "reason": (raw or "لا مزوّد عقل متاح").strip("()")[:120]}
        return {"ok": True, "text": raw.strip()[:2000], "engine": engine}

    def _lessons_for(self, topic):
        try:
            from agent_os.memory import contextual_memory as cm
            hits = cm.recall(topic, limit=3)
            return [h.get("problem") for h in hits if h.get("problem")]
        except Exception:
            return []

    def _remember(self, kind, topic, text):
        try:
            st = C.load_json(_advice_file(), {"advice": []})
            st["advice"].append({"time": C.now_iso(), "kind": kind,
                                 "topic": topic[:120], "text": text[:500]})
            st["advice"] = st["advice"][-200:]
            C.atomic_write(_advice_file(), st)
        except Exception:
            pass

    # ---- الواجهات العامة ----
    def ask(self, question, context=""):
        lessons = self._lessons_for(question)
        hint = ("\nدروس سابقة ذات صلة:\n- " + "\n- ".join(lessons)) if lessons else ""
        res = self._ask_brain(f"{context}\nالسؤال: {question}{hint}")
        if res["ok"]:
            self._remember("ask", question, res["text"])
        return res

    def plan(self, task):
        res = self._ask_brain(
            f"ضع خطة عملية 3-6 خطوات لتنفيذ: «{task}». اذكر أدوات/حزم محددة.")
        if res["ok"]:
            self._remember("plan", task, res["text"])
        return res

    def review(self, text):
        res = self._ask_brain(
            f"راجع نقدياً وباقتضاب (مخاطر/أخطاء/تحسينات) ما يلي:\n{text[:2500]}")
        if res["ok"]:
            self._remember("review", text[:60], res["text"])
        return res

    def advice_count(self):
        return len(C.load_json(_advice_file(), {"advice": []}).get("advice", []))


_DEFAULT = None


def get():
    """مساعد Hermes مشترك (كسول)."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Hermes()
    return _DEFAULT


if __name__ == "__main__":
    import json
    q = " ".join(sys.argv[1:]) or "كيف أبدأ أداة CLI بايثون احترافية؟"
    print(json.dumps(get().ask(q), ensure_ascii=False, indent=2))
