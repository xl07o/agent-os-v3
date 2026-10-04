"""
self_evolving.py - البنية المتطورة ذاتياً (Self-Evolving Architecture) v1.0
===========================================================================
مو بس يتعلم معلومات؛ يتعلم كيف يحسن نفسه.

يكتشف:
  "كل مرة مهمة X تفشل بسبب الطريقة Y."

فيقترح تعديل الـworkflow أو skill، يشغله في Sandbox،
يقارن الأداء بالإصدار القديم، وإذا أفضل → يعتمد النسخة الجديدة.

الدورة:
  Agent → يراقب نفسه → يكتشف ضعف → يبني تحسين → يختبره → يقرر اعتماده
"""

import ast
import datetime
import json
import os
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

EVOLVE_DIR = os.path.join(BASE_DIR, "data", "evolve")
SANDBOX_DIR = os.path.join(BASE_DIR, "data", "evolve", "sandbox")
os.makedirs(EVOLVE_DIR, exist_ok=True)
os.makedirs(SANDBOX_DIR, exist_ok=True)

EVOLVE_DB = os.path.join(EVOLVE_DIR, "improvements.json")

# مكتبات مسموحة في الـ Sandbox
ALLOWED_IMPORTS = {
    "math", "re", "json", "itertools", "functools", "collections",
    "datetime", "string", "random", "statistics", "heapq", "bisect",
    "dataclasses", "typing", "enum", "decimal", "fractions", "copy",
    "unittest", "hashlib", "base64",
}


def _load_db():
    if os.path.exists(EVOLVE_DB):
        try:
            with open(EVOLVE_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"improvements": [], "patterns": {}, "adopted": []}


def _save_db(data):
    tmp = EVOLVE_DB + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, EVOLVE_DB)


def _static_guard(code: str) -> tuple:
    """فحص أمني للكود قبل تشغيله في الـ Sandbox."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"خطأ صياغة: {e}"

    if len(code.splitlines()) > 200:
        return False, "الكود أطول من 200 سطر"

    forbidden = {"os", "sys", "subprocess", "socket", "eval", "exec",
                 "__import__", "open", "pathlib", "shutil"}

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in getattr(node, "names", [])]
            mod = getattr(node, "module", "") or ""
            for name in names + [mod]:
                root = name.split(".")[0]
                if root and root not in ALLOWED_IMPORTS:
                    return False, f"استيراد ممنوع: {root}"
        elif isinstance(node, ast.Name) and node.id in forbidden:
            return False, f"استخدام ممنوع: {node.id}"

    return True, "ok"


def _run_in_sandbox(code: str, timeout: int = 30) -> tuple:
    """يشغل الكود في بيئة معزولة."""
    ok, reason = _static_guard(code)
    if not ok:
        return False, f"رُفض أمنياً: {reason}"

    path = os.path.join(SANDBOX_DIR, f"test_{int(time.time())}.py")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        result = subprocess.run(
            [sys.executable, "-B", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
            cwd=SANDBOX_DIR,
        )
        success = result.returncode == 0
        output = (result.stdout + result.stderr)[:500]
        return success, output
    except subprocess.TimeoutExpired:
        return False, "انتهت المهلة"
    except Exception as e:
        return False, str(e)[:200]
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


class SelfEvolver:
    """يراقب الأداء ويقترح تحسينات ذاتية."""

    def record_pattern(self, task_type: str, method: str, success: bool, duration: float = 0):
        """يسجل نمط أداء لمهمة معينة."""
        db = _load_db()
        key = f"{task_type}::{method}"
        if key not in db["patterns"]:
            db["patterns"][key] = {"success": 0, "fail": 0, "total_duration": 0, "count": 0}
        p = db["patterns"][key]
        p["count"] += 1
        p["total_duration"] += duration
        if success:
            p["success"] += 1
        else:
            p["fail"] += 1
        _save_db(db)

    def find_weak_patterns(self, min_failures: int = 2) -> list:
        """يكتشف الأنماط الضعيفة التي تفشل كثيراً."""
        db = _load_db()
        weak = []
        for key, p in db["patterns"].items():
            if p["fail"] >= min_failures:
                fail_rate = p["fail"] / max(p["count"], 1)
                if fail_rate > 0.4:  # أكثر من 40% فشل
                    task_type, method = key.split("::", 1)
                    weak.append({
                        "task_type": task_type,
                        "method": method,
                        "fail_rate": round(fail_rate, 2),
                        "failures": p["fail"],
                        "total": p["count"],
                    })
        return sorted(weak, key=lambda x: x["fail_rate"], reverse=True)

    def propose_improvement(self, weak_pattern: dict) -> dict:
        """يقترح تحسيناً لنمط ضعيف."""
        try:
            import brain
            b = brain.Brain("أنت مهندس تحسين. اقترح تحسيناً محدداً وقابلاً للتنفيذ.")
            prompt = (
                f"النمط الضعيف: '{weak_pattern['task_type']}' بطريقة '{weak_pattern['method']}' "
                f"يفشل {int(weak_pattern['fail_rate']*100)}% من الوقت.\n"
                f"اقترح تحسيناً محدداً مع كود بايثون بسيط يمكن اختباره."
            )
            response, engine = b.ask(prompt)
            return {
                "pattern": weak_pattern,
                "proposal": response[:800],
                "engine": engine,
                "status": "proposed",
                "created_at": datetime.datetime.now().isoformat(),
            }
        except Exception as e:
            return {"pattern": weak_pattern, "proposal": "", "error": str(e)[:100], "status": "failed"}

    def test_improvement(self, improvement: dict) -> dict:
        """يختبر التحسين في Sandbox."""
        proposal = improvement.get("proposal", "")
        # استخراج الكود من الاقتراح
        import re
        code_match = re.search(r"```python\n(.*?)```", proposal, re.DOTALL)
        if not code_match:
            code_match = re.search(r"```\n(.*?)```", proposal, re.DOTALL)

        if not code_match:
            return {**improvement, "test_result": "لم يُعثر على كود للاختبار", "adopted": False}

        code = code_match.group(1)
        success, output = _run_in_sandbox(code)
        return {
            **improvement,
            "test_result": output,
            "test_passed": success,
            "adopted": False,
        }

    def adopt_improvement(self, improvement: dict) -> bool:
        """ينجح اختبار الـ sandbox لا يكفي للاعتماد: يُرسَل التحسين لبوابة
        الموافقة البشرية (agent_os.approval_center) ولا يُعتمد فعلياً إلا
        بعد موافقة صريحة — نفس البوابة التي يستخدمها self_improve_engine.py
        للتعديلات الحرجة، بدل اعتماد مباشر بلا مراجعة."""
        if not improvement.get("test_passed"):
            return False
        try:
            from agent_os import approval_center
        except Exception as e:
            print(f"[Self-Evolving] ⚠️ تعذّر الوصول لمركز الموافقات: {str(e)[:100]} — لن يُعتمد التحسين بلا موافقة.")
            return False

        req = approval_center.create_request(
            f"اعتماد تحسين ذاتي: {improvement.get('pattern', {}).get('task_type', '?')}",
            f"اجتاز اختبار الـ sandbox. نتيجة الاختبار: {str(improvement.get('test_result', ''))[:200]}",
            ["راجع الكود المقترح أدناه", "وافق للاعتماد أو ارفض للتجاهل"],
            kind="code_change", risk="high",
            payload={"proposal": improvement.get("proposal", "")[:4000],
                     "pattern": improvement.get("pattern", {})},
        )
        improvement["adopted"] = False
        improvement["approval_request_id"] = req["id"]
        improvement["status"] = "pending_approval"
        db = _load_db()
        db["improvements"].append(improvement)
        _save_db(db)
        print(f"[Self-Evolving] ⏳ تحسين بانتظار موافقتك: طلب #{req['id']}")
        return False


    def run_evolution_cycle(self) -> dict:
        """دورة تطور كاملة: اكتشف → اقترح → اختبر → اعتمد."""
        print("[Self-Evolving] 🧬 بدء دورة التطور...")
        weak = self.find_weak_patterns()
        if not weak:
            print("[Self-Evolving] لا توجد أنماط ضعيفة حالياً.")
            return {"status": "no_weak_patterns"}

        results = []
        for pattern in weak[:2]:  # نعالج أسوأ نمطين
            print(f"[Self-Evolving] اكتشفت نمط ضعيف: {pattern['task_type']} ({int(pattern['fail_rate']*100)}% فشل)")
            improvement = self.propose_improvement(pattern)
            tested = self.test_improvement(improvement)
            if tested.get("test_passed"):
                self.adopt_improvement(tested)
                print("[Self-Evolving] ⏳ تحسين بانتظار موافقتك (راجع agent_os/approval_center.py list)")
            else:
                print(f"[Self-Evolving] ❌ فشل الاختبار: {tested.get('test_result', '')[:100]}")
            results.append(tested)

        return {"status": "done", "cycles": len(results), "results": results}

    def report(self) -> str:
        """تقرير التطور الذاتي."""
        db = _load_db()
        lines = ["# تقرير التطور الذاتي", ""]
        lines.append(f"**الأنماط المرصودة:** {len(db['patterns'])}")
        lines.append(f"**التحسينات المعتمدة:** {len(db['adopted'])}")
        weak = self.find_weak_patterns()
        if weak:
            lines.append(f"\n**أضعف الأنماط:**")
            for w in weak[:3]:
                lines.append(f"- {w['task_type']}: {int(w['fail_rate']*100)}% فشل")
        return "\n".join(lines)


def finalize_pending_adoptions() -> dict:
    """يُستدعى دورياً: يتحقق من طلبات التحسين المعلّقة في approval_center
    ويعتمد في قاعدة بيانات self_evolving ما وافق عليه المستخدم فعلياً فقط."""
    try:
        from agent_os import approval_center
    except Exception as e:
        return {"status": "error", "reason": str(e)[:100]}

    db = _load_db()
    finalized = []
    for imp in db["improvements"]:
        rid = imp.get("approval_request_id")
        if not rid or imp.get("adopted"):
            continue
        resolved = approval_center.check_resolution(rid)
        if not resolved:
            continue
        if resolved.get("status") == "done":
            imp["adopted"] = True
            imp["adopted_at"] = datetime.datetime.now().isoformat()
            db["adopted"].append(imp)
            finalized.append({"id": rid, "status": "adopted"})
        else:
            imp["status"] = "rejected"
            finalized.append({"id": rid, "status": "rejected"})
    if finalized:
        _save_db(db)
    return {"status": "done", "finalized": finalized}


# Singleton
_evolver = SelfEvolver()


def record_pattern(task_type, method, success, duration=0):
    _evolver.record_pattern(task_type, method, success, duration)


def run_evolution_cycle():
    return _evolver.run_evolution_cycle()


def evolution_report():
    return _evolver.report()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "report"
    if action == "run":
        import json
        print(json.dumps(run_evolution_cycle(), ensure_ascii=False, indent=2))
    elif action == "report":
        print(evolution_report())
    else:
        print("الاستخدام: python self_evolving.py run | report")
