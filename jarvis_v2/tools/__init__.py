# -*- coding: utf-8 -*-
"""سجلّ الأدوات — الأسماء تُربط بالدوال الحقيقية؛ التنفيذ الفعلي فقط (لا محاكاة)."""
from . import fs, exec_, web, sandbox

TOOLS = {
    "read_file": fs.read_file,
    "write_file": fs.write_file,
    "edit_file": fs.edit_file,
    "glob": fs.glob,
    "grep": fs.grep,
    "bash": exec_.run_bash,
    "fetch_url": web.fetch_url,
    "sandbox_create": sandbox.sandbox_create,
    "sandbox_bash": sandbox.sandbox_bash,
    "sandbox_screenshot": sandbox.sandbox_screenshot,
    "sandbox_click": sandbox.sandbox_click,
    "sandbox_type": sandbox.sandbox_type,
    "sandbox_destroy": sandbox.sandbox_destroy,
    "sandbox_list": sandbox.sandbox_list,
}

# أوامر تحتاج إذنًا عند سياسة ask. sandbox_create/bash/click/type/destroy تغيّر
# حالة حقيقية (لو داخل sandbox معزول لا على الجهاز) — نفس حذر bash/write_file.
# sandbox_screenshot/sandbox_list للقراءة فقط، لا تحتاج إذناً.
DESTRUCTIVE = {
    "bash", "write_file", "edit_file",
    "sandbox_create", "sandbox_bash", "sandbox_click", "sandbox_destroy", "sandbox_type",
}

DESCRIPTIONS = {
    "read_file": "قراءة ملف (path)",
    "write_file": "كتابة/تجاوز ملف داخل الجذر (path, content)",
    "edit_file": "استبدال نص داخل ملف (path, old, new)",
    "glob": "بحث ملفات بنمط (pattern, [dir])",
    "grep": "بحث نص في ملفات (pattern, [path], [include])",
    "bash": "أمر PowerShell حقيقي (command) — قد يكون خطيرًا",
    "fetch_url": "جلب صفحة/JSON من عنوان (url)",
    "sandbox_create": "أنشئ sandbox Daytona معزول للتحكم الحاسوبي ([label]) — يرجع sandbox_id",
    "sandbox_bash": "نفّذ أمر bash داخل sandbox معزول (sandbox_id, command)",
    "sandbox_screenshot": "لقطة شاشة من داخل sandbox (sandbox_id)",
    "sandbox_click": "كليك داخل sandbox (sandbox_id, x, y)",
    "sandbox_type": "اكتب نصاً داخل sandbox (sandbox_id, text)",
    "sandbox_destroy": "دمّر sandbox بعد الانتهاء (sandbox_id)",
    "sandbox_list": "اعرض sandboxes النشطة حالياً",
}


def exists(name):
    return name in TOOLS


def run(name, args, approver=None):
    """تنفيذ أداة مع سيطرة إذن عبر approver (func(tool, args) -> bool). يرجع dict نتيجة."""
    if name not in TOOLS:
        return {"ok": False, "error": "أداة غير معروفة: %s" % name}
    if name in DESTRUCTIVE and approver:
        if not approver(name, args):
            return {"ok": False, "error": "رُفض الأمر من المستخدم", "denied": True}
    try:
        res = TOOLS[name](args)
        if not isinstance(res, dict):
            res = {"ok": True, "output": str(res)}
        res.setdefault("ok", True)
        return res
    except PermissionError as ex:
        return {"ok": False, "error": str(ex)}
    except Exception as ex:
        return {"ok": False, "error": "%s: %s" % (type(ex).__name__, str(ex)[:300])}