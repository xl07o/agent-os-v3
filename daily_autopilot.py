"""
daily_autopilot.py - المحرك اليومي الرئيسي (v1.0)
=============================================
يجمع كل الأنظمة ويشغّلها بشكل متكامل يومياً:

0. الأخبار والاستخبارات - يتابع الأخبار والثغرات والفرص
1. العقل الاستراتيجي - يحدد أفضل الفرص
2. التعلم الشامل - يتعلم من كل مجال
3. الاقتراحات الذكية - يقترح مشاريع مربحة (من الأخبار)
4. فحص الكود - يفحص ويحسّن
5. تعلم الجهاز - يتعلم من بيئتك
6. التطوير الذاتي - يحسن نفسه ذاتياً
7. التقرير الصباحي - يولد ملخص شامل

الاستخدام:
  python daily_autopilot.py          - تشغيل كامل
  python daily_autopilot.py --quick  - تشغيل سريع
  python daily_autopilot.py --report - تقرير فقط
  python daily_autopilot.py --loop   - تشغيل مستمر 24/7
"""

import datetime
import json
import os
import sys
import time
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LOG_FILE = os.path.join(BASE_DIR, "logs", "daily_autopilot.log")
REPORT_FILE = os.path.join(BASE_DIR, "output", "daily_autopilot_report.md")
STATE_FILE = os.path.join(BASE_DIR, "data", "autopilot_state.json")

for d in ["logs", "output", "data"]:
    os.makedirs(os.path.join(BASE_DIR, d), exist_ok=True)


# ===== سجل =====

def _log(msg, level="INFO"):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] [{level}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_run": None,
        "total_runs": 0,
        "total_suggestions": 0,
        "total_skills": 0,
        "total_reviews": 0,
        "history": []
    }


# ===== مراحل التشغيل =====

def phase_intel():
    """مرحلة 0: الأخبار والاستخبارات."""
    _log("📰 مرحلة 0: الأخبار والاستخبارات")
    result = {"status": "skipped"}
    try:
        import news_intel
        # إذا جمعنا اليوم بالفعل نستخدمها، وإلا نجلب جديدة
        intel = news_intel.get_latest_intel()
        if not intel:
            intel = news_intel.run_full_intel()
        result = {
            "status": "done",
            "news_count": len(intel.get("hacker_news", [])) + len(intel.get("tech_news", [])),
            "cve_count": len(intel.get("cve_recent", [])),
            "github_count": len(intel.get("github_trending", [])),
            "skills": intel.get("extracted_skills", []),
            "freelance": len(intel.get("freelance", [])),
            "crypto": intel.get("crypto_prices", {}),
        }
        _log(f"  ✓ أخبار: {result['news_count']} | CVE: {result['cve_count']} | مهارات: {len(result['skills'])}")
    except Exception as e:
        _log(f"  ⚠️ تعذر: {e}")
        result["error"] = str(e)
    return result


def phase_self_improve():
    """مرحلة 7: التطوير الذاتي."""
    _log("🔄 مرحلة 7: التطوير الذاتي")
    result = {"status": "skipped"}
    try:
        from agent_os import self_improve_engine as sie
        r = sie.run_improvement_cycle()
        result = {
            "status": "done" if r.get("status") in {"committed", "applied", "already_applied"} else r.get("status", "finished"),
            "fixed": 1 if r.get("status") in {"committed", "applied", "already_applied"} else 0,
            "failed": 0 if r.get("status") in {"committed", "applied", "already_applied", "no_patch"} else 1,
            "target": r.get("target", ""),
            "detail": str(r.get("reason", r.get("status", "")))[:300],
        }
        _log(f"  ✓ دورة التطور: {result['status']} | الهدف: {result['target']}")
    except Exception as e:
        _log(f"  ⚠️ تعذر: {e}")
        result["error"] = str(e)
    return result


def phase_strategy():
    """مرحلة 1: العقل الاستراتيجي."""
    _log("🎯 مرحلة 1: العقل الاستراتيجي")
    result = {"status": "skipped", "opportunities": []}
    try:
        import strategic_mind as sm
        strategy = sm.daily_strategy()
        result = {
            "status": "done",
            "recommendation": strategy.get("recommendation", ""),
            "opportunities": [o["trend"] for o in strategy.get("top_opportunities", [])[:5]],
            "focus_tracks": strategy.get("focus_tracks", []),
        }
        _log(f"  ✓ التوصية: {result['recommendation'][:80]}")
    except Exception as e:
        _log(f"  ⚠️ تعذر: {e}")
        result["error"] = str(e)
    return result


def phase_learn(focus_tracks=None):
    """مرحلة 2: التعلم الشامل."""
    _log("🧠 مرحلة 2: التعلم")
    result = {"status": "skipped", "cycles": 0}
    try:
        import mastery
        # دورة تعلم واحدة
        mastery._run_cycle()
        state = mastery._load_state()
        result = {
            "status": "done",
            "total_cycles": state.get("total_cycles", 0),
            "total_demos": state.get("total_demos", 0),
        }
        _log(f"  ✓ دورات: {result['total_cycles']} | مكتبات: {result['total_demos']}")
    except Exception as e:
        _log(f"  ⚠️ تعذر: {e}")
        result["error"] = str(e)
    return result


def phase_suggest(intel=None):
    """مرحلة 3: الاقتراحات الذكية."""
    _log("💡 مرحلة 3: الاقتراحات")
    result = {"status": "skipped", "suggestions": []}
    try:
        import suggest
        suggestions, engine = suggest.generate_suggestions(count=5, intel=intel)
        if suggestions:
            result = {
                "status": "done",
                "count": len(suggestions),
                "engine": engine,
                "top": suggestions[0].get("idea", "") if suggestions else "",
                "suggestions": [{"idea": s.get("idea"), "profit": s.get("profit")} for s in suggestions],
            }
            _log(f"  ✓ {len(suggestions)} اقتراح | أفضل: {result['top'][:60]}")
        else:
            result["status"] = "no_suggestions"
    except Exception as e:
        _log(f"  ⚠️ تعذر: {e}")
        result["error"] = str(e)
    return result


def phase_review_code():
    """مرحلة 4: فحص الكود."""
    _log("🔍 مرحلة 4: فحص الكود")
    result = {"status": "skipped"}
    try:
        import code_reviewer
        report = code_reviewer.review_project(use_ai=False)  # بدون AI للسرعة
        result = {
            "status": "done",
            "files": report.get("files_reviewed", 0),
            "total_issues": report.get("total_issues", 0),
            "critical": report.get("critical", 0),
            "score": report.get("avg_score", 0),
            "grade": report.get("overall_grade", "-"),
        }
        _log(f"  ✓ {result['files']} ملف | درجة: {result['score']}/100 ({result['grade']}) | حرج: {result['critical']}")
    except Exception as e:
        _log(f"  ⚠️ تعذر: {e}")
        result["error"] = str(e)
    return result


def phase_learn_system():
    """مرحلة 5: تعلم من الجهاز."""
    _log("🖥️ مرحلة 5: تعلم من الجهاز")
    result = {"status": "skipped"}
    try:
        import computer_control as cc
        data = cc.learn_from_system()
        result = {
            "status": "done",
            "apps": len(data.get("running_apps", [])),
            "dirs": len(data.get("important_dirs", [])),
            "system": data.get("system", {}).get("user", ""),
        }
        _log(f"  ✓ تعلم: {result['apps']} برنامج | {result['dirs']} مجلد")
    except Exception as e:
        _log(f"  ⚠️ تعذر (طبيعي لو لم تثبت المكتبات): {e}")
        result["error"] = str(e)
    return result


def phase_report(phases_results):
    """مرحلة 7: التقرير الصباحي."""
    _log("📊 مرحلة 7: بناء التقرير")
    now = datetime.datetime.now()

    strategy = phases_results.get("strategy", {})
    learn = phases_results.get("learn", {})
    suggest = phases_results.get("suggest", {})
    review = phases_results.get("review", {})
    system = phases_results.get("system", {})
    intel = phases_results.get("intel", {})
    self_improve = phases_results.get("self_improve", {})

    lines = [
        f"# 🌙 تقرير المحرك اليومي - {now:%Y-%m-%d %H:%M}",
        "",
        "## 📰 الأخبار والاستخبارات",
    ]

    if intel.get("status") == "done":
        lines.append(f"✅ أخبار: {intel.get('news_count', 0)} | CVE: {intel.get('cve_count', 0)} | GitHub: {intel.get('github_count', 0)}")
        skills_intel = intel.get("skills", [])
        if skills_intel:
            lines.append(f"🧠 تقنيات ناشئة: {', '.join(skills_intel[:6])}")
        if intel.get("freelance"):
            lines.append(f"💼 فرص عمل حر: {intel.get('freelance')}")
        lines.append("▶️ للتفاصيل: `python news_intel.py`")
    elif intel.get("status") == "skipped_quick_mode":
        lines.append("⏭️ متجاوز في الوضع السريع")
    else:
        lines.append(f"⚠️ {intel.get('error', 'لم يشتغل')}")

    lines += ["", "## 🎯 العقل الاستراتيجي",
    ]

    if strategy.get("status") == "done":
        lines.append(f"✅ التوصية: {strategy.get('recommendation', '-')}")
        opps = strategy.get("opportunities", [])
        if opps:
            lines.append(f"📈 أفضل الفرص: {', '.join(opps[:3])}")
    else:
        lines.append(f"⚠️ {strategy.get('error', 'لم يشتغل')}")

    lines += ["", "## 🧠 التعلم"]
    if learn.get("status") == "done":
        lines.append(f"✅ دورات: {learn.get('total_cycles', 0)} | مكتبات مبنية: {learn.get('total_demos', 0)}")
    else:
        lines.append(f"⚠️ {learn.get('error', 'لم يشتغل')}")

    lines += ["", "## 💡 الاقتراحات"]
    if suggest.get("status") == "done":
        lines.append(f"✅ {suggest.get('count', 0)} اقتراحات جديدة")
        for s in suggest.get("suggestions", [])[:3]:
            lines.append(f"  - {s.get('idea', '-')} | {s.get('profit', '-')}")
        lines.append("▶️ للتفاصيل: `python suggest.py --today`")
    else:
        lines.append(f"⚠️ {suggest.get('error', 'لم يشتغل')}")

    lines += ["", "## 🔍 فحص الكود"]
    if review.get("status") == "done":
        grade = review.get('grade', '-')
        score = review.get('score', 0)
        critical = review.get('critical', 0)
        emoji = "🟢" if grade in ["A", "B"] else "🟡" if grade == "C" else "🔴"
        lines.append(f"{emoji} درجة الكود: {score}/100 ({grade}) | مشاكل حرجة: {critical}")
        if critical > 0:
            lines.append(f"⚠️ يوجد {critical} مشكلة حرجة تحتاج إصلاح!")
    else:
        lines.append(f"⚠️ {review.get('error', 'لم يشتغل')}")

    lines += ["", "## 🖥️ الجهاز"]
    if system.get("status") == "done":
        lines.append(f"✅ تعلم: {system.get('apps', 0)} برنامج نشط")
    else:
        lines.append("⚠️ شغّل `python computer_control.py --install` أولاً")

    lines += ["", "## 🔄 التطوير الذاتي"]
    if self_improve.get("status") == "done":
        lines.append(f"✅ إصلاحات: {self_improve.get('fixed', 0)} | فشل: {self_improve.get('failed', 0)} | استراتيجية v{self_improve.get('strategy_version', '?')}")
    elif self_improve.get("status") == "skipped_quick_mode":
        lines.append("⏭️ متجاوز في الوضع السريع")
    else:
        lines.append(f"⚠️ {self_improve.get('error', 'لم يشتغل')}")

    lines += [
        "",
        "## ⏰ الخطوات التالية",
        "- `python suggest.py --today` - شوف الاقترادات",
        "- `python suggest.py --execute 1` - نفّذ الاقتراح الأول",
        "- `python legendary_agent.py ask \"سؤالك\"` - اسأل الوكيل الأسطوري",
        "- `python mastery.py run` - شغّل التعلم المستمر",
        "- `cd security_empire && python empire.py programs` - Bug Bounty",
        "",
        f"*تقرير مولّد تلقائياً - {now:%Y-%m-%d %H:%M}*",
    ]

    content = "\n".join(lines)
    _atomic_write(REPORT_FILE, content)
    _log(f"  ✓ التقرير: {REPORT_FILE}")
    return content


# ===== المحرك الرئيسي =====

def run_full(quick=False):
    """تشغيل كامل - دورة الحياة الكاملة."""
    start = time.time()
    _log("=" * 55)
    _log("🚀 بدء المحرك اليومي الرئيسي - دورة الحياة الكاملة")
    _log("=" * 55)

    state = _load_state()
    results = {}

    # مرحلة 0: الأخبار والاستخبارات
    if not quick:
        results["intel"] = phase_intel()
    else:
        results["intel"] = {"status": "skipped_quick_mode"}

    # مرحلة 1: العقل الاستراتيجي
    results["strategy"] = phase_strategy()

    # مرحلة 2: التعلم
    if not quick:
        results["learn"] = phase_learn(results["strategy"].get("focus_tracks"))
    else:
        results["learn"] = {"status": "skipped_quick_mode"}

    # مرحلة 3: الاقتراحات
    results["suggest"] = phase_suggest(results["intel"])

    # مرحلة 4: فحص الكود
    results["review"] = phase_review_code()

    # مرحلة 5: تعلم الجهاز
    results["system"] = phase_learn_system()

    # مرحلة 6: التطوير الذاتي
    if not quick:
        results["self_improve"] = phase_self_improve()
    else:
        results["self_improve"] = {"status": "skipped_quick_mode"}

    # مرحلة 7: التقرير
    report = phase_report(results)

    # تحديث الحالة
    elapsed = round(time.time() - start, 1)
    state["last_run"] = datetime.datetime.now().isoformat()
    state["total_runs"] += 1
    if results["suggest"].get("count"):
        state["total_suggestions"] += results["suggest"]["count"]
    state["history"].append({
        "date": datetime.datetime.now().isoformat(),
        "elapsed": elapsed,
        "phases": {k: v.get("status") for k, v in results.items()},
    })
    # نحتفظ آخر 30 جلسة فقط
    state["history"] = state["history"][-30:]
    _atomic_write(STATE_FILE, state)

    _log("=" * 55)
    _log(f"✅ اكتمل في {elapsed} ثانية")
    _log(f"📄 التقرير: {REPORT_FILE}")
    _log("=" * 55)

    return results, report


def run_loop(interval_hours=6):
    """تشغيل مستمر كل X ساعات."""
    _log(f"🔄 وضع الحلقة - كل {interval_hours} ساعات")
    while True:
        try:
            run_full()
        except Exception as e:
            _log(f"خطأ في الحلقة: {e}", "ERROR")
        _log(f"💤 استراحة {interval_hours} ساعات...")
        time.sleep(interval_hours * 3600)


def show_report():
    """عرض آخر تقرير."""
    if os.path.exists(REPORT_FILE):
        with open(REPORT_FILE, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print("لا يوجد تقرير بعد. شغّل: python daily_autopilot.py")


def show_status():
    """عرض حالة النظام."""
    state = _load_state()
    print("\n" + "=" * 50)
    print("🚀 حالة المحرك اليومي")
    print("=" * 50)
    print(f"📅 آخر تشغيل: {state.get('last_run', 'لم يشتغل بعد')}")
    print(f"🔄 إجمالي التشغيلات: {state.get('total_runs', 0)}")
    print(f"💡 إجمالي الاقتراحات: {state.get('total_suggestions', 0)}")

    # حالة الأنظمة
    print("\n📦 حالة الأنظمة:")
    modules = [
        ("strategic_mind", "🎯 العقل الاستراتيجي"),
        ("mastery", "🧠 محرك التعلم"),
        ("suggest", "💡 الاقتراحات"),
        ("code_reviewer", "🔍 فاحص الكود"),
        ("computer_control", "🖥️ تحكم الجهاز"),
        ("legendary_agent", "🏆 الوكيل الأسطوري"),
        ("brain", "🔌 العقل المتعدد"),
    ]
    for mod, label in modules:
        try:
            __import__(mod)
            print(f"  ✅ {label}")
        except ImportError:
            print(f"  ❌ {label} - غير متاح")

    print("=" * 50)


# ===== الواجهة الرئيسية =====

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--report" in args:
        show_report()

    elif "--status" in args:
        show_status()

    elif "--loop" in args:
        hours = 6
        if "--hours" in args:
            idx = args.index("--hours")
            try:
                hours = int(args[idx + 1])
            except (IndexError, ValueError):
                pass
        run_loop(interval_hours=hours)

    elif "--quick" in args:
        run_full(quick=True)

    else:
        # تشغيل كامل
        run_full(quick=False)
