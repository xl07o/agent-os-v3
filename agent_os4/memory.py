"""
ذاكرة بسيطة وصادقة: تشابه كلمات مفتاحية، لا "embeddings" ولا أي وعد
بفهم دلالي لا يوجد فعلاً. إن احتجنا بحثاً دلالياً حقيقياً لاحقاً، يُضاف
كطبقة اختيارية فوق recall() بدون كسرها — ليس الآن.
"""

import json
import os
import re
import time

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_FILE = os.path.join(_DATA_DIR, "memory.json")


def _load() -> list[dict]:
    if not os.path.exists(_FILE):
        return []
    with open(_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(entries: list[dict]) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _FILE)


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def count() -> int:
    return len(_load())


def drain() -> list[dict]:
    """يرجع كل الذكريات الحالية ويفضي الملف — تُستخدم فقط عند أرشفتها
    بمكان دائم (Obsidian)، لا لحذفها بلا أرشفة."""
    entries = _load()
    _save([])
    return entries


def remember(text: str, source: str = "chat") -> None:
    entries = _load()
    entries.append({
        "text": text,
        "source": source,
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save(entries)


def recall(query: str, limit: int = 5) -> list[str]:
    """ترجع أقرب النصوص المخزَّنة لاستعلام query بتشابه كلمات بسيط."""
    q_words = _words(query)
    if not q_words:
        return []
    scored = []
    for e in _load():
        overlap = len(q_words & _words(e["text"]))
        if overlap:
            scored.append((overlap, e["text"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:limit]]
