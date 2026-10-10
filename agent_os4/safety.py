"""
القاعدة الوحيدة لهذا الملف: مصدر حقيقة واحد لِـ"هل هذا الأمر/المسار آمن؟".
agent-os-v3 كرر هذا المنطق في selfrunner.py و computer_control.py بقائمتين
منفصلتين — أي تحديث أمني كان لازم يصير بمكانين، ونسيان أحدهما يفتح ثغرة
بصمت. هنا نسخة واحدة فقط، ويستوردها أي كود يحتاجها.
"""

import os
import shlex

SAFE_COMMANDS = {"python", "python3", "pip", "git", "node", "npm", "ls", "cat", "echo"}
FORBIDDEN_COMMANDS = {"curl", "wget", "sh", "bash", "cmd", "powershell", "pwsh", "ssh", "nc"}
EVAL_FLAGS = {"-c", "-e", "--eval", "-m"}
FORCE_FLAGS = {"-rf", "-fr", "--recursive", "--force"}


def is_safe_command(cmd: str) -> tuple[bool, str]:
    """يرفض ربط الأوامر، المفسرات الممنوعة، وأعلام التنفيذ الحر/القوة."""
    if any(tok in cmd for tok in ("&&", "||", ";", "|", "`", "$(")):
        return False, "ربط أوامر ممنوع"
    try:
        parts = shlex.split(cmd)
    except ValueError as e:
        return False, f"صياغة أمر غير صالحة: {e}"
    if not parts:
        return False, "أمر فارغ"
    main = parts[0]
    if main in FORBIDDEN_COMMANDS:
        return False, f"'{main}' ممنوع نهائياً"
    if main not in SAFE_COMMANDS:
        return False, f"'{main}' ليس في القائمة البيضاء"
    if any(p in EVAL_FLAGS for p in parts[1:]):
        return False, "تنفيذ كود حر عبر مفسّر ممنوع"
    if any(p in FORCE_FLAGS for p in parts[1:]) and main != "git":
        return False, "علم قوة/حذف قسري ممنوع"
    return True, "آمن"


def validate_path(path: str, base_dir: str) -> tuple[bool, str]:
    """يرفض أي مسار يهرب خارج base_dir، حتى عبر روابط رمزية."""
    real_base = os.path.realpath(base_dir)
    real_target = os.path.realpath(path)
    if os.path.commonpath([real_base, real_target]) != real_base:
        return False, f"المسار يخرج عن '{base_dir}'"
    if os.path.basename(real_target).startswith(".env"):
        return False, "ملفات .env محظورة"
    return True, "آمن"
