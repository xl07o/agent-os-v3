"""
stt.py - تحويل الصوت إلى نص عبر faster-whisper (البند 13)
=========================================================
يعمل محلياً بلا إنترنت وبلا مفاتيح فور تثبيت الحزمة على جهاز المالك:
    pip install faster-whisper

يتدهور بصدق: إن غابت الحزمة يُرجع سبباً صريحاً، لا يفبرك نصاً (البند 5).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import _common as C

_MODEL = None
_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")


def available():
    """هل faster-whisper مثبّتة؟"""
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def _get_model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        # int8 على المعالج = سريع وخفيف بلا GPU.
        _MODEL = WhisperModel(_MODEL_NAME, device="cpu", compute_type="int8")
    return _MODEL


def transcribe(audio_path, language=None):
    """يحوّل ملف صوت إلى نص. يرجع {ok, text|reason, language}."""
    if not available():
        return {"ok": False, "reason": "faster-whisper غير مثبّتة — pip install faster-whisper"}
    if not os.path.exists(audio_path):
        return {"ok": False, "reason": f"ملف الصوت غير موجود: {audio_path}"}
    try:
        segments, info = _get_model().transcribe(audio_path, language=language, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        C.log(f"🎙️ STT: {len(text)} حرفاً ({info.language})")
        return {"ok": True, "text": text, "language": info.language}
    except Exception as e:
        return {"ok": False, "reason": f"فشل التحويل: {str(e)[:150]}"}


if __name__ == "__main__":
    import json
    if len(sys.argv) >= 2:
        print(json.dumps(transcribe(sys.argv[1]), ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"available": available(), "model": _MODEL_NAME}, ensure_ascii=False))
