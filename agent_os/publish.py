# -*- coding: utf-8 -*-
"""
publish.py - النشر والدفع (هيكل آمن)
====================================
يحوّل مخرجات الوكيل إلى منتج قابل للنشر وسجل إيراد محلي:

    create_product(title, content, price)  -> مجلد جاهز في output/publish/<slug>/
    record_sale(slug, amount, note)         -> قيد في data/agent_os/sales.jsonl
    report()                                -> إجماليات الإيراد والمنتجات

قواعد أمان/قانون:
  - لا نشر شبكي تلقائي ولا وصول لحساب دفع. المستخدم يعيّن رابط الدفع
    في AGENT_OS_PAYMENT_LINK ثم يرفع المجلد بنفسه (Netlify/GitHub Pages/متجره).
  - لا مفاتيح ولا بيانات دفع تُخزَّن هنا أبداً.
"""

import os
import re
import sys
import json
import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
from agent_os import _common as C

PRODUCTS_FILE = os.path.join(C.AGENT_OS_DIR, "products.json")
SALES_FILE = os.path.join(C.AGENT_OS_DIR, "sales.jsonl")
PUBLISH_DIR = os.path.join(BASE, "output", "publish")


def _slug(text):
    s = re.sub(r"[^\w\s-]", "", str(text), flags=re.UNICODE).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    return (s or "product")[:60]


def _payment_link():
    return os.getenv("AGENT_OS_PAYMENT_LINK", "").strip()


_PAGE = """<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root{{--bg:#0b0f14;--card:#121821;--fg:#e8eef5;--mut:#8aa0b4;--acc:#37d0c4}}
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:system-ui,'Segoe UI',Tahoma,sans-serif;background:var(--bg);color:var(--fg);line-height:1.8}}
  .wrap{{max-width:820px;margin:0 auto;padding:48px 20px}}
  .card{{background:var(--card);border:1px solid #1e2a37;border-radius:16px;padding:32px}}
  h1{{margin:0 0 8px;font-size:30px}}
  .price{{color:var(--acc);font-size:26px;font-weight:700}}
  .body{{margin:24px 0;white-space:pre-wrap}}
  .btn{{display:inline-block;background:var(--acc);color:#04201d;font-weight:700;text-decoration:none;padding:14px 28px;border-radius:10px}}
  .note{{color:var(--mut);font-size:13px;margin-top:18px}}
</style>
</head>
<body><div class="wrap"><div class="card">
  <h1>{title}</h1>
  <div class="price">{price_txt}</div>
  <div class="body">{body}</div>
  {cta}
  <div class="note">{note}</div>
</div></div></body></html>
"""


def create_product(title, content, price_usd=0.0, tags=None, payment_link=None):
    """ينشئ منتجاً + صفحة هبوط جاهزة. يعيد بيانات المنتج."""
    link = (payment_link or _payment_link()).strip()
    slug = _slug(title)
    folder = os.path.join(PUBLISH_DIR, slug)
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        return {"ok": False, "reason": str(e)[:160]}

    price_txt = f"${float(price_usd):.2f}"
    if link:
        cta = f'<a class="btn" href="{link}">اشترِ الآن</a>'
        note = "الدفع عبر الرابط الآمن أعلاه."
    else:
        cta = '<span class="note">⚠️ لم يُعيَّن رابط دفع بعد — عيّن AGENT_OS_PAYMENT_LINK.</span>'
        note = "لتفعيل الشراء: عيّن رابط الدفع الخاص بك في متغير البيئة AGENT_OS_PAYMENT_LINK."

    body = str(content).strip().replace("<", "&lt;")
    html = _PAGE.format(title=str(title), price_txt=price_txt, body=body, cta=cta, note=note)
    try:
        with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        return {"ok": False, "reason": str(e)[:160]}

    data = C.load_json(PRODUCTS_FILE, {"items": []})
    rec = {"slug": slug, "title": str(title), "price_usd": float(price_usd),
           "tags": list(tags or []), "folder": folder,
           "payment_ready": bool(link), "created": C.now_iso(),
           "sales": 0, "revenue_usd": 0.0}
    data["items"] = [p for p in data.get("items", []) if p.get("slug") != slug] + [rec]
    C.atomic_write(PRODUCTS_FILE, data)
    return {"ok": True, "slug": slug, "folder": folder, "payment_ready": bool(link)}


def record_sale(slug, amount_usd, note=""):
    """يسجّل بيعة في السجل ويزيد إجمالي المنتج. لا يلمس أي بوابة دفع."""
    slug = _slug(slug)
    amt = float(amount_usd)
    line = json.dumps({"time": C.now_iso(), "slug": slug, "amount_usd": amt,
                       "note": str(note)[:200]}, ensure_ascii=False)
    try:
        with open(SALES_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        return {"ok": False, "reason": str(e)[:160]}
    data = C.load_json(PRODUCTS_FILE, {"items": []})
    for p in data.get("items", []):
        if p.get("slug") == slug:
            p["sales"] = int(p.get("sales", 0)) + 1
            p["revenue_usd"] = round(float(p.get("revenue_usd", 0.0)) + amt, 4)
    C.atomic_write(PRODUCTS_FILE, data)
    try:
        from agent_os import event_bus
        event_bus.publish("sale", {"slug": slug, "amount_usd": amt})
    except Exception:
        pass
    return {"ok": True, "slug": slug, "amount_usd": amt}


def sales_ledger():
    out = []
    if os.path.exists(SALES_FILE):
        try:
            with open(SALES_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            out.append(json.loads(line))
                        except Exception:
                            continue
        except Exception:
            pass
    return out


def report():
    items = C.load_json(PRODUCTS_FILE, {"items": []}).get("items", [])
    ledger = sales_ledger()
    ready = sum(1 for p in items if p.get("payment_ready"))
    return {"products": len(items), "payment_ready": ready,
            "total_sales": len(ledger),
            "total_revenue_usd": round(sum(e.get("amount_usd", 0.0) for e in ledger), 4),
            "publish_dir": PUBLISH_DIR}


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "create" and len(args) >= 3:
        print(json.dumps(create_product(args[1], args[2]), ensure_ascii=False, indent=1))
    elif args and args[0] == "sale" and len(args) >= 3:
        print(json.dumps(record_sale(args[1], args[2], args[3] if len(args) > 3 else ""),
                         ensure_ascii=False, indent=1))
    else:
        print(json.dumps(report(), ensure_ascii=False, indent=1))