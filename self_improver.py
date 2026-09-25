"""
self_improver.py - نظام التطوير الذاتي الحقيقي (v1.0)
=====================================================
يراجع كوده ويصلح العيوب
يحدث استراتيجيته بناءً على النتائج
يتعلم من أخطائه

الاستخدام:
  python self_improver.py              - تشغيل كامل
  python self_improver.py --fix        - إصلاح العيوب فقط
  python self_improver.py --strategy   - تحديث الاستراتيجية
  python self_improver.py --lessons    - عرض الدروس المتعلمة
"""

import ast
import datetime
import json
import os
import re
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LESSONS_FILE = os.path.join(BASE_DIR, "data", "lessons_learned.json")
STRATEGY_HISTORY = os.path.join(BASE_DIR, "data", "strategy_history.json")
FIX_LOG = os.path.join(BASE_DIR, "logs", "self_fixes.log")
IMPROVE_DIR = os.path.join(BASE_DIR, "data", "improvements")

for d in ["data", "logs", IMPROVE_DIR]:
    os.makedirs(os.path.join(BASE_DIR, d) if not os.path.isabs(d) else d, exist_ok=True)


# ===== أدوات =====

def _log(msg):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    try:
        with open(FIX_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_lessons():
    if os.path.exists(LESSONS_FILE):
        try:
            with open(LESSONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"lessons": [], "total": 0, "fixed": 0, "failed": 0}


def _load_strategy_history():
    if os.path.exists(STRATEGY_HISTORY):
        try:
            with open(STRATEGY_HISTORY, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"versions": [], "current_version": 1}


# ============================================================
# 1. مراجعة الكود وإصلاح العيوب
# ============================================================

def _get_fixable_issues(review_report):
    """يستخرج العيوب القابلة للإصلاح آلياً."""
    fixable = []
    for file_result in review_report.get("files", []):
        for issue in file_result.get("issues", []):
            issue_type = issue.get("type", "")
            # هذه العيوب يمكن إصلاحها آلياً
            if issue_type in [
                "Missing Docstring",
                "Long Line",
                "Technical Debt",
                "Insecure HTTP",
                "Weak Hash MD5",
            ]:
                fixable.append({
                    "file": file_result.get("file", ""),
                    "issue": issue,
                })
    return fixable


def _fix_missing_docstring(code, line_num, func_name):
    """يضيف docstring لدالة."""
    lines = code.splitlines()
    if line_num <= 0 or line_num > len(lines):
        return code, False
    # ابحث عن سطر def
    for i in range(line_num - 1, min(line_num + 2, len(lines))):
        if lines[i].strip().startswith("def ") or lines[i].strip().startswith("async def "):
            # ابحث عن نهاية سطر def
            indent = len(lines[i]) - len(lines[i].lstrip())
            body_indent = " " * (indent + 4)
            # أدخل docstring بعد سطر def
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if '"""' not in next_line and "'''" not in next_line:
                    docstring = f'{body_indent}"""دالة {func_name}."""'
                    lines.insert(i + 1, docstring)
                    return "\n".join(lines), True
    return code, False


def _fix_insecure_http(code):
    """يبدل http:// بـ https:// حيثما أمكن."""
    # فقط في السلاسل النصية الواضحة
    fixed = re.sub(
        r'(["\'])http://((?!localhost|127\.0\.0\.1)[^"\']+)(["\'])',
        r'\1https://\2\3',
        code
    )
    changed = fixed != code
    return fixed, changed


def _fix_weak_hash(code):
    """يبدل md5 بـ sha256."""
    fixed = re.sub(r'hashlib\.md5\(', 'hashlib.sha256(', code)
    fixed = re.sub(r'md5\(', 'hashlib.sha256(', fixed)
    changed = fixed != code
    return fixed, changed


def fix_file_issues(filepath, issues):
    """يصلح عيوب ملف واحد."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            original_code = f.read()
    except Exception as e:
        return False, str(e)

    code = original_code
    fixes_applied = []

    for issue in issues:
        issue_type = issue.get("type", "")
        line_num = issue.get("line", 0)

        if issue_type == "Insecure HTTP":
            code, changed = _fix_insecure_http(code)
            if changed:
                fixes_applied.append(f"تم تحويل http إلى https")

        elif issue_type == "Weak Hash MD5":
            code, changed = _fix_weak_hash(code)
            if changed:
                fixes_applied.append(f"تم تحويل md5 إلى sha256")

        elif issue_type == "Technical Debt":
            # أضف تعليق بجانب TODO
            lines = code.splitlines()
            if 0 < line_num <= len(lines):
                line = lines[line_num - 1]
                if "TODO" in line or "FIXME" in line:
                    lines[line_num - 1] = line + "  # تم الرصد - يحتاج معالجة"
                    code = "\n".join(lines)
                    fixes_applied.append(f"تم وسم TODO في سطر {line_num}")

    if not fixes_applied:
        return False, "لا توجد إصلاحات قابلة للتطبيق"

    if code == original_code:
        return False, "لم يتغير شيء"

    # تحقق من صحة الكود بعد التعديل
    if filepath.endswith(".py"):
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, f"خطأ صياغة بعد التعديل: {e}"

    # حفظ نسخة احتياطية
    backup = filepath + f".bak_{datetime.datetime.now():%Y%m%d_%H%M%S}"
    try:
        with open(backup, "w", encoding="utf-8") as f:
            f.write(original_code)
    except Exception:
        pass

    # حفظ التعديل
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(code)
    os.replace(tmp, filepath)

    return True, "\n".join(fixes_applied)


def review_and_fix():
    """يراجع كل الكود ويصلح العيوب القابلة."""
    _log("🔍 بدء مراجعة وإصلاح الكود...")
    lessons = _load_lessons()
    fixed_count = 0
    failed_count = 0
    results = []

    try:
        import code_reviewer
        report = code_reviewer.review_project(use_ai=False)
    except Exception as e:
        _log(f"خطأ في الفحص: {e}")
        return {"status": "error", "error": str(e)}

    # جمع العيوب القابلة للإصلاح
    fixable = _get_fixable_issues(report)
    _log(f"  وجد {len(fixable)} عيبة قابلة للإصلاح")

    # تجميع العيوب حسب الملف
    by_file = {}
    for item in fixable:
        fp = item["file"]
        if fp not in by_file:
            by_file[fp] = []
        by_file[fp].append(item["issue"])

    for rel_path, issues in by_file.items():
        full_path = os.path.join(BASE_DIR, rel_path)
        if not os.path.isfile(full_path):
            continue
        # لا نعدّل ملفات النظام الحساسة
        if rel_path in {"brain.py", "selfrunner.py", "self_improver.py", "code_reviewer.py"}:
            _log(f"  ⚠️ تجاهل ملف حساس: {rel_path}")
            continue

        ok, msg = fix_file_issues(full_path, issues)
        result = {"file": rel_path, "ok": ok, "msg": msg, "issues_count": len(issues)}
        results.append(result)

        if ok:
            fixed_count += 1
            _log(f"  ✅ أصلح {rel_path}: {msg}")
            # تعلم من النجاح
            lessons["lessons"].append({
                "type": "fix_success",
                "file": rel_path,
                "msg": msg,
                "date": datetime.datetime.now().isoformat(),
            })
            lessons["fixed"] += 1
        else:
            failed_count += 1
            _log(f"  ❌ فشل {rel_path}: {msg}")
            # تعلم من الفشل
            lessons["lessons"].append({
                "type": "fix_failed",
                "file": rel_path,
                "msg": msg,
                "date": datetime.datetime.now().isoformat(),
            })
            lessons["failed"] += 1

    lessons["total"] += len(fixable)
    # نحتفظ آخر 200 درس
    lessons["lessons"] = lessons["lessons"][-200:]
    _atomic_write(LESSONS_FILE, lessons)

    _log(f"  نتيجة: أصلح {fixed_count} | فشل {failed_count}")
    return {
        "status": "done",
        "fixed": fixed_count,
        "failed": failed_count,
        "results": results,
        "score_before": report.get("avg_score", 0),
    }


# ============================================================
# 2. تحديث الاستراتيجية بناءً على النتائج
# ============================================================

def update_strategy():
    """يحدث الاستراتيجية بناءً على النتائج والدروس."""
    _log("🎯 تحديث الاستراتيجية...")
    lessons = _load_lessons()
    history = _load_strategy_history()

    # تحليل الدروس
    recent = lessons["lessons"][-50:]
    fix_success = [l for l in recent if l["type"] == "fix_success"]
    fix_failed = [l for l in recent if l["type"] == "fix_failed"]
    strategy_lessons = [l for l in recent if l["type"] == "strategy"]

    # حساب معدل النجاح
    total_fixes = len(fix_success) + len(fix_failed)
    success_rate = len(fix_success) / total_fixes if total_fixes > 0 else 0

    # بناء الاستراتيجية الجديدة
    new_strategy = {
        "version": history["current_version"] + 1,
        "date": datetime.datetime.now().isoformat(),
        "based_on": {
            "fix_success_rate": round(success_rate, 2),
            "total_fixes": total_fixes,
            "lessons_count": len(recent),
        },
        "adjustments": [],
    }

    # تعديلات بناءً على النتائج
    if success_rate < 0.3:
        new_strategy["adjustments"].append(
            "معدل إصلاح منخفض - سأركز على التعلم بدل الإصلاح"
        )
    elif success_rate > 0.7:
        new_strategy["adjustments"].append(
            "معدل إصلاح عالي - سأزيد عدد الملفات المفحوصة"
        )

    # تحليل الملفات الأكثر مشكلة
    problem_files = {}
    for l in fix_failed:
        f = l.get("file", "")
        problem_files[f] = problem_files.get(f, 0) + 1
    if problem_files:
        worst = max(problem_files, key=problem_files.get)
        new_strategy["adjustments"].append(
            f"الملف الأكثر مشكلة: {worst} ({problem_files[worst]} فشل) - يحتاج مراجعة يدوية"
        )

    # تحديث الاستراتيجية في strategic_mind
    try:
        import strategic_mind as sm
        current = sm.daily_strategy()
        new_strategy["opportunities"] = current.get("top_opportunities", [])[:5]
        new_strategy["focus"] = current.get("focus_tracks", [])
    except Exception as e:
        new_strategy["strategy_error"] = str(e)

    # حفظ
    history["versions"].append(new_strategy)
    history["versions"] = history["versions"][-20:]  # آخر 20 نسخة
    history["current_version"] = new_strategy["version"]
    _atomic_write(STRATEGY_HISTORY, history)

    # تسجيل الدرس
    lessons["lessons"].append({
        "type": "strategy",
        "version": new_strategy["version"],
        "adjustments": new_strategy["adjustments"],
        "date": datetime.datetime.now().isoformat(),
    })
    _atomic_write(LESSONS_FILE, lessons)

    for adj in new_strategy["adjustments"]:
        _log(f"  → {adj}")

    _log(f"  ✓ الاستراتيجية v{new_strategy['version']} جاهزة")
    return new_strategy


# ============================================================
# 3. التعلم من الأخطاء بالذكاء الاصطناعي
# ============================================================

def learn_from_mistakes():
    """يستخدم الذكاء الاصطناعي لتحليل الأخطاء واستخلاص دروس."""
    _log("📚 التعلم من الأخطاء...")
    lessons = _load_lessons()
    recent_failures = [l for l in lessons["lessons"][-100:] if l["type"] == "fix_failed"]

    if not recent_failures:
        _log("  ✓ لا توجد أخطاء حديثة للتحليل")
        return {"status": "no_failures"}

    try:
        import brain
        failures_summary = json.dumps(recent_failures[:10], ensure_ascii=False)
        b = brain.Brain(
            "أنت محلل ذكاء اصطناعي متخصص في تحسين الكود."
        )
        analysis, engine = b.ask(
            f"""حلّل هذه الأخطاء التي فشل إصلاحها واستخلص دروساً محددة:
{failures_summary}

أجب بهذا الشكل:
1. سبب الفشل:
2. الدرس المستفاد:
3. كيف نتجنبه مستقبلاً:"""
        )

        # حفظ التحليل
        lesson = {
            "type": "ai_analysis",
            "analysis": analysis,
            "engine": engine,
            "failures_analyzed": len(recent_failures[:10]),
            "date": datetime.datetime.now().isoformat(),
        }
        lessons["lessons"].append(lesson)
        _atomic_write(LESSONS_FILE, lessons)

        _log(f"  ✓ تحليل الذكاء الاصطناعي اكتمل")
        _log(f"  الدرس: {analysis[:200]}")

        return {
            "status": "done",
            "analysis": analysis,
            "engine": engine,
            "failures_count": len(recent_failures),
        }

    except Exception as e:
        _log(f"  ⚠️ تعذر: {e}")
        return {"status": "error", "error": str(e)}


# ============================================================
# المحرك الرئيسي
# ============================================================

def run_full_improvement():
    """تشغيل دورة تحسين كاملة."""
    _log("=" * 55)
    _log("🔄 بدء دورة التطوير الذاتي")
    _log("=" * 55)

    results = {}

    # 1. مراجعة وإصلاح
    results["fix"] = review_and_fix()

    # 2. تحديث الاستراتيجية
    results["strategy"] = update_strategy()

    # 3. تعلم من الأخطاء
    results["learn"] = learn_from_mistakes()

    _log("=" * 55)
    _log("✅ اكتملت دورة التطوير الذاتي")
    return results


def show_lessons():
    """عرض الدروس المتعلمة."""
    lessons = _load_lessons()
    history = _load_strategy_history()

    print("\n" + "=" * 55)
    print("📚 الدروس المتعلمة")
    print("=" * 55)
    print(f"إجمالي الدروس: {lessons['total']}")
    print(f"إصلاحات ناجحة: {lessons['fixed']}")
    print(f"إصلاحات فاشلة: {lessons['failed']}")
    print(f"إصدار الاستراتيجية: v{history['current_version']}")

    print("\nآخر الدروس:")
    for l in lessons["lessons"][-10:]:
        t = l.get("type", "")
        date = l.get("date", "")[:10]
        if t == "fix_success":
            print(f"  ✅ [{date}] أصلح {l.get('file')}: {l.get('msg', '')[:60]}")
        elif t == "fix_failed":
            print(f"  ❌ [{date}] فشل {l.get('file')}: {l.get('msg', '')[:60]}")
        elif t == "strategy":
            print(f"  🎯 [{date}] استراتيجية v{l.get('version')}: {', '.join(l.get('adjustments', [])[:2])}")
        elif t == "ai_analysis":
            print(f"  🧠 [{date}] تحليل ذكاء: {l.get('analysis', '')[:80]}")

    print("=" * 55)


# ===== الواجهة الرئيسية =====

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--fix" in args:
        result = review_and_fix()
        print(f"\n✅ أصلح: {result.get('fixed', 0)} | فشل: {result.get('failed', 0)}")

    elif "--strategy" in args:
        strategy = update_strategy()
        print(f"\n🎯 استراتيجية v{strategy.get('version')}")
        for adj in strategy.get("adjustments", []):
            print(f"  → {adj}")

    elif "--learn" in args or "--lessons" in args:
        show_lessons()

    elif "--mistakes" in args:
        result = learn_from_mistakes()
        if result.get("analysis"):
            print(f"\n🧠 التحليل:\n{result['analysis']}")

    else:
        run_full_improvement()
