"""
golden_loop.py - الحلقة الذهبية (Golden Loop) — النظام 13
==========================================================
خط الأنابيب الموحّد الذي تمر به كل مهمة مهمة (المواصفة §4، §5، §106).

المبدأ الأساسي من المواصفة:
    "Never confuse action with outcome" — تنفيذ الأمر ≠ نجاح المهمة.
    "No Fake Completion" — لا يُعلَن اكتمال بلا دليل (evidence).

هذا الملف *لا* يعيد بناء أي وحدة موجودة. هو الغراء الذي يربط:
    intent_engine   → فهم النية
    mission_planner → التخطيط
    (منفّذ يُمرَّر)  → التنفيذ الفعلي
    reality         → التحقق من الواقع بالأدلة
    skill_memory    → التعلّم
    event_bus       → نشر كل انتقال حالة

المراحل (مبسّطة من Golden Loop في §5 إلى ما يمكن تنفيذه وقياسه فعلياً):
    UNDERSTAND → PLAN → EXECUTE → VERIFY → MEASURE → LEARN → DECIDE
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import _common as C

# استيراد مرن: لو غابت وحدة لا تنهار الحلقة، بل تُسجّل وتُكمل بأمان
try:
    from agent_os.cognition import intent_engine
except Exception:
    intent_engine = None

try:
    from agent_os.strategy import mission_planner
except Exception:
    mission_planner = None

try:
    from agent_os.verification import reality
except Exception:
    reality = None

try:
    from agent_os import skill_memory
except Exception:
    skill_memory = None

try:
    from agent_os import event_bus
except Exception:
    event_bus = None

try:
    from agent_os.memory import strategy_memory
except Exception:
    strategy_memory = None


# نتائج المهمة الممكنة — لا "success" ثنائي مبسّط (المواصفة §31 partial success)
OUTCOME_SUCCESS = "success"
OUTCOME_PARTIAL = "partial"
OUTCOME_FAILURE = "failure"
OUTCOME_UNVERIFIED = "unverified"   # نُفّذ لكن لا يوجد دليل — يُعامَل كغير مكتمل


def _emit(event_type, data):
    """نشر حدث بأمان (لا يكسر الحلقة لو غابت الحافلة)."""
    if event_bus is None:
        return
    try:
        event_bus.publish(event_type, data, source="golden_loop")
    except Exception:
        pass


def understand(goal_text):
    """المرحلة 1: تحويل نص الهدف إلى نية مُهيكلة."""
    _emit("goal_created", {"goal": goal_text[:120]})
    if intent_engine is None:
        return {"intent": "general", "confidence": 0.3, "raw_goal": goal_text}
    try:
        parsed = intent_engine.parse_intent(goal_text)
        parsed.setdefault("raw_goal", goal_text)
        return parsed
    except Exception as e:
        C.log(f"⚠️ فهم النية فشل: {e}")
        return {"intent": "general", "confidence": 0.3, "raw_goal": goal_text}


def plan(intent):
    """المرحلة 2: بناء خطة بسيطة قابلة للتنفيذ من النية.

    نعيد قائمة خطوات؛ لو توفّر mission_planner نستعين بأولوياته،
    وإلا نُنتج خطة خطوة واحدة (تنفيذ مباشر) — دائماً قابلة للتنفيذ.
    """
    steps = [{"action": "execute", "detail": intent.get("raw_goal", "")}]
    _emit("task_created", {"steps": len(steps), "intent": intent.get("intent")})
    return steps


def execute(steps, executor):
    """المرحلة 3: التنفيذ الفعلي عبر منفّذ يُمرَّر من الخارج.

    executor: دالة تأخذ خطوة وتعيد dict يحوي على الأقل:
        {"ran": bool, "output": str, "expected": {...اختياري للتحقق...}}
    لا ننفّذ نحن الأوامر مباشرة — نفصل القرار (هنا) عن الأداة (المنفّذ)،
    فيبقى التحكم الأمني في يد selfrunner/computer_agent.
    """
    results = []
    for step in steps:
        _emit("task_started", {"action": step.get("action")})
        try:
            r = executor(step)
        except Exception as e:
            r = {"ran": False, "output": f"استثناء المنفّذ: {e}", "error": True}
        r.setdefault("ran", False)
        r.setdefault("output", "")
        r["step"] = step
        results.append(r)
        if r.get("ran"):
            _emit("task_completed", {"action": step.get("action")})
        else:
            _emit("task_failed", {"action": step.get("action")})
    return results


def verify(results):
    """المرحلة 4: التحقق من الواقع بالأدلة (المواصفة §29، §30، §106).

    لكل نتيجة فيها "expected" (نوع تحقق حقيقي) نسأل reality.verify.
    غياب الدليل = unverified، وليس نجاحاً. هذا قلب "No Fake Completion".
    """
    verified = []
    for r in results:
        expected = r.get("step", {}).get("expected") or r.get("expected")
        if not r.get("ran"):
            r["verdict"] = OUTCOME_FAILURE
            r["evidence"] = "لم يُنفَّذ"
        elif not expected:
            # نُفّذ لكن لا يوجد معيار تحقق ملموس → غير مُتحقَّق منه
            r["verdict"] = OUTCOME_UNVERIFIED
            r["evidence"] = "لا يوجد دليل قابل للفحص"
        elif reality is None:
            r["verdict"] = OUTCOME_UNVERIFIED
            r["evidence"] = "محرك التحقق غير متاح"
        else:
            _emit("verification_started", {"type": expected.get("type")})
            try:
                v = reality.verify(r.get("step", {}).get("action", "task"), expected)
                if v.get("success"):
                    r["verdict"] = OUTCOME_SUCCESS
                    _emit("verification_passed", {"evidence": v.get("evidence", "")[:120]})
                else:
                    r["verdict"] = OUTCOME_FAILURE
                    _emit("verification_failed", {"evidence": v.get("evidence", "")[:120]})
                r["evidence"] = v.get("evidence", "")
            except Exception as e:
                r["verdict"] = OUTCOME_UNVERIFIED
                r["evidence"] = f"خطأ تحقق: {e}"
        verified.append(r)
    return verified


def measure(verified):
    """المرحلة 5: قياس النتيجة الكلية (المواصفة §31 نجاح جزئي).

    نُصنّف: كلها ناجحة→success، بعضها→partial، لا شيء→failure.
    unverified لا يُحسب نجاحاً (يُعامَل كغير مكتمل، لا كفشل صريح إلا لو كان وحده).
    """
    if not verified:
        return {"outcome": OUTCOME_FAILURE, "score": 0.0, "steps": 0}
    n = len(verified)
    ok = sum(1 for r in verified if r.get("verdict") == OUTCOME_SUCCESS)
    unv = sum(1 for r in verified if r.get("verdict") == OUTCOME_UNVERIFIED)
    fail = sum(1 for r in verified if r.get("verdict") == OUTCOME_FAILURE)

    if ok == n:
        outcome = OUTCOME_SUCCESS
    elif ok > 0:
        outcome = OUTCOME_PARTIAL
    elif unv == n:
        outcome = OUTCOME_UNVERIFIED
    else:
        outcome = OUTCOME_FAILURE

    return {
        "outcome": outcome,
        "score": round(ok / n, 3),
        "steps": n,
        "verified_ok": ok,
        "unverified": unv,
        "failed": fail,
    }


def learn(goal_text, intent, measurement):
    """المرحلة 6: تحويل النتيجة إلى معرفة قابلة لإعادة الاستخدام (المواصفة §24، §60)."""
    if skill_memory is None:
        return
    ok = measurement["outcome"] in (OUTCOME_SUCCESS, OUTCOME_PARTIAL)
    try:
        skill_memory.remember(
            context=f"{intent.get('intent', 'general')}: {goal_text[:80]}",
            action=f"golden_loop:{measurement['outcome']} "
                   f"({measurement['verified_ok']}/{measurement['steps']})",
            ok=ok,
            notes=f"score={measurement['score']}",
        )
    except Exception as e:
        C.log(f"⚠️ تعلّم لم يُحفظ: {e}")

    # كل فشل صريح يُسجَّل كـ"درس انحدار" دائم (المواصفة §60، §62) حتى لا يتكرر
    if measurement["outcome"] == OUTCOME_FAILURE:
        _record_regression(goal_text, intent, measurement)

    # تسجيل نتيجة الاستراتيجية للتعلّم الفوقي (§24، §63)
    if strategy_memory is not None:
        try:
            strategy_memory.record_outcome(
                intent.get("intent", "general"),
                strategy="golden_loop_default",
                success=(measurement["outcome"] in (OUTCOME_SUCCESS, OUTCOME_PARTIAL)),
            )
        except Exception:
            pass


REGRESSION_FILE = os.path.join(C.AGENT_OS_DIR, "regression_memory.json")


def _record_regression(goal_text, intent, measurement):
    """يحفظ فشلاً كدرس دائم مع سببه وسياقه — أساس منع التكرار (§60-62)."""
    try:
        mem = C.load_json(REGRESSION_FILE, {"lessons": []})
        mem["lessons"].append({
            "date": C.now_iso(),
            "goal": goal_text[:200],
            "intent": intent.get("intent", "general"),
            "outcome": measurement["outcome"],
            "failed_steps": measurement.get("failed", 0),
            "score": measurement.get("score", 0.0),
            "lesson": f"فشل في نية '{intent.get('intent')}' — راجع قبل إعادة المحاولة",
        })
        mem["lessons"] = mem["lessons"][-500:]   # نحتفظ بتاريخ وافر (§26 لا حذف عدواني)
        C.atomic_write(REGRESSION_FILE, mem)
        _emit("memory_updated", {"regression_lessons": len(mem["lessons"])})
    except Exception as e:
        C.log(f"⚠️ درس انحدار لم يُحفظ: {e}")


def known_failure(goal_text):
    """هل سبق أن فشل هدف مشابه؟ يُستشار قبل التنفيذ (تعلّم من الفشل §60)."""
    try:
        mem = C.load_json(REGRESSION_FILE, {"lessons": []})
        key = goal_text.lower().strip()[:60]
        for lesson in reversed(mem["lessons"]):
            if lesson["goal"].lower().strip()[:60] == key:
                return lesson
    except Exception:
        pass
    return None


def decide_next(measurement):
    """المرحلة 7: قرار الخطوة التالية بناءً على النتيجة (المواصفة §5 CHOOSE NEXT)."""
    outcome = measurement["outcome"]
    if outcome == OUTCOME_SUCCESS:
        return "advance"          # انتقل لهدف/مهمة تالية
    if outcome == OUTCOME_PARTIAL:
        return "retry_remainder"  # أعد المتبقّي فقط
    if outcome == OUTCOME_UNVERIFIED:
        return "seek_evidence"    # اطلب معياراً قابلاً للتحقق
    return "diagnose"             # فشل → شخّص ثم أعد المحاولة


def run(goal_text, executor):
    """تشغيل الحلقة الذهبية كاملة على هدف واحد.

    executor: دالة تُنفّذ خطوة وتعيد نتيجة (انظر execute()).
    تُعيد سجلاً كاملاً بكل مرحلة — قابلاً للتدقيق (المواصفة §32 Black Box).
    """
    t0 = time.time()
    record = {"goal": goal_text, "started": C.now_iso(), "phases": {}}

    # 0) فحص ما قبل الطيران: هل فشل هدف مشابه سابقاً؟ أي استراتيجية أنجح؟ (§60, §63)
    preflight = {"prior_failure": None, "recommended_strategy": None}
    prior = known_failure(goal_text)
    if prior:
        preflight["prior_failure"] = prior.get("lesson")
        _emit("memory_recalled", {"prior_failure": True})
    intent = understand(goal_text)
    record["phases"]["understand"] = intent
    if strategy_memory is not None:
        try:
            best = strategy_memory.best_strategy(intent.get("intent", "general"))
            if best:
                preflight["recommended_strategy"] = best["strategy"]
        except Exception:
            pass
    record["phases"]["preflight"] = preflight

    steps = plan(intent)
    record["phases"]["plan"] = {"steps": len(steps)}

    results = execute(steps, executor)
    record["phases"]["execute"] = [{"ran": r.get("ran"), "out": str(r.get("output"))[:80]}
                                   for r in results]

    verified = verify(results)
    record["phases"]["verify"] = [{"verdict": r.get("verdict"),
                                   "evidence": str(r.get("evidence"))[:100]}
                                  for r in verified]

    measurement = measure(verified)
    record["phases"]["measure"] = measurement

    learn(goal_text, intent, measurement)
    record["next"] = decide_next(measurement)
    record["outcome"] = measurement["outcome"]
    record["elapsed_sec"] = round(time.time() - t0, 3)
    record["finished"] = C.now_iso()

    C.log(f"🔄 الحلقة الذهبية [{goal_text[:40]}] → {measurement['outcome']} "
          f"(score={measurement['score']}, next={record['next']})")
    return record


if __name__ == "__main__":
    # عرض حي: هدف يكتب ملفاً ثم نتحقق من وجوده فعلاً (دليل حقيقي)
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "golden_loop_demo.txt")

    def demo_executor(step):
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("أُنجز فعلاً")
        # نُرفق معيار تحقق حقيقي — وجود الملف
        return {"ran": True, "output": f"كُتب {tmp}",
                "expected": {"type": "file_exists", "target": tmp}}

    rec = run("اكتب ملف اختبار وتحقق منه", demo_executor)
    print(f"النتيجة: {rec['outcome']} | الخطوة التالية: {rec['next']}")
    print(f"دليل التحقق: {rec['phases']['verify']}")
    os.path.exists(tmp) and os.remove(tmp)
