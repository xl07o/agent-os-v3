"""
point_in_time.py - مخزن بيانات زمني آمن (Point-In-Time Store) v1.0
=====================================================================
كل حقيقة لها تاريخان مختلفان دائماً:

  period    الفترة اللي الحقيقة تتكلم عنها (مثلاً "ربع 2024 Q1" أو يوم سعر)
  known_on  أول لحظة فعلياً قدرت تعرف فيها هذي القيمة وتتداول عليها

أي backtest يقرأ القيمة حسب period بدل known_on يغش بلا قصد (lookahead
bias) — بالضبط درس الحلقة #1 (خبر الساعة 20:29 هو خبر الغد، مو اليوم)
والحلقة #3 (الرقم كما طُبع وقتها، لا كما أُعيد ذكره لاحقاً). الاستعلام
الوحيد المتاح هنا هو as_of(date) ويستبعد تلقائياً أي حقيقة معرفتها
جاءت بعد ذلك التاريخ — فيستحيل تهريب غش عرضي.

الاستخدام:
  from trading import point_in_time as pit
  pit.record_fact("stooq", "AAPL", "close", 187.44, period="2024-01-15", known_on="2024-01-15")
  pit.record_fact("sec_edgar", "AAPL", "revenue_q", 119.6e9, period="2023-Q4", known_on="2024-02-01")
  pit.latest_value_as_of("2024-01-20", "AAPL", "revenue_q")  # يرجع آخر رقم معروف فعلياً بذلك التاريخ
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)
from agent_os import _common as C

DATA_DIR = os.path.join(ROOT_DIR, "data", "trading")
os.makedirs(DATA_DIR, exist_ok=True)
FACTS_FILE = os.path.join(DATA_DIR, "facts.json")


def _load():
    return C.load_json(FACTS_FILE, {"facts": [], "next_id": 1})


def _save(state):
    C.atomic_write(FACTS_FILE, state)


def record_fact(source, ticker, metric, value, period, known_on, extra=None):
    """يسجل حقيقة واحدة. known_on هو الوحيد المستخدم للاستعلام — period
    مجرد تصنيف/وصف لا يُستخدم أبداً لتقرير "هل هذا معروف الآن؟"."""
    state = _load()
    fact = {
        "id": state["next_id"],
        "source": source,
        "ticker": ticker.upper(),
        "metric": metric,
        "value": value,
        "period": period,
        "known_on": known_on,  # YYYY-MM-DD — تاريخ أول إمكانية تداول حقيقية عليه
        "extra": extra or {},
        "recorded_at": C.now_iso(),
    }
    state["next_id"] += 1
    state["facts"].append(fact)
    _save(state)
    return fact


def record_facts_bulk(facts):
    """إدخال دفعة حقائق دفعة وحدة (أسرع من استدعاء record_fact لكل صف)."""
    state = _load()
    out = []
    for f in facts:
        f = dict(f)
        f["id"] = state["next_id"]
        f["ticker"] = f["ticker"].upper()
        f.setdefault("extra", {})
        f.setdefault("recorded_at", C.now_iso())
        state["next_id"] += 1
        state["facts"].append(f)
        out.append(f)
    _save(state)
    return out


def facts_as_of(as_of_date, ticker=None, metric=None, source=None):
    """كل الحقائق المعروفة فعلياً بحلول as_of_date — أي known_on <= as_of_date
    فقط. هذا هو قانون المنع الوحيد بكل الملف."""
    state = _load()
    out = []
    for f in state["facts"]:
        if f["known_on"] > as_of_date:
            continue
        if ticker and f["ticker"] != ticker.upper():
            continue
        if metric and f["metric"] != metric:
            continue
        if source and f["source"] != source:
            continue
        out.append(f)
    return out


def latest_value_as_of(as_of_date, ticker, metric):
    """آخر قيمة معروفة لمقياس معين بحلول تاريخ معين، باعتبار period (أحدث
    فترة) ثم known_on (أحدث تسجيل لنفس الفترة — يلتقط التصحيحات اللاحقة
    بشرط أنها نفسها معروفة فعلياً بذلك التاريخ، وإلا القيمة الأصلية كما
    طُبعت وقتها هي التي تُرجَع — حلقة #3)."""
    rows = facts_as_of(as_of_date, ticker=ticker, metric=metric)
    if not rows:
        return None
    rows.sort(key=lambda r: (r["period"], r["known_on"]))
    return rows[-1]


def value_as_originally_known(ticker, metric, period):
    """القيمة كما طُبعت أول مرة لفترة معينة (أقدم known_on) — عكس
    value_as_currently_known. يحاكي مقارنة "the file column" مقابل
    "the printed column" بالحلقة #3."""
    state = _load()
    rows = [f for f in state["facts"]
            if f["ticker"] == ticker.upper() and f["metric"] == metric and f["period"] == period]
    if not rows:
        return None
    rows.sort(key=lambda r: r["known_on"])
    return rows[0]


def coverage_report(tickers, metrics, start_date, end_date):
    """نسبة التغطية لكل مصدر — إجابة الحلقة #4: "90,720 cells, 16% منها
    فيها الأربعة". يرجع لكل مقياس: عدد الخلايا الممكنة مقابل المُغطاة فعلياً."""
    state = _load()
    report = {}
    possible = len(tickers)
    for metric in metrics:
        covered = set()
        for f in state["facts"]:
            if f["metric"] != metric or f["ticker"] not in [t.upper() for t in tickers]:
                continue
            if start_date <= f["known_on"] <= end_date:
                covered.add(f["ticker"])
        report[metric] = {
            "covered": len(covered),
            "possible": possible,
            "pct": round(100 * len(covered) / possible, 1) if possible else 0.0,
        }
    return report


def all_facts(metric=None, ticker=None):
    """كل الحقائق بلا أي تصفية زمنية — للاستخدام الداخلي فقط (مثل محرك
    الـbacktest الذي يحتاج يبني فهرساً بالذاكرة مرة وحدة بدل قراءة الملف
    بكل تكرار). الكود اللي يحاكي قرار تداول حقيقي يجب يمرّ من facts_as_of
    أو latest_value_as_of، لا من هنا."""
    rows = _load()["facts"]
    if metric:
        rows = [r for r in rows if r["metric"] == metric]
    if ticker:
        rows = [r for r in rows if r["ticker"] == ticker.upper()]
    return rows


def fact_count():
    return len(_load()["facts"])


def clear_all():
    """يمسح كل الحقائق المسجلة — يُستخدم فقط لإعادة بناء مخزن تجريبي نظيف."""
    _save({"facts": [], "next_id": 1})


if __name__ == "__main__":
    print(f"عدد الحقائق المسجلة: {fact_count()}")
