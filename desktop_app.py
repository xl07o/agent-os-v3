"""
desktop_app.py — نافذة سطح مكتب حقيقية للوكيل (بديل JARVIS المحذوف)
===================================================================
نفس فكرة JARVIS القديم (نافذة برنامج حقيقية، بدون متصفح/cmd) لكن
تفتح لوحة agent_os/chat_api.py المُختبرة فعلياً (مش jarvis_ui القديمة
اللي فيها خلل النص المشوّه). يشغّل Ollama تلقائياً لو موجود، ويشغّل
سيرفر chat_api.py بخيط منفصل داخل نفس العملية.

التشغيل:
  python desktop_app.py
  أو بنقرة واحدة صامتة: AGENT.vbs
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
    """تشغيل Ollama تلقائياً لو مش شغال — اختياري، فشله لا يوقف البرنامج."""
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/version", timeout=2)
        return  # شغّال مسبقاً
    except Exception:
        pass
    try:
        import subprocess
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        return  # Ollama غير مثبّت — المزوّدات الأخرى (Groq/Anthropic/...) تكفي
    for _ in range(15):
        time.sleep(1)
        try:
            urllib.request.urlopen("http://localhost:11434/api/version", timeout=2)
            return
        except Exception:
            pass


def _start_chat_api():
    """يشغّل chat_api.py (السيرفر المحلي المُختبر) بخيط منفصل."""
    from agent_os import chat_api
    server_thread = threading.Thread(target=chat_api.main, daemon=True)
    server_thread.start()

    import urllib.request
    url = f"http://{chat_api.HOST}:{chat_api.PORT}/api/status"
    for _ in range(20):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            pass
    return False


def main():
    import webview
    from agent_os import chat_api

    threading.Thread(target=_start_ollama, daemon=True).start()
    ready = _start_chat_api()
    if not ready:
        print("تحذير: chat_api.py لم يرد بالوقت المتوقع — النافذة بتحاول تفتح نفس الرابط.")

    url = f"http://{chat_api.HOST}:{chat_api.PORT}/"
    webview.create_window(
        title="Agent OS",
        url=url,
        width=1280,
        height=800,
        min_size=(900, 600),
        background_color="#0f172a",
        text_select=True,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
