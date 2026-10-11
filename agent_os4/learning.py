"""
تعلّم حقيقي من الشغل — بدون ادّعاء "ذكاء يتطور لحاله".

اللي يصير فعلاً، وتقدر تفتحه وتقرأه بـObsidian:
- كل مهمة تنتهي لموظف ← درس قصير باسمه: وش نجح، وش فشل، وش رفضته أنت.
- كل موظف جديد ← دليل معرفة لدوره (يكتبه الـCEO وقت التوظيف، راجع ceo.py).
- كل مهمة جديدة لنفس الموظف ← دليله + أقرب دروسه للمهمة تنضاف لسياقه.

هذا "خبرة متراكمة" بشكل قابل للفحص والتصحيح: لو درس غلط، تحذفه من
Obsidian وينتهي أثره. ما فيه أوزان مخفية تتغيّر.
"""

import os
import re

from . import obsidian, textnorm

LESSON_PREFIX = "درس"
KNOWLEDGE_PREFIX = "معرفة"
_FOLDER = "wiki"


def _words(text: str) -> set[str]:
    return textnorm.words(text, min_len=2)


def _employee_notes(employee: str) -> list[tuple[str, str, float]]:
    folder = os.path.join(obsidian.VAULT_DIR, _FOLDER)
    if not os.path.isdir(folder):
        return []
    notes = []
    for prefix in (KNOWLEDGE_PREFIX, LESSON_PREFIX):
        tag = f"{prefix}[{employee}]"
        for fname in os.listdir(folder):
            if fname.startswith(tag) and fname.endswith(".md"):
                path = os.path.join(folder, fname)
                try:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        notes.append((prefix, f.read(), os.path.getmtime(path)))
                except OSError:
                    continue
    return notes


def _body(content: str) -> str:
    """بدون frontmatter وسطر العنوان — النص المفيد فقط."""
    content = re.sub(r"(?s)\A---\n.*?\n---\n", "", content).strip()
    return re.sub(r"\A# .*\n", "", content).strip()


def context_for(employee: str, task: str, lessons: int = 3) -> str:
    """دليل الموظف (لو موجود) + أقرب دروسه للمهمة الحالية."""
    notes = _employee_notes(employee)
    if not notes:
        return ""
    knowledge = [_body(c) for p, c, _ in notes if p == KNOWLEDGE_PREFIX]
    task_words = _words(task)
    past = sorted(
        ((len(task_words & _words(c)), mtime, _body(c)) for p, c, mtime in notes if p == LESSON_PREFIX),
        reverse=True,
    )[:lessons]
    parts = []
    if knowledge:
        parts.append("دليل دورك (من Obsidian):\n" + "\n\n".join(k[:2500] for k in knowledge[:1]))
    if past:
        parts.append("دروس من مهامك السابقة (من Obsidian):\n" + "\n".join(f"- {b[:400]}" for _, _, b in past))
    return "\n\n".join(parts)


def record(employee: str, task: str, verdict: str, results: list[dict]) -> str | None:
    """درس قصير من نتيجة فعلية — بدون استدعاء مدفوع، من النتائج نفسها."""
    succeeded = [r.get("tool", "") for r in results if r.get("ok")]
    failed = []
    for r in results:
        if r.get("ok"):
            continue
        error = r.get("error") or (r.get("result") or {}).get("error") or "فشل"
        failed.append(f"{r.get('tool', '')}: {str(error)[:200]}")
    body = f"**المهمة:** {task}\n**الحكم:** {verdict}\n"
    if succeeded:
        body += "**نجح:** " + "، ".join(succeeded) + "\n"
    if failed:
        body += "**فشل:**\n" + "\n".join(f"- {f}" for f in failed) + "\n"
    if any("رفض المستخدم" in f for f in failed):
        body += "\n**الدرس:** صاحب الشركة رفض هذا الإجراء — لا تقترحه بنفس الشكل مرة ثانية بدون سبب جديد.\n"
    elif failed:
        body += "\n**الدرس:** تحقق من سبب الفشل أعلاه قبل ما تعيد نفس الخطوة.\n"
    elif succeeded:
        body += "\n**الدرس:** هذا الأسلوب نجح لمهمة مشابهة.\n"
    return obsidian.write_note(_FOLDER, f"{LESSON_PREFIX}[{employee}] {task[:50]}", body,
                               tags=["os4", "lesson", employee])


def write_knowledge(employee: str, title: str, content: str) -> str | None:
    return obsidian.write_note(_FOLDER, f"{KNOWLEDGE_PREFIX}[{employee}] {title}", content,
                               tags=["os4", "knowledge", employee])
