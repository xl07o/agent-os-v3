"""
طبقة الأدلة والجودة — تتحقق من الادّعاءات بدليل مستقل فعلي، لا تصدّق
"ok": True من الأداة نفسها بلا تحقق ثانٍ. امتداد فوق decision.ledger()
وtools.py الموجودين، لا نظام تخزين جديد ولا تقييم لغوي من مخ قابل
للتحيّز — فقط مقارنة فعلية وعدّ فعلي.
"""

import os

from . import decision


def verify_write(path: str, expected_content: str) -> dict:
    """Claim Verification + False Success Detector لـwrite_file تحديداً:
    يعيد قراءة الملف من القرص مباشرة ويقارنه حرفياً بما اتدّعى كتابته —
    لا يثق بـ"ok": True من الأداة وحدها."""
    if not os.path.isfile(path):
        return {"verified": False, "reason": "الملف غير موجود فعلياً على القرص رغم ادّعاء الكتابة"}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        actual = f.read()
    if actual != expected_content:
        return {"verified": False, "reason": "محتوى الملف الفعلي على القرص يختلف عمّا اتدّعى كتابته"}
    return {"verified": True}


def audit(limit: int = 200) -> dict:
    """Decision Review & Audit: إحصاءات حقيقية محسوبة من decision.ledger()
    — عدّ فعلي، لا حكم لغوي من مخ قابل للمبالغة أو التحيّز."""
    entries = decision.ledger(limit=limit)
    by_actor: dict[str, dict[str, int]] = {}
    proposed = approved = rejected = 0
    for e in entries:
        stage = e.get("stage")
        if stage == "proposed":
            proposed += 1
            actor = e.get("proposed_by", "?")
        elif stage == "approved":
            approved += 1
            actor = e.get("decided_by", "?")
        elif stage == "rejected":
            rejected += 1
            actor = e.get("decided_by", "?")
        else:
            continue
        by_actor.setdefault(actor, {})
        by_actor[actor][stage] = by_actor[actor].get(stage, 0) + 1

    decided = approved + rejected
    approval_rate = round(approved / decided, 2) if decided else None
    return {
        "total_entries": len(entries),
        "proposed": proposed, "approved": approved, "rejected": rejected,
        "approval_rate": approval_rate,
        "by_actor": by_actor,
    }
