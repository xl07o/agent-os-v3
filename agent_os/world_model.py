"""
world_model.py - النظام 12: نموذج العالم المركزي (v3.0)
=========================================================
صورة حال كل ما يجري: مشاريع، منتجات، إيرادات، أهداف، أدوات، طلبات،
عمليات نشر، نتائج قياس، استخبارات، وتطور من اليوم السابق.

  build()   -> OCSV unified snapshot (دون أسنان من دماغ الشبكة)
  daily_delta() -> ما الذي تغيّر عن اليوم الماضي.

الاستخدام:
  python agent_os/world_model.py build
  python agent_os/world_model.py delta
"""

import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

# حالة اليوم السابق (قبل إعادة البناء) للتطوير diff
WORLD_FILE = os.path.join(C.AGENT_OS_DIR, "world_state.json")


def _today():
    return datetime.date.today().isoformat()


def build():
    """اجمع كل مصادر الحالة في كائن واحد متسق (يعمل بلا شبكة)."""
    s = {
        "built": C.now_iso(),
        "day": _today(),
        "goals": _count_status("agent_os.goal_manager", "goals", "active"),
        "benchmark": _count("agent_os/benchmark", "results"),
        "subsystems": {},
        "products": _count("agent_os/product_factory", "products"),
        "deploys": _count("agent_os/devops_agent", "deploys"),
        "tools": _count("agent_os/tool_registry", "tools"),
        "requests_pending": _count("agent_os/approval_center", "requests"),
        "findings": _count("agent_os/bounty_engine", "findings"),
        "txns": _count("agent_os/finance_intel", "txns"),
    }
    for mod, key in [
        ("agent_os.tool_registry", "tools"),
        ("agent_os.browser_agent", "state"),
        ("agent_os.product_factory", "products"),
        ("agent_os.devops_agent", "deploys"),
        ("agent_os.bounty_engine", "findings"),
        ("agent_os.business_autopilot", "ideas"),
        ("agent_os.finance_intel", "txns"),
        ("agent_os.approval_center", "requests"),
        ("agent_os.goal_manager", "goals"),
        ("agent_os.benchmark", "results"),
        ("agent_os.self_improve_engine", "improvements"),
    ]:
        try:
            m = __import__(mod, fromlist=["x"])
            data = m.list_related() if hasattr(m, "list_related") else m._load()
            if isinstance(data, dict) and key in data:
                s["subsystems"][mod] = {"count": len(data[key])}
        except Exception as e:
            s["subsystems"][mod] = {"error": str(e)[:80]}
    # استخبارات اليوم إن توفر
    try:
        import news_intel
        intel = news_intel.get_latest_intel()
        s["intel"] = {
            "news": len(intel.get("tech_news", [])) if intel else 0,
            "hn": len(intel.get("hacker_news", [])) if intel else 0,
        }
    except Exception:
        s["intel"] = {"error": "غير متاح"}
    C.atomic_write(WORLD_FILE, s)
    C.log(f"🌍 بناء نموذج العالم: {s['day']}")
    return s


def _count(mod, key):
    try:
        m = __import__(mod, fromlist=["x"])
        data = m._load()
        return len(data.get(key, [])) if isinstance(data, dict) else 0
    except Exception:
        return 0


def _count_status(mod, key, status):
    try:
        m = __import__(mod, fromlist=["x"])
        data = m._load()
        items = data.get(key, [])
        active = sum(1 for it in items if it.get("status") == status)
        return {"total": len(items), status: active}
    except Exception:
        return {"total": 0}


def daily_delta():
    """احسب ما تغيّر منذ آخر بناء."""
    prev = C.load_json(WORLD_FILE, None)
    cur = build()
    if not prev:
        return {"prev": None, "changes": ["أول بناء للنموذج"]}
    changes = []
    for k, v in cur.items():
        if k in ("built", "subsystems", "intel", "kpi"):
            continue
        if prev.get(k) != v:
            changes.append(f"{k}: {prev.get(k)} → {v}")
    if not changes:
        changes.append("لم يطرأ تغيير")
    return {"prev_day": prev.get("day"), "today": cur["day"], "changes": changes}


def kpi():
    """لوحة مؤشرات الأداء: كل الأرقام الحيوية في صف واحد."""
    w = C.load_json(WORLD_FILE, None) or build()
    return {
        "day": w.get("day"),
        "goals_active": w.get("goals", {}).get("active", 0),
        "products": w.get("products", 0),
        "deploys": w.get("deploys", 0),
        "tools": w.get("tools", 0),
        "pending_human": w.get("requests_pending", 0),
        "findings": w.get("findings", 0),
        "benchmark_runs": w.get("benchmark", 0),
    }


def narrative():
    """نص جاهز للإدراج في التقارير."""
    w = C.load_json(WORLD_FILE, None) or build()
    raw, _ = C.call_brain(
        "أنت رئيس أركان رقمي تشرح الوضع باختصار.",
        f"""صف الوضع الحالي بجملة أو اثنتين:
الأهداف النشطة: {w.get('goals', {}).get('active', 0)}
المنتجات: {w.get('products', 0)} | النشرات: {w.get('deploys', 0)}
طوابير الطلبات: {w.get('requests_pending', 0)}""",
    )
    return (raw or "الوضع مستقر — لا تغييرات ملحوظة.").strip()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "delta":
        print(daily_delta())
    elif args and args[0] == "narrative":
        print(narrative())
    else:
        print(build())