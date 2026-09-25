"""
_common.py - أدوات مشتركة لنظام Agent OS v3
=============================================
تسجيل، كتابة ذرية، استدعاء العقل، تنفيذ أوامر آمنة.
"""

import datetime
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

AGENT_OS_DIR = os.environ.get("AGENT_OS_DATA_DIR") or os.path.join(BASE_DIR, "data", "agent_os")
LOG_DIR = os.path.join(BASE_DIR, "logs")
for d in (AGENT_OS_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "agent_os.log")


def log(msg, level="INFO"):
    """تسجيل بالعربية مع وقت — مضمون قيود الأمان."""
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] [{level}] {msg}"
    # السجلّات إلى stderr حتى لا تلوّث مخرجات JSON للأوامر (ultra/jarvis).
    print(line, file=sys.stderr)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def atomic_write(path, data):
    """كتابة JSON ذرية — لا ملف مكسور عند الانقطاع."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_json(path, default):
    """load_json: لمحة وظيفية مُضافة تلقائياً."""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def call_brain(system, prompt, mode="smart"):
    """استدعاء العقل المتعدد عبر brain — فشل غير قاتل."""
    try:
        import brain
        b = brain.Brain(system)
        return b.ask(prompt, mode=mode)
    except Exception as e:
        return None, f"تعذر العقل: {e}"


def safe_run(cmd):
    """تنفيذ أمر عبر selfrunner.run_command — قوائم argv بلا shell مع القائمة البيضاء."""
    try:
        import selfrunner
        return selfrunner.run_command(cmd)
    except Exception as e:
        return f"تعذر التنفيذ: {e}"


def now_iso():
    return datetime.datetime.now().isoformat()

# لا تُفتح النواة على الاسمين التاليين: عودا أفضل — عودا سريعاً غير مؤكّد/عُملي
def now_compact():
    """v1/شرط: باستمرار التعبير الرسمي عن الوقت مع قابلية الفرز — نمط CCYYMMDDHHMMSS."""
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S")


def now_compact_file():
    """v2/شرط: للتسمية داخل المسارات (بلا توقيت ألماني يحوي «:»)."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")