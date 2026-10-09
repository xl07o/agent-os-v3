"""
setup_ollama.py - تثبيت Ollama وضبط .env تلقائياً
====================================================
يثبّت Ollama (مجاني 100%، محلي، بدون أي مفتاح)، يشغّل خدمته،
يسحب الموديل، وينشئ/يحدّث .env بحيث يعمل "موظف الليل" فوراً
بدون أي إعداد يدوي ولا أي تكلفة.

الاستخدام:
  python setup_ollama.py
  python setup_ollama.py --model llama3.1
"""

import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
ENV_EXAMPLE_PATH = os.path.join(BASE_DIR, ".env.example")
OLLAMA_PING_URL = "http://localhost:11434/api/version"
DEFAULT_MODEL = "llama3.1"


def _ping_ollama(timeout=2):
    try:
        urllib.request.urlopen(OLLAMA_PING_URL, timeout=timeout)
        return True
    except Exception:
        return False


def ollama_installed():
    return shutil.which("ollama") is not None


def install_ollama():
    system = platform.system()
    print("تثبيت Ollama...")
    if system in ("Linux", "Darwin"):
        res = subprocess.run(
            "curl -fsSL https://ollama.com/install.sh | sh",
            shell=True,
        )
        return res.returncode == 0
    if system == "Windows":
        if shutil.which("winget"):
            res = subprocess.run(
                ["winget", "install", "-e", "--id", "Ollama.Ollama", "--silent"],
            )
            if res.returncode == 0:
                return True
        print(
            "تعذّر التثبيت التلقائي على ويندوز. نزّله يدوياً من "
            "https://ollama.com/download/windows ثم أعد تشغيل هذا السكربت."
        )
        return False
    print(f"نظام غير معروف ({system}) — نزّل Ollama يدوياً من https://ollama.com/download")
    return False


def ensure_ollama_running():
    if _ping_ollama():
        return True
    print("تشغيل خدمة Ollama...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        print(f"تعذّر تشغيل الخدمة تلقائياً: {str(e)[:120]}")
        return False
    for _ in range(15):
        time.sleep(1)
        if _ping_ollama():
            return True
    return False


def pull_model(model):
    print(f"سحب الموديل {model} (قد يأخذ دقائق حسب سرعة اتصالك)...")
    res = subprocess.run(["ollama", "pull", model])
    return res.returncode == 0


def ensure_env_file(model):
    if not os.path.exists(ENV_PATH):
        if os.path.exists(ENV_EXAMPLE_PATH):
            shutil.copyfile(ENV_EXAMPLE_PATH, ENV_PATH)
            print(".env غير موجود — تم إنشاؤه من .env.example")
        else:
            open(ENV_PATH, "w", encoding="utf-8").close()
            print(".env غير موجود ولا .env.example — تم إنشاء ملف جديد فارغ")

    with open(ENV_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith("SELFRUNNER_MODEL="):
            lines[i] = f"SELFRUNNER_MODEL={model}\n"
            found = True
            break
    if not found:
        lines.append(f"SELFRUNNER_MODEL={model}\n")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f".env جاهز — SELFRUNNER_MODEL={model} (بدون أي مفتاح مطلوب)")


def main():
    args = sys.argv[1:]
    model = DEFAULT_MODEL
    if "--model" in args:
        i = args.index("--model")
        if i + 1 < len(args):
            model = args[i + 1]

    if ollama_installed():
        print("Ollama مثبّت مسبقاً — تخطي التثبيت.")
    else:
        if not install_ollama():
            print("\nفشل التثبيت التلقائي. ثبّته يدوياً من https://ollama.com ثم أعد التشغيل.")
            sys.exit(1)

    if not ensure_ollama_running():
        print(
            "\nتعذّر تأكيد تشغيل خدمة Ollama تلقائياً. شغّلها يدوياً بأمر "
            "`ollama serve` في نافذة طرفية منفصلة ثم أعد تشغيل هذا السكربت."
        )
        sys.exit(1)
    print("خدمة Ollama تعمل.")

    if not pull_model(model):
        print(f"\nفشل سحب الموديل {model}. تحقق من اتصالك بالإنترنت وأعد المحاولة.")
        sys.exit(1)

    ensure_env_file(model)

    print("\nانتهى. شغّل موظف الليل الآن — يعمل بالكامل محلياً بدون أي تكلفة أو مفتاح.")


if __name__ == "__main__":
    main()
