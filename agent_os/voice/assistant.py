"""
assistant.py - حلقة المساعد الصوتي الكاملة (البند 13)
=====================================================
تربط: كلمة الإيقاظ → صوت→نص → نواة Agent OS → نص→صوت. على نمط Jarvis،
لكن بأدواتنا ومجاناً ومحلياً.

  status()            -> جاهزية كل مكوّن صوتي (صدق تام عمّا ينقص)
  handle_utterance()  -> ينفّذ جملة نصية عبر النواة ويعيد ردّاً منطوقاً
  run_loop()          -> الحلقة الحية (تتطلب ميكروفون + الأدوات)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import _common as C
from agent_os.voice import stt, tts, wake


def status():
    """تقرير جاهزية صريح — ما المتاح وما ينقص لتشغيل الصوت كاملاً."""
    return {
        "stt_faster_whisper": stt.available(),
        "tts_piper": tts.available(),
        "wakeword": wake.available(),
        "voice_model_set": bool(os.getenv("PIPER_VOICE")),
        "ready": stt.available() and tts.available() and wake.available()
                 and bool(os.getenv("PIPER_VOICE")),
    }


def _spoken_reply(result):
    """يصوغ ردّاً قصيراً صالحاً للنطق من نتيجة النواة."""
    res = result.get("result", {})
    st = res.get("status", "?")
    intent = result.get("intent", "?")
    if st == "verified":
        art = result.get("artifact")
        return f"تم تنفيذ المهمة ({intent})." + (f" المخرَج جاهز." if art else "")
    if st == "needs_human":
        return f"المهمة ({intent}) تحتاج موافقتك قبل المتابعة."
    return f"لم أُكمل المهمة ({intent}) بعد؛ الحالة: {st}."


def handle_utterance(text, speak_reply=False):
    """ينفّذ جملة المستخدم النصية عبر النواة ويعيد ردّاً (ونُطقاً اختيارياً).
    هذا المسار قابل للاختبار بلا ميكروفون ولا مكبّر."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "reason": "جملة فارغة"}
    from agent_os import agent_os as A
    result = A.run_task(text)
    reply = _spoken_reply(result)
    spoken = None
    if speak_reply:
        spoken = tts.speak(reply)
    return {"ok": True, "reply": reply, "result": result, "spoken": spoken}


def run_loop(max_turns=None):
    """الحلقة الحية: إيقاظ → استماع → تنفيذ → ردّ صوتي.
    تتطلب الأدوات + ميكروفون؛ تتوقف بصدق مع سبب إن نقص شيء."""
    stat = status()
    if not stat["ready"]:
        missing = [k for k, v in stat.items() if v is False]
        return {"ok": False, "reason": "الصوت غير جاهز — ينقص: " + ", ".join(missing)}
    turns = 0
    while max_turns is None or turns < max_turns:
        w = wake.listen_once()
        if not w.get("ok"):
            return {"ok": False, "reason": w.get("reason")}
        if not w.get("detected"):
            continue
        # سجّل مقطعاً قصيراً ثم حوّله — يترك التسجيل لأداة النظام (arecord/sox).
        audio = os.path.join(C.AGENT_OS_DIR, "utterance.wav")
        heard = stt.transcribe(audio)
        if not heard.get("ok"):
            tts.speak("لم أسمعك بوضوح.")
            continue
        out = handle_utterance(heard["text"], speak_reply=True)
        C.log(f"🗣️ رد: {out.get('reply')}")
        turns += 1
    return {"ok": True, "turns": turns}


if __name__ == "__main__":
    import json
    if len(sys.argv) >= 2 and sys.argv[1] != "status":
        print(json.dumps(handle_utterance(" ".join(sys.argv[1:])), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
