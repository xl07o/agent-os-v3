"""
empire.py - المحرك الرئيسي لإمبراطورية الأمن الرقمي (v1.0)
=======================================================
يجمع كل الأنظمة ويشغّلها بشكل متكامل

الاستخدام:
  python empire.py scan <domain>     - فحص شامل
  python empire.py report <domain>   - تقرير فقط
  python empire.py programs          - أفضل البرامج
  python empire.py stats             - إحصائيات
  python empire.py auto              - تشغيل تلقائي
"""
import json
import os
import sys
import time
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from recon import full_recon
from scanner import full_scan
from report_writer import write_report_arabic, write_report_english, estimate_bounty
from bounty_tracker import get_best_programs, record_submission, get_stats

EMPIRE_LOG = os.path.join(BASE_DIR, "logs", "empire.log")
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)

# أهداف تدريبية مسموح بها قانونياً (مواقع تجريبية عامة)
SAFE_PRACTICE_TARGETS = [
    "testphp.vulnweb.com",
    "demo.testfire.net",
    "juice-shop.herokuapp.com",
    "dvwa.co.uk",
    "hackthissite.org",
    "tryhackme.com",
    "hackthebox.com",
]


def _log(msg):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    try:
        with open(EMPIRE_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def full_pipeline(domain, save_report=True):
    """الخط الكامل: استطلاع → فحص → تقرير."""
    _log(f"🚀 بدء تحليل {domain}")

    # 1. استطلاع
    recon = full_recon(domain)

    # 2. فحص
    scan = full_scan(domain, recon)

    # 3. تقارير
    reports = {}
    if save_report and scan["total"] > 0:
        reports["arabic"] = write_report_arabic(domain, recon, scan)
        reports["english"] = write_report_english(domain, recon, scan)
        _log(f"📄 تقارير: {reports}")

    # 4. تقدير المكافأة
    bounty = estimate_bounty(scan["findings"])

    result = {
        "domain": domain,
        "recon": recon,
        "scan": scan,
        "reports": reports,
        "bounty_estimate": bounty,
    }

    _log(f"✅ اكتمل {domain}: {scan['total']} ثغرة | مكافأة: ${bounty['min']:,}-${bounty['max']:,}")
    return result


def auto_mode():
    """وضع تلقائي: يفحص الأهداف التدريبية ويولد تقارير."""
    _log("🤖 وضع تلقائي - فحص الأهداف التدريبية")
    _log("⚠️ للفحص الحقيقي: أضف النطاقات المسموح بها في .env كـ BOUNTY_TARGETS")

    # فحص الأهداف التدريبية
    results = []
    for target in SAFE_PRACTICE_TARGETS[:2]:  # هدفين فقط في الوضع التلقائي
        try:
            result = full_pipeline(target)
            results.append(result)
            time.sleep(2)  # احترام الخادم
        except Exception as e:
            _log(f"خطأ في {target}: {e}")

    # تقرير موجز
    total_findings = sum(r["scan"]["total"] for r in results)
    total_bounty_min = sum(r["bounty_estimate"]["min"] for r in results)
    total_bounty_max = sum(r["bounty_estimate"]["max"] for r in results)
    _log(f"📊 النتائج: {total_findings} ثغرة | مكافأة: ${total_bounty_min:,}-${total_bounty_max:,}")
    return results


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "programs":
        print("🏆 أفضل برامج Bug Bounty:")
        for p in get_best_programs()[:8]:
            print(f"  • {p['name']} | متوسط: ${p['avg_bounty']:,} | صعوبة: {p['difficulty']}")
            print(f"    {p['url']}")

    elif args[0] == "scan" and len(args) > 1:
        domain = args[1]
        result = full_pipeline(domain)
        print(f"\n✅ اكتمل!")
        print(f"🔎 ثغرات: {result['scan']['total']}")
        print(f"💰 مكافأة متوقعة: ${result['bounty_estimate']['min']:,} - ${result['bounty_estimate']['max']:,}")
        if result.get("reports"):
            print(f"📄 تقرير عربي: {result['reports'].get('arabic')}")
            print(f"📄 تقرير إنجليزي: {result['reports'].get('english')}")

    elif args[0] == "stats":
        stats = get_stats()
        print(f"📊 إحصائيات Bug Bounty:")
        print(f"  إجمالي التقارير: {stats['total_submissions']}")
        print(f"  معلقة: {stats['pending']}")
        print(f"  مقبولة: {stats['accepted']}")
        print(f"  مدفوعة: {stats['paid']}")
        print(f"  💰 إجمالي المكاسب: ${stats['total_earned']:,}")

    elif args[0] == "auto":
        auto_mode()

    else:
        print("الاستخدام:")
        print("  python empire.py programs              أفضل البرامج")
        print("  python empire.py scan <domain>         فحص هدف")
        print("  python empire.py stats                 إحصائيات")
        print("  python empire.py auto                  وضع تلقائي")
