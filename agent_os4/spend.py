"""
سقف صرف شهري على Claude API — فلوس حقيقية، أرقام حقيقية فقط.

ما فيه "ربط محفظة": الفوترة الفعلية تبقى بحساب Anthropic حقك. هذا
الملف يعدّ تكلفة كل استدعاء من usage اللي ترجعه Anthropic نفسها (لا
تقدير من عندنا)، ويمنع أي استدعاء جديد لو ممكن يتعدّى السقف.

كيف يضمن ما يتعدّى السقف حتى لو فيه طلبات بنفس اللحظة:
قبل كل استدعاء نحجز أسوأ تكلفة ممكنة (كل حرف = توكن إدخال + الحد
الأقصى للإخراج، بأغلى سعر محتمل)، وبعد الرد نحسب التكلفة الفعلية من
usage ونفك الحجز. لو (المصروف + المحجوز + أسوأ تكلفة) > السقف → رفض.
"""

import json
import os
import threading
from datetime import datetime, timezone

from . import env  # noqa: F401 — يضمن تحميل .env قبل أي getenv هنا

_FILE = os.path.join(os.path.dirname(__file__), "data", "spend.json")
_DEFAULT_BUDGET_USD = 10.0
_RECENT_LIMIT = 200

# دولار لكل مليون توكن: (إدخال، إخراج، قراءة كاش). كتابة الكاش = 1.25× الإدخال.
# المصدر: جدول الموديلات الرسمي (Claude API docs). أي موديل مو بالجدول
# يُحسب بأغلى سعر معروف ويُعلَّم "تقديري" — نبالغ بالتكلفة ولا نقلّلها.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-opus-4-8": (5.0, 25.0, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
    "claude-sonnet-5": (2.0, 10.0, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-fable-5-1": (10.0, 50.0, 0.25),
    "claude-fable-5": (10.0, 50.0, 1.00),
}
_HAIKU_LONG_PROMPT = (0.50, 2.50, 0.05)  # Haiku 5.5 لو الإدخال > 100K توكن
_MOST_EXPENSIVE = max(PRICES.values(), key=lambda p: p[1])

_lock = threading.Lock()
_reserved = 0.0


class BudgetExceeded(Exception):
    pass


def _month(now=None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m")


def _load() -> dict:
    if not os.path.exists(_FILE):
        return {"months": {}, "recent": []}
    with open(_FILE, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("months", {})
    data.setdefault("recent", [])
    return data


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    tmp = _FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _FILE)


def _price(model: str, input_tokens: int = 0):
    if model == "claude-haiku-5-5" and input_tokens > 100_000:
        return _HAIKU_LONG_PROMPT, False
    if model in PRICES:
        return PRICES[model], False
    return _MOST_EXPENSIVE, True


def budget_usd() -> float:
    """السقف: المحفوظ من الداشبورد أولاً، ثم OS4_CLAUDE_MONTHLY_BUDGET_USD، ثم 10$."""
    saved = _load().get("budget_usd")
    if saved is not None:
        return float(saved)
    raw = os.getenv("OS4_CLAUDE_MONTHLY_BUDGET_USD")
    try:
        return float(raw) if raw else _DEFAULT_BUDGET_USD
    except ValueError:
        return _DEFAULT_BUDGET_USD


def set_budget(amount) -> float:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        raise ValueError("السقف لازم يكون رقم")
    if not (0 <= value <= 10_000):
        raise ValueError("السقف لازم يكون بين 0 و 10000 دولار")
    with _lock:
        data = _load()
        data["budget_usd"] = round(value, 2)
        _save(data)
    return round(value, 2)


def cost_of(model: str, input_tokens: int, output_tokens: int,
            cache_creation: int = 0, cache_read: int = 0):
    (p_in, p_out, p_cache_read), estimated = _price(model, input_tokens)
    cost = (
        input_tokens * p_in
        + output_tokens * p_out
        + cache_creation * p_in * 1.25
        + cache_read * p_cache_read
    ) / 1_000_000
    return cost, estimated


def worst_case_cost(model: str, prompt: str, max_tokens: int) -> float:
    """حد أعلى مضمون: كل حرف توكن، والإخراج كامل، وبأغلى سعر بين
    الموديل المطلوب وأي موديل ممكن يرد بداله (fallback)."""
    (p_in, p_out, _), _ = _price(model, len(prompt))
    fallback_in, fallback_out = PRICES["claude-opus-5"][:2]
    p_in, p_out = max(p_in, fallback_in), max(p_out, fallback_out)
    return (len(prompt) * p_in + max_tokens * p_out) / 1_000_000


def reserve(model: str, prompt: str, max_tokens: int) -> float:
    """يحجز أسوأ تكلفة قبل الاستدعاء، أو يرفع BudgetExceeded."""
    global _reserved
    worst = worst_case_cost(model, prompt, max_tokens)
    with _lock:
        spent = _load()["months"].get(_month(), {}).get("cost_usd", 0.0)
        limit = budget_usd()
        if spent + _reserved + worst > limit:
            raise BudgetExceeded(
                f"سقف Claude الشهري ({limit:.2f}$) ما يكفي هذا الطلب — "
                f"المصروف هالشهر {spent:.4f}$. ارفع السقف من الداشبورد لو تبي."
            )
        _reserved += worst
    return worst


def release(reservation: float) -> None:
    global _reserved
    with _lock:
        _reserved = max(0.0, _reserved - reservation)


def record(reservation: float, requested_model: str, served_model: str, usage) -> dict:
    """يفك الحجز ويسجّل التكلفة الفعلية من usage حق Anthropic."""
    global _reserved
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    model = served_model or requested_model
    cost, estimated = cost_of(model, input_tokens, output_tokens, cache_creation, cache_read)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "requested_model": requested_model,
        "served_model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
        "cost_usd": round(cost, 6),
        "estimated": estimated,
    }
    with _lock:
        _reserved = max(0.0, _reserved - reservation)
        data = _load()
        month = data["months"].setdefault(_month(), {
            "cost_usd": 0.0, "calls": 0, "input_tokens": 0, "output_tokens": 0,
        })
        month["cost_usd"] = round(month["cost_usd"] + cost, 6)
        month["calls"] += 1
        month["input_tokens"] += input_tokens
        month["output_tokens"] += output_tokens
        data["recent"] = (data["recent"] + [entry])[-_RECENT_LIMIT:]
        _save(data)
    return entry


def summary() -> dict:
    data = _load()
    month = data["months"].get(_month(), {})
    spent = month.get("cost_usd", 0.0)
    limit = budget_usd()
    return {
        "month": _month(),
        "budget_usd": limit,
        "spent_usd": round(spent, 4),
        "remaining_usd": round(max(0.0, limit - spent), 4),
        "calls": month.get("calls", 0),
        "input_tokens": month.get("input_tokens", 0),
        "output_tokens": month.get("output_tokens", 0),
        "recent": data["recent"][-10:],
        "history": {k: v.get("cost_usd", 0.0) for k, v in sorted(data["months"].items())[-12:]},
    }
