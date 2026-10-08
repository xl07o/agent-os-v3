"""
data_sources.py - بيانات حقيقية بلا مفتاح + بديل تجريبي صريح v1.0
=====================================================================
مصدران حقيقيان فعلياً بلا أي مفتاح API:
  stooq.com       أسعار إغلاق يومية تاريخية (CSV عام)
  SEC EDGAR XBRL  أرقام مالية فعلية مع تاريخ الإيداع الحقيقي (filed) —
                   هذا بالضبط known_on اللي الحلقة #3 تتكلم عنها، لأن
                   SEC تنشر متى *فعلياً* عرف السوق كل رقم.

لو تعذّر الاتصال (بيئة بلا إنترنت خارجي، أو سياسة شبكة تمنعه) — كل دالة
تفشل بهدوء وترجع [] بدل استثناء، تماماً كنمط news_intel.py._safe_get
بهذا المشروع. عندها استخدم demo_dataset() صراحة: بيانات اصطناعية
*موسومة بوضوح* كتجريبية، بذرة عشوائية ثابتة (نتائج قابلة لإعادة الإنتاج)،
أبداً لا تُعرض ولا تُحفظ كأنها بيانات سوق حقيقية.
"""

import csv
import io
import json
import os
import random
import sys
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)

SEC_CONTACT_UA = os.environ.get(
    "SEC_EDGAR_USER_AGENT", "agent-os-v3 research (set SEC_EDGAR_USER_AGENT to your real contact)"
)


def _safe_get(url, timeout=10, headers=None):
    try:
        req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0 (compatible; agent-os-v3)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def fetch_daily_prices_stooq(ticker):
    """أسعار إغلاق يومية حقيقية من stooq.com (بلا مفتاح). يرجع قائمة
    صفوف [{date, close}] من الأقدم للأحدث، أو [] إن تعذّر الاتصال."""
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    raw = _safe_get(url, timeout=12)
    if not raw or "Date" not in raw:
        return []
    rows = []
    reader = csv.DictReader(io.StringIO(raw))
    for row in reader:
        try:
            rows.append({"date": row["Date"], "close": float(row["Close"])})
        except (KeyError, ValueError):
            continue
    return rows


def fetch_sec_company_facts(cik, concept="Revenues", taxonomy="us-gaap"):
    """بيانات مالية فعلية من SEC EDGAR XBRL مع تاريخ الإيداع الحقيقي.
    cik بصيغة رقمية (مثلاً 320193 لآبل) — تُنسَّق تلقائياً لعشرة أرقام.
    يرجع قائمة [{period, value, filed}] أو [] إن تعذّر الاتصال."""
    cik10 = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik10}/{taxonomy}/{concept}.json"
    raw = _safe_get(url, timeout=12, headers={"User-Agent": SEC_CONTACT_UA})
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    out = []
    for unit_rows in data.get("units", {}).values():
        for row in unit_rows:
            if row.get("form") not in ("10-Q", "10-K"):
                continue
            fy, fp, filed, val = row.get("fy"), row.get("fp"), row.get("filed"), row.get("val")
            if not (fy and filed and val is not None):
                continue
            out.append({"period": f"{fy}-{fp or 'FY'}", "value": val, "filed": filed, "form": row.get("form")})
    return out


def ingest_prices_as_facts(ticker, rows):
    """يحوّل صفوف stooq إلى حقائق point_in_time — سعر الإغلاق معروف فعلياً
    بنفس يوم الإغلاق (بعد إغلاق السوق)."""
    from trading import point_in_time as pit
    facts = [
        {"source": "stooq", "ticker": ticker, "metric": "close", "value": r["close"],
         "period": r["date"], "known_on": r["date"]}
        for r in rows
    ]
    return pit.record_facts_bulk(facts) if facts else []


def ingest_sec_facts_as_facts(ticker, rows, metric="revenue"):
    """يحوّل صفوف SEC EDGAR إلى حقائق point_in_time — known_on هو filed
    الحقيقي، لا نهاية الفترة المالية (هذا بالضبط ما يمنع الحلقة #3)."""
    from trading import point_in_time as pit
    facts = [
        {"source": "sec_edgar", "ticker": ticker, "metric": metric, "value": r["value"],
         "period": r["period"], "known_on": r["filed"], "extra": {"form": r.get("form")}}
        for r in rows
    ]
    return pit.record_facts_bulk(facts) if facts else []


# ===== بديل تجريبي صريح — يُستخدم فقط إن تعذّر الاتصال بأي مصدر حقيقي =====

DEMO_TICKERS = ["ADEM", "BRKT", "CVLX", "DRFT", "ELYS", "FNDR", "GLMR", "HRVN"]


def demo_dataset(seed=42, days=260, start="2023-01-02"):
    """بيانات اصطناعية موسومة بوضوح 'is_demo': True — بذرة ثابتة فتكرار
    التشغيل يعطي نفس الأرقام بالضبط. لا تُستخدم أبداً كأنها بيانات سوق
    حقيقية؛ فقط لإثبات أن المحرك يعمل صح حين لا يوجد اتصال خارجي."""
    rng = random.Random(seed)
    import datetime
    cur = datetime.date.fromisoformat(start)
    price_facts, fundamental_facts, listings = [], [], []

    for ticker in DEMO_TICKERS:
        price = rng.uniform(20, 180)
        drift = rng.uniform(-0.0004, 0.0012)
        vol = rng.uniform(0.012, 0.03)
        listed_start = (cur - datetime.timedelta(days=rng.randint(0, 400))).isoformat()
        delisted = rng.random() < 0.12  # يشابه شركات تُفلس خلال الفترة — لاختبار survivorship_gap
        listing_end = None
        d = cur
        quarter_counter = 0
        base_revenue = rng.uniform(5e7, 5e9)
        for i in range(days):
            price *= max(0.5, 1 + drift + rng.gauss(0, vol))
            date_s = d.isoformat()
            price_facts.append({"ticker": ticker, "metric": "close", "value": round(price, 2),
                                 "period": date_s, "known_on": date_s, "source": "demo"})
            if i % 63 == 0:  # إيداع ربعي تقريبي
                quarter_counter += 1
                growth = rng.gauss(0.03, 0.08)
                base_revenue *= (1 + growth)
                filed = (d + datetime.timedelta(days=rng.randint(25, 45))).isoformat()
                printed_value = base_revenue * rng.uniform(0.9, 1.0)  # أول رقم مطبوع، غالباً متحفظ
                fundamental_facts.append({
                    "ticker": ticker, "metric": "revenue", "value": round(printed_value, 2),
                    "period": f"Q{quarter_counter}", "known_on": filed, "source": "demo",
                })
                # تصحيح لاحق أحياناً — يحاكي "ما طُبع لاحقاً" بالحلقة #3
                if rng.random() < 0.3:
                    restated_filed = (d + datetime.timedelta(days=rng.randint(200, 400))).isoformat()
                    fundamental_facts.append({
                        "ticker": ticker, "metric": "revenue", "value": round(base_revenue, 2),
                        "period": f"Q{quarter_counter}", "known_on": restated_filed, "source": "demo",
                    })
            if delisted and i == int(days * rng.uniform(0.3, 0.9)):
                listing_end = date_s
                d += datetime.timedelta(days=1)
                break
            d += datetime.timedelta(days=1)
        listings.append({"ticker": ticker, "start_date": listed_start, "end_date": listing_end,
                          "note": "demo — أُفلست اصطناعياً" if listing_end else ""})

    return {
        "is_demo": True,
        "seed": seed,
        "tickers": DEMO_TICKERS,
        "price_facts": price_facts,
        "fundamental_facts": fundamental_facts,
        "listings": listings,
    }


def load_demo_into_store(seed=42):
    """يحمّل demo_dataset كاملاً في point_in_time + universe — يمسح أي
    بيانات تجريبية سابقة أولاً حتى لا تتكرر."""
    from trading import point_in_time as pit, universe
    data = demo_dataset(seed=seed)
    pit.clear_all()
    pit.record_facts_bulk(data["price_facts"])
    pit.record_facts_bulk(data["fundamental_facts"])
    universe._save({"listings": []})
    universe.record_listings_bulk(data["listings"])
    return {"is_demo": True, "tickers": data["tickers"],
            "price_facts": len(data["price_facts"]), "fundamental_facts": len(data["fundamental_facts"])}


if __name__ == "__main__":
    rows = fetch_daily_prices_stooq("AAPL")
    if rows:
        print(f"✅ اتصال حقيقي بـ stooq نجح: {len(rows)} يوم سعر لـ AAPL")
    else:
        print("⚠️ تعذّر الاتصال بـ stooq — استخدم demo_dataset() بدلاً منه")
