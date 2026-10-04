"""
notifier.py - تنبيهات حقيقية للمستخدم خارج جلسة الدردشة (v1.0)
==================================================================
يوصّلك بما يصير وأنت مو قاعد قدام الطرفية: طلب موافقة معلّق، نتيجة دورة
تعلّم ذاتي، مهمة انتهت. ثلاث قنوات حقيقية، كل وحدة تشتغل فقط إذا جهّزت
مفاتيحها بنفسك في .env — ولا قناة مفعّلة افتراضياً بدون إعداد صريح منك:

  - Telegram (مجاني تماماً): TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
  - SMS عبر Twilio (مدفوع): TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_FROM_NUMBER + NOTIFY_PHONE_NUMBER
  - مكالمة صوتية عبر Twilio (مدفوع، "يدق رقم" فعلياً): نفس مفاتيح SMS + NOTIFY_CALL=1

الإعداد (على جهازك، هذا الملف لا يُنشئ حسابات ولا يدفع فواتير نيابة عنك):
  1) Telegram: أنشئ بوت عبر @BotFather، خذ التوكن، وخذ chat_id من
     https://api.telegram.org/bot<TOKEN>/getUpdates بعد ما ترسل له أي رسالة.
  2) Twilio (SMS/مكالمة): أنشئ حساب على twilio.com، خذ Account SID وAuth
     Token ورقم Twilio، وحط رقمك الشخصي في NOTIFY_PHONE_NUMBER.

لماذا لم تُختبر مكالمة أو رسالة فعلية هنا: هذه بيئة تطوير بلا حساب Twilio
ولا بوت Telegram حقيقي تابع لك، وإنشاء حساب يحتاج بياناتك ودفعك الشخصي —
قرار لا يُتخذ نيابة عنك. كل دالة هنا تتحقق من وجود مفاتيحها وتُرجع خطأ
واضحاً بدل الادعاء بنجاح لم يحدث.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from agent_os import security_kernel as _auth

REQUEST_TIMEOUT = 20

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
NOTIFY_PHONE_NUMBER = os.getenv("NOTIFY_PHONE_NUMBER", "")
NOTIFY_CALL_ENABLED = os.getenv("NOTIFY_CALL", "0") in ("1", "true", "yes")


def _missing(what: str) -> dict:
    return {"ok": False, "error": f"إعداد ناقص: {what}"}


def _post_form(url: str, data: dict, auth: tuple = None) -> dict:
    _auth.url_guard(url)
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if auth:
        import base64
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return {"ok": True, "response": json.loads(raw)}
            except json.JSONDecodeError:
                return {"ok": True, "response": raw[:300]}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:300]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def send_telegram(message: str) -> dict:
    """رسالة نصية فورية عبر بوت Telegram — مجاني تماماً، بديل أول موصى به."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return _missing("TELEGRAM_BOT_TOKEN و/أو TELEGRAM_CHAT_ID في .env")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    return _post_form(url, {"chat_id": TELEGRAM_CHAT_ID, "text": message[:4000]})


def send_sms(message: str) -> dict:
    """رسالة SMS عبر Twilio — يحتاج حساب Twilio مدفوع خاص بك."""
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, NOTIFY_PHONE_NUMBER]):
        return _missing("TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM_NUMBER/NOTIFY_PHONE_NUMBER في .env")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    return _post_form(
        url,
        {"To": NOTIFY_PHONE_NUMBER, "From": TWILIO_FROM_NUMBER, "Body": message[:1500]},
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
    )


def call_phone(message: str) -> dict:
    """مكالمة صوتية فعلية تقرأ الرسالة — عبر Twilio، ويحتاج تفعيلاً صريحاً
    إضافياً (NOTIFY_CALL=1) لأن الاتصال الصوتي أكثر تطفلاً وتكلفة من SMS."""
    if not NOTIFY_CALL_ENABLED:
        return _missing("المكالمات الصوتية معطّلة؛ فعّلها بضبط NOTIFY_CALL=1 في .env صراحة")
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, NOTIFY_PHONE_NUMBER]):
        return _missing("TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM_NUMBER/NOTIFY_PHONE_NUMBER في .env")

    safe_text = message.replace("&", "و").replace("<", "").replace(">", "")[:600]
    twiml = f'<Response><Say language="ar-SA">{safe_text}</Say></Response>'
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls.json"
    return _post_form(
        url,
        {"To": NOTIFY_PHONE_NUMBER, "From": TWILIO_FROM_NUMBER, "Twiml": twiml},
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
    )


def notify(message: str, prefer: str = None) -> dict:
    """يرسل عبر أول قناة متاحة فعلياً: telegram (مجاني) ثم sms ثم مكالمة
    (الأكثر تطفلاً، يحتاج NOTIFY_CALL=1). prefer يفرض قناة محدّدة بدل الترتيب."""
    channels = {"telegram": send_telegram, "sms": send_sms, "call": call_phone}
    order = [prefer] if prefer in channels else ["telegram", "sms", "call"]

    attempts = {}
    for name in order:
        result = channels[name](message)
        attempts[name] = result
        if result.get("ok"):
            return {"ok": True, "channel": name, "attempts": attempts}

    return {"ok": False, "error": "لا توجد قناة تنبيه مُعدَّة فعلياً", "attempts": attempts}


def status() -> dict:
    return {
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "sms_configured": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER and NOTIFY_PHONE_NUMBER),
        "call_configured": NOTIFY_CALL_ENABLED and bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER and NOTIFY_PHONE_NUMBER),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
    elif len(sys.argv) > 2 and sys.argv[1] == "send":
        print(json.dumps(notify(" ".join(sys.argv[2:])), ensure_ascii=False, indent=2))
    else:
        print("الاستخدام: python notifier.py status | send <رسالة>")
