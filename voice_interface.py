"""
voice_interface.py - الواجهة الصوتية التفاعلية (v1.0 — سكّلة تكامل أولية)
==========================================================================
يربط ثلاث مكوّنات صوتية محلية ومجانية:
  - faster-whisper          : كلام → نص
  - openWakeWord             : كشف كلمة التنبيه، لتفعيل الاستماع عند الحاجة فقط
  - Piper                    : نص → كلام

هذا الملف "سكّلة تكامل" (integration scaffold) لا تطبيق كامل جاهز للاستخدام:
الاعتماديات الثلاث اختيارية وثقيلة (مكتبات + نماذج AI محلية بالميجابايتات)،
ولا يمكن تثبيتها أو تنزيل نماذجها من بيئة التطوير التي كُتب فيها هذا الملف
(بيئة بلا مايكروفون فعلي وبلا قدرة مؤكَّدة على تنزيل نماذج ضخمة). كل دالة
هنا تتحقق من توفر الاعتمادية والنموذج قبل أي استخدام، وتعيد رسالة خطأ واضحة
بدل الانهيار أو الادعاء بنجاح لم يحدث.

التثبيت الفعلي (على جهاز المستخدم، خارج هذا المستودع):
  pip install faster-whisper openwakeword piper-tts sounddevice
  + تنزيل نموذج faster-whisper (مثلاً "small") ونموذج صوت Piper (.onnx).

الخصوصية: التصميم الافتراضي محلي بالكامل — لا يُرسل أي صوت خام لأي خدمة
خارجية؛ ما يُسجَّل يبقى على جهاز المستخدم.
"""

import os

VOICE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "voice")
os.makedirs(VOICE_DIR, exist_ok=True)

WHISPER_MODEL_SIZE = os.getenv("AGENT_WHISPER_MODEL", "small")
PIPER_VOICE_PATH = os.getenv("AGENT_PIPER_VOICE", "")  # مسار ملف صوت .onnx لـ Piper
WAKE_WORD = os.getenv("AGENT_WAKE_WORD", "hey jarvis")

_wake_model = None


def _missing(dep_name, install_hint):
    return {"ok": False, "error": f"الاعتمادية '{dep_name}' غير مثبّتة. ثبّتها بـ: {install_hint}"}


def transcribe(audio_path: str) -> dict:
    """كلام → نص عبر faster-whisper."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return _missing("faster-whisper", "pip install faster-whisper")

    if not os.path.isfile(audio_path):
        return {"ok": False, "error": f"ملف الصوت غير موجود: {audio_path}"}

    try:
        model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path)
        text = "".join(seg.text for seg in segments)
        return {"ok": True, "text": text.strip(), "language": info.language}
    except Exception as e:
        return {"ok": False, "error": f"فشل التفريغ: {str(e)[:200]}"}


def speak(text: str, out_path: str = None) -> dict:
    """نص → كلام عبر Piper. يحتاج AGENT_PIPER_VOICE على مسار ملف .onnx محمّل مسبقاً."""
    if not PIPER_VOICE_PATH or not os.path.isfile(PIPER_VOICE_PATH):
        return {"ok": False, "error": "لم يُحدَّد صوت Piper صالح. اضبط AGENT_PIPER_VOICE على مسار ملف .onnx."}

    try:
        from piper import PiperVoice
    except ImportError:
        return _missing("piper-tts", "pip install piper-tts")

    out_path = out_path or os.path.join(VOICE_DIR, "last_reply.wav")
    try:
        voice = PiperVoice.load(PIPER_VOICE_PATH)
        with open(out_path, "wb") as f:
            voice.synthesize(text, f)
        return {"ok": True, "audio_path": out_path}
    except Exception as e:
        return {"ok": False, "error": f"فشل التوليد الصوتي: {str(e)[:200]}"}


def listen_for_wake_word(audio_frame) -> dict:
    """يفحص إطار صوت واحد (numpy array) بحثاً عن كلمة التنبيه عبر openWakeWord.
    التقاط الصوت من المايكروفون (sounddevice/pyaudio) مسؤولية خارج هذا الملف
    عمداً — هنا فقط منطق الكشف، ليبقى قابلاً للاختبار بدون عتاد صوتي فعلي."""
    global _wake_model
    try:
        from openwakeword.model import Model
    except ImportError:
        return _missing("openwakeword", "pip install openwakeword")

    try:
        if _wake_model is None:
            _wake_model = Model()
        predictions = _wake_model.predict(audio_frame)
        triggered = any(score > 0.5 for score in predictions.values())
        return {"ok": True, "triggered": triggered, "scores": predictions}
    except Exception as e:
        return {"ok": False, "error": f"فشل كشف كلمة التنبيه: {str(e)[:200]}"}


def status() -> dict:
    """يفحص أي مكوّنات الصوت مثبّتة فعلياً على هذا الجهاز، بصدق تام —
    لا توجد حالة افتراضية مزيّفة لأي مكوّن."""
    result = {}
    for mod_name, key in (("faster_whisper", "faster_whisper"),
                           ("openwakeword", "openwakeword"),
                           ("piper", "piper")):
        try:
            __import__(mod_name)
            result[key] = "مثبّت"
        except ImportError:
            result[key] = "غير مثبّت"

    result["piper_voice_configured"] = bool(PIPER_VOICE_PATH and os.path.isfile(PIPER_VOICE_PATH))
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(status(), ensure_ascii=False, indent=2))
