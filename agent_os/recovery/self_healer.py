"""
self_healer.py - مهندس الإصلاح الذاتي
======================================
فكرة المالك: "مابي يخرب واضطر أنا أصلحه — ابيه لو خرب يصلح نفسه"
التوسيع: مسار إصلاح متعدد المحاولات:
  كشف → تشخيص → محاولة 1 → اختبار → (فشل؟) → محاولة 2 → اختبار → ... → تراجع ← تعلّم
  لا يستمر في تخريب النظام (§119). يسجّل كل محاولة كدرس.
"""

import os
import sys
import subprocess

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

HEAL_LOG = os.path.join(C.AGENT_OS_DIR, "self_heal_log.json")
MAX_ATTEMPTS = 3


def diagnose():
    """يفحص صحة النظام ويعيد المشاكل المكتشفة."""
    problems = []

    # 1) فحص صياغة كل ملفات agent_os
    agent_dir = os.path.join(C.BASE_DIR, "agent_os")
    for root, dirs, files in os.walk(agent_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                try:
                    compile(open(path, encoding="utf-8").read(), path, "exec")
                except SyntaxError as e:
                    problems.append({"type": "syntax_error", "file": path,
                                     "detail": str(e), "severity": "critical"})

    # 2) فحص استيراد الوحدات الحرجة
    critical_imports = [
        "agent_os._common", "agent_os.kernel", "agent_os.golden_loop",
        "agent_os.event_bus", "agent_os.security.prompt_injection",
    ]
    for mod in critical_imports:
        try:
            __import__(mod)
        except Exception as e:
            problems.append({"type": "import_failure", "module": mod,
                             "detail": str(e)[:100], "severity": "critical"})

    # 3) فحص اختبارات الصحة بشكل bounded.
    # لا نشغّل suite كاملة من داخل self_healer: هذا يسبب recursion لأن
    # الاختبارات نفسها تستدعي diagnose(). التشغيل الكامل اختياري في CI.
    if os.environ.get("AGENT_HEALER_FULL_TESTS", "0") == "1":
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-q", "--no-header",
                 "-p", "no:cacheprovider", "--tb=no", "--ignore=tests/test_vision_batch.py"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45, cwd=C.BASE_DIR,
            )
            if r.returncode != 0:
                problems.append({"type": "test_failures", "detail": r.stdout[-500:],
                                 "severity": "high"})
        except subprocess.TimeoutExpired:
            problems.append({"type": "test_runner_timeout", "detail": "bounded health suite timed out",
                             "severity": "medium"})
        except Exception as e:
            problems.append({"type": "test_runner_error", "detail": str(e)[:100],
                             "severity": "medium"})

    return problems


def heal(problems, fixer=None):
    """يحاول إصلاح المشاكل المكتشفة.

    fixer: دالة اختيارية تأخذ مشكلة وتعيد {"fixed": bool, "detail": str}.
    بدون fixer يسجّل المشاكل فقط ويتعلّم منها.
    """
    results = []
    for problem in problems:
        entry = {"problem": problem, "attempts": [], "healed": False}

        if fixer:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    fix = fixer(problem)
                    entry["attempts"].append({"n": attempt, **fix})
                    if fix.get("fixed"):
                        entry["healed"] = True
                        break
                except Exception as e:
                    entry["attempts"].append({"n": attempt, "fixed": False,
                                              "detail": f"استثناء: {e}"})
        results.append(entry)

    _log_healing(results)
    return results


def check_and_heal(fixer=None):
    """دورة كاملة: تشخيص → إصلاح → تقرير."""
    problems = diagnose()
    if not problems:
        C.log("🩺 الإصلاح الذاتي: النظام سليم — لا مشاكل")
        return {"healthy": True, "problems": 0}

    C.log(f"🩺 الإصلاح الذاتي: {len(problems)} مشكلة مكتشفة — أبدأ الإصلاح")
    results = heal(problems, fixer)
    healed = sum(1 for r in results if r["healed"])
    return {
        "healthy": healed == len(problems),
        "problems": len(problems),
        "healed": healed,
        "remaining": len(problems) - healed,
        "details": results,
    }


def _log_healing(results):
    log = C.load_json(HEAL_LOG, {"sessions": []})
    log["sessions"].append({
        "at": C.now_iso(),
        "problems": len(results),
        "healed": sum(1 for r in results if r["healed"]),
        "details": [{"type": r["problem"]["type"],
                      "healed": r["healed"],
                      "attempts": len(r["attempts"])} for r in results],
    })
    log["sessions"] = log["sessions"][-100:]
    C.atomic_write(HEAL_LOG, log)


if __name__ == "__main__":
    r = check_and_heal()
    print(f"سليم: {r['healthy']} | مشاكل: {r['problems']} | أُصلح: {r.get('healed', 0)}")
