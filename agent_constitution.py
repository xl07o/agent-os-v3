"""
agent_constitution.py - دستور الـ Agent (v1.0)
===============================================
دستور داخلي مع Validator يتأكد أن كل تصرف التزم بالدستور.

المبادئ:
  1. لا تدعي نجاح شيء لم تتحقق منه
  2. تحقق من النتائج قبل التقرير
  3. لا تغير Production مباشرة
  4. اختبر قبل الدمج
  5. احتفظ بسبب القرارات
  6. عند الشك، اجمع أدلة
  7. لا تكرر الفشل نفسه
  8. حافظ على الموارد والتكلفة
"""

import datetime
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONST_DIR = os.path.join(BASE_DIR, "data", "constitution")
os.makedirs(CONST_DIR, exist_ok=True)
VIOLATIONS_LOG = os.path.join(CONST_DIR, "violations.json")

# الدستور
CONSTITUTION = [
    {
        "id": 1,
        "principle": "لا تدعي نجاح شيء لم تتحقق منه",
        "check": "verified",
        "severity": "critical",
    },
    {
        "id": 2,
        "principle": "تحقق من النتائج قبل التقرير",
        "check": "results_verified",
        "severity": "high",
    },
    {
        "id": 3,
        "principle": "لا تغير Production مباشرة",
        "check": "no_direct_production",
        "severity": "critical",
    },
    {
        "id": 4,
        "principle": "اختبر قبل الدمج",
        "check": "tested_before_merge",
        "severity": "high",
    },
    {
        "id": 5,
        "principle": "احتفظ بسبب القرارات",
        "check": "decision_reason_recorded",
        "severity": "medium",
    },
    {
        "id": 6,
        "principle": "عند الشك، اجمع أدلة",
        "check": "evidence_collected",
        "severity": "medium",
    },
    {
        "id": 7,
        "principle": "لا تكرر الفشل نفسه",
        "check": "no_repeated_failure",
        "severity": "high",
    },
    {
        "id": 8,
        "principle": "حافظ على الموارد والتكلفة",
        "check": "resource_efficient",
        "severity": "medium",
    },
]


def _load_violations():
    if os.path.exists(VIOLATIONS_LOG):
        try:
            with open(VIOLATIONS_LOG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"violations": []}


def _save_violations(data):
    tmp = VIOLATIONS_LOG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, VIOLATIONS_LOG)


class ConstitutionValidator:
    """يتحقق أن كل تصرف التزم بالدستور."""

    def validate_action(self, action: dict) -> dict:
        """
        يتحقق من تصرف قبل تنفيذه.

        action يجب أن يحتوي:
          - type: نوع التصرف (deploy, merge, delete, report, ...)
          - verified: هل تم التحقق من النتيجة؟
          - tested: هل تم الاختبار؟
          - reason: سبب القرار
          - target: الهدف (production/staging/dev)
        """
        violations = []
        warnings = []

        action_type = action.get("type", "")
        verified = action.get("verified", False)
        tested = action.get("tested", False)
        reason = action.get("reason", "")
        target = action.get("target", "")
        evidence = action.get("evidence", [])

        # المبدأ 1: لا تدعي نجاح شيء لم تتحقق منه
        if action_type in ("report", "complete", "done") and not verified:
            violations.append({"principle": 1, "msg": "تدعي الإنجاز بدون تحقق"})

        # المبدأ 2: تحقق من النتائج قبل التقرير
        if action_type == "report" and not verified:
            violations.append({"principle": 2, "msg": "تقرير بدون تحقق من النتائج"})

        # المبدأ 3: لا تغير Production مباشرة
        if "production" in target.lower() and action_type in ("deploy", "modify", "delete", "update"):
            violations.append({"principle": 3, "msg": f"محاولة تعديل Production مباشرة: {action_type}"})

        # المبدأ 4: اختبر قبل الدمج
        if action_type == "merge" and not tested:
            violations.append({"principle": 4, "msg": "دمج بدون اختبار"})

        # المبدأ 5: احتفظ بسبب القرارات
        if not reason and action_type in ("deploy", "merge", "delete", "modify"):
            warnings.append({"principle": 5, "msg": "لا يوجد سبب مسجل للقرار"})

        # المبدأ 6: عند الشك، اجمع أدلة
        if action.get("confidence", 1.0) < 0.5 and not evidence:
            warnings.append({"principle": 6, "msg": "ثقة منخفضة بدون أدلة"})

        result = {
            "action": action,
            "violations": violations,
            "warnings": warnings,
            "approved": len(violations) == 0,
            "checked_at": datetime.datetime.now().isoformat(),
        }

        # تسجيل الانتهاكات
        if violations:
            self._log_violations(action, violations)

        return result

    def _log_violations(self, action: dict, violations: list):
        data = _load_violations()
        data["violations"].append({
            "action_type": action.get("type", ""),
            "violations": violations,
            "at": datetime.datetime.now().isoformat(),
        })
        data["violations"] = data["violations"][-100:]  # احتفظ بآخر 100
        _save_violations(data)

    def get_constitution(self) -> list:
        """يرجع الدستور كاملاً."""
        return CONSTITUTION

    def violations_report(self) -> str:
        """تقرير الانتهاكات."""
        data = _load_violations()
        violations = data.get("violations", [])
        lines = ["# تقرير انتهاكات الدستور", ""]
        lines.append(f"**إجمالي الانتهاكات:** {len(violations)}")
        if violations:
            lines.append("\n**آخر الانتهاكات:**")
            for v in violations[-5:]:
                lines.append(f"- [{v['at'][:19]}] {v['action_type']}: {v['violations'][0]['msg']}")
        return "\n".join(lines)


# Singleton
_validator = ConstitutionValidator()


def validate_action(action: dict) -> dict:
    return _validator.validate_action(action)


def get_constitution() -> list:
    return _validator.get_constitution()


def violations_report() -> str:
    return _validator.violations_report()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        print(violations_report())
    elif len(sys.argv) > 1 and sys.argv[1] == "show":
        for p in get_constitution():
            print(f"{p['id']}. [{p['severity'].upper()}] {p['principle']}")
    else:
        # اختبار
        result = validate_action({
            "type": "deploy",
            "target": "production",
            "verified": False,
            "tested": False,
            "reason": "",
        })
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
