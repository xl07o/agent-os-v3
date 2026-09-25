"""
opportunity_brain.py - عقل الفرص التجارية (ركن 18% ← الهدف)
=============================================================
يجمع إشارات محلية بلا شبكة في قائمة فرص مرّتبة بالنقاط:

  - ميزانية اليوم + الرصيد المكتسب (finance_intel)
  - أهداف نشطة غير منجزة (goal_manager)
  - منتجات جاهزة للبيع في products.json (product_factory)
  - مستودعات مرخّصة جديدة من github_hunter.new_hunt_since

يرتب النتيجة في opportunities.json ويوصي أعلى فرصة — والنواة تحوّلها هدفاً.

الاستخدام:
  python agent_os/opportunity_brain.py scan
  python agent_os/opportunity_brain.py top
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

OPP_FILE = os.path.join(C.AGENT_OS_DIR, "opportunities.json")


def scan():
    """اجمع الإشارات ورتّب الفرص محلياً (بلا إجابة مفتوحة)."""
    import datetime
    opps = []
    try:
        from agent_os import finance_intel
        fin = finance_intel.daily_report()
        if fin.get("self_earned_usd", 0) > 0:
            opps.append({"name": "تشغيل paid-task في السقف المكتسب",
                         "score": 90, "kind": "revenue", "tag": "budget",
                         "note": f"رصيد مكتسب {fin.get('self_earned_usd')} نقداً"})
    except Exception:
        pass
    try:
        from agent_os import goal_manager
        active = goal_manager.get_active_goals() or []
        if active:
            opps.append({"name": "أكمل الأهداف النشطة", "score": 80,
                         "kind": "goals", "tag": "focus",
                         "note": f"{len(active)} هدف نشط"})
    except Exception:
        pass
    try:
        from agent_os import product_factory
        products = product_factory.list_products()
        ready = [p for p in products if p.get("status") == "built"]
        if ready:
            opps.append({"name": "تجهيز منتجات للعرض/البيع", "score": 85,
                         "kind": "revenue", "tag": "ship",
                         "note": f"{len(ready)} منتج مكتمل في المصنع"})
    except Exception:
        pass
    try:
        from agent_os import github_hunter
        h = github_hunter.new_hunt_since(datetime.date.today().strftime("%Y-%m-%d"))
        if h:
            opps.append({"name": f"تعلّم نمط من {len(h)} مادة مرخّصة جديدة",
                         "score": 70, "kind": "learning", "tag": "github",
                         "note": h[-1]["query"]})
    except Exception:
        pass
    opps.sort(key=lambda o: -o["score"])
    state = {"scanned": C.now_iso(), "opportunities": opps[:6]}
    C.atomic_write(OPP_FILE, state)
    C.log(f"🚀 عقل الفرص: {len(opps)} فرصة مرصودة")
    return state


def top():
    return C.load_json(OPP_FILE, {"opportunities": []}).get("opportunities", [])


if __name__ == "__main__":
    import json
    if sys.argv[1:2] == ["top"]:
        for o in top():
            print(f"[{o['score']}] {o['name']} — {o.get('note', '')[:80]}")
    else:
        print(json.dumps(scan(), ensure_ascii=False, indent=1))