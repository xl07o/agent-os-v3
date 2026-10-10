"""
مؤشرات القياس — لقطة أرقام حقيقية مجمّعة من البيانات الموجودة فعلياً
(decision.ledger, memory, skills). عدّ وحساب فقط، لا تقييم لغوي من مخ
قابل للتحيّز أو المبالغة — نفس فلسفة evidence.audit().
"""

from . import evidence, memory, skills


def snapshot() -> dict:
    audit = evidence.audit()
    by_actor = audit["by_actor"]

    bot_usage = {
        actor: counts.get("proposed", 0)
        for actor, counts in by_actor.items()
        if actor != "owner"
    }

    return {
        "decisions": {
            "total": audit["total_entries"],
            "proposed": audit["proposed"],
            "approved": audit["approved"],
            "rejected": audit["rejected"],
            "approval_rate": audit["approval_rate"],
        },
        "bot_usage": bot_usage,
        "memory_entries": memory.count(),
        "skills_registered": len(skills.list_skills()),
    }
