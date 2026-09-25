"""
اختبار الواجهة الصوتية (البند 13).
هنا بلا الأدوات الصوتية: نتأكد أنها تتدهور بصدق (سبب صريح، بلا انهيار،
بلا تلفيق) وأن المسار النصي عبر النواة يعمل.
"""
import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "voice_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os.voice import stt, tts, wake, assistant


def test_status_is_wellformed():
    s = assistant.status()
    for k in ("stt_faster_whisper", "tts_piper", "wakeword", "ready"):
        assert k in s and isinstance(s[k], bool)


def test_stt_degrades_honestly_without_lib():
    if not stt.available():
        r = stt.transcribe("/nonexistent.wav")
        assert r["ok"] is False and r.get("reason")


def test_tts_empty_and_missing_voice_are_honest():
    assert tts.synthesize("")["ok"] is False
    # بلا ملف صوت مضبوط → سبب صريح، لا صمت كاذب
    r = tts.synthesize("مرحبا", voice=None)
    assert r["ok"] is False and r.get("reason")


def test_wake_degrades_honestly():
    if not wake.available():
        r = wake.listen_once(timeout=1)
        assert r["ok"] is False and r.get("reason")


def test_handle_utterance_runs_kernel_text_path():
    out = assistant.handle_utterance("سجّل هدف بناء متجر", speak_reply=False)
    assert out["ok"] is True
    assert isinstance(out["reply"], str) and out["reply"]
    assert "result" in out


def test_handle_utterance_empty_is_honest():
    assert assistant.handle_utterance("")["ok"] is False
