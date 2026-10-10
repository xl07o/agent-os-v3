"""
ترتيب الذاكرة بعد كل جلسة: يجمع ما تراكم بـmemory.json (ذاكرة عمل مؤقتة)
ويؤرشفه كملاحظة Obsidian واحدة منظمة — Obsidian يصير الأرشيف الدائم، لا
memory.json. لو فيه مخ متاح يلخّص، ولو ما فيه (كحال هذا الصندوق بلا
مفتاح) يكتب القائمة الخام بصدق بدون أي تلخيص مزعوم لم يحدث فعلاً.
"""

import time

from . import brain, memory, obsidian

_SUMMARY_PROMPT = (
    "لخّص هذه الذكريات بنقاط قصيرة بالعربي، بصدق وبدون إضافة أي شيء لم "
    "يُذكر فعلاً:\n\n{items}"
)


def tidy() -> dict:
    entries = memory.drain()
    if not entries:
        return {"archived": 0}

    items_text = "\n".join(f"- [{e['source']}] {e['text']}" for e in entries)

    summary = None
    try:
        summary = brain.ask(_SUMMARY_PROMPT.format(items=items_text))
    except Exception:
        pass  # لا مخ متاح أو فشل — نكتب الخام بصدق بدل الادّعاء بتلخيص

    body = (f"{summary}\n\n---\n" if summary else "") + f"**خام ({len(entries)} عنصر):**\n\n{items_text}"
    title = f"ذاكرة {time.strftime('%Y-%m-%d %H-%M')}"
    # "inbox" لأنها لقطة خام غير مُراجَعة بشرياً — نفس منطق mirror_memory_item
    # القديم (wiki مخصّصة لمعرفة مستقرة مؤكّدة الأهمية، لا لتفريغ جلسة).
    obsidian.write_note("inbox", title, body, tags=["os4", "memory"])
    return {"archived": len(entries), "summarized": summary is not None}
