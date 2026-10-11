"""
تطبيع خفيف للنص العربي قبل مطابقة الكلمات — بدونه "المبيعات" ما تطابق
"مبيعات"، و"بالشهر" ما تطابق "الشهر". يشيل التشكيل والتطويل، يوحّد
الألف (أ إ آ ← ا) والتاء المربوطة والألف المقصورة، ويشيل أدوات التعريف
الملتصقة (ال، بال، وال، كال، فال، لل) لو بقي من الكلمة 3 أحرف أو أكثر.
مو "فهم دلالي" — مطابقة كلمات أدق، بس.
"""

import re

_TASHKEEL = re.compile(r"[ً-ْٰـ]")
_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"})
_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")


def _norm(word: str) -> str:
    word = word.lower().translate(_LETTERS)
    for prefix in _PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 3:
            return word[len(prefix):]
    return word


def words(text: str, min_len: int = 3) -> set[str]:
    clean = _TASHKEEL.sub("", text or "")
    return {w for w in (_norm(t) for t in re.findall(r"\w+", clean)) if len(w) >= min_len}
