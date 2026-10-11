"""
غرفة نقاش جماعية — "موظفون" (بوتات) يتناقشون بصوت عالٍ، كل كلمة مسجّلة
ومرئية لك كاملة. أقرب حاجة لما وصفته ("قروب بين موظفين، الـAI يكلمون
بعض"): غرفة واحدة، نص فقط، بدون أي أثر جانبي — brain.ask() بشخصية كل
بوت مع المحادثة كاملة كسياق، لا أكثر.

هذا عمداً لا يفتح مسار تنفيذ جديد: أي قرار يخرج من النقاش يحتاج يمر عبر
bots.run()/decision.py العاديين بالضبط مثل أي مهمة ثانية — الغرفة
للنقاش والعرض فقط، لا تنفّذ ولا توافق على شيء بنفسها.

resolve() تضيف Conflict/Deadlock Resolution: تجمع توصية نهائية صريحة
من كل بوت (نص مباشر، لا تخمين دلالي من مخ ثانٍ قد يخطئ)، وتقارنها
حرفياً. توصيات متطابقة = توافق = طلب موافقة واحد. توصيات مختلفة = تعارض
حقيقي = طلب موافقة منفصل لكل توصية، صاحب النظام يختار — لا حسم تلقائي
لتعارض حقيقي أبداً، وهذا بالضبط معنى "الجدل حوله بين أدلة لا نقاش بلا
نهاية": النقاش محدود بعدد rounds، وأي خلاف يبقى محلولاً لا معلّقاً إلى
الأبد — إما باتفاق أو بإحالة صريحة لك.
"""

import json
import os
import re
import time

from . import bots, brain, decision, roles

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_ROOM_FILE = os.path.join(_DATA_DIR, "chatroom.json")

_DISCUSS_PROMPT = (
    "أنت بغرفة نقاش جماعية مع بوتات أخرى حول هذا الموضوع:\n{topic}\n\n"
    "المحادثة حتى الآن:\n{transcript}\n\n"
    "رد بفقرة قصيرة (سطرين كحد أقصى) برأيك أنت فقط كشخصيتك، بلا تكرار ما "
    "قيل. لو توافق رأياً سابقاً، قل ذلك بإيجاز بدل إعادة شرحه."
)

_FINAL_PROMPT = (
    "بناءً على النقاش أعلاه فقط، اكتب توصيتك النهائية بجملة واحدة قصيرة "
    "جداً، بالضبط بهذا الشكل ولا شيء غيره:\nالتوصية: <نص قصير>"
)

_FINAL_RE = re.compile(r"التوصية\s*:\s*(.+)", re.S)

_ARBITRATE_PROMPT = (
    "موضوع النقاش: {topic}\n\nالنقاش كامل:\n{transcript}\n\n"
    "الموظفون اختلفوا على هذه التوصيات:\n{options}\n\n"
    "اختر التوصية الأفضل بناءً على قوة الأدلة والحجج بالنقاش — لا بعدد "
    "المؤيدين فقط. اكتب بالضبط بهذا الشكل ولا شيء غيره:\n"
    "الاختيار: <رقم>\nالسبب: <سببك بإيجاز>"
)
_CHOICE_RE = re.compile(r"الاختيار\s*:\s*(\d+)")
_REASON_RE = re.compile(r"السبب\s*:\s*(.+)", re.S)


def _load_room() -> list[dict]:
    if not os.path.exists(_ROOM_FILE):
        return []
    with open(_ROOM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_room(messages: list[dict]) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _ROOM_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _ROOM_FILE)


def post(speaker: str, text: str) -> None:
    """speaker: اسم بوت من bots.BOTS، أو "owner" لرسالتك أنت."""
    messages = _load_room()
    messages.append({"speaker": speaker, "text": text, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    _save_room(messages)


def history(limit: int = 50) -> list[dict]:
    return _load_room()[-limit:]


def _transcript_text(messages: list[dict]) -> str:
    if not messages:
        return "(لا رسائل بعد)"
    return "\n".join(f"[{m['speaker']}] {m['text']}" for m in messages)


def discuss(bot_keys: list[str], topic: str, rounds: int = 1) -> list[dict]:
    """كل بوت بالترتيب يشوف المحادثة كاملة (بما فيها كلام بقية البوتات
    بنفس الجولة قبله) ويرد بشخصيته — عدة جولات = نقاش متراكم حقيقي، لا
    ردود مستقلة متوازية تتجاهل بعضها."""
    unknown = [k for k in bot_keys if k not in bots.BOTS]
    if unknown:
        raise ValueError(f"بوتات غير موجودة: {unknown}")

    post("owner", f"موضوع جديد للنقاش: {topic}")
    new_messages = []
    for _ in range(rounds):
        for bot_key in bot_keys:
            persona = bots.BOTS[bot_key]["persona"]
            transcript = _transcript_text(_load_room())
            prompt = f"{persona}\n\n{_DISCUSS_PROMPT.format(topic=topic, transcript=transcript)}"
            try:
                reply = brain.ask(prompt)
            except Exception as e:  # noqa: BLE001 — فشل رد بوت واحد لا يوقف النقاش، يُسجَّل بصدق لا يُخفى
                reply = f"(تعذّر رد {bot_key}: {type(e).__name__}: {e})"
            post(bot_key, reply)
            new_messages.append({"speaker": bot_key, "text": reply})
    return new_messages


def _final_recommendation(bot_key: str, topic: str) -> tuple[str, bool]:
    """ترجع (النص, failed). failed=True يعني فشل حقيقي باستدعاء المخ —
    لازم يُستبعد من مقارنة التوافق/التعارض، لا يُعامَل كتوصية فعلية."""
    persona = bots.BOTS[bot_key]["persona"]
    transcript = _transcript_text(_load_room())
    prompt = f"{persona}\n\nموضوع النقاش: {topic}\n\nالمحادثة:\n{transcript}\n\n{_FINAL_PROMPT}"
    try:
        reply = brain.ask(prompt)
    except Exception as e:  # noqa: BLE001 — فشل بوت بالتوصية النهائية يُسجَّل بصدق، لا يُعامَل كقرار
        return f"تعذّر الحصول على توصية {bot_key}: {type(e).__name__}: {e}", True
    match = _FINAL_RE.search(reply)
    return (match.group(1).strip() if match else reply.strip()), False


def _arbitrate(topic: str, options: list[tuple[str, list[str]]]) -> tuple[int, str] | None:
    """مدير القرارات (chief_decision_officer) يختار أفضل توصية من
    المتعارضة ويذكر السبب. None لو فشل أو رده ما ينفهم — وقتها يرجع
    resolve() للعرض القديم (كل الخيارات لك) بدل ما يخمّن."""
    numbered = "\n".join(
        f"{i}) {rec} — يؤيدها: {', '.join(supporters)}" for i, (rec, supporters) in enumerate(options, 1)
    )
    question = _ARBITRATE_PROMPT.format(
        topic=topic, transcript=_transcript_text(_load_room()[-40:]), options=numbered,
    )
    try:
        reply = roles.consult("chief_decision_officer", question)
    except Exception:  # noqa: BLE001
        return None
    choice = _CHOICE_RE.search(reply)
    if not choice or not 1 <= int(choice.group(1)) <= len(options):
        return None
    reason = _REASON_RE.search(reply)
    return int(choice.group(1)) - 1, (reason.group(1).strip() if reason else "").strip()


def resolve(bot_keys: list[str], topic: str, rounds: int = 1, proposed_by: str = "supreme_orchestrator") -> dict:
    """يدير نقاشاً عبر discuss()، يجمع توصية نهائية صريحة من كل بوت، ثم:

    - توصية موحّدة بين الكل (نص مطابق حرفياً) → Decision Engine: طلب
      موافقة واحد يحمل التوافق.
    - توصيات مختلفة → مدير القرارات (chief_decision_officer) يختار
      الأقوى حجةً ويذكر سببه، ويوصلك طلب موافقة واحد فيه اختياره
      والخيارات الثانية كاملة — أنت توافق أو ترفض، ما ينفّذ شي بنفسه.
      لو مدير القرارات فشل أو رده ما ينفهم: طلب موافقة منفصل لكل
      توصية (الطريقة القديمة)، أنت تختار — لا تخمين.
    - **فشل كل البوتات أو بعضها** (لا مخ متاح، مثلاً) لا يُعامَل أبداً
      كتوصية أو كتوافق — بوت فشل يُستبعد من المقارنة ويُذكر صراحة. لو
      فشل الكل، ترجع outcome="failed" بلا أي طلب موافقة مفتوح على
      فراغ — فشل الاتصال ليس قراراً بالإجماع.

    هذا فعلياً Deadlock Resolution أيضاً: النقاش محدود بـrounds (لا جدل
    بلا نهاية)، وأي تعارض يُحال لك صراحةً بدل ما يبقى معلّقاً أو يُحسم
    عشوائياً."""
    unknown = [k for k in bot_keys if k not in bots.BOTS]
    if unknown:
        raise ValueError(f"بوتات غير موجودة: {unknown}")

    discuss(bot_keys, topic, rounds=rounds)

    recommendations: dict[str, list[str]] = {}
    failed_bots: list[str] = []
    for bot_key in bot_keys:
        rec, failed = _final_recommendation(bot_key, topic)
        post(bot_key, f"{'فشل الحصول على توصية نهائية' if failed else 'التوصية النهائية'}: {rec}")
        if failed:
            failed_bots.append(bot_key)
            continue
        recommendations.setdefault(rec, []).append(bot_key)

    if not recommendations:
        return {"outcome": "failed", "failed_bots": failed_bots}

    if len(recommendations) == 1:
        rec_text, supporters = next(iter(recommendations.items()))
        result = decision.propose(
            what=f"نقاش جماعي: {topic}",
            why=f"توصية موحّدة من {', '.join(supporters)}: {rec_text}",
            proposed_by=proposed_by,
        )
        return {"outcome": "consensus", "recommendation": rec_text, "supporters": supporters, "failed_bots": failed_bots, **result}

    options = list(recommendations.items())
    arbitration = _arbitrate(topic, options)
    if arbitration is not None:
        # تعارض حقيقي → مدير القرارات يختار ويشرح، وأنت توافق أو ترفض
        # اختياره. الخيارات الثانية مذكورة كاملة بنص الطلب، ما تختفي.
        idx, reason = arbitration
        rec_text, supporters = options[idx]
        alternatives = [{"recommendation": r, "supporters": s} for i, (r, s) in enumerate(options) if i != idx]
        post("chief_decision_officer", f"حسمت التعارض: {rec_text}\nالسبب: {reason or '—'}")
        alt_text = "\n".join(f"- {a['recommendation']} (يؤيدها: {', '.join(a['supporters'])})" for a in alternatives)
        result = decision.propose(
            what=f"نقاش جماعي (حسمه مدير القرارات): {topic}",
            why=(
                f"اختار مدير القرارات توصية {', '.join(supporters)}: {rec_text}\n\n"
                f"السبب: {reason or '—'}\n\nالخيارات اللي ما اختارها:\n{alt_text}"
            ),
            proposed_by="chief_decision_officer",
        )
        return {
            "outcome": "arbitrated", "recommendation": rec_text, "supporters": supporters,
            "arbiter_reason": reason, "alternatives": alternatives, "failed_bots": failed_bots, **result,
        }

    proposals = []
    for rec_text, supporters in recommendations.items():
        others = len(recommendations) - 1
        result = decision.propose(
            what=f"نقاش جماعي (خيار متنافس): {topic}",
            why=(
                f"توصية من {', '.join(supporters)}: {rec_text}\n\n"
                f"(تعارض مع {others} توصية أخرى لنفس الموضوع — راجع كل الخيارات قبل الموافقة على أي واحد)"
            ),
            proposed_by=proposed_by,
        )
        proposals.append({"recommendation": rec_text, "supporters": supporters, **result})
    return {"outcome": "conflict", "proposals": proposals, "failed_bots": failed_bots}
