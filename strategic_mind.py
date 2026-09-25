"""
strategic_mind.py - العقل الاستراتيجي (v1.0)
=============================================
يتابع الترندات، يحدد الفرص المربحة، يربط المعرفة بالمال،
يتعلم من نجاحاتك، يركّز التعلم على الأكثر ربحاً.
"""

import datetime
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STRATEGY_FILE = os.path.join(BASE_DIR, "data", "strategy.json")
SUCCESS_FILE = os.path.join(BASE_DIR, "data", "successes.json")
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)


# ===== الترندات المربحة حالياً =====

HOT_TRENDS = [
    # تقنية
    {"trend": "AI Agents", "profit": 5, "growth": "سريع جداً", "skills": ["ml-ai", "system-design"]},
    {"trend": "LLM Fine-tuning", "profit": 5, "growth": "سريع", "skills": ["ml-ai"]},
    {"trend": "Cybersecurity", "profit": 5, "growth": "سريع", "skills": ["offensive-security", "defensive-web-security"]},
    {"trend": "Blockchain/Web3", "profit": 4, "growth": "متذبذب", "skills": ["blockchain"]},
    {"trend": "SaaS Products", "profit": 5, "growth": "سريع", "skills": ["web-dev", "business"]},
    {"trend": "No-Code/Low-Code", "profit": 4, "growth": "سريع", "skills": ["web-dev"]},
    {"trend": "Data Analytics", "profit": 4, "growth": "سريع", "skills": ["ml-ai", "mathematics"]},
    {"trend": "Mobile Apps", "profit": 4, "growth": "مستقر", "skills": ["mobile-dev"]},
    {"trend": "Content Creation AI", "profit": 4, "growth": "سريع", "skills": ["ml-ai", "content"]},
    {"trend": "E-commerce", "profit": 4, "growth": "مستقر", "skills": ["ecommerce", "marketing"]},
    # علوم
    {"trend": "Quantum Computing", "profit": 5, "growth": "بطيء لكن ضخم", "skills": ["physics", "mathematics"]},
    {"trend": "Biotech/Genomics", "profit": 5, "growth": "سريع", "skills": ["biology"]},
    {"trend": "Space Tech", "profit": 5, "growth": "سريع", "skills": ["astronomy", "physics"]},
    {"trend": "Clean Energy", "profit": 4, "growth": "سريع", "skills": ["energy"]},
    # أعمال
    {"trend": "Digital Marketing", "profit": 4, "growth": "مستقر", "skills": ["marketing"]},
    {"trend": "Online Education", "profit": 4, "growth": "سريع", "skills": ["content", "psychology"]},
    {"trend": "Freelancing Platforms", "profit": 3, "growth": "مستقر", "skills": ["business"]},
    {"trend": "Crypto Trading", "profit": 4, "growth": "متذبذب", "skills": ["finance", "blockchain"]},
]


def _atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_strategy():
    if os.path.exists(STRATEGY_FILE):
        try:
            with open(STRATEGY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"focus_tracks": [], "opportunities": [], "last_update": None}


def _load_successes():
    if os.path.exists(SUCCESS_FILE):
        try:
            with open(SUCCESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"projects": [], "total": 0}


def _load_knowledge():
    """جلب كل ما يعرفه الوكيل."""
    skills = []
    skills_dir = os.path.join(BASE_DIR, "skills")
    if os.path.isdir(skills_dir):
        for name in os.listdir(skills_dir):
            if not name.startswith("_"):
                skills.append(name.replace("-", " "))

    mastery_tracks = []
    state_file = os.path.join(BASE_DIR, "data", "mastery_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            for tid, data in state.get("tracks", {}).items():
                mastery_tracks.append({"id": tid, "level": data.get("level", 1)})
        except Exception:
            pass

    return {"skills": skills, "mastery": mastery_tracks}


def analyze_opportunities():
    """تحليل الفرص بناءً على ما يعرفه الوكيل."""
    knowledge = _load_knowledge()
    known_tracks = {t["id"] for t in knowledge["mastery"] if t["level"] >= 2}
    known_skills = set(knowledge["skills"])

    scored = []
    for trend in HOT_TRENDS:
        score = trend["profit"]
        # مكافأة إذا كان عنده مهارات مرتبطة
        for skill in trend["skills"]:
            if skill in known_tracks:
                score += 2
            if any(skill.replace("-", " ") in s for s in known_skills):
                score += 1
        scored.append({**trend, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:10]


def get_focus_tracks():
    """المسارات التي يجب التركيز عليها أولاً."""
    opps = analyze_opportunities()
    focus = set()
    for opp in opps[:5]:
        for skill in opp["skills"]:
            focus.add(skill)
    return list(focus)


def record_success(project_name, domain, revenue_estimate=""):
    """تسجيل نجاح مشروع."""
    successes = _load_successes()
    successes["projects"].append({
        "name": project_name,
        "domain": domain,
        "revenue": revenue_estimate,
        "date": datetime.datetime.now().isoformat(),
    })
    successes["total"] += 1
    _atomic_write(SUCCESS_FILE, successes)
    return f"تم تسجيل نجاح: {project_name}"


def daily_strategy():
    """تقرير استراتيجي يومي."""
    opps = analyze_opportunities()
    focus = get_focus_tracks()
    successes = _load_successes()

    strategy = {
        "date": datetime.datetime.now().isoformat(),
        "top_opportunities": opps[:5],
        "focus_tracks": focus,
        "total_successes": successes["total"],
        "recommendation": _generate_recommendation(opps, successes),
    }
    _atomic_write(STRATEGY_FILE, strategy)
    return strategy


def _generate_recommendation(opps, successes):
    if not opps:
        return "ابدأ بالتعلم أولاً"
    top = opps[0]
    rec = f"الفرصة الأقوى الآن: {top['trend']} (ربحية {top['profit']}/5, نمو {top['growth']})"
    if successes["total"] > 0:
        last = successes["projects"][-1]
        rec += f" | آخر نجاح: {last['name']} في {last['domain']}"
    return rec


if __name__ == "__main__":
    print("🧠 العقل الاستراتيجي")
    print("=" * 50)
    strategy = daily_strategy()
    print(f"\n🎯 التوصية: {strategy['recommendation']}")
    print(f"\n📈 أفضل 5 فرص:")
    for i, opp in enumerate(strategy["top_opportunities"], 1):
        print(f"  {i}. {opp['trend']} - ربحية: {'⭐'*opp['profit']} - نمو: {opp['growth']}")
    print(f"\n📚 ركّز تعلمك على: {', '.join(strategy['focus_tracks'])}")
