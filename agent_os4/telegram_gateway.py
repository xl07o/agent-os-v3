"""
بوابة تيليجرام بأسلوب Hermes Agent — تكلّم الرئيس التنفيذي من جوالك:

- رسالتك ← الرئيس التنفيذي (نفس /api/ceo بالضبط) ← الرد يوصلك.
- أي طلب موافقة (توظيف، أداة، كتابة ملف...) يوصلك بزرّين: وافق / رفض.
- نتائج المهام المجدولة توصلك رسالة.
- /pending الطلبات المعلّقة بأزرارها، /status الصرف والحالة.

الأمان: البوت يسمع لحساب واحد بس — TELEGRAM_OWNER_ID بـ.env (نفس فكرة
"DM pairing" بـHermes). أي أحد ثاني يراسل البوت: ما ينفّذ له شي أبداً،
بس يرد مرة وحدة برقم حسابه (عشان أنت تعرف رقمك أول مرة وتحطه بـ.env).
التوكن ما ينطبع بأي سجل.

الإعداد: كلّم @BotFather بتيليجرام ← /newbot ← حط التوكن بـ
TELEGRAM_BOT_TOKEN ← راسل بوتك ← يرد برقمك ← حطه بـTELEGRAM_OWNER_ID.
"""

import os
import threading
import time

import requests

from . import env  # noqa: F401 — يضمن تحميل .env قبل أي getenv هنا

_API = "https://api.telegram.org"
_MAX_TEXT = 4000
_POLL_TIMEOUT = 25


def _token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def _owner() -> int | None:
    raw = os.getenv("TELEGRAM_OWNER_ID", "").strip()
    return int(raw) if raw.lstrip("-").isdigit() else None


def configured() -> bool:
    return bool(_token())


def _call(method: str, payload: dict, timeout: float = 15) -> dict:
    r = requests.post(f"{_API}/bot{_token()}/{method}", json=payload, timeout=timeout)
    try:
        return r.json()
    except ValueError:
        return {"ok": False, "description": f"HTTP {r.status_code}"}


def send(chat_id: int, text: str, buttons: list | None = None) -> None:
    text = text or "(بدون نص)"
    chunks = [text[i:i + _MAX_TEXT] for i in range(0, len(text), _MAX_TEXT)]
    for i, chunk in enumerate(chunks):
        payload = {"chat_id": chat_id, "text": chunk}
        if buttons and i == len(chunks) - 1:
            payload["reply_markup"] = {"inline_keyboard": buttons}
        _call("sendMessage", payload)


def approval_buttons(request_id: str) -> list:
    return [[{"text": "وافق", "callback_data": f"ok:{request_id}"},
             {"text": "رفض", "callback_data": f"no:{request_id}"}]]


def notify_owner(text: str, buttons: list | None = None) -> bool:
    owner = _owner()
    if not configured() or owner is None:
        return False
    send(owner, text, buttons)
    return True


class Gateway:
    """on_message(text) -> (reply_text, [(request_id, what), ...])
    on_decide(request_id, approved) -> (نص النتيجة, [(request_id, what), ...] لو طلعت موافقة جديدة)
    on_pending() -> [(request_id, what), ...]
    on_status() -> نص"""

    def __init__(self, on_message, on_decide, on_pending, on_status):
        self.on_message, self.on_decide = on_message, on_decide
        self.on_pending, self.on_status = on_pending, on_status
        self.offset = 0
        self._told_strangers: set[int] = set()

    def _stranger(self, chat_id: int, user_id: int) -> None:
        if user_id in self._told_strangers:
            return
        self._told_strangers.add(user_id)
        hint = ("هذا البوت خاص بصاحبه. رقم حسابك: "
                f"{user_id}\nلو أنت صاحب البوت، حط هذا الرقم بـTELEGRAM_OWNER_ID بملف .env وأعد التشغيل.")
        send(chat_id, hint)

    def _send_with_approvals(self, chat_id: int, text: str, approvals: list) -> None:
        send(chat_id, text)
        for request_id, what in approvals:
            send(chat_id, f"يحتاج موافقتك: {what}", approval_buttons(request_id))

    def handle_update(self, update: dict) -> None:
        self.offset = max(self.offset, update.get("update_id", 0) + 1)
        owner = _owner()
        if "callback_query" in update:
            cq = update["callback_query"]
            user_id = cq.get("from", {}).get("id")
            msg = cq.get("message") or {}
            chat_id = (msg.get("chat") or {}).get("id")
            if owner is None or user_id != owner:
                _call("answerCallbackQuery", {"callback_query_id": cq.get("id"), "text": "غير مصرّح"})
                return
            kind, _, request_id = str(cq.get("data", "")).partition(":")
            if kind not in ("ok", "no") or not request_id:
                _call("answerCallbackQuery", {"callback_query_id": cq.get("id"), "text": "زر غير معروف"})
                return
            result, approvals = self.on_decide(request_id, kind == "ok")
            _call("answerCallbackQuery", {"callback_query_id": cq.get("id"), "text": "تم"})
            if chat_id is not None and msg.get("message_id") is not None:
                _call("editMessageText", {"chat_id": chat_id, "message_id": msg["message_id"],
                                          "text": f"{msg.get('text', '')}\n\n← {'وافقت' if kind == 'ok' else 'رفضت'}"})
            if chat_id is not None:
                self._send_with_approvals(chat_id, result or "تم", approvals)
            return

        message = update.get("message") or {}
        chat = message.get("chat") or {}
        user_id = (message.get("from") or {}).get("id")
        text = (message.get("text") or "").strip()
        if not chat or user_id is None:
            return
        if owner is None or user_id != owner or chat.get("type") != "private":
            self._stranger(chat["id"], user_id)
            return
        if not text:
            send(chat["id"], "أفهم الرسائل النصية بس حالياً.")
        elif text in ("/start", "/help"):
            send(chat["id"], "أهلاً. اكتب طلبك وأنا (الرئيس التنفيذي) أوزّعه على الموظفين.\n"
                             "/pending الطلبات اللي تنتظر موافقتك\n/status الصرف والحالة")
        elif text == "/pending":
            items = self.on_pending()
            if not items:
                send(chat["id"], "ما فيه طلبات معلّقة.")
            for request_id, what in items:
                send(chat["id"], f"يحتاج موافقتك: {what}", approval_buttons(request_id))
        elif text == "/status":
            send(chat["id"], self.on_status())
        else:
            reply, approvals = self.on_message(text)
            self._send_with_approvals(chat["id"], reply, approvals)

    def poll_once(self, timeout: float = _POLL_TIMEOUT) -> int:
        data = _call("getUpdates", {"offset": self.offset, "timeout": timeout,
                                    "allowed_updates": ["message", "callback_query"]}, timeout=timeout + 10)
        updates = (data.get("result") or []) if data.get("ok") else []
        for update in updates:
            try:
                self.handle_update(update)
            except Exception as e:  # noqa: BLE001 — رسالة وحدة فشلت ما توقف البوابة
                print(f"[telegram] فشل معالجة رسالة: {type(e).__name__}")
        return len(updates)

    def start(self) -> threading.Thread:
        def loop():
            while True:
                try:
                    self.poll_once()
                except requests.RequestException as e:
                    print(f"[telegram] تعذّر الاتصال ({type(e).__name__}) — إعادة المحاولة بعد 5 ثواني")
                    time.sleep(5)
        t = threading.Thread(target=loop, daemon=True, name="os4-telegram")
        t.start()
        return t
