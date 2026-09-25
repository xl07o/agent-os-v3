"""
why_engine.py - محرك الـ Why (v1.0)
=====================================
يسجل سبب كل قرار مهم مع الدليل.
بعد شهر تقدر تسأله: "ليش غيرت الموديل؟" ويجاوبك.

الاستخدام:
  from why_engine import WhyEngine
  why = WhyEngine()
  why.record(decision="غيرت الموديل من A لـ B",
             reason="A فشل 17% أكثر",
             evidence=["Benchmark #184"])
  why.ask("ليش غيرت الموديل")  # يرجع القرار المناسب
"""

import datetime
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WHY_DIR = os.path.join(BASE_DIR, "data", "why")
os.makedirs(WHY_DIR, exist_ok=True)
WHY_DB = os.path.join(WHY_DIR, "decisions.json")


def _load():
    if os.path.exists(WHY_DB):
        try:
            with open(WHY_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"decisions": []}


def _save(data):
    tmp = WHY_DB + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, WHY_DB)


def _similarity(a: str, b: str) -> float:
    """تشابه بسيط بين نصين."""
    a_words = set(re.findall(r'[\w\u0600-\u06FF]{2,}', a.lower()))
    b_words = set(re.findall(r'[\w\u0600-\u06FF]{2,}', b.lower()))
    if not a_words or not b_words:
        return 0.0
    common = a_words & b_words
    return len(common) / max(len(a_words), len(b_words))


class WhyEngine:
    """يسجل ويسترجع أسباب القرارات."""

    def record(self, decision: str, reason: str, evidence: list = None,
               category: str = "general", impact: str = "") -> dict:
        """يسجل قرار مع سببه ودليله."""
        db = _load()
        entry = {
            "id": f"d_{len(db['decisions'])+1:04d}",
            "decision": decision,
            "reason": reason,
            "evidence": evidence or [],
            "category": category,
            "impact": impact,
            "recorded_at": datetime.datetime.now().isoformat(),
        }
        db["decisions"].append(entry)
        _save(db)
        return entry

    def ask(self, question: str, top_k: int = 3) -> list:
        """يبحث عن قرارات مرتبطة بالسؤال."""
        db = _load()
        results = []
        for d in db["decisions"]:
            score = max(
                _similarity(question, d["decision"]),
                _similarity(question, d["reason"]),
                _similarity(question, d.get("category", "")),
            )
            if score > 0.1:
                results.append({**d, "relevance": round(score, 3)})
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:top_k]

    def format_answer(self, question: str) -> str:
        """يرجع إجابة منسقة على سؤال Why."""
        results = self.ask(question)
        if not results:
            return f"لا يوجد قرار مسجل مرتبط بـ: '{question}'"

        lines = [f"## إجابة: {question}", ""]
        for r in results:
            lines.append(f"### القرار: {r['decision']}")
            lines.append(f"**السبب:** {r['reason']}")
            if r.get("evidence"):
                lines.append(f"**الدليل:** {', '.join(r['evidence'])}")
            if r.get("impact"):
                lines.append(f"**التأثير:** {r['impact']}")
            lines.append(f"*{r['recorded_at'][:10]}*")
            lines.append("")
        return "\n".join(lines)

    def recent_decisions(self, limit: int = 10) -> list:
        """آخر القرارات."""
        db = _load()
        return db["decisions"][-limit:][::-1]


# Singleton
_why = WhyEngine()


def record_decision(decision, reason, evidence=None, category="general", impact=""):
    return _why.record(decision, reason, evidence, category, impact)


def ask_why(question):
    return _why.format_answer(question)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "ask":
        print(ask_why(" ".join(sys.argv[2:])))
    elif len(sys.argv) > 1 and sys.argv[1] == "recent":
        import json
        decisions = _why.recent_decisions()
        for d in decisions:
            print(f"[{d['recorded_at'][:10]}] {d['decision'][:60]}")
            print(f"  السبب: {d['reason'][:80]}")
    else:
        print("الاستخدام: python why_engine.py ask <سؤال> | recent")
