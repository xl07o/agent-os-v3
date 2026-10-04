"""
priority_manager.py - إدارة الأولويات بناءً على المحادثات (v1.0)
==================================================================
يقرأ أدوار المستخدم في المحادثة، يستخرج منها طلبات/مهام محتملة،
ويقدّر استعجالها من كلمات صريحة استخدمها المستخدم نفسه في نصه (لا تخمين
من الوكيل، ولا تحليل نوايا معقّد). النتيجة تُضاف إلى roi_brain كمقترح
أولوية يراجعه المستخدم — لا تنفيذ تلقائي لأي شيء من هنا.

الاستخدام:
  from priority_manager import process_conversation, priority_brief
  process_conversation(brain_session.history)
  print(priority_brief())
"""

import roi_brain
from memory_bank import _similarity

# ترتيب تنازلي يهم: أول تطابق كلمة أعلى استعجالاً يفوز
URGENCY_KEYWORDS = [
    ("عاجل", 1.0), ("ضروري جداً", 0.95), ("ضروري", 0.9),
    ("اليوم بالذات", 0.9), ("الحين", 0.85), ("اليوم", 0.8), ("بسرعة", 0.8),
    ("مهم جداً", 0.9), ("مهم", 0.65),
    ("لما تقدر", 0.25), ("مو مستعجل", 0.15), ("مب مستعجل", 0.15),
]

TASK_VERBS = [
    "سوّي", "سوي", "ابي", "أبي", "ابغى", "أبغى", "ساعدني",
    "اعمل", "أعمل", "جهز", "جهّز", "طبق", "طبّق", "راجع", "حل",
    "حلّ", "صمم", "صمّم", "ابحث", "أبحث", "اكتب", "أكتب",
]

MIN_TASK_LEN = 8
DUPLICATE_THRESHOLD = 0.6


def _estimate_urgency(text: str) -> float:
    """يقرأ كلمات استعجال صريحة في النص نفسه فقط — بدون تخمين."""
    for kw, score in URGENCY_KEYWORDS:
        if kw in text:
            return score
    return 0.5  # محايد افتراضياً عند غياب أي إشارة صريحة


def _looks_like_task(text: str) -> bool:
    text = text.strip()
    if len(text) < MIN_TASK_LEN:
        return False
    return any(v in text for v in TASK_VERBS)


def _is_duplicate(name: str, existing_names: list) -> bool:
    return any(_similarity(name, existing) >= DUPLICATE_THRESHOLD for existing in existing_names)


def extract_from_message(text: str, tags: list = None):
    """يحلل رسالة مستخدم واحدة. يرجع المهمة المضافة، أو None إن لم تبدُ
    كطلب واضح أو كانت مكررة لمهمة معلّقة فعلاً."""
    text = (text or "").strip()
    if not _looks_like_task(text):
        return None

    pending_names = [t["name"] for t in roi_brain.get_ranked_tasks(50)]
    name = text[:120]
    if _is_duplicate(name, pending_names):
        return None

    urgency = _estimate_urgency(text)
    return roi_brain.add_task(
        name,
        value=0,
        time_hours=1,
        probability=0.6,
        urgency=urgency,
        risk=0.3,
        cost=0,
        tags=(tags or []) + ["from_conversation"],
    )


def process_conversation(messages: list) -> list:
    """messages: [{"role": "user"/"assistant", "content": str}, ...].
    يعالج أدوار المستخدم فقط ويرجع قائمة المهام المضافة فعلياً (بدون التكرارات)."""
    added = []
    for m in messages or []:
        if m.get("role") != "user":
            continue
        task = extract_from_message(m.get("content", ""))
        if task:
            added.append(task)
    return added


def priority_brief() -> str:
    """نفس ترتيب roi_brain.morning_brief لكن مع توضيح صريح أنها مقترحات
    للمراجعة، لا أوامر تُنفَّذ تلقائياً."""
    body = roi_brain.morning_brief()
    return body + "\n\n> هذه مقترحات أولوية مستخرجة من محادثاتك، تُعرض للمراجعة ولا تُنفَّذ تلقائياً."


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "brief":
        print(priority_brief())
    else:
        print("الاستخدام: python priority_manager.py brief")
