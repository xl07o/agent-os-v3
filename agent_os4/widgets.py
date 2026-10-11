"""
ودجت لوحة التحكم — أنواع محددة مسبقاً فقط (سهم، قائمة متابعة، محفظة).

ليش أنواع محددة وما نخلي الـCEO يكتب واجهة بنفسه: كود HTML/JS يولّده
الذكاء ويتنفذ بمتصفحك = باب لأي شي. هنا الـCEO يختار نوع + إعدادات
(رمز سهم، مدى، كميات)، والواجهة نفسها ثابتة ومختبرة. الأرقام كلها من
market.py (مصدر حقيقي) — الكميات بالمحفظة أنت اللي تدخلها.
"""

import json
import os
import time
import uuid

from . import market

_FILE = os.path.join(os.path.dirname(__file__), "data", "widgets.json")
MAX_WIDGETS = 12
_MAX_SYMBOLS = 12

TYPES = {
    "stock": "سهم واحد — سعر لحظي + رسم بياني",
    "watchlist": "قائمة متابعة — عدة رموز بجدول",
    "portfolio": "محفظة — قيمة ممتلكاتك بأسعار السوق الحالية",
}


def _load() -> list[dict]:
    if not os.path.exists(_FILE):
        return []
    with open(_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save(items: list[dict]) -> None:
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    tmp = _FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _FILE)


def _symbols(raw) -> list[str] | None:
    if isinstance(raw, str):
        raw = [s for s in raw.replace("،", ",").split(",")]
    if not isinstance(raw, list):
        return None
    out = [str(s).strip().upper() for s in raw if str(s).strip()]
    return out if out and all(market.valid_symbol(s) for s in out) else None


def validate(spec: dict) -> tuple[dict | None, str | None]:
    if not isinstance(spec, dict):
        return None, "مواصفات الودجت لازم تكون كائن"
    kind = spec.get("type")
    if kind not in TYPES:
        return None, f"نوع ودجت غير معروف: {kind} (المتاح: {', '.join(TYPES)})"
    config = spec.get("config") if isinstance(spec.get("config"), dict) else {}
    title = str(spec.get("title") or "").strip()[:60]

    if kind == "stock":
        symbol = str(config.get("symbol", "")).strip().upper()
        rng = str(config.get("range", "1d"))
        if not market.valid_symbol(symbol):
            return None, f"رمز سهم غير صالح: {symbol!r}"
        if rng not in market.RANGES:
            return None, f"مدى غير مدعوم: {rng} (المتاح: {', '.join(market.RANGES)})"
        return {"type": kind, "title": title or symbol, "config": {"symbol": symbol, "range": rng}}, None

    if kind == "watchlist":
        symbols = _symbols(config.get("symbols"))
        if not symbols or len(symbols) > _MAX_SYMBOLS:
            return None, f"قائمة الرموز فاضية أو فيها رمز غير صالح (حد أقصى {_MAX_SYMBOLS})"
        return {"type": kind, "title": title or "قائمة متابعة", "config": {"symbols": symbols}}, None

    holdings = []
    for h in config.get("holdings") or []:
        if not isinstance(h, dict):
            return None, "كل عنصر بالمحفظة لازم يكون {symbol, qty}"
        symbol = str(h.get("symbol", "")).strip().upper()
        try:
            qty = float(h.get("qty"))
        except (TypeError, ValueError):
            return None, f"كمية غير صالحة لـ{symbol}"
        if not market.valid_symbol(symbol) or not (0 < qty < 1e12):
            return None, f"عنصر محفظة غير صالح: {symbol} × {h.get('qty')}"
        holdings.append({"symbol": symbol, "qty": qty})
    if not holdings or len(holdings) > _MAX_SYMBOLS:
        return None, f"المحفظة فاضية أو أكبر من {_MAX_SYMBOLS} عنصر"
    return {"type": kind, "title": title or "محفظتي", "config": {"holdings": holdings}}, None


def add(spec: dict, added_by: str = "owner") -> dict:
    cleaned, error = validate(spec)
    if error:
        raise ValueError(error)
    items = _load()
    if len(items) >= MAX_WIDGETS:
        raise ValueError(f"وصلت الحد الأقصى ({MAX_WIDGETS} ودجت) — احذف واحد أولاً")
    widget = {"id": uuid.uuid4().hex[:10], **cleaned, "added_by": added_by,
              "added_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    items.append(widget)
    _save(items)
    return widget


def remove(widget_id: str) -> bool:
    items = _load()
    kept = [w for w in items if w["id"] != widget_id]
    if len(kept) == len(items):
        return False
    _save(kept)
    return True


def list_widgets() -> list[dict]:
    return _load()


def _brief(quote: dict) -> dict:
    keys = ("ok", "error", "symbol", "name", "currency", "price", "change", "change_pct", "market_time")
    return {k: quote.get(k) for k in keys if k in quote}


def data(widget: dict) -> dict:
    cfg = widget["config"]
    if widget["type"] == "stock":
        return market.chart(cfg["symbol"], cfg["range"])
    if widget["type"] == "watchlist":
        return {"ok": True, "rows": [_brief(market.chart(s, "1d")) for s in cfg["symbols"]], "source": market.SOURCE}
    rows, totals, missing = [], {}, []
    for h in cfg["holdings"]:
        q = market.chart(h["symbol"], "1d")
        row = {"symbol": h["symbol"], "qty": h["qty"], **_brief(q)}
        if q.get("ok"):
            row["value"] = round(q["price"] * h["qty"], 2)
            totals[q["currency"]] = round(totals.get(q["currency"], 0) + row["value"], 2)
        else:
            missing.append(h["symbol"])
        rows.append(row)
    # مجموع لكل عملة على حدة — ما نحوّل بين العملات بسعر صرف من عندنا
    return {"ok": True, "rows": rows, "totals": totals, "missing": missing, "source": market.SOURCE}


def snapshot() -> list[dict]:
    return [{**w, "data": data(w)} for w in _load()]
