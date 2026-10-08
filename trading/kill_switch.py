"""
kill_switch.py - قاطع أمان لا يُعطَّل برمجياً أبداً v1.0
==============================================================
حتى باختيار "تنفيذ تلقائي بالكامل، بلا موافقة لكل صفقة" — يبقى هذا
الملف نشطاً دائماً: حد خسارة يومي صريح + قاطع دائرة يوقف أي صفقة جديدة
فور تجاوزه. هذا ليس قيداً يتعارض مع "تلقائي بالكامل" (كل صفقة لسه
تُنفَّذ بلا انتظار موافقتك)؛ فقط يمنع كارثة لو صارت الاستراتيجية نفسها
معطوبة وهي تتعلم.

لا دالة هنا تسمح بتعطيل القاطع آلياً بعد تفعيله — reset() يتطلب استدعاء
بشرياً صريحاً ويُسجَّل من فعله ومتى.

الاستخدام:
  from trading import kill_switch
  kill_switch.check_and_trip(start_of_day_equity=10000, current_equity=9400)
  kill_switch.is_tripped()
  kill_switch.reset(by="you")
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)
from agent_os import _common as C

DATA_DIR = os.path.join(ROOT_DIR, "data", "trading")
os.makedirs(DATA_DIR, exist_ok=True)
STATE_FILE = os.path.join(DATA_DIR, "kill_switch.json")

# نسبة مئوية من رصيد بداية اليوم — تجاوزها يوقف كل تنفيذ فوري. يُضبط عبر
# متغير بيئة، لكن أبداً لا تُلغى الحماية نفسها (فقط عتبتها قابلة للتشديد
# أو التخفيف، والافتراضي محافظ).
DAILY_LOSS_LIMIT_PCT = float(os.environ.get("TRADING_DAILY_LOSS_LIMIT_PCT", "3.0"))


def _load():
    return C.load_json(STATE_FILE, {"tripped": False, "tripped_at": None, "reason": None,
                                     "reset_log": [], "last_check": None})


def _save(state):
    C.atomic_write(STATE_FILE, state)


def is_tripped():
    return _load().get("tripped", False)


def check_and_trip(start_of_day_equity, current_equity):
    """يفحص خسارة اليوم مقابل الحد. لو تجاوزته يوقف كل تنفيذ تلقائي حتى
    reset() بشري صريح. يرجع True لو القاطع فُعِّل الآن أو كان مفعّلاً
    أصلاً."""
    state = _load()
    if state.get("tripped"):
        return True
    if start_of_day_equity <= 0:
        return state.get("tripped", False)
    loss_pct = 100 * (start_of_day_equity - current_equity) / start_of_day_equity
    state["last_check"] = {"start_of_day_equity": start_of_day_equity, "current_equity": current_equity,
                            "loss_pct": round(loss_pct, 3), "at": C.now_iso()}
    if loss_pct >= DAILY_LOSS_LIMIT_PCT:
        state["tripped"] = True
        state["tripped_at"] = C.now_iso()
        state["reason"] = f"خسارة اليوم {round(loss_pct, 2)}% >= الحد {DAILY_LOSS_LIMIT_PCT}%"
        _save(state)
        C.log(f"🛑 [kill_switch] توقف كل تنفيذ تلقائي: {state['reason']}", level="WARN")
        try:
            import notifier
            notifier.notify(f"🛑 قاطع أمان التداول فُعِّل: {state['reason']} — التنفيذ موقوف حتى تراجعه يدوياً.",
                             prefer="call")
        except Exception:
            pass
        return True
    _save(state)
    return False


def reset(by):
    """إعادة تفعيل التنفيذ — استدعاء بشري صريح فقط، يُسجَّل من ومتى."""
    state = _load()
    state["tripped"] = False
    state.setdefault("reset_log", []).append({"by": by, "at": C.now_iso()})
    _save(state)
    C.log(f"✅ [kill_switch] أعاد {by} تفعيل التنفيذ التلقائي.")
    return state


def status():
    return _load()


if __name__ == "__main__":
    s = status()
    print(f"القاطع: {'مفعّل 🛑' if s['tripped'] else 'سليم ✅'} — حد الخسارة اليومي: {DAILY_LOSS_LIMIT_PCT}%")
