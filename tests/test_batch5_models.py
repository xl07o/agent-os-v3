"""اختبارات الدفعة 5: ذكاء النماذج (consensus, router)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os.models import consensus as cons
from agent_os.models import router as rt


# ===== Consensus =====

def test_majority_vote():
    r = cons.majority_vote(["نعم", "نعم", "لا"])
    assert r["winner"] == "نعم"
    assert r["agreement"] == round(2 / 3, 3)
    assert r["unanimous"] is False


def test_majority_unanimous():
    r = cons.majority_vote(["42", "42", "42"])
    assert r["unanimous"] is True
    assert r["agreement"] == 1.0


def test_similarity_picks_representative():
    answers = [
        "استخدم قائمة بيضاء للأوامر وتحقق من المسارات",
        "استخدم قائمة أوامر بيضاء وتحقق المسارات الحساسة",
        "افتح كل الصلاحيات بلا أي قيود إطلاقاً",
    ]
    r = cons.similarity_consensus(answers)
    # الإجابتان المتشابهتان يجب أن تهزما الشاذة
    assert r["winner_index"] in (0, 1)


def test_similarity_detects_divergence():
    r = cons.similarity_consensus(["قطة تأكل سمك", "الطقس مشمس اليوم", "الرياضيات صعبة جدا"])
    assert r["divergent"] is True


def test_decide_auto_short_uses_majority():
    r = cons.decide(["A", "A", "B"])
    assert r["method"] == "majority"


def test_decide_auto_long_uses_similarity():
    long_ans = ["هذا نص طويل جدا يشرح الفكرة بتفصيل كامل ووافٍ للقارئ الكريم هنا",
                "هذا نص طويل يشرح الفكرة بتفصيل كامل ووافٍ للقارئ الكريم في هذا"]
    r = cons.decide(long_ans)
    assert r["method"] == "similarity"


def test_confidence_weighted():
    r = cons.confidence_weighted([
        {"answer": "A", "confidence": 0.6},
        {"answer": "B", "confidence": 0.9},
    ])
    assert r["winner"] == "B"


# ===== Router =====

def test_router_cheap_prefers_free():
    r = rt.route("cheap")
    # مزوّد التكلفة الأدنى يجب أن يكون مجانياً
    prov = next(p for p in rt.DEFAULT_PROVIDERS if p["id"] == r["provider"])
    assert prov["cost"] == 0.0


def test_router_quality_can_pick_premium_if_no_key(monkeypatch=None):
    # بلا مفاتيح مدفوعة، أفضل جودة متاحة يجب أن تكون مجانية
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)
    r = rt.route("quality")
    prov = next(p for p in rt.DEFAULT_PROVIDERS if p["id"] == r["provider"])
    assert prov["free"] is True


def test_router_fallback_chain_nonempty():
    chain = rt.fallback_chain("balanced")
    assert len(chain) >= 3
    assert all(isinstance(x, str) for x in chain)


def test_router_no_providers():
    r = rt.route("balanced", providers=[], only_available=True)
    assert r["provider"] is None
