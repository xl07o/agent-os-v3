"""
news_intel.py - طبقة الأخبار والاستخبارات (v1.0)
=====================================================
يتابع كل شيء ويستخلص معلومات مفيدة:
- Hacker News, TechCrunch, SecurityWeek
- CVE الجديدة
- GitHub Trending
- فرص العمل الحر
- أسعار العملات
"""

import datetime
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from agent_os import security_kernel as _auth

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

INTEL_DIR = os.path.join(BASE_DIR, "data", "intel")
os.makedirs(INTEL_DIR, exist_ok=True)


def _safe_get(url, timeout=10):
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SelfRunner/2.0)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return ""


def _atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ===== مصادر الأخبار =====

def fetch_hacker_news(limit=10):
    """جلب أفضل أخبار Hacker News."""
    try:
        data = _safe_get("https://hacker-news.firebaseio.com/v0/topstories.json")
        if not data:
            return []
        ids = json.loads(data)[:limit]
        stories = []
        for sid in ids:
            story_data = _safe_get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
            if story_data:
                story = json.loads(story_data)
                if story.get("title"):
                    stories.append({
                        "title": story.get("title", ""),
                        "url": story.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                        "score": story.get("score", 0),
                        "source": "HackerNews",
                    })
            time.sleep(0.1)
        return stories
    except Exception:
        return []


def fetch_github_trending():
    """جلب مشاريع GitHub الرائجة."""
    try:
        html = _safe_get("https://github.com/trending", timeout=15)
        if not html:
            return []
        # استخراج أسماء المشاريع
        pattern = r'href="/([\w-]+/[\w.-]+)"'
        matches = re.findall(pattern, html)
        repos = []
        seen = set()
        for m in matches:
            if "/" in m and m not in seen and len(m) > 3:
                seen.add(m)
                repos.append({
                    "repo": m,
                    "url": f"https://github.com/{m}",
                    "source": "GitHub Trending",
                })
            if len(repos) >= 10:
                break
        return repos
    except Exception:
        return []


def fetch_cve_recent():
    """جلب آخر الثغرات CVE."""
    try:
        data = _safe_get(
            "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=5",
            timeout=15
        )
        if not data:
            return []
        parsed = json.loads(data)
        cves = []
        for item in parsed.get("vulnerabilities", []):
            cve = item.get("cve", {})
            cve_id = cve.get("id", "")
            desc = ""
            for d in cve.get("descriptions", []):
                if d.get("lang") == "en":
                    desc = d.get("value", "")[:200]
                    break
            metrics = cve.get("metrics", {})
            score = 0
            for key in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
                if key in metrics and metrics[key]:
                    score = metrics[key][0].get("cvssData", {}).get("baseScore", 0)
                    break
            if cve_id:
                cves.append({
                    "id": cve_id,
                    "description": desc,
                    "score": score,
                    "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    "source": "NVD CVE",
                })
        return cves
    except Exception:
        return []


def fetch_crypto_prices():
    """جلب أسعار العملات الرئيسية."""
    try:
        data = _safe_get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true",
            timeout=10
        )
        if not data:
            return {}
        return json.loads(data)
    except Exception:
        return {}


def fetch_freelance_opportunities():
    """جلب فرص عمل حر من مصادر متعددة."""
    opportunities = []
    try:
        import webtools
        results = webtools.search(
            "freelance AI developer jobs remote 2025 site:upwork.com OR site:freelancer.com",
            save=False, num=5
        )
        for r in results.get("results", [])[:5]:
            if isinstance(r, dict) and r.get("title"):
                opportunities.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", "")[:150],
                    "source": "Freelance Search",
                })
    except Exception:
        pass
    return opportunities


def fetch_tech_news():
    """جلب أخبار تقنية عامة."""
    news = []
    try:
        import webtools
        results = webtools.search(
            "AI technology news today 2025",
            save=False, num=5
        )
        for r in results.get("results", [])[:5]:
            if isinstance(r, dict) and r.get("title"):
                news.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", "")[:150],
                    "source": "Tech News",
                })
    except Exception:
        pass
    return news


def fetch_security_news():
    """جلب أخبار الأمن."""
    news = []
    try:
        import webtools
        results = webtools.search(
            "cybersecurity news vulnerability 2025",
            save=False, num=5
        )
        for r in results.get("results", [])[:5]:
            if isinstance(r, dict) and r.get("title"):
                news.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", "")[:150],
                    "source": "Security News",
                })
    except Exception:
        pass
    return news


def extract_skills_from_news(news_items):
    """يستخرج مهارات وتقنيات من الأخبار."""
    tech_keywords = [
        "python", "javascript", "rust", "golang", "typescript",
        "react", "nextjs", "fastapi", "docker", "kubernetes",
        "llm", "gpt", "claude", "gemini", "ai agent",
        "blockchain", "solidity", "web3", "defi",
        "cybersecurity", "penetration", "vulnerability",
        "machine learning", "deep learning", "neural",
        "quantum", "robotics", "iot",
    ]
    found_skills = set()
    for item in news_items:
        text = (item.get("title", "") + " " + item.get("snippet", "")).lower()
        for kw in tech_keywords:
            if kw in text:
                found_skills.add(kw)
    return list(found_skills)


def run_full_intel():
    """جلب كل المعلومات."""
    print("\n📰 جلب الأخبار والاستخبارات...")
    intel = {
        "date": datetime.datetime.now().isoformat(),
        "hacker_news": [],
        "github_trending": [],
        "cve_recent": [],
        "crypto_prices": {},
        "freelance": [],
        "tech_news": [],
        "security_news": [],
        "extracted_skills": [],
    }

    print("  → Hacker News...")
    intel["hacker_news"] = fetch_hacker_news(8)
    print(f"    ✓ {len(intel['hacker_news'])} خبر")

    print("  → GitHub Trending...")
    intel["github_trending"] = fetch_github_trending()
    print(f"    ✓ {len(intel['github_trending'])} مشروع")

    print("  → CVE الجديدة...")
    intel["cve_recent"] = fetch_cve_recent()
    print(f"    ✓ {len(intel['cve_recent'])} ثغرة")

    print("  → أسعار العملات...")
    intel["crypto_prices"] = fetch_crypto_prices()
    print(f"    ✓ {len(intel['crypto_prices'])} عملة")

    print("  → أخبار التقنية...")
    intel["tech_news"] = fetch_tech_news()
    print(f"    ✓ {len(intel['tech_news'])} خبر")

    print("  → أخبار الأمن...")
    intel["security_news"] = fetch_security_news()
    print(f"    ✓ {len(intel['security_news'])} خبر")

    print("  → فرص العمل الحر...")
    intel["freelance"] = fetch_freelance_opportunities()
    print(f"    ✓ {len(intel['freelance'])} فرصة")

    # استخراج المهارات
    all_news = intel["hacker_news"] + intel["tech_news"] + intel["security_news"]
    intel["extracted_skills"] = extract_skills_from_news(all_news)
    print(f"  ✓ مهارات مستخرجة: {', '.join(intel['extracted_skills'][:5])}")

    # حفظ
    out = os.path.join(INTEL_DIR, f"intel_{datetime.datetime.now():%Y%m%d}.json")
    _atomic_write(out, intel)
    print(f"  ✓ محفوظ: {out}")

    return intel


def get_latest_intel():
    """جلب آخر استخبارات."""
    today = datetime.datetime.now().strftime("%Y%m%d")
    path = os.path.join(INTEL_DIR, f"intel_{today}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


if __name__ == "__main__":
    intel = run_full_intel()
    print(f"\n📊 ملخص:")
    print(f"  📰 أخبار: {len(intel['hacker_news']) + len(intel['tech_news'])}")
    print(f"  🔒 ثغرات CVE: {len(intel['cve_recent'])}")
    print(f"  🐈 GitHub: {len(intel['github_trending'])} مشروع")
    if intel["crypto_prices"]:
        btc = intel["crypto_prices"].get("bitcoin", {}).get("usd", 0)
        print(f"  💰 Bitcoin: ${btc:,}")
    print(f"  💼 فرص عمل: {len(intel['freelance'])}")
    print(f"  🧠 مهارات: {', '.join(intel['extracted_skills'][:8])}")