"""
tts.py - تحويل النص إلى صوت عبر Piper (البند 13)
=================================================
صوت طبيعي محلي مجاني (عربي + إنجليزي) عبر Piper:
    pip install piper-tts     # أو ثنائي piper في PATH
    # ثم نزّل صوتاً: ar_JO-kareem أو en_US-lessac … (ملف .onnx)

يفضّل حزمة python (piper) ثم الثنائي (piper) كاحتياط. يتدهور بصدق حين
يغيب كلاهما أو يغيب ملف الصوت — لا صمت كاذب ولا ادّعاء نجاح (البند 5).
"""

import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import _common as C

VOICE_MODEL = os.getenv("PIPER_VOICE")  # مسار ملف .onnx للصوت


def _has_python_piper():
    try:
        import piper  # noqa: F401
        return True
    except Exception:
        return False


def available():
    """هل Piper متاح (حزمة python أو ثنائي في PATH)؟"""
    return _has_python_piper() or bool(shutil.which("piper"))


def synthesize(text, out_path=None, voice=None):
    """يولّد ملف WAV من النص. يرجع {ok, path|reason}."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "reason": "نص فارغ"}
    voice = voice or VOICE_MODEL
    out_path = out_path or os.path.join(C.AGENT_OS_DIR, "tts_out.wav")

    if not voice or not os.path.exists(str(voice)):
        return {"ok": False, "reason": "لم يُحدَّد ملف صوت Piper (.onnx) — اضبط PIPER_VOICE"}

    # 1) حزمة python
    if _has_python_piper():
        try:
            from piper import PiperVoice
            import wave
            v = PiperVoice.load(voice)
            with wave.open(out_path, "wb") as wf:
                v.synthesize(text, wf)
            C.log(f"🔊 TTS(piper-py) → {out_path}")
            return {"ok": True, "path": out_path, "engine": "piper-python"}
        except Exception as e:
            return {"ok": False, "reason": f"فشل piper-python: {str(e)[:150]}"}

    # 2) ثنائي piper في PATH
    try:
        proc = subprocess.run(
            [shutil.which("piper"), "--model", str(voice), "--output_file", out_path],
            input=text, capture_output=True, text=True, timeout=60,
        )
        if proc.returncode == 0 and os.path.exists(out_path):
            C.log(f"🔊 TTS(piper-bin) → {out_path}")
            return {"ok": True, "path": out_path, "engine": "piper-binary"}
        return {"ok": False, "reason": (proc.stderr or "فشل ثنائي piper")[:150]}
    except Exception as e:
        return {"ok": False, "reason": f"تعذّر تشغيل piper: {str(e)[:150]}"}


def speak(text, voice=None):
    """يولّد الصوت ويشغّله على مكبّر الجهاز (إن توفّر مشغّل)."""
    res = synthesize(text, voice=voice)
    if not res.get("ok"):
        return res
    for player in ("aplay", "paplay", "afplay", "ffplay"):
        exe = shutil.which(player)
        if exe:
            args = [exe, res["path"]]
            if player == "ffplay":
                args = [exe, "-nodisp", "-autoexit", res["path"]]
            try:
                subprocess.run(args, capture_output=True, timeout=120)
                res["played"] = True
                return res
            except Exception:
                pass
    res["played"] = False
    res["note"] = "الملف جاهز، لكن لا مشغّل صوت في PATH"
    return res


if __name__ == "__main__":
    import json
    txt = " ".join(sys.argv[1:]) or "مرحباً، أنا نظام Agent OS."
    print(json.dumps(speak(txt), ensure_ascii=False, indent=2))
