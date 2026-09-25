"""
registry_center.py - سجل مركزي للأصول (Registries) — ركن توثيق/شغّال
==================================================================
نافذة واحدة **صادقة** فوق كل السجلات المحلية: مهارات، أدوات، فرص،
منتجات، إيرادات. لا نسجّل شيئاً غير موجود؛ نقرأ الملفات الجقيقية ونلخّصها.

الاستخدام:
  python agent_os/register_center.py summary
  python agent_os/register_center.py snapshot [json]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C


def skills_snapshot():
    """السجلات من ذاكرة المهارات: ماذا نعرف فعلاً؟"""
    try:
        from agent_os import skill_memory
        return skill_memory.summarize()
    except Exception as e:
        return {"error": str(e)[:120]}


def tools_snapshot():
    try:
        from agent_os import tool_registry
        return tool_registry.list_available()
    except Exception as e:
        return {"error": str(e)[:120]}


def goals_snapshot():
    try:
        from agent_os import goal_manager
        gs = []
        for g in goal_manager.get_active_goals():
            done = sum(1 for t in g.get("tasks", []) if t.get("status") == "done")
            gs.append({"id": g["id"], "title": g["title"][:60],
                       "priority": g.get("priority"), "done": done,
                       "total": len(g.get("tasks", []))})
        return {"active": gs}
    except Exception as e:
        return {"error": str(e)[:120]}


def opportunities_snapshot():
    try:
        from agent_os import opportunity_brain
        opps = opportunity_brain.top(5).get("opportunities", [])
        return {"count": len(opps), "top": [o["name"][:60] for o in opps[:3]]}
    except Exception:
        return {"count": 0, "top": []}


def revenue_snapshot():
    try:
        from agent_os import revenue_engine
        r = revenue_engine.report()
        return {"total_usd": r["total_usd"], "by_kind": r["by_kind"],
                "sales_ready": r.get("sales_ready", 0)}
    except Exception:
        return {}


def snapshot():
    """قطة سجلّ موحّدة — تُوثَّق بالساعة وتُحفظ كملف."""
    data = {
        "skills": skills_snapshot(),
        "tools": tools_snapshot(),
        "goals": goals_snapshot(),
        "opportunities": opportunities_snapshot(),
        "revenue": revenue_snapshot(),
        "taken_at": C.now_iso(),
    }
    out = os.path.join(C.AGENT_OS_DIR, "registry_snapshot.json")
    C.atomic_write(out, data)
    return data


def summary():
    d = snapshot()
    tools = d.get("tools", {})
    return {
        "skills_records": d.get("skills", {}).get("total", 0),
        "skills_ok": d.get("skills", {}).get("ok_rate", 0),
        "tools_available": len(tools) if isinstance(tools, list) else tools.get("count", 0),
        "active_goals": len(d.get("goals", {}).get("active", [])),
        "opportunities": d.get("opportunities", {}).get("count", 0),
        "revenue_usd": d.get("revenue", {}).get("total_usd", 0),
        "sales_ready": d.get("revenue", {}).get("sales_ready", 0),
        "taken_at": d["taken_at"],
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "summary":
        s = summary()
        print(f"سجلات: {s['skills_records']} مهارة ({s['skills_ok']}% نجاح) | "
              f"{s['tools_available']} أداة | {s['active_goals']} هدفاً نشطاً | "
              f"{s['opportunities']} فرصة | إيراد ${s['revenue_usd']} ({s['sales_ready']} جاهزة للبيع)")
    else:
        import json
        print(json.dumps(snapshot(), ensure_ascii=False, indent=1)[:1500])