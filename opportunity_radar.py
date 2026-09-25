"""
opportunity_radar.py - رادار الفرص (v1.0)
==========================================
يبحث دورياً عن فرص مرتبطة بأهدافك:
  Web, GitHub, Bug bounty, Open-source, Marketplaces

Discover → Score → Verify → Recommend

يقول لك فقط الفرص التي تستحق وقتك.
"""

import datetime
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

RADAR_DIR = os.path.join(BASE_DIR, "data", "radar")
os.makedirs(RADAR_DIR, exist_ok=True)
RADAR_DB = os.path.join(RADAR_DIR, "opportunities.json")

# أنواع الفرص
OPP_TYPES = [
    {"type": "github", "query": "trending python AI agent", "score_base": 0.7},
    {"type": "bug_bounty", "query": "bug bounty program open 2025", "score_base": 0.8},
    {"type": "open_source", "query": "open source project looking contributors", "score_base": 0.6},
    {"type": "saas", "query": "SaaS micro startup idea 2025", "score_base": 0.75},
    {"type": "freelance", "query": "python AI freelance project", "score_base": 0.65},
]


def _load():
    if os.path.exists(RADAR_DB):
        try:
            with open(RADAR_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"opportunities": [], "last_scan": None}


def _save(data):
    tmp = RADAR_DB + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RADAR_DB)


def _score_opportunity(opp: dict, base_score: float) -> float:
    """يقيّم الفرصة."""
    score = base_score
    title = opp.get("title", "").lower()
    snippet = opp.get("snippet", "").lower()

    # كلمات تزيد الدرجة
    boost_words = ["paid", "reward", "bounty", "hire", "job", "opportunity",
                   "مدفوع", "مكافأة", "فرصة", "عمل"]
    for word in boost_words:
        if word in title or word in snippet:
            score += 0.05

    # كلمات تنقص الدرجة
    penalty_words = ["closed", "expired", "منتهي", "مغلق"]
    for word in penalty_words:
        if word in title or word in snippet:
            score -= 0.1

    return min(max(score, 0.0), 1.0)


def scan(goals: list = None, max_per_type: int = 3) -> list:
    """يبحث عن فرص جديدة."""
    try:
        import webtools
    except ImportError:
        return []

    db = _load()
    new_opportunities = []
    existing_urls = {o.get("url") for o in db["opportunities"]}

    search_queries = list(OPP_TYPES)
    if goals:
        for goal in goals[:2]:
            search_queries.append({
                "type": "custom",
                "query": f"{goal} opportunity 2025",
                "score_base": 0.7,
            })

    for opp_type in search_queries:
        try:
            results = webtools.search(opp_type["query"], save=False, num=max_per_type)
            for r in results.get("results", [])[:max_per_type]:
                if not isinstance(r, dict):
                    continue
                url = r.get("url", "")
                if not url or url in existing_urls:
                    continue

                score = _score_opportunity(r, opp_type["score_base"])
                opp = {
                    "id": f"opp_{len(db['opportunities'])+len(new_opportunities)+1:04d}",
                    "type": opp_type["type"],
                    "title": r.get("title", "")[:100],
                    "url": url,
                    "snippet": r.get("snippet", "")[:200],
                    "score": round(score, 3),
                    "status": "discovered",
                    "discovered_at": datetime.datetime.now().isoformat(),
                }
                new_opportunities.append(opp)
                existing_urls.add(url)
        except Exception:
            continue

    # احتفظ بأعلى الفرص فقط
    new_opportunities.sort(key=lambda x: x["score"], reverse=True)
    db["opportunities"].extend(new_opportunities[:10])
    db["opportunities"] = sorted(db["opportunities"],
                                  key=lambda x: x["score"], reverse=True)[:50]
    db["last_scan"] = datetime.datetime.now().isoformat()
    _save(db)

    return new_opportunities


def get_top_opportunities(limit: int = 5, min_score: float = 0.6) -> list:
    """يرجع أفضل الفرص."""
    db = _load()
    filtered = [o for o in db["opportunities"] if o.get("score", 0) >= min_score]
    return filtered[:limit]


def format_opportunities(opps: list) -> str:
    """ينسق الفرص للعرض."""
    if not opps:
        return "لا توجد فرص مكتشفة بعد. شغّل: python opportunity_radar.py scan"

    lines = ["## 🎯 أفضل الفرص المكتشفة", ""]
    for i, o in enumerate(opps, 1):
        lines.append(f"### {i}. {o['title'][:60]}")
        lines.append(f"**النوع:** {o['type']} | **الدرجة:** {o['score']:.0%}")
        if o.get("snippet"):
            lines.append(f"> {o['snippet'][:150]}")
        lines.append(f"🔗 {o['url']}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "top"
    if action == "scan":
        goals = sys.argv[2:] if len(sys.argv) > 2 else None
        found = scan(goals=goals)
        print(f"اكتشفت {len(found)} فرصة جديدة.")
        print(format_opportunities(found[:5]))
    elif action == "top":
        opps = get_top_opportunities()
        print(format_opportunities(opps))
    else:
        print("الاستخدام: python opportunity_radar.py scan [goals...] | top")
