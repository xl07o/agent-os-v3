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


# أوامر لا رجعة فيها إطلاقاً — محظورة حتى بوضع الوصول الكامل للجهاز حتى
# لو وافقت عليها بالخطأ. هذي طبقة حماية إضافية، لا بديل عن موافقتك:
# الموافقة الصريحة لكل أمر تبقى خط الدفاع الأساسي بوضع PC.
PC_FORBIDDEN_PATTERNS = (
    "rm -rf /", "rm -rf ~", "rm -rf *", "rm -rf .",
    "format ", "mkfs", "dd if=", ":(){ :|:& };:",
    "> /dev/sd", "chmod -R 777 /", "del /s /q c:\\",
    "rd /s /q c:\\", "shutdown", "reboot", "diskpart",
)


def is_safe_pc_command(cmd: str) -> tuple[bool, str]:
    """وضع الوصول الكامل للجهاز: قائمة حظر لا قائمة سماح — موافقتك
    الصريحة على نص الأمر الكامل قبل أي تنفيذ هي الحماية الحقيقية هنا،
    لا صندوق رملي ولا قائمة بيضاء ضيقة. هذي فقط حماية من كوارث معروفة
    لا رجعة فيها."""
    lowered = cmd.lower().replace(" ", "")
    for pattern in PC_FORBIDDEN_PATTERNS:
        if pattern.replace(" ", "") in lowered:
            return False, f"أمر مدمّر معروف محظور حتى بموافقتك: يحتوي نمط '{pattern}'"
    return True, "يحتاج مراجعتك الصريحة — لا قائمة بيضاء بوضع الوصول الكامل"


def pc_access_enabled() -> bool:
    """وضع الوصول الكامل للجهاز معطّل افتراضياً — يحتاج تفعيلاً صريحاً
    بـ.env، نفس فلسفة مفاتيح API: لا يُفترض الوصول الخطير صامتاً أبداً."""
    import os as _os
    return _os.environ.get("OS4_ALLOW_PC_ACCESS", "").strip() == "1"


def validate_pc_path(path: str) -> tuple[bool, str]:
    """وضع الوصول الكامل للجهاز: لا حصر بمجلد واحد — هذا بالضبط
    المطلوب. الحماية هنا محدودة عمداً لملفات .env وحل الروابط الرمزية؛
    الحماية الحقيقية هي موافقتك الصريحة على كل كتابة قبل ما تصير، لا
    صندوق رملي يحصر المسار."""
    real_target = os.path.realpath(path)
    if os.path.basename(real_target).startswith(".env"):
        return False, "ملفات .env محظورة حتى بوضع الوصول الكامل"
    return True, "يحتاج مراجعتك"
