"""
knowledge_dna.py - الذاكرة المعرفية المتقدمة (Knowledge DNA) v1.0
=================================================================
مو مجرد Memory. كل معلومة لها:
  FACT
  ├── Source
  ├── Timestamp
  ├── Confidence
  ├── Evidence
  ├── Derived from
  ├── Used by
  └── Last verified

إذا مصدر تغير، يعرف القرارات المبنية عليه ويعيد فحصها.
هنا الذاكرة تصير شبكة معرفة حقيقية.
"""

import datetime
import hashlib
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DNA_DIR = os.path.join(BASE_DIR, "data", "knowledge_dna")
os.makedirs(DNA_DIR, exist_ok=True)
DNA_DB = os.path.join(DNA_DIR, "knowledge.json")


def _load():
    if os.path.exists(DNA_DB):
        try:
            with open(DNA_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"facts": {}, "relations": []}


def _save(data):
    tmp = DNA_DB + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DNA_DB)


class KnowledgeDNA:
    """شبكة معرفة حقيقية مع provenance كامل."""

    def store(self, fact: str, source: str = "", confidence: float = 0.8,
              evidence: list = None, derived_from: list = None,
              category: str = "general") -> str:
        """يخزن معلومة مع كامل سياقها."""
        db = _load()
        fact_id = hashlib.md5(fact.encode()).hexdigest()[:12]
        now = datetime.datetime.now().isoformat()

        db["facts"][fact_id] = {
            "id": fact_id,
            "fact": fact,
            "source": source,
            "confidence": confidence,
            "evidence": evidence or [],
            "derived_from": derived_from or [],
            "used_by": [],
            "category": category,
            "created_at": now,
            "last_verified": now,
            "verification_count": 0,
            "stale": False,
        }
        _save(db)
        return fact_id

    def recall(self, query: str, min_confidence: float = 0.3) -> list:
        """يسترجع المعلومات المرتبطة بالسؤال."""
        db = _load()
        results = []
        query_words = set(re.findall(r'[\w\u0600-\u06FF]{2,}', query.lower()))

        for fid, fact in db["facts"].items():
            if fact.get("confidence", 0) < min_confidence:
                continue
            fact_words = set(re.findall(r'[\w\u0600-\u06FF]{2,}', fact["fact"].lower()))
            overlap = len(query_words & fact_words) / max(len(query_words), 1)
            if overlap > 0.1:
                results.append({**fact, "relevance": round(overlap, 3)})

        results.sort(key=lambda x: x["relevance"] * x.get("confidence", 0.5), reverse=True)
        return results[:5]

    def mark_used(self, fact_id: str, used_by: str):
        """يسجل أن معلومة استُخدمت في قرار."""
        db = _load()
        if fact_id in db["facts"]:
            if used_by not in db["facts"][fact_id]["used_by"]:
                db["facts"][fact_id]["used_by"].append(used_by)
            _save(db)

    def verify(self, fact_id: str, still_valid: bool, new_confidence: float = None):
        """يحدث حالة التحقق من معلومة."""
        db = _load()
        if fact_id in db["facts"]:
            f = db["facts"][fact_id]
            f["last_verified"] = datetime.datetime.now().isoformat()
            f["verification_count"] = f.get("verification_count", 0) + 1
            f["stale"] = not still_valid
            if new_confidence is not None:
                f["confidence"] = new_confidence
            _save(db)

    def find_stale(self, days: int = 30) -> list:
        """يجد المعلومات القديمة التي تحتاج إعادة تحقق."""
        db = _load()
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        stale = []
        for fid, fact in db["facts"].items():
            if fact.get("last_verified", "") < cutoff or fact.get("stale"):
                stale.append(fact)
        return stale

    def garbage_collect(self, min_confidence: float = 0.2, max_age_days: int = 90):
        """ينظف المعلومات القديمة وضعيفة الثقة."""
        db = _load()
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=max_age_days)).isoformat()
        before = len(db["facts"])
        db["facts"] = {
            fid: f for fid, f in db["facts"].items()
            if f.get("confidence", 0) >= min_confidence
            or f.get("last_verified", "") >= cutoff
            or len(f.get("used_by", [])) > 0
        }
        _save(db)
        return {"removed": before - len(db["facts"]), "remaining": len(db["facts"])}

    def stats(self) -> dict:
        db = _load()
        facts = list(db["facts"].values())
        return {
            "total_facts": len(facts),
            "avg_confidence": round(sum(f.get("confidence", 0) for f in facts) / max(len(facts), 1), 2),
            "stale_count": sum(1 for f in facts if f.get("stale")),
            "categories": list(set(f.get("category", "general") for f in facts)),
        }


# Singleton
_dna = KnowledgeDNA()


def store_fact(fact, source="", confidence=0.8, evidence=None, derived_from=None, category="general"):
    return _dna.store(fact, source, confidence, evidence, derived_from, category)


def recall_facts(query, min_confidence=0.3):
    return _dna.recall(query, min_confidence)


def knowledge_stats():
    return _dna.stats()


if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if action == "stats":
        import json
        print(json.dumps(knowledge_stats(), ensure_ascii=False, indent=2))
    elif action == "gc":
        import json
        print(json.dumps(_dna.garbage_collect(), ensure_ascii=False, indent=2))
    elif action == "stale":
        stale = _dna.find_stale()
        for f in stale:
            print(f"[{f['last_verified'][:10]}] {f['fact'][:80]}")
    else:
        print("الاستخدام: python knowledge_dna.py stats | gc | stale")
