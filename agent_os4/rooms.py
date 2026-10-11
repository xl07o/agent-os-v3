"""
غرف دردشة منفصلة — غرفة لكل بوت/مديرية من الثمانية بـbots.py + غرفة
تنفيذية واحدة (الإدارة العليا/مكتب صاحب النظام). نفس فكرة chatroom.py
بالضبط (سجل رسائل JSON بسيط، بلا أثر جانبي من هذا الملف نفسه) لكن لكل
غرفة خيطها الخاص بدل غرفة جماعية واحدة — عشان تقدر تراقب كل قسم لحاله،
أو كل الأقسام مجتمعة عبر recent_all().

هذا الملف لا يقرر شيء ولا ينفّذ أداة بنفسه — فقط يخزّن ويعرض. التنفيذ
الفعلي يبقى حصراً عبر kernel.run_task()/bots.run() بالضبط مثل أي مهمة
ثانية، بنفس بوابة الموافقة الموحّدة.
"""

import json
import os
import time

from . import bots, sessions

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_ROOMS_FILE = os.path.join(_DATA_DIR, "rooms.json")

EXECUTIVE = "executive"
_EXECUTIVE_TITLE = "الإدارة العليا — مكتب صاحب النظام"


def is_valid(room: str) -> bool:
    return room == EXECUTIVE or room in bots.BOTS


def list_rooms() -> list[dict]:
    """كل الغرف المتاحة — التنفيذية أولاً، ثم بوت لكل مديرية."""
    rooms = [{"key": EXECUTIVE, "title_ar": _EXECUTIVE_TITLE, "directorate": None}]
    rooms += [
        {"key": k, "title_ar": v["title_ar"], "directorate": v["directorate"]}
        for k, v in bots.BOTS.items()
    ]
    return rooms


def _load() -> list[dict]:
    if not os.path.exists(_ROOMS_FILE):
        return []
    with open(_ROOMS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(entries: list[dict]) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _ROOMS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _ROOMS_FILE)


def post(room: str, speaker: str, text: str) -> None:
    """speaker: "owner" لرسالتك أنت، أو مفتاح الغرفة نفسه (اسم بوت أو
    "executive") لرد الطرف الآخر."""
    if not is_valid(room):
        raise ValueError(f"غرفة غير معروفة: {room}")
    entries = _load()
    at = time.strftime("%Y-%m-%d %H:%M:%S")
    entries.append({"room": room, "speaker": speaker, "text": text, "at": at})
    _save(entries)
    try:
        sessions.index(room, speaker, text, at)  # بحث بكل المحادثات — راجع sessions.py
    except Exception:  # noqa: BLE001 — فشل الفهرسة ما يضيّع الرسالة نفسها
        pass


def history(room: str, limit: int = 60) -> list[dict]:
    if not is_valid(room):
        raise ValueError(f"غرفة غير معروفة: {room}")
    return [e for e in _load() if e["room"] == room][-limit:]


def recent_all(limit: int = 40) -> list[dict]:
    """للمراقبة: آخر الرسائل من كل الغرف مجتمعة بترتيبها الزمني الحقيقي
    — لا فلترة لغرفة واحدة. هذا بالضبط ما يلزم لـ"أراقب محادثاتهم"."""
    return _load()[-limit:]
