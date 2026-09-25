"""
reinvestment_wallet.py - محفظة إعادة الاستثمار
================================================
فكرة المالك: "له نسبة من الفلوس في تطوير وشراء API"
التوسيع: الوكيل يتتبع إيراداته ويخصّص نسبة لإعادة الاستثمار:
  - شراء APIs أقوى
  - ترقية نماذج
  - أدوات جديدة
  مع ميزانية شفافة ولا يتجاوزها بدون إذن المالك.
"""

import os
import sys

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

WALLET_FILE = os.path.join(C.AGENT_OS_DIR, "reinvestment_wallet.json")

DEFAULT_SHARE = 0.15   # 15% من الإيرادات للوكيل


def _load():
    return C.load_json(WALLET_FILE, {
        "share_rate": DEFAULT_SHARE,
        "balance": 0.0,
        "total_earned": 0.0,
        "total_invested": 0.0,
        "transactions": [],
    })


def _save(w):
    C.atomic_write(WALLET_FILE, w)


def record_revenue(amount, source=""):
    """يسجّل إيراداً ويخصّص الحصة تلقائياً."""
    w = _load()
    share = round(float(amount) * w["share_rate"], 2)
    w["total_earned"] = round(w["total_earned"] + float(amount), 2)
    w["balance"] = round(w["balance"] + share, 2)
    w["transactions"].append({
        "type": "revenue", "amount": float(amount), "share": share,
        "source": source, "at": C.now_iso(),
    })
    w["transactions"] = w["transactions"][-500:]
    _save(w)
    C.log(f"💰 إيراد {amount} → حصة الوكيل {share}")
    return {"share": share, "balance": w["balance"]}


def spend(amount, purpose=""):
    """يستثمر من الرصيد (شراء API/أداة). يتطلب موافقة لو تجاوز 50% من الرصيد."""
    w = _load()
    amount = round(float(amount), 2)
    if amount > w["balance"]:
        return {"ok": False, "reason": f"رصيد غير كافٍ ({w['balance']})",
                "needs_topup": round(amount - w["balance"], 2)}
    needs_approval = amount > w["balance"] * 0.5
    w["balance"] = round(w["balance"] - amount, 2)
    w["total_invested"] = round(w["total_invested"] + amount, 2)
    w["transactions"].append({
        "type": "investment", "amount": amount,
        "purpose": purpose, "at": C.now_iso(),
    })
    _save(w)
    return {"ok": True, "spent": amount, "remaining": w["balance"],
            "needs_approval": needs_approval}


def balance():
    w = _load()
    return {"balance": w["balance"], "total_earned": w["total_earned"],
            "total_invested": w["total_invested"], "share_rate": w["share_rate"]}


def set_share_rate(rate):
    """يغيّر نسبة الحصة (0..0.5 — لا يتجاوز نصف الإيرادات)."""
    rate = max(0.0, min(0.5, float(rate)))
    w = _load()
    w["share_rate"] = rate
    _save(w)
    return rate


if __name__ == "__main__":
    record_revenue(1000, "مشروع SaaS")
    record_revenue(500, "أتمتة")
    print(balance())
    r = spend(50, "شراء API DeepSeek")
    print(f"استثمار: {r}")
