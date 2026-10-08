"""
alpaca_client.py - تنفيذ حقيقي عبر Alpaca (ورقي + حي، بنفس الواجهة) v1.0
============================================================================
الافتراضي الدائم: ورقي (paper) — بلا فلوس حقيقية إطلاقاً. الانتقال
للوضع الحي يتطلب:

  1) ALPACA_PAPER=false صراحة في البيئة (ليس افتراضياً أبداً)
  2) موافقة بشرية مسجَّلة عبر set_live_mode(True) — مرة واحدة فقط،
     ليس لكل صفقة (حسب اختيارك: "تنفيذ تلقائي بالكامل" لكل صفقة بعدها)
  3) قاطع الخسارة اليومي (trading/kill_switch.py) غير مفعّل — لا يُعطَّل
     برمجياً أبداً، تفعيله يوقف كل تنفيذ حتى مراجعة بشرية صريحة

المفاتيح تُقرأ من البيئة فقط (ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY)
— لا تُكتب ولا تُخزَّن بأي ملف هنا.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)
from agent_os import _common as C

PAPER_BASE = "https://paper-api.alpaca.markets"
LIVE_BASE = "https://api.alpaca.markets"

LIVE_APPROVAL_PREFIX = "تفعيل التداول الحي (أموال حقيقية) عبر Alpaca"


def _mode():
    return "paper" if os.environ.get("ALPACA_PAPER", "true").strip().lower() not in ("false", "0", "no") else "live"


def _base_url():
    return LIVE_BASE if _mode() == "live" else PAPER_BASE


def _creds():
    return os.environ.get("ALPACA_API_KEY_ID", ""), os.environ.get("ALPACA_API_SECRET_KEY", "")


def is_configured():
    key, secret = _creds()
    return bool(key and secret)


def mode():
    return _mode()


def _request(method, path, body=None):
    key, secret = _creds()
    if not key or not secret:
        return None, "لا مفاتيح Alpaca مُعدّة (ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY) — وضع القراءة فقط"
    url = _base_url() + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return (json.loads(raw) if raw else {}), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
    except Exception as e:
        return None, str(e)[:200]


def account():
    return _request("GET", "/v2/account")


def clock():
    return _request("GET", "/v2/clock")


def positions():
    return _request("GET", "/v2/positions")


def set_live_mode(enable, requested_by="user"):
    """تفعيل الوضع الحي يمر ببوابة موافقة بشرية مرة واحدة فقط — ليس لكل
    صفقة. إيقاف الوضع الحي (enable=False) لا يحتاج موافقة أبداً، لأن
    تقليل الخطر لا يحتاج إذناً."""
    if not enable:
        os.environ["ALPACA_PAPER"] = "true"
        C.log("⏸️ [alpaca] رجع الوضع إلى paper فوراً — بلا حاجة موافقة.")
        return {"status": "paper"}

    from agent_os import approval_center
    req = approval_center.create_request(
        LIVE_APPROVAL_PREFIX,
        "تفعيل لمرة واحدة فقط — بعدها كل صفقة تُنفَّذ تلقائياً بلا موافقة فردية، حسب اختيارك الصريح. "
        "قاطع الخسارة اليومي يبقى نشطاً دائماً ولا يمكن تعطيله برمجياً.",
        ["تأكد أن مفاتيح Alpaca الحية مضبوطة فعلاً بالبيئة",
         "تأكد أنك تقبل خسارة المبلغ المربوط بالحساب",
         "وافق فقط لو جاهز للتداول الحقيقي الآن"],
        kind="financial", risk="high",
        payload={"requested_by": requested_by},
    )
    C.log(f"⏳ [alpaca] طلب تفعيل التداول الحي بانتظار موافقتك: طلب #{req['id']}")
    return {"status": "pending_approval", "approval_request_id": req["id"]}


def is_live_approved():
    """هل آخر طلب تفعيل حي اتوافق عليه فعلياً عبر approval_center؟"""
    from agent_os import approval_center
    reqs = [r for r in approval_center.list_requests() if r["what"] == LIVE_APPROVAL_PREFIX]
    if not reqs:
        return False
    return reqs[-1]["status"] == "done"


def submit_order(symbol, qty, side, order_type="market", time_in_force="day"):
    """تنفيذ صفقة فعلية. يُرفض فوراً (بلا أي استثناء) لو: القاطع مفعّل،
    أو الوضع حي بلا موافقة مسجّلة، أو لا مفاتيح مُعدّة."""
    from trading import kill_switch

    if kill_switch.is_tripped():
        return None, "مرفوض: قاطع الخسارة اليومي مفعّل — راجع trading/kill_switch.py ثم reset() يدوياً"
    if _mode() == "live" and not is_live_approved():
        return None, "مرفوض: الوضع حي بلا موافقة بشرية مسجّلة — استدعِ set_live_mode(True) أولاً"
    if not is_configured():
        return None, "مرفوض: لا مفاتيح Alpaca مُعدّة بالبيئة"

    body = {"symbol": symbol, "qty": qty, "side": side, "type": order_type, "time_in_force": time_in_force}
    result, err = _request("POST", "/v2/orders", body)
    tag = "🔴 LIVE" if _mode() == "live" else "🧪 paper"
    C.log(f"{tag} [alpaca] أمر {side} {qty} {symbol}: {'نجح' if result else err}")
    return result, err


def status():
    return {
        "mode": _mode(),
        "configured": is_configured(),
        "live_approved": is_live_approved() if _mode() == "live" else None,
    }


if __name__ == "__main__":
    s = status()
    print(f"الوضع: {s['mode']} — مفاتيح مُعدّة: {s['configured']}")
    if s["mode"] == "live":
        print(f"موافق عليه: {s['live_approved']}")
