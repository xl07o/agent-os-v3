"""
بوتات مساعدة حقيقية — كل بوت موظف مصغّر: شخصية (persona) + مجموعة أدوات
محدودة + مديرية. يستخدم نفس kernel.run_task()/decision.py/safety.py
الموجودين بالضبط — لا بنية تحتية ولا حالة ولا بوابة أمان منفصلة لكل
بوت. تسجيل بوت جديد = سطر بيانات هنا، لا ملف/نظام جديد.

هذا يُفعِّل "Mission Control" (توزيع مهمة على البوت الأنسب) وأرضية
حقيقية لـConflict/Deadlock Resolution لاحقاً — ما فيه شيء يتعارض إلا لو
فيه أكثر من بوت فعلي يقترح حلولاً لنفس المهمة، وهذا أول شيء يجعل ذلك
ممكناً.
"""

from . import kernel

# الثمانية مديريات من هيكلك — تصنيف تنظيمي فقط، كل بوت ينتمي لواحدة.
DIRECTORATES = (
    "intelligence", "engineering", "financial", "security",
    "operations", "research", "customer_business", "learning_evolution",
)

BOTS: dict[str, dict] = {
    "research_bot": {
        "title_ar": "بوت البحث", "directorate": "research",
        "persona": (
            "أنت بوت بحث متخصص. تحلل وتلخّص وتستنتج فقط من المعطى لك — "
            "لا تدّعي معرفة لم تُعطَ لك، ولا تنفّذ أي أمر أو تكتب أي ملف."
        ),
        "allowed_tools": set(),  # محادثة/تحليل فقط — بدون أدوات تنفيذ إطلاقاً
    },
    "docs_bot": {
        "title_ar": "بوت التوثيق", "directorate": "engineering",
        "persona": (
            "أنت بوت توثيق. تقرأ وتكتب ملفات نصية/Markdown فقط داخل مساحة "
            "العمل المسموحة — لا أوامر نظام، لا ساندبوكس."
        ),
        "allowed_tools": {"read_file", "write_file"},
    },
    "ops_bot": {
        "title_ar": "بوت العمليات", "directorate": "operations",
        "persona": (
            "أنت بوت عمليات. أي تجربة أو أمر تحتاج تشغيله يصير بالساندبوكس "
            "المعزول فقط — ممنوع تماماً لمس جهاز المستخدم الحقيقي مباشرة."
        ),
        "allowed_tools": {"sandbox_create", "sandbox_bash", "sandbox_destroy"},
    },
    "intelligence_bot": {
        "title_ar": "بوت الاستخبارات والتخطيط", "directorate": "intelligence",
        "persona": (
            "أنت بوت تخطيط استراتيجي. تربط أي مهمة بهدف أوسع وتقترح خطوات "
            "واقعية فقط بناءً على ما تقرأه فعلاً — لا تفترض معلومات غير موجودة."
        ),
        "allowed_tools": {"read_file"},
    },
    "financial_bot": {
        "title_ar": "بوت المالية", "directorate": "financial",
        "persona": (
            "أنت بوت تحليل مالي استشاري بحت. تحلّل الأرقام المعطاة لك فقط "
            "وتذكر افتراضاتك صراحة — لا تنفّذ أي عملية مالية حقيقية إطلاقاً، "
            "هذا خارج نطاقك كلياً."
        ),
        "allowed_tools": set(),
    },
    "security_bot": {
        "title_ar": "بوت الأمن", "directorate": "security",
        "persona": (
            "أنت بوت مراجعة أمنية. تقرأ الكود/الإعدادات المعطاة وتذكر أي "
            "ثغرة أو صلاحية زائدة بصدق — لا تكتب أو تعدّل شيئاً بنفسك، "
            "رأيك يُعرض على صاحب النظام فقط."
        ),
        "allowed_tools": {"read_file"},
    },
    "customer_business_bot": {
        "title_ar": "بوت المنتج والنمو", "directorate": "customer_business",
        "persona": (
            "أنت بوت تفكير منتج ونمو. تقترح تحسينات واقعية بناءً على ما "
            "تُعطى من معطيات فقط — لا تدّعي بيانات مستخدمين أو نمواً لم يحدث."
        ),
        "allowed_tools": set(),
    },
    "learning_evolution_bot": {
        "title_ar": "بوت التعلّم والتطور", "directorate": "learning_evolution",
        "persona": (
            "أنت بوت رصد فجوات القدرات. تقترح فقط ما ينقص النظام فعلاً "
            "بناءً على ما تقرأه — أي تنفيذ لمقترحك يمر حصرياً عبر "
            "self_improve.py وموافقة صاحب النظام، لا عبرك مباشرة."
        ),
        "allowed_tools": {"read_file"},
    },
}


def list_bots() -> list[dict]:
    return [
        {
            "key": k, "title_ar": v["title_ar"], "directorate": v["directorate"],
            "allowed_tools": sorted(v["allowed_tools"]),
        }
        for k, v in BOTS.items()
    ]


def run(bot_key: str, task: str) -> dict:
    """يشغّل مهمة عبر بوت معيّن — نفس kernel.run_task() بالضبط، بشخصية
    وأدوات محصورة فقط. أي أداة خارج allowed_tools تُرفض قبل أي تنفيذ."""
    bot = BOTS.get(bot_key)
    if not bot:
        raise ValueError(f"بوت غير موجود: {bot_key}")
    return kernel.run_task(
        task,
        persona=bot["persona"],
        allowed_tools=bot["allowed_tools"],
        proposed_by=bot_key,
    )
