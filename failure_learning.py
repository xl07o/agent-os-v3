"""
failure_learning.py - نظام تعلم الفشل (v1.0)
=============================================
كل فشل يتحول إلى:
  Failure → Cause → Fix → Preventive Rule → Regression Test

بعدها ما يكرر نفس الغلطة.

الاستخدام:
  from failure_learning import FailureLearner
  fl = FailureLearner()
  fl.record(task="deploy", error="timeout", cause="API بطيء", fix="زد timeout")
  rules = fl.get_rules("deploy")  # يرجع القواعد الوقائية
"""

import datetime
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAILURE_DIR = os.path.join(BASE_DIR, "data", "failures")
os.makedirs(FAILURE_DIR, exist_ok=True)

FAILURE_DB = os.path.join(FAILURE_DIR, "failure_db.json")
RULES_DB = os.path.join(FAILURE_DIR, "preventive_rules.json")
TESTS_DB = os.path.join(FAILURE_DIR, "regression_tests.json")


def _load(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class FailureLearner:
    """يتعلم من الأخطاء ويبني قواعد وقائية واختبارات."""

    def record(self, task: str, error: str, cause: str = "", fix: str = "",
               context: dict = None) -> dict:
        """
        يسجل فشل ويستخرج منه:
        - السبب الجذري
        - الإصلاح
        - القاعدة الوقائية
        - اختبار انحدار
        """
        db = _load(FAILURE_DB, {"failures": []})
        now = datetime.datetime.now().isoformat()

        # بناء القاعدة الوقائية تلقائياً
        rule = self._build_rule(task, error, cause, fix)

        # بناء اختبار انحدار
        test = self._build_test(task, error, fix)

        entry = {
            "id": f"f_{len(db['failures'])+1:04d}",
            "task": task,
            "error": error,
            "cause": cause,
            "fix": fix,
            "rule": rule,
            "test": test,
            "context": context or {},
            "recorded_at": now,
            "times_seen": 1,
        }

        # فحص إذا نفس الخطأ موجود مسبقاً
        for f in db["failures"]:
            if f["task"] == task and f["error"][:50] == error[:50]:
                f["times_seen"] = f.get("times_seen", 1) + 1
                f["last_seen"] = now
                _save(FAILURE_DB, db)
                self._save_rule(task, rule)
                self._save_test(task, test)
                return {"status": "updated", "id": f["id"], "times_seen": f["times_seen"]}

        db["failures"].append(entry)
        _save(FAILURE_DB, db)
        self._save_rule(task, rule)
        self._save_test(task, test)

        return {"status": "recorded", "id": entry["id"], "rule": rule, "test": test}

    def _build_rule(self, task: str, error: str, cause: str, fix: str) -> str:
        """يبني قاعدة وقائية من الفشل."""
        if "timeout" in error.lower():
            return f"عند تنفيذ '{task}': استخدم timeout أطول + retry strategy"
        if "permission" in error.lower() or "denied" in error.lower():
            return f"عند تنفيذ '{task}': تحقق من الصلاحيات أولاً قبل التنفيذ"
        if "not found" in error.lower() or "404" in error:
            return f"عند تنفيذ '{task}': تحقق من وجود المورد قبل استخدامه"
        if "memory" in error.lower() or "ram" in error.lower():
            return f"عند تنفيذ '{task}': راقب استهلاك الذاكرة وقسّم المهمة"
        if fix:
            return f"عند تنفيذ '{task}': {fix}"
        if cause:
            return f"عند تنفيذ '{task}': تجنب '{cause}'"
        return f"عند تنفيذ '{task}': تحقق من الخطأ '{error[:60]}' قبل المتابعة"

    def _build_test(self, task: str, error: str, fix: str) -> dict:
        """يبني اختبار انحدار من الفشل."""
        return {
            "name": f"test_{re.sub(r'[^a-z0-9]', '_', task.lower())[:30]}_regression",
            "description": f"تأكد أن خطأ '{error[:60]}' لا يتكرر في '{task}'",
            "check": fix or f"تحقق من عدم تكرار: {error[:60]}",
            "created_at": datetime.datetime.now().isoformat(),
        }

    def _save_rule(self, task: str, rule: str):
        """يحفظ القاعدة الوقائية."""
        rules = _load(RULES_DB, {"rules": {}})
        if task not in rules["rules"]:
            rules["rules"][task] = []
        if rule not in rules["rules"][task]:
            rules["rules"][task].append(rule)
        _save(RULES_DB, rules)

    def _save_test(self, task: str, test: dict):
        """يحفظ اختبار الانحدار."""
        tests = _load(TESTS_DB, {"tests": []})
        # تجنب التكرار
        names = {t["name"] for t in tests["tests"]}
        if test["name"] not in names:
            tests["tests"].append(test)
            _save(TESTS_DB, tests)

    def get_rules(self, task: str = None) -> list:
        """يرجع القواعد الوقائية لمهمة معينة أو كلها."""
        rules = _load(RULES_DB, {"rules": {}})
        if task:
            return rules["rules"].get(task, [])
        # كل القواعد
        all_rules = []
        for t, r_list in rules["rules"].items():
            for r in r_list:
                all_rules.append(f"[{t}] {r}")
        return all_rules

    def get_tests(self) -> list:
        """يرجع كل اختبارات الانحدار."""
        tests = _load(TESTS_DB, {"tests": []})
        return tests["tests"]

    def report(self) -> str:
        """تقرير كامل بالأخطاء والقواعد."""
        db = _load(FAILURE_DB, {"failures": []})
        rules = _load(RULES_DB, {"rules": {}})
        tests = _load(TESTS_DB, {"tests": []})

        lines = ["# تقرير نظام تعلم الفشل", ""]
        lines.append(f"**إجمالي الأخطاء المسجلة:** {len(db['failures'])}")
        lines.append(f"**القواعد الوقائية:** {sum(len(v) for v in rules['rules'].values())}")
        lines.append(f"**اختبارات الانحدار:** {len(tests['tests'])}")
        lines.append("")

        if db["failures"]:
            lines.append("## أكثر الأخطاء تكراراً")
            sorted_f = sorted(db["failures"], key=lambda x: x.get("times_seen", 1), reverse=True)
            for f in sorted_f[:5]:
                lines.append(f"- [{f['task']}] {f['error'][:60]} (تكرر {f.get('times_seen',1)} مرة)")
                if f.get("rule"):
                    lines.append(f"  → القاعدة: {f['rule']}")
            lines.append("")

        return "\n".join(lines)

    def check_before_task(self, task: str) -> list:
        """قبل تنفيذ مهمة، يرجع تحذيرات بناءً على أخطاء سابقة."""
        rules = self.get_rules(task)
        db = _load(FAILURE_DB, {"failures": []})
        warnings = []
        for f in db["failures"]:
            if f["task"] == task and f.get("times_seen", 1) > 1:
                warnings.append(f"⚠️ هذه المهمة فشلت {f['times_seen']} مرة بسبب: {f['error'][:60]}")
        warnings.extend([f"📋 قاعدة: {r}" for r in rules])
        return warnings


# Singleton
_learner = FailureLearner()


def record_failure(task, error, cause="", fix="", context=None):
    return _learner.record(task, error, cause, fix, context)


def get_rules(task=None):
    return _learner.get_rules(task)


def check_before_task(task):
    return _learner.check_before_task(task)


def failure_report():
    return _learner.report()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        print(failure_report())
    elif len(sys.argv) > 1 and sys.argv[1] == "rules":
        task = sys.argv[2] if len(sys.argv) > 2 else None
        rules = get_rules(task)
        for r in rules:
            print(r)
    else:
        print("الاستخدام: python failure_learning.py report | rules [task]")
