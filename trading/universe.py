"""
universe.py - قائمة الشركات كما كانت، لا كما هي اليوم (Point-In-Time Universe) v1.0
=======================================================================================
درس الحلقة #2: لو اختبرت استراتيجية قديمة على قائمة شركات *اليوم*، أنت
تستبعد كل شركة أفلست أو انشطبت بالطريق — فتحصل رقماً أفضل من الواقع
بلا مبرر (survivorship bias). القائمة الصحيحة الوحيدة هي: "مين كان
مدرَجاً بهذا التاريخ بالذات؟".

الاستخدام:
  from trading import universe
  universe.record_listing("AAPL", start_date="1980-12-12")
  universe.record_listing("ENRN", start_date="1989-01-01", end_date="2001-12-02", note="أفلست")
  universe.universe_as_of("2001-06-01")   # تتضمن ENRN
  universe.universe_as_of("2002-06-01")   # لا تتضمن ENRN
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)
from agent_os import _common as C

DATA_DIR = os.path.join(ROOT_DIR, "data", "trading")
os.makedirs(DATA_DIR, exist_ok=True)
UNIVERSE_FILE = os.path.join(DATA_DIR, "universe.json")


def _load():
    return C.load_json(UNIVERSE_FILE, {"listings": []})


def _save(state):
    C.atomic_write(UNIVERSE_FILE, state)


def record_listing(ticker, start_date, end_date=None, exchange="", note=""):
    """يسجل أن شركة كانت مدرجة بين تاريخين. end_date=None يعني لا تزال
    مدرجة حتى الآن."""
    state = _load()
    state["listings"].append({
        "ticker": ticker.upper(),
        "start_date": start_date,
        "end_date": end_date,
        "exchange": exchange,
        "note": note,
    })
    _save(state)


def record_listings_bulk(rows):
    state = _load()
    for r in rows:
        r = dict(r)
        r["ticker"] = r["ticker"].upper()
        state["listings"].append(r)
    _save(state)


def universe_as_of(as_of_date):
    """كل الشركات المدرجة فعلياً بهذا التاريخ بالذات — القائمة الوحيدة
    الآمنة لبناء استراتيجية تاريخية عليها."""
    state = _load()
    out = []
    for row in state["listings"]:
        if row["start_date"] > as_of_date:
            continue
        if row["end_date"] and row["end_date"] < as_of_date:
            continue
        out.append(row["ticker"])
    return sorted(set(out))


def survivorship_gap(as_of_date, today_date=None):
    """يقيس فجوة الـsurvivorship bias فعلياً: الفرق بين قائمة اليوم
    وقائمة as_of_date — هذا بالضبط ما يصنعه الخطأ لو استُخدم بالغلط."""
    today_date = today_date or C.now_iso()[:10]
    today_universe = set(universe_as_of(today_date))
    then_universe = set(universe_as_of(as_of_date))
    missing_if_used_today_list = then_universe - today_universe
    return {
        "as_of": as_of_date,
        "then_count": len(then_universe),
        "today_count": len(today_universe),
        "delisted_since_missing_from_todays_list": sorted(missing_if_used_today_list),
    }


def listing_count():
    return len(_load()["listings"])


if __name__ == "__main__":
    print(f"عدد الإدراجات المسجلة: {listing_count()}")
