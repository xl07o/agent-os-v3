"""
التوجيه الذكي — هذا ما يجعل Supreme Orchestrator (المعرَّف بـroles.py)
مُستخدَماً فعلياً، لا شخصية موثّقة بلا استعمال. بدل ما تحفظ أوامر حرفية
("بوت docs_bot اكتب...")، تكتب طلبك عادي وهذا يقرر الوجهة الأنسب: بوت
محدد لو الطلب يطابق تخصصه بوضوح، أو المسار العام.

التوجيه نفسه بلا أي أثر جانبي مطلقاً — تصنيف خاطئ أسوأ حالة يرسل الطلب
للمسار العام (نفس ما كان يصير قبل وجود هذا الملف). لا يغيّر أي بوابة
أمان: بوت يُختار لسا محصور بأدواته (allowed_tools)، وأي أثر فعلي لسا
يحتاج موافقتك بالضبط زي قبل — التوجيه قرار "مين يتولى الطلب"، مو تفويضاً
بتنفيذه.
"""

import json
import re

from . import bots, brain, roles

_ROUTE_PROMPT = """البوتات المتاحة:
{bots_list}

الطلب: {task}

ردّك JSON فقط بهذا الشكل، بلا أي نص خارجي:
{{"route": "bot", "bot_key": "..."}}
أو
{{"route": "general"}}

اختر "bot" فقط لو الطلب ينتمي بوضوح لتخصص بوت واحد محدد بالقائمة. لو
الطلب عادي، أو عام، أو يحتاج أكثر من تخصص، أو غير واضح — اختر "general"
دائماً. الشك يحسم لصالح "general"."""


def _bots_list_text() -> str:
    return "\n".join(
        f"- {k}: {v['title_ar']} ({v['directorate']}) — أدوات: {sorted(v['allowed_tools']) or 'بلا، تحليل فقط'}"
        for k, v in bots.BOTS.items()
    )


def classify(task: str) -> dict:
    """يرجع {"route": "bot", "bot_key": "..."} أو {"route": "general"}.
    أي فشل بالمخ أو رد غير مفهوم → "general" دائماً (فشل آمن، لا تخمين)."""
    prompt = f"{roles.persona('supreme_orchestrator')}\n\n{_ROUTE_PROMPT.format(bots_list=_bots_list_text(), task=task)}"
    try:
        reply = brain.ask(prompt)
    except Exception:
        return {"route": "general"}

    match = re.search(r"\{.*\}", reply, re.S)
    if not match:
        return {"route": "general"}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"route": "general"}

    if data.get("route") == "bot" and data.get("bot_key") in bots.BOTS:
        return {"route": "bot", "bot_key": data["bot_key"]}
    return {"route": "general"}
