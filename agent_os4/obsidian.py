"""
جسر رفيع لـ obsidian_vault.py الموجود بجذر المشروع — جرّبته حياً ويشتغل
صحيح، فلا داعي لإعادة كتابته. مجرد استيراد + دالة بحث واحدة أضفتها هنا
(لا بـobsidian_vault.py نفسه — ذاك ملف مشترك مع agent-os-v3 القديم،
أعدل عليه أقل ما يمكن).

search() تمشي على نفس فلسفة memory.recall() بالضبط: تشابه كلمات مفتاحية
حقيقي، لا "embeddings" ولا فهم دلالي وهمي. تقرأ ملفات الـvault مباشرة
من القرص — بما فيها كل مجلدات JARVIS الأربعة (inbox/projects/content/
wiki)، يعني عملياً كل تاريخ كل مهمة من كل بوت/قسم (kernel.py يكتب ملاحظة
Obsidian لكل مهمة تنتهي، proposed_by أي بوت كان) — هذا بالضبط ما يخلي
"المراجع المستقل" له خبرة متراكمة حقيقية بدل رأي مجرّد بلا سياق.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from obsidian_vault import FOLDERS, VAULT_DIR, write_note  # noqa: E402,F401

from . import textnorm  # noqa: E402


def _words(text: str) -> set[str]:
    return textnorm.words(text, min_len=2)


def search(query: str, limit: int = 5) -> list[dict]:
    """بحث حقيقي عبر كل ملاحظات الـvault — يرجع أقرب limit ملاحظة
    لـquery بعدد الكلمات المشتركة. لا فهرس منفصل يحتاج تزامناً، يقرأ
    الملفات كما هي كل استدعاء — حجم الـvault هنا صغير بما يكفي."""
    q_words = _words(query)
    if not q_words or not os.path.isdir(VAULT_DIR):
        return []
    scored: list[tuple[int, str, str, str]] = []
    for folder in FOLDERS:
        folder_path = os.path.join(VAULT_DIR, folder)
        if not os.path.isdir(folder_path):
            continue
        for fname in os.listdir(folder_path):
            if not fname.endswith(".md"):
                continue
            try:
                with open(os.path.join(folder_path, fname), "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                continue
            overlap = len(q_words & _words(content))
            if overlap:
                scored.append((overlap, folder, fname, content))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"folder": folder, "file": fname, "excerpt": content[:400]}
        for _, folder, fname, content in scored[:limit]
    ]
