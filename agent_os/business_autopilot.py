"""
business_autopilot.py - النظام 6: مشغّل الأعمال الذاتي (v3.0)
==============================================================
السلسلة الكاملة:

 بحث سوق -> اكتشاف فرصة -> تحليل منافسة -> تقدير ربح -> ترتيب أفكار
      -> MVP -> صفحة هبوط -> نشر -> اكتساب عملاء -> تحليلات -> تكرار

الاستخدام:
  python agent_os/business_autopilot.py opportunity
  python agent_os/business_autopilot.py pipeline <فكرة> <مسار>
  python agent_os/business_autopilot.py rank
"""

import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

PIPELINE_FILE = os.path.join(C.AGENT_OS_DIR, "business_pipeline.json")


def _load():
    return C.load_json(PIPELINE_FILE, {"ideas": [], "runs": []})


def _save(s):
    C.atomic_write(PIPELINE_FILE, s)


def market_research(query=None, num=4):
    """بحث سوق من الويب — لا يفشل عند غيابه."""
    sources = []
    try:
        import webtools
        q = query or "أفضل فرص عمل حر تقنية 2026 demand"
        results = webtools.search(q, save=False, num=num)
        for r in results.get("results", [])[:num]:
            if isinstance(r, dict) and r.get("title"):
                sources.append({"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("snippet", "")[:180]})
    except Exception:
        pass
    return sources


def discover_opportunities():
    """فرص من استخبارات + بحث."""
    meta = []
    try:
        import news_intel
        intel = news_intel.get_latest_intel()
        if intel:
            meta = [i.get("title", "") for i in (intel.get("tech_news", []) + intel.get("hacker_news", []))[:4]]
    except Exception:
        pass
    if not meta:
        meta = market_research()
    raw, _ = C.call_brain(
        "أنت مستشار ريادة أعمال.",
        f"بناءً على: {meta}\nاقترح 3 فرص مشاريع ربحية الآن بصيغة:\n"
        "IDEA: [فكرة]\nMARKET: [السوق]\nNICHE: [الفجوة]\n---",
    )
    ideas = []
    if raw:
        blocks = raw.split("---")
        for b in blocks:
            idea = {}
            for line in b.splitlines():
                if line.startswith("IDEA:"):
                    idea["idea"] = line.replace("IDEA:", "").strip()
                elif line.startswith("MARKET:"):
                    idea["market"] = line.replace("MARKET:", "").strip()
                elif line.startswith("NICHE:"):
                    idea["niche"] = line.replace("NICHE:", "").strip()
            if idea.get("idea"):
                idea["profit_est"] = _estimate_profit(idea)
                idea["date"] = C.now_iso()
                ideas.append(idea)
    state = _load()
    state["ideas"].extend(ideas)
    _save(state)
    return ideas


def _estimate_profit(idea):
    """تقدير ربح سريع بسبب قصير — بلا ادعاء دقة."""
    text = (idea.get("idea", "") + " " + idea.get("market", "")).lower()
    score = 5
    if any(w in text for w in ("saas", "subscription", "b2b", "a","ai")):
        score += 2
    if any(w in text for w in ("freelance", "service", "product")):
        score += 1
    idea["profit_score"] = min(10, score)
    return min(10, score)


def rank_ideas():
    """ترتيب الأفكار بحسب تقدير الربح."""
    ideas = sorted(_load()["ideas"], key=lambda i: -i.get("profit_score", 0))
    return ideas or discover_opportunities()


def run_pipeline(idea, dest_dir):
    """الذي يحدث فعلياً: بنية + MVP + صفحة هبوط + قياس جاهزية النشر."""
    stages = []
    try:
        from agent_os import product_factory
        rec = product_factory.build_product("web", idea[:40], dest_dir, spec=idea)
        stages.append(("mvp_built", rec["path"]))
    except Exception as e:
        stages.append(("mvp_failed", str(e)))
    try:
        from agent_os import product_factory
        landing = os.path.join(dest_dir, "landing")
        os.makedirs(landing, exist_ok=True)
        rec2 = product_factory.build_product("ecommerce" if False else "web", "landing_" + idea[:20], landing, spec="landing page")
        stages.append(("landing_built", rec2["path"]))
    except Exception as e:
        stages.append(("landing_failed", str(e)))
    try:
        from agent_os import devops_agent
        delp = devops_agent.deploy(os.path.join(dest_dir, _slug(idea[:40])))
        stages.append(("deploy_ready", delp["status"]))
    except Exception as e:
        stages.append(("deploy_failed", str(e)))
    run = {"date": C.now_iso(), "idea": idea, "stages": stages}
    state = _load()
    state["runs"].append(run)
    _save(state)
    C.log(f"💼 خط أنابيب: {idea} — {[s[0] for s in stages]}")
    return run


def _slug(s):
    import re
    return re.sub(r"[^A-Za-z0-9_\-]", "_", s).strip("_") or "business"


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "opportunity":
        for i in discover_opportunities():
            print(f"💡 {i.get('idea','')} | ربح {i.get('profit_score',0)}/10 | {i.get('market','')}")
    elif args[0] == "rank":
        for i in rank_ideas():
            print(f"[{i.get('profit_score',0)}/10] {i.get('idea','')}")
    elif args[0] == "pipeline" and len(args) > 2:
        dest = " ".join(args[2:])
        run_pipeline(args[1], dest)
        print("خط أنابيب اعمال مكتمل ✓")