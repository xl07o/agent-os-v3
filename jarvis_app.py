"""
jarvis_app.py — JARVIS: تطبيق سطح المكتب الحقيقي
===================================================
يفتح JARVIS كنافذة برنامج حقيقية (مو متصفح).
يشغّل Ollama + API + الواجهة كلها داخل نافذة واحدة.
"""

import os
import sys
import threading
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

os.environ["PYTHONUTF8"] = "1"

from dotenv import load_dotenv
load_dotenv(_HERE / ".env")


def _start_ollama():
    """تشغيل Ollama تلقائياً لو مش شغال."""
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/version", timeout=2)
        return  # شغّال مسبقاً
    except Exception:
        pass
    import subprocess
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    # انتظر حتى يجهز
    for _ in range(15):
        time.sleep(1)
        try:
            urllib.request.urlopen("http://localhost:11434/api/version", timeout=2)
            return
        except Exception:
            pass


def _start_api_server():
    """يشغّل JARVIS API في خيط منفصل."""
    import jarvis
    server_thread = threading.Thread(
        target=jarvis.run_server,
        kwargs={"open_browser": False},
        daemon=True,
    )
    server_thread.start()
    # انتظر حتى يجهز الـ API
    import urllib.request
    for _ in range(10):
        time.sleep(0.5)
        try:
            urllib.request.urlopen("http://localhost:8082/status", timeout=2)
            return True
        except Exception:
            pass
    return False


def main():
    import webview

    # 1. شغّل Ollama
    ollama_thread = threading.Thread(target=_start_ollama, daemon=True)
    ollama_thread.start()

    # 2. شغّل API server
    api_ready = _start_api_server()

    url = "http://localhost:8082" if api_ready else str(_HERE / "jarvis_ui" / "index.html")

    # 3. افتح النافذة
    window = webview.create_window(
        title="JARVIS — موظف الليل",
        url=url,
        width=1280,
        height=800,
        min_size=(900, 600),
        background_color="#050a14",
        text_select=True,
    )

    # تشغيل النافذة (blocking)
    webview.start(debug=False)


if __name__ == "__main__":
    main()
