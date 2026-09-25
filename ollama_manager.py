"""
ollama_manager.py - مدير Ollama الذكي (v2.0)
=============================================
إدارة نماذج Ollama:
  - فحص النماذج المتاحة
  - تحميل نماذج مفيدة
  - إدارة ذكية للنماذج
"""

import json
import re
import sys
import os
import subprocess

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _safe_model_name(name):
    """تعقيم اسم النموذج — أحرف آمنة فقط (وليست أوامر/مسارات)."""
    if not isinstance(name, str):
        raise ValueError("اسم النموذج غير صالح")
    if re.fullmatch(r"[A-Za-z0-9_.:\-/]{1,128}", name):
        return name
    raise ValueError("اسم النموذج يحتوي أحرفاً غير مسموحة")

OLLAMA_URL = "http://localhost:11434"
RECOMMENDED_MODELS = {
    "llama3.1": "الشامل - مناسب لأغلب المهام",
    "qwen2.5:7b": "قوي بالبرمجة",
    "mistral:7b": "ردود سريعة",
    "phi3:mini": "خفيف وسريع",
}

import urllib.request


def is_ollama_running():
    """فحص إذا كان Ollama يعمل."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
            return True, data
    except Exception:
        return False, None


def list_models():
    """قائمة النماذج المتاحة محلياً."""
    running, data = is_ollama_running()
    if not running:
        return []
    return [m.get("name", "") for m in data.get("models", [])]


def pull_model(model_name):
    """تحميل نموذج."""
    running, _ = is_ollama_running()
    if not running:
        return False, "Ollama غير مشغّل. ثبّته من ollama.com وشغّله أولاً."

    try:
        model_name = _safe_model_name(model_name)
    except ValueError as e:
        return False, str(e)

    try:
        print(f"جارٍ تحميل {model_name}... (قد يستغرق دقائق)")
        result = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
        )
        if result.returncode == 0:
            return True, f"تم تحميل {model_name} بنجاح."
        return False, f"فشل التحميل: {result.stderr or result.stdout}"
    except FileNotFoundError:
        return False, "أمر ollama غير موجود. ثبّت Ollama من https://ollama.com"
    except subprocess.TimeoutExpired:
        return False, "انتهت مهلة التحميل (15 دقيقة)."
    except Exception as e:
        return False, f"خطأ: {e}"


def ensure_model(model_name="llama3.1"):
    """التأكد من وجود النموذج المحدد."""
    running, _ = is_ollama_running()
    if not running:
        return False, "Ollama غير مشغّل."
    try:
        model_name = _safe_model_name(model_name)
    except ValueError as e:
        return False, str(e)
    if model_name in list_models():
        return True, f"النموذج {model_name} جاهز."
    return pull_model(model_name)


def delete_model(model_name):
    """حذف نموذج."""
    try:
        model_name = _safe_model_name(model_name)
        result = subprocess.run(
            ["ollama", "rm", model_name],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
        return result.returncode == 0, result.stdout or result.stderr
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def status_report():
    """تقرير جاهزية Ollama."""
    running, data = is_ollama_running()
    models = [m.get("name", "") for m in data.get("models", [])] if running else []
    return {
        "running": running,
        "models": models,
        "model_count": len(models),
        "recommended": RECOMMENDED_MODELS,
    }


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "status":
        report = status_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not report["running"]:
            print("\nOllama غير مشغّل. ثبّته من https://ollama.com")
    elif action == "pull" and len(sys.argv) > 2:
        ok, msg = pull_model(sys.argv[2])
        print(msg)
    elif action == "list":
        for m in list_models():
            print(m)
    else:
        print("استخدام: status | list | pull <model>")