"""
bounty_tracker.py - تتبع برامج Bug Bounty (v1.0)
=============================================
يتابع البرامج، يختار الأفضل، يتابع حالة التقارير
"""
import datetime
import json
import os
import sys
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

TRACKER_FILE = os.path.join(BASE_DIR, "data", "bounty_tracker.json")
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

# برامج معروفة ومسموح بها قانونياً
KNOWN_PROGRAMS = [
    {"name": "HackerOne Public Programs", "url": "https://hackerone.com/programs",
     "platform": "hackerone", "avg_bounty": 500, "difficulty": "medium"},
    {"name": "Bugcrowd Public Programs", "url": "https://bugcrowd.com/programs",
     "platform": "bugcrowd", "avg_bounty": 400, "difficulty": "medium"},
    {"name": "Intigriti Programs", "url": "https://app.intigriti.com/programs",
     "platform": "intigriti", "avg_bounty": 600, "difficulty": "medium"},
    {"name": "Google VRP", "url": "https://bughunters.google.com",
     "platform": "google", "avg_bounty": 3000, "difficulty": "hard"},
    {"name": "Microsoft MSRC", "url": "https://msrc.microsoft.com/bounty",
     "platform": "microsoft", "avg_bounty": 2000, "difficulty": "hard"},
    {"name": "Apple Security", "url": "https://security.apple.com/bounty",
     "platform": "apple", "avg_bounty": 5000, "difficulty": "very_hard"},
    {"name": "Meta Bug Bounty", "url": "https://www.facebook.com/whitehat",
     "platform": "meta", "avg_bounty": 1000, "difficulty": "hard"},
    {"name": "GitHub Security", "url": "https://bounty.github.com",
     "platform": "github", "avg_bounty": 2000, "difficulty": "hard"},
    {"name": "Shopify Bug Bounty", "url": "https://hackerone.com/shopify",
     "platform": "hackerone", "avg_bounty": 1500, "difficulty": "medium"},
    {"name": "Twitter/X Security", "url": "https://hackerone.com/twitter",
     "platform": "hackerone", "avg_bounty": 1000, "difficulty": "medium"},
]


def _atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"submissions": [], "total_earned": 0, "pending": 0}


def get_best_programs(difficulty=None, min_bounty=0):
    """اختيار أفضل البرامج."""
    programs = KNOWN_PROGRAMS
    if difficulty:
        programs = [p for p in programs if p["difficulty"] == difficulty]
    programs = [p for p in programs if p["avg_bounty"] >= min_bounty]
    return sorted(programs, key=lambda x: x["avg_bounty"], reverse=True)


def record_submission(domain, program, findings_count, severity, status="pending", bounty=0):
    """تسجيل تقرير مرسل."""
    tracker = _load_tracker()
    submission = {
        "id": len(tracker["submissions"]) + 1,
        "domain": domain,
        "program": program,
        "findings": findings_count,
        "severity": severity,
        "status": status,
        "bounty": bounty,
        "date": datetime.datetime.now().isoformat(),
    }
    tracker["submissions"].append(submission)
    if status == "paid":
        tracker["total_earned"] += bounty
    elif status == "pending":
        tracker["pending"] += 1
    _atomic_write(TRACKER_FILE, tracker)
    return submission


def update_submission(submission_id, status, bounty=0):
    """تحديث حالة تقرير."""
    tracker = _load_tracker()
    for s in tracker["submissions"]:
        if s["id"] == submission_id:
            old_status = s["status"]
            s["status"] = status
            s["bounty"] = bounty
            if status == "paid" and old_status != "paid":
                tracker["total_earned"] += bounty
                tracker["pending"] = max(0, tracker["pending"] - 1)
            break
    _atomic_write(TRACKER_FILE, tracker)
    return tracker


def get_stats():
    """إحصائيات شاملة."""
    tracker = _load_tracker()
    subs = tracker["submissions"]
    return {
        "total_submissions": len(subs),
        "pending": len([s for s in subs if s["status"] == "pending"]),
        "accepted": len([s for s in subs if s["status"] == "accepted"]),
        "paid": len([s for s in subs if s["status"] == "paid"]),
        "rejected": len([s for s in subs if s["status"] == "rejected"]),
        "total_earned": tracker["total_earned"],
        "recent": subs[-5:],
    }


if __name__ == "__main__":
    print("🏆 أفضل برامج Bug Bounty:")
    for p in get_best_programs()[:5]:
        print(f"  - {p['name']} | متوسط: ${p['avg_bounty']} | صعوبة: {p['difficulty']}")
    stats = get_stats()
    print(f"\n💰 إجمالي المكاسب: ${stats['total_earned']}")
