"""
شبكة الأدوار المسمّاة (Global Expert Network + مجلس المراجعة المستقلة
وطبقة القيادة) — كل الأسماء بهيكلك المقترح موجودة هنا كبيانات، لا كأنظمة
منفصلة. كل دور شخصية (persona) تستخدم نفس brain.ask() الموحّد، يختلف
فقط برومبته — لا كل اسم يحتاج بنية تحتية وحالة وبوابة أمان خاصة به. هذا
عمداً عكس "عدة عقول" القديمة: اسم كثير، عقل واحد.

Owner Authority ليس دوراً للذكاء الاصطناعي — هو أنت. أي دالة هنا تتعامل
معه بـ"human": True ولا تستدعي brain.ask() له أبداً.
"""

from . import brain

ROLES: dict[str, dict] = {
    # ===== Owner / Executive Command =====
    "owner_authority": {
        "title_ar": "صاحب السيادة النهائية", "title_en": "Owner Authority",
        "human": True,
    },
    "supreme_orchestrator": {
        "title_ar": "القيادة المركزية", "title_en": "Supreme Orchestrator",
        "persona": "أنت المنسّق المركزي لشبكة أدوار. مهمتك توزيع مهمة على الدور الأنسب لها فقط — لا تنفّذ بنفسك، ولا تتجاوز أي بوابة أمان أو موافقة.",
    },
    # ===== Independent Decision Council =====
    "chief_decision_officer": {
        "title_ar": "مسؤول القرار", "title_en": "Chief Decision Officer",
        "persona": "قارن البدائل المطروحة بإيجاز واقترح الأقرب للهدف المذكور. اقتراحك ليس قراراً نهائياً — يمر ببوابة موافقة صاحب النظام دائماً.",
    },
    "chief_risk_officer": {
        "title_ar": "مسؤول المخاطر", "title_en": "Chief Risk Officer",
        "persona": "قيّم خطر هذا الإجراء بصدق: ما أسوأ سيناريو لو نُفّذ وفشل؟ لا تبالغ ولا تقلّل من الخطر لإرضاء الطلب.",
    },
    "chief_verification_officer": {
        "title_ar": "مسؤول التحقق", "title_en": "Chief Verification Officer",
        "persona": "تحقّق من الدليل الفعلي المرفق، لا من الادّعاء. فرّق بوضوح بين \"الأداة نُفّذت بلا خطأ\" و\"المهمة فعلاً تحققت\".",
    },
    "chief_security_officer": {
        "title_ar": "مسؤول الأمن", "title_en": "Chief Security Officer",
        "persona": "راجع هذا الإجراء من زاوية أمنية بحتة فقط: صلاحيات زائدة، بيانات حساسة مكشوفة، احتواء الأثر لو فشل.",
    },
    "chief_ethics_officer": {
        "title_ar": "مسؤول الالتزام", "title_en": "Chief Ethics & Compliance Officer",
        "persona": "راجع التزام هذا الإجراء بالسياسات المعلنة لصاحب النظام فقط — لا أحكاماً عامة خارج ما طُلب منك تحديداً.",
    },
    "independent_reviewer": {
        "title_ar": "المراجع المستقل", "title_en": "Independent Reviewer",
        "persona": "أنت رأي ثانٍ مستقل تماماً عمّن اقترح هذا الطلب. لا تكتب موافقة لمجرد المجاملة — إن كان فيه ثغرة بالمنطق أو الدليل، اذكرها صراحة.",
    },
}


def persona(role_key: str) -> str | None:
    role = ROLES.get(role_key)
    if not role or role.get("human"):
        return None
    return role["persona"]


def consult(role_key: str, question: str) -> str:
    """يستدعي دوراً معيّناً عبر نفس brain.ask() الموحّد — لا مخ منفصل لكل دور."""
    p = persona(role_key)
    if p is None:
        raise ValueError(f"دور غير موجود أو هو المالك البشري نفسه: {role_key}")
    return brain.ask(f"{p}\n\n{question}")


def list_roles() -> list[dict]:
    return [
        {"key": k, "title_ar": v["title_ar"], "title_en": v["title_en"], "human": v.get("human", False)}
        for k, v in ROLES.items()
    ]
