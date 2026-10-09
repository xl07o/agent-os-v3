"""
obsidian_vault.py - مرآة الذاكرة لـ Obsidian
==============================================
يكتب كل ما يتعلّمه/يحفظه الوكيل كملفات markdown عادية بهيكل متوافق مع
Obsidian (نفس بنية "JARVIS OS": inbox/ projects/ content/ wiki/)، بحيث
لو فتحت مجلد الـvault كـObsidian vault تشوف كل شي مباشرة — بدون أي
API أو إضافة، مجرد ملفات نصية.

غير قاتل أبداً: أي فشل بالكتابة يُتجاهل بصمت (الذاكرة الأصلية
بـmemory_bank.json تبقى المصدر الموثوق، هذا مجرد انعكاس قابل للقراءة).

الاستخدام:
  import obsidian_vault
  obsidian_vault.write_note("wiki", "عنوان الملاحظة", "المحتوى...", tags=["تعلم"])
"""

import datetime
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = os.getenv("OBSIDIAN_VAULT_PATH") or os.path.join(BASE_DIR, "obsidian_vault")

# نفس بنية JARVIS OS بالضبط
FOLDERS = ("inbox", "projects", "content", "wiki")


def _safe_filename(title):
    """يبقي الحروف العربية (للقراءة)، يزيل فقط ما يكسر اسم ملف."""
    cleaned = re.sub(r'[\\/:*?"<>|\r\n]+', " ", str(title)).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)[:120]
    return cleaned or "ملاحظة"


def ensure_vault():
    """ينشئ بنية الـvault إن ما كانت موجودة. غير قاتل."""
    try:
        for folder in FOLDERS:
            os.makedirs(os.path.join(VAULT_DIR, folder), exist_ok=True)
        return True
    except Exception:
        return False


def write_note(folder, title, content, tags=None):
    """يكتب ملاحظة markdown بهيكل Obsidian (frontmatter + محتوى).

    folder: واحد من inbox/projects/content/wiki (أي قيمة أخرى تُحفظ بـinbox).
    يرجع مسار الملف أو None عند الفشل (غير قاتل أبداً).
    """
    if folder not in FOLDERS:
        folder = "inbox"
    if not ensure_vault():
        return None
    try:
        now = datetime.datetime.now()
        fname = _safe_filename(title) + ".md"
        path = os.path.join(VAULT_DIR, folder, fname)
        tag_line = " ".join(f"#{t}" for t in (tags or []) if t)
        frontmatter = (
            "---\n"
            f"created: {now.isoformat(timespec='seconds')}\n"
            f"source: agent-os-v3\n"
            "---\n\n"
        )
        body = f"# {title}\n\n{content}\n"
        if tag_line:
            body += f"\n{tag_line}\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(frontmatter + body)
        return path
    except Exception:
        return None


def mirror_memory_item(key, content, tags=None, importance=1.0):
    """نسخة مختصرة لـwrite_note مخصصة لعناصر memory_bank — تصنّف تلقائياً:
    أهمية عالية (>=0.8) → wiki (معرفة مستقرة)، غير ذلك → inbox (ملتقط خام)."""
    folder = "wiki" if importance >= 0.8 else "inbox"
    return write_note(folder, key, content, tags)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        ok = ensure_vault()
        print(f"الـvault جاهز: {VAULT_DIR}" if ok else "فشل إنشاء الـvault")
    else:
        p = write_note("inbox", "تجربة", "هذي ملاحظة تجريبية من obsidian_vault.py", tags=["تجربة"])
        print(f"كُتبت: {p}" if p else "فشلت الكتابة")
