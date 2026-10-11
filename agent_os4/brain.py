"""
المخ: Claude فقط (Anthropic) — دالة وحدة ask(prompt).

ما فيه مزودين ثانيين ولا تراجع لموديلات مجانية: لو Claude ما قدر يرد
(ما فيه مفتاح، خلص السقف، مشكلة اتصال)، يطلع لك خطأ واضح بالعربي بدل
ما يرد موديل ثاني بالخفاء. الشي الوحيد اللي ينتقل: fallbacks="default"
من Anthropic نفسها — لو مصنّف الأمان رفض، تعيد الطلب على موديل Claude
ثاني بنفس الاستدعاء. يعني دايماً Claude.
"""

import os

from . import env  # noqa: F401 — يضمن تحميل .env قبل أي getenv هنا
from . import spend

_CLAUDE_TIMEOUT = 300  # Opus يفكّر قبل ما يرد — 30 ثانية ما تكفي
_CLAUDE_MAX_TOKENS = 16000
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
# يُلحق بالرد لو انقطع عند الحد الأقصى — اللي يولّد كود يفحصه ويرفض
# الرد كامل بدل ما يحفظ ملفاً مبتوراً.
TRUNCATED_MARKER = "[تنبيه: الرد انقطع عند الحد الأقصى للطول]"


class Refused(Exception):
    """Claude (وموديل الاحتياط حقه) رفض الطلب لأسباب أمان. ما نحوّله
    لمزوّد ثاني — هذا يكون تحايل على الرفض، مو تراجع شبكة."""


def _anthropic(prompt: str) -> str:
    # استيراد متأخر: لو الحزمة مو منزّلة، Claude يُتخطّى بخطأ واضح
    # والمزودين الثانيين يكملون — بدل ما ينهار brain.py كامل.
    import anthropic

    model = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
    reservation = spend.reserve(model, prompt, _CLAUDE_MAX_TOKENS)
    try:
        client = anthropic.Anthropic(timeout=_CLAUDE_TIMEOUT, max_retries=2)
        # stream + get_final_message: يمنع انقطاع الطلبات الطويلة.
        # fallbacks="default": لو رفض مصنّف الأمان، Anthropic تعيد
        # الطلب على الموديل الاحتياطي المناسب داخل نفس الاستدعاء.
        with client.beta.messages.stream(
            model=model,
            max_tokens=_CLAUDE_MAX_TOKENS,
            betas=[_FALLBACK_BETA],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response = stream.get_final_message()
    except Exception:
        spend.release(reservation)
        raise
    spend.record(reservation, model, getattr(response, "model", model), response.usage)

    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None) or "غير محدد"
        raise Refused(f"Claude رفض الطلب (التصنيف: {category})")

    # الرد ممكن يبدأ ببلوك تفكير — نجمع بلوكات النص فقط، مو content[0].
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise RuntimeError(f"Claude رجّع رد بلا نص (stop_reason={response.stop_reason})")
    if response.stop_reason == "max_tokens":
        text += "\n\n" + TRUNCATED_MARKER
    return text


# أخطاء حزمة anthropic بأسماء أصنافها ← رسالة واضحة لك
_ERRORS = {
    "AuthenticationError": "مفتاح Claude غلط أو منتهي — تأكد من ANTHROPIC_API_KEY بملف .env",
    "PermissionDeniedError": "مفتاح Claude ما عنده صلاحية لهذا الموديل — تأكد من حسابك أو غيّر ANTHROPIC_MODEL",
    "NotFoundError": "الموديل مو موجود — تأكد من ANTHROPIC_MODEL بملف .env (مثلاً claude-opus-5-5)",
    "RateLimitError": "وصلت حد الاستخدام عند Anthropic — جرّب بعد شوي",
    "APIConnectionError": "ما قدرت أوصل لـClaude — تأكد من الإنترنت",
    "APITimeoutError": "Claude تأخر بالرد أكثر من 5 دقايق — جرّب مرة ثانية",
    "InternalServerError": "مشكلة مؤقتة عند Anthropic — جرّب بعد شوي",
}


def ask(prompt: str) -> str:
    """يسأل Claude ويرجع نص الرد. أي فشل = خطأ واضح، بدون بديل."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ما فيه ANTHROPIC_API_KEY بملف .env — agent_os4 يشتغل بـClaude بس")
    try:
        return _anthropic(prompt)
    except (Refused, spend.BudgetExceeded):
        raise
    except Exception as e:  # noqa: BLE001 — نترجم الخطأ لرسالة مفهومة ونحتفظ بالأصل
        message = _ERRORS.get(type(e).__name__)
        if message:
            raise RuntimeError(f"{message} ({type(e).__name__})") from e
        raise
