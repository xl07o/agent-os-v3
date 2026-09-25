"""
revenue_engine.py - محرّك الإيرادات (ركن 18% ← الهدف)
======================================================
لا «دخل مالي مجاني» وهمي — كتابة أمانة: دفتر دخل/مصروف، جرد منتجات قابلة للشحن،
فواتير أولية، وأفق دخل شهري سُفلي يأخذه الموظف كهدف.

  - sales_ledger.json: كل إيراد مدخل (sale/service/bounty/credit) ليد للموظف فقط.
  - يمكن للموظف توليد فاتورة مصطلحية (بلا تعاملات مالية فعلية بلا موافقة بنكية —
    البنك عبر ملف الطلبات البشرية كما فعّلت سابقاً).

الاستخدام:
  python agent_os/revenue_engine.py income <مصدر> <مبلغ>
  python agent_os/revenue_engine.py sales-ready
  python agent_os/revenue_engine.py invoice <عميل> <مبلغ> <وصف>
  python agent_os/revenue_engine.py report
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

LEDGER_FILE = os.path.join(C.AGENT_OS_DIR, "sales_ledger.json")
INVOICES_DIR = os.path.join(C.AGENT_OS_DIR, "invoices")


def _ledger():
    return C.load_json(LEDGER_FILE, {"rows": []})


def add_income(source, amount, kind="sale"):
    """دخول دخل حقيقي (يعمل الموظف الأمانة: يُصرَّح أو لا يُسجَّل وهمياً)."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "مبلغ غير رقمي"}
    if amount <= 0:
        return {"ok": False, "reason": "مبلغ غير موجب"}
    if kind not in ("sale", "service", "bounty", "credit"):
        kind = "sale"
    st = _ledger()
    row = {"time": C.now_iso(), "source": str(source)[:120],
           "amount": amount, "kind": kind}
    st["rows"].append(row)
    C.atomic_write(LEDGER_FILE, st)
    C.log(f"💵 إيراد: {amount:.2f}$ ← {source}")
    return {"ok": True, "row": row}


def sales_ready():
    """منتجات مكتملة في المصنع جاهزة للعرض/البيع — الحقيقية لا الافتراضية."""
    try:
        from agent_os import product_factory
        prods = product_factory.list_products()
        return [p for p in prods if p.get("status") == "built"]
    except Exception:
        return []


def invoice(customer, amount, description="", issue=True):
    """فاتورة مصطلحية (وثيقة أولية) — لا ترسل أموالاً؛ الدفع عبر موافقة بنكية بشرية."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "مبلغ غير رقمي"}
    import json
    os.makedirs(INVOICES_DIR, exist_ok=True)
    num = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    doc = {
        "invoice": f"INV-{num}", "customer": customer[:120],
        "amount": amount, "description": (description or "")[:300],
        "issued": C.now_iso(), "paid": False,
    }
    path = os.path.join(INVOICES_DIR, f"{doc['invoice']}.json")
    C.atomic_write(path, doc)
    return {"ok": True, "invoice": doc, "path": path, "payment": "بانتظار موافقة بشرية"}


def report():
    """ملخص دفتر الإيرادات والمنتجات الجاهزة — للموظف والنواة."""
    rows = _ledger().get("rows", [])
    total = round(sum(r["amount"] for r in rows), 2)
    by_kind = {}
    for r in rows:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + r["amount"]
    return {
        "entries": len(rows),
        "total_usd": total,
        "by_kind": by_kind,
        "sales_ready": len(sales_ready()),
        "ledger": LEDGER_FILE,
        "note": "دخل حقيقي يُسجَّل بإذن صرّح عنه؛ لا إيراد وهمي أبداً",
    }


if __name__ == "__main__":
    import json
    args = sys.argv[1:]
    if not args or args[0] == "report":
        print(json.dumps(report(), ensure_ascii=False, indent=1))
    elif args[0] == "income" and len(args) >= 3:
        print(json.dumps(add_income(args[1], args[2]), ensure_ascii=False, indent=1))
    elif args[0] == "sales-ready":
        for p in sales_ready():
            print(f"- {p['name']} ({p['type']}) — {p['path']}")
    elif args[0] == "invoice" and len(args) >= 3:
        print(json.dumps(invoice(args[1], args[2],
                                 " ".join(args[3:])), ensure_ascii=False, indent=1))
    else:
        print("الاستعمال: income <مصدر> <مبلغ> | sales-ready | invoice <عميل> <مبلغ> [وصف] | report")