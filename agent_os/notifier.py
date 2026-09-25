"""
notifier.py - إشعارات Agent OS v3
==================================
الأمور الحرجة (موافقة مطلوبة، مهمة محظورة، خطأ فادح) تصلك فوراً، لا تنتظر فتح الملفات:

  - ملف JSON (القناة الافتراضية دائماً): data/agent_os/notifications.json
  - Telegram bot (اختياري): مُهيّأ عبر env إن وُجد:
      NOTIFIER_TELEGRAM_BOT_TOKEN, NOTIFIER_TELEGRAM_CHAT_ID
  - بريد SMTP (اختياري): عبر env إن وُجد:
      NOTIFIER_SMTP_HOST, NOTIFIER_SMTP_PORT, NOTIFIER_SMTP_USER, NOTIFIER_SMTP_PASS,
      NOTIFIER_SMTP_TO

الاستخدام:
  from agent_os import notifier
  notifier.notify("critical", "موافقة مطلوبة", "طلب #12 ينتظرك")
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

NOTIF_FILE = os.path.join(C.AGENT_OS_DIR, "notifications.json")
MAX_STORED = 200


def _store(level, title, message):
    data = C.load_json(NOTIF_FILE, {"items": []})
    data["items"].append({
        "level": level,
        "title": (title or "")[:120],
        "message": (message or "")[:500],
        "time": C.now_iso(),
    })
    data["items"] = data["items"][-MAX_STORED:]
    C.atomic_write(NOTIF_FILE, data)


def _telegram(level, title, message):
    import urllib.parse
    import urllib.request
    token = os.environ.get("NOTIFIER_TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("NOTIFIER_TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat):
        return
    text = f"[{level}] {title}\n{message[:400]}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    from agent_os import security_kernel
    security_kernel.url_guard(url)
    req = urllib.request.Request(url, data=body)
    urllib.request.urlopen(req, timeout=10)


def _smtp(level, title, message):
    import smtplib
    from email.mime.text import MIMEText
    host = os.environ.get("NOTIFIER_SMTP_HOST", "").strip()
    port = int(os.environ.get("NOTIFIER_SMTP_PORT", "587"))
    user = os.environ.get("NOTIFIER_SMTP_USER", "").strip()
    pwd = os.environ.get("NOTIFIER_SMTP_PASS", "").strip()
    to = os.environ.get("NOTIFIER_SMTP_TO", "").strip()
    if not (host and user and to):
        return
    msg = MIMEText(f"[{level}] {title}\n\n{message[:2000]}")
    msg["Subject"] = f"[Agent OS] {level}: {title[:80]}"
    msg["From"] = user
    msg["To"] = to
    server = smtplib.SMTP(host, port)
    try:
        server.starttls()
        server.login(user, pwd)
        server.send_message(msg)
    finally:
        server.quit()


def notify(level="info", title="", message="", channels=("json",)):
    """أرسل إشعاراً: ملف JSON حصراً إلا مع إعداد env للقنوات الاختيارية."""
    _store(level, title, message)
    for ch in channels:
        try:
            if ch == "telegram":
                _telegram(level, title, message)
            elif ch == "smtp":
                _smtp(level, title, message)
        except Exception as e:
            C.log(f"⚠️ فشل إشعار {ch}: {str(e)[:80]}")


def list_notifications():
    """آخر الإشعارات المخزنة (الأحدث أولاً)."""
    items = C.load_json(NOTIF_FILE, {"items": []}).get("items", [])
    return list(reversed(items))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("الاستعمال: notify <مستوى> <عنوان> <رسالة> | list")
    elif args[0] == "list":
        for n in list_notifications():
            print(f"{n['time']} [{n['level']}] {n['title']}")
    else:
        notify(args[0], args[1] if len(args) > 1 else "", " ".join(args[2:]))