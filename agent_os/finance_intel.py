"""
finance_intel.py - النظام 10: الذكاء المالي (v3.0)
===================================================
عندما تصحى تجد: الإيرادات، المصروفات، الصافي، أفضل مصدر دخل، أفضل فرصة.
فئات: إيرادات، مصروفات، تكاليف API، استضافة، اشتراكات، جوالات بجتي،
عمل حر، مبيعات منتجات، استرداد، ربح، عائد استثمار.

الاستخدام:
  python agent_os/finance_intel.py add <فئة> <مبلغ> <وصف>
  python agent_os/finance_intel.py report
  python agent_os/finance_intel.py today
"""

import os
import sys
import json
import gzip
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

FINANCE_FILE = os.path.join(C.AGENT_OS_DIR, "finance.json")
ARCHIVE_DIR = os.path.join(C.AGENT_OS_DIR, "archives")

CATEGORIES = {
    "revenue": "إيرادات", "expense": "مصروف", "api_cost": "تكلفة API",
    "hosting": "استضافة", "subscription": "اشتراك", "bounty": "جوالة بجتي",
    "freelance": "عمل حر", "sale": "مبيعات منتجات", "refund": "استرداد",
}


def _load():
    return C.load_json(FINANCE_FILE, {"txns": [], "next_id": 1, "self_earned_usd": 0.0,
                                      "spent_today_usd": 0.0, "last_reset": "", "ledger": []})


def _save(s):
    C.atomic_write(FINANCE_FILE, s)


MAX_PAID_COST_USD = float(os.environ.get("SELFRUNNER_MAX_COST_USD", "2.0"))

# تقدير تكلفة مكالمة مجانية تقريباً (إن كلفت شيئاً) — لعرض التوفير اليومي (عيب 25)
FREE_CALL_ESTIMATE_USD = float(os.environ.get("FREE_CALL_ESTIMATE_USD", "0.0015"))


def _reset_if_new_day(state):
    """سقف يومي يتجدد كل يوم."""
    today = str(datetime.date.today())
    if state.get("last_reset") != today:
        state["spent_today_usd"] = 0.0
        state["free_calls_today"] = 0
        state["last_reset"] = today
    return state


def record_income(source, amount_usd, note=""):
    """دخل يُسجَّل في رصيد الوكيل — لا يلمس أي حساب بنكي إطلاقاً."""
    state = _reset_if_new_day(_load())
    state["self_earned_usd"] += float(amount_usd)
    state.setdefault("ledger", []).append({"type": "income", "source": source,
                                           "amount": float(amount_usd), "note": note[:200],
                                           "time": C.now_iso()})
    _save(state)
    return state["self_earned_usd"]


def can_spend(amount_usd, is_free_provider=False):
    """المجاني لا يُحتسب أبداً؛ المدفوع من رصيد مكتسب فقط + سقف يومي."""
    if is_free_provider:
        return True
    state = _reset_if_new_day(_load())
    if state["spent_today_usd"] + amount_usd > MAX_PAID_COST_USD:
        return False
    if state["self_earned_usd"] < amount_usd:
        return False
    return True


def record_expense(purpose, amount_usd, is_free_provider=False):
    """نفقة فعلية تخصم من رصيد الوكيل تحت السقف اليومي."""
    if is_free_provider:
        return True
    state = _reset_if_new_day(_load())
    if not can_spend(amount_usd, is_free_provider):
        return False
    state["spent_today_usd"] += float(amount_usd)
    state["self_earned_usd"] -= float(amount_usd)
    state.setdefault("ledger", []).append({"type": "expense", "purpose": purpose[:200],
                                           "amount": float(amount_usd), "time": C.now_iso()})
    _save(state)
    return True


def record_free_use(note=""):
    """كل استخدام لمزوّد مجاني يُحسب ويُعرض توفيره في التقرير (عيب 25) —
    المجاني لا يلمس الميزانية إطلاقاً، بل يزيد عداد الوفورات."""
    state = _reset_if_new_day(_load())
    state.setdefault("free_calls_today", 0)
    state["free_calls_today"] += 1
    state["ledger"].append({"type": "free", "note": note[:200], "time": C.now_iso()})
    _save(state)
    return state["free_calls_today"]


def daily_report():
    """الميزانية اليومية: مكتسب/مصروف/متبقٍ من السقف + توفير المجاني (عيب 25)."""
    state = _reset_if_new_day(_load())
    today = str(datetime.date.today())
    today_income = sum(e["amount"] for e in state.get("ledger", [])
                       if e.get("type") == "income" and e.get("time", "").startswith(today))
    free_calls = state.get("free_calls_today", 0)
    return {
        "self_earned_usd": round(state["self_earned_usd"], 4),
        "spent_today_usd": round(state["spent_today_usd"], 4),
        "income_today_usd": round(today_income, 4),
        "budget_remaining_today": round(max(0, MAX_PAID_COST_USD - state["spent_today_usd"]), 4),
        "free_calls_today": free_calls,
        "free_savings_usd": round(free_calls * FREE_CALL_ESTIMATE_USD, 4),
    }


# ===== أرشفة برد (cold) بلا حذف: كل البيانات تصان، فقط تُنقل لملف مضغوط =====

def _arch_path(month):
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    return os.path.join(ARCHIVE_DIR, f"txns_{month}.json.gz")


def read_archive(month):
    """قراءة أرشيف شهر: يعيد كل حركاته (أو [] إن لم يوجد)."""
    path = _arch_path(month)
    if not os.path.exists(path):
        return []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def archive_old_records(cutoff_days=30):
    """نقش: حركات أقدم من cutoff_days تُنقل (لا تُحذف) إلى أرشيف الشهر.
    المجاني/الحالي لا يتأثر — البيانات تبقى كاملة وتُقرأ عند الحاجة."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=cutoff_days)).isoformat()
    state = _load()
    moving, keep = [], []
    for t in state["txns"]:
        d = (t.get("date") or "")[:10]
        if d and d < cutoff:
            moving.append(t)
        else:
            keep.append(t)
    if not moving:
        return {"moved": 0, "months": []}
    by_month = {}
    for t in moving:
        m = (t.get("date") or "")[:7]
        by_month.setdefault(m, []).append(t)
    for m, items in sorted(by_month.items()):
        combined = read_archive(m) + items
        with gzip.open(_arch_path(m), "wt", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False)
    state["txns"] = keep
    _save(state)
    months = sorted(by_month)
    C.log(f"📦 أُرشفت {len(moving)} حركة مالية ({', '.join(months)}) — بلا حذف")
    return {"moved": len(moving), "months": months}


def add_transaction(category, amount, note=""):
    """تسجيل حركة: فئات الدخل تجمع، والباقي تطرح."""
    if category not in CATEGORIES:
        raise ValueError(f"الفئة غير معروفة: {category}. المتاح: {', '.join(CATEGORIES)}")
    state = _load()
    txn = {
        "id": state["next_id"],
        "category": category,
        "label": CATEGORIES[category],
        "amount": round(float(amount), 2),
        "income": category in ("revenue", "bounty", "freelance", "sale"),
        "note": note[:200],
        "date": C.now_iso(),
    }
    state["next_id"] += 1
    state["txns"].append(txn)
    _save(state)
    sign = "+" if txn["income"] else "-"
    C.log(f"💰 {sign}{txn['amount']} ({CATEGORIES[category]}) — {note}")
    return txn


def _in_month(txns, months=0):
    now = datetime.datetime.now()
    base = (now.year, now.month - months)
    y, m = (base[0] - 1, 12) if base[1] <= 0 else base
    return [t for t in txns if (int(t["date"][:4]), int(t["date"][5:7])) == (y, m)] if months else txns[-1000:]


def report(months=0):
    """تقرير شهري: دخل/مصروف/صافي + أفضل مصدر + أفضل شهر."""
    txns = _in_month(_load()["txns"], months)
    income = sum(t["amount"] for t in txns if t["income"])
    expenses = sum(t["amount"] for t in txns if not t["income"])
    by_source = {}
    for t in txns:
        if t["income"]:
            by_source[t["label"]] = by_source.get(t["label"], 0) + t["amount"]
    best = max(by_source.items(), key=lambda kv: kv[1])[0] if by_source else "لا يوجد"
    return {
        "period": "شهر" if months else "كل البيانات",
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "net": round(income - expenses, 2),
        "best_source": best,
        "roi": round((income - expenses) / expenses, 2) if expenses else None,
    }


def morning_brief():
    """ملخص صباحي جاهز للتقارير."""
    from agent_os import benchmark
    r = report()
    bench = benchmark.summary()
    lines = []
    lines.append(f"الإيرادات: ${r['income']}")
    lines.append(f"المصروفات: ${r['expenses']}")
    lines.append(f"الصافي: ${r['net']}")
    if r["best_source"] != "لا يوجد":
        lines.append(f"أفضل مصدر دخل: {r['best_source']}")
    lines.append(f"أضعف مجال للوكيل: {', '.join(bench.get('weakest', []))}")
    return "\n".join(lines)


def totals():
    return report()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("الاستعمال: add <فئة> <مبلغ> <وصف> | report | brief")
    elif args[0] == "add" and len(args) >= 3:
        add_transaction(args[1], args[2], " ".join(args[3:]))
    elif args[0] == "report":
        r = report()
        for k, v in r.items():
            print(f"  {k}: {v}")
    elif args[0] == "brief":
        print(morning_brief())