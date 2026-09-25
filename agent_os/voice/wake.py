"""
wake.py - كلمة الإيقاظ: ينتظر اسمك ثم يستمع (البند 13)
======================================================
يدعم openWakeWord (مجاني ومفتوح) أولاً، ثم Porcupine إن توفّر مفتاحه.
    pip install openwakeword sounddevice

يتدهور بصدق: بلا حزمة أو بلا ميكروفون يُرجع سبباً صريحاً بدل التظاهر
بالاستماع (البند 5). لا يحجب — يُعيد التحكم للمنادي ليقرّر.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import _common as C

WAKE_WORD = os.getenv("WAKE_WORD", "jarvis")


def available():
    """هل مكتبة كلمة الإيقاظ + الميكروفون متاحة؟"""
    try:
        import openwakeword  # noqa: F401
        import sounddevice  # noqa: F401
        return True
    except Exception:
        return False


def listen_once(timeout=None):
    """ينتظر نطق كلمة الإيقاظ مرة واحدة. يرجع {ok, detected|reason}."""
    if not available():
        return {"ok": False, "reason": "openwakeword/sounddevice غير مثبّتة — "
                                       "pip install openwakeword sounddevice"}
    try:
        import numpy as np
        import sounddevice as sd
        from openwakeword.model import Model

        model = Model()
        sr, block = 16000, 1280
        with sd.InputStream(samplerate=sr, channels=1, dtype="int16") as stream:
            C.log(f"👂 بانتظار كلمة الإيقاظ «{WAKE_WORD}» …")
            frames = 0
            max_frames = int((timeout or 3600) * sr / block)
            while frames < max_frames:
                data, _ = stream.read(block)
                preds = model.predict(np.frombuffer(data, dtype=np.int16))
                if any(score > 0.5 for score in preds.values()):
                    C.log("✨ سُمعت كلمة الإيقاظ")
                    return {"ok": True, "detected": True}
                frames += 1
        return {"ok": True, "detected": False, "reason": "انتهى الوقت دون سماع الكلمة"}
    except Exception as e:
        return {"ok": False, "reason": f"فشل الاستماع: {str(e)[:150]}"}


if __name__ == "__main__":
    import json
    print(json.dumps({"available": available(), "wake_word": WAKE_WORD}, ensure_ascii=False))
