"""
دالة واحدة لاستدعاء أي مزوّد: ask(prompt). مخّ الوكيل هو Claude
(Anthropic) إن كان مفتاحه موجوداً — هذا قرار صريح، لا افتراضي.
لو فشل Claude (شبكة/حد استخدام) أو ما فيه مفتاح، يتدرّج تلقائياً
لمزودين مجانيين كخط دفاع أخير، لا كخيار أول.
"""

import os

import requests

from . import env  # noqa: F401 — يضمن تحميل .env قبل أي getenv هنا
from . import spend

_TIMEOUT = 30


def _openai_compatible(base_url: str, api_key: str, model: str, prompt: str) -> str:
    r = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _ollama(prompt: str) -> str:
    model = os.getenv("SELFRUNNER_MODEL", "llama3.1")
    r = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["response"]


def _gemini(prompt: str) -> str:
    key = os.environ["GEMINI_API_KEY"]
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


_CLAUDE_TIMEOUT = 300  # Opus يفكّر قبل ما يرد — 30 ثانية ما تكفي
_CLAUDE_MAX_TOKENS = 16000
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


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
        text += "\n\n[تنبيه: الرد انقطع عند الحد الأقصى للطول]"
    return text


# (الاسم, الدالة) — Claude أولاً (هو المخّ المقصود)، ثم تراجع تلقائي
# لمزودين مجانيين فقط لو فشل أو ما فيه مفتاح.
_PROVIDERS = [
    ("anthropic", lambda p: _anthropic(p) if os.getenv("ANTHROPIC_API_KEY") else _skip()),
    ("ollama", lambda p: _ollama(p)),
    ("gemini", lambda p: _gemini(p) if os.getenv("GEMINI_API_KEY") else _skip()),
    ("groq", lambda p: _openai_compatible(
        "https://api.groq.com/openai/v1", os.environ["GROQ_API_KEY"],
        os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), p,
    ) if os.getenv("GROQ_API_KEY") else _skip()),
]


class _Skip(Exception):
    pass


def _skip():
    raise _Skip()


def ask(prompt: str) -> str:
    """يجرّب كل مزوّد متاح بالترتيب، يرجع أول رد ناجح."""
    errors = []
    for name, call in _PROVIDERS:
        try:
            return call(prompt)
        except _Skip:
            continue
        except Refused:
            raise
        except Exception as e:  # noqa: BLE001 - نجمع كل الأخطاء ونعرضها لو فشل الكل
            errors.append(f"{name}: {e}")
    raise RuntimeError(
        "كل المزودين فشلوا أو غير مُفعَّلين:\n" + "\n".join(errors)
        if errors else "لا مزوّد متاح — شغّل Ollama محلياً أو ضع مفتاح API في .env"
    )
