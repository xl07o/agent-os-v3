"""
أسعار أسهم/عملات حقيقية — من Yahoo Finance (واجهة chart العامة، بلا مفتاح).

يغطي الأسهم الأمريكية (AAPL)، تداول السعودي (2222.SR = أرامكو)، والعملات
الرقمية (BTC-USD)، والمؤشرات (^GSPC). الأسعار ممكن تتأخر حسب السوق —
كل نتيجة فيها وقت آخر سعر من المصدر نفسه، والواجهة تعرضه.

ما فيه أي رقم من عندنا: لو المصدر ما رد، نرجّع خطأ صريح، لا سعر قديم
متنكّر ولا رقم تقديري. كاش 60 ثانية فقط عشان اللوحة ما تغرق المصدر.
"""

import re
import threading
import time

import requests

_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
_UA = "Mozilla/5.0 (X11; Linux x86_64) agent_os4-dashboard"
_TIMEOUT = 15
_CACHE_SECONDS = 60
SOURCE = "Yahoo Finance"

# المدى ← الدقّة: يوم واحد بفواصل 5 دقائق = متابعة شبه لحظية
RANGES = {"1d": "5m", "5d": "30m", "1mo": "1d", "6mo": "1d", "1y": "1wk"}
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-^=]{1,20}$")

_cache: dict[tuple[str, str], tuple[float, dict]] = {}
_lock = threading.Lock()


def valid_symbol(symbol: str) -> bool:
    return bool(_SYMBOL_RE.match(symbol or ""))


def chart(symbol: str, rng: str = "1mo") -> dict:
    symbol = (symbol or "").strip().upper()
    if not valid_symbol(symbol):
        return {"ok": False, "error": f"رمز غير صالح: {symbol!r}"}
    if rng not in RANGES:
        return {"ok": False, "error": f"مدى غير مدعوم: {rng}"}
    key = (symbol, rng)
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < _CACHE_SECONDS:
            return hit[1]
    result = _fetch(symbol, rng)
    if result["ok"]:
        with _lock:
            _cache[key] = (time.time(), result)
    return result


def _fetch(symbol: str, rng: str) -> dict:
    try:
        r = requests.get(
            _BASE + requests.utils.quote(symbol, safe=""),
            params={"range": rng, "interval": RANGES[rng]},
            headers={"User-Agent": _UA}, timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        return {"ok": False, "error": f"تعذّر الوصول لـ{SOURCE}: {type(e).__name__}"}
    if r.status_code == 404:
        return {"ok": False, "error": f"الرمز {symbol} مو موجود عند {SOURCE}"}
    if r.status_code != 200:
        return {"ok": False, "error": f"{SOURCE} رجّع HTTP {r.status_code}"}
    try:
        res = r.json()["chart"]["result"][0]
        meta = res["meta"]
        price = float(meta["regularMarketPrice"])
    except (ValueError, KeyError, IndexError, TypeError):
        return {"ok": False, "error": f"رد {SOURCE} ما فيه سعر للرمز {symbol}"}
    quote = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    points = [
        {"t": t, "c": round(c, 4)}
        for t, c in zip(res.get("timestamp") or [], quote.get("close") or [])
        if c is not None
    ]
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    change = (price - prev) if prev else None
    return {
        "ok": True, "symbol": meta.get("symbol", symbol), "name": meta.get("longName") or meta.get("shortName") or "",
        "currency": meta.get("currency", ""), "exchange": meta.get("exchangeName", ""),
        "price": price, "previous_close": prev,
        "change": round(change, 4) if change is not None else None,
        "change_pct": round(change / prev * 100, 2) if change is not None and prev else None,
        "market_time": meta.get("regularMarketTime"), "range": rng, "points": points,
        "source": SOURCE, "fetched_at": int(time.time()),
    }
