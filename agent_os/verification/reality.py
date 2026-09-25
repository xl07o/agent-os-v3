"""
reality.py - محرك التحقق من الواقع (Reality Verification Engine)
=================================================================
لا يعتبر تنفيذ الأمر = نجاح المهمة.
يجب إثبات النتيجة الحقيقية.

المبدأ: Never confuse action with outcome.
"""

import datetime
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

VERIF_DIR = os.path.join(BASE_DIR, "data", "verification")
os.makedirs(VERIF_DIR, exist_ok=True)
VERIF_LOG = os.path.join(VERIF_DIR, "verifications.json")


def _load():
    if os.path.exists(VERIF_LOG):
        try:
            with open(VERIF_LOG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"verifications": []}


def _save(data):
    tmp = VERIF_LOG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, VERIF_LOG)


class RealityVerifier:
    """
    يتحقق من النتيجة الحقيقية بعد كل عملية مهمة.

    الأنواع المدعومة:
      - file_exists: تحقق من وجود ملف
      - url_reachable: تحقق من وصول URL
      - command_output: تحقق من ناتج أمر
      - process_running: تحقق من تشغيل عملية
      - content_contains: تحقق من محتوى ملف
    """

    def verify(self, action: str, expected: dict, context: str = "") -> dict:
        """
        يتحقق من نتيجة عملية.

        action: وصف العملية (مثل: "نشر الموقع")
        expected: ما يجب أن يكون صحيحاً
          - type: نوع التحقق
          - target: الهدف (مسار/URL/أمر)
          - contains: نص يجب أن يكون موجوداً (اختياري)
        """
        result = {
            "action": action,
            "expected": expected,
            "context": context,
            "verified_at": datetime.datetime.now().isoformat(),
            "success": False,
            "evidence": "",
            "confidence": 0.0,
        }

        vtype = expected.get("type", "")
        target = expected.get("target", "")

        try:
            if vtype == "file_exists":
                exists = os.path.exists(target)
                result["success"] = exists
                result["evidence"] = f"الملف {'موجود' if exists else 'غير موجود'}: {target}"
                result["confidence"] = 1.0 if exists else 0.0

            elif vtype == "content_contains":
                contains = expected.get("contains", "")
                if os.path.exists(target):
                    with open(target, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    found = contains in content
                    result["success"] = found
                    result["evidence"] = f"النص {'موجود' if found else 'غير موجود'} في {target}"
                    result["confidence"] = 1.0 if found else 0.0
                else:
                    result["evidence"] = f"الملف غير موجود: {target}"

            elif vtype == "url_reachable":
                try:
                    from agent_os import security_kernel
                    security_kernel.url_guard(target)
                    import webtools
                    body = webtools._fetch(target, timeout=10)
                    status = 200 if body is not None else 0
                    result["success"] = 200 <= status < 400
                    result["evidence"] = f"HTTP {status}: {target}"
                    result["confidence"] = 0.9 if result["success"] else 0.1
                except Exception as e:
                    result["evidence"] = f"فشل الاتصال: {e}"

            elif vtype == "command_output":
                import subprocess
                cmd = expected.get("command", target)
                expected_out = expected.get("contains", "")
                try:
                    from agent_os import security_kernel
                    command_text = cmd if isinstance(cmd, str) else " ".join(map(str, cmd))
                    ok_cmd, reason, _ = security_kernel.check_command(command_text)
                    if not ok_cmd:
                        raise PermissionError(reason)
                    r = subprocess.run(
                        cmd if isinstance(cmd, list) else cmd.split(),
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, shell=False
                    )
                    output = r.stdout + r.stderr
                    if expected_out:
                        result["success"] = expected_out in output
                        result["evidence"] = f"الناتج: {output[:200]}"
                    else:
                        result["success"] = r.returncode == 0
                        result["evidence"] = f"Exit code: {r.returncode}"
                    result["confidence"] = 0.9
                except Exception as e:
                    result["evidence"] = f"فشل الأمر: {e}"

            elif vtype == "directory_exists":
                exists = os.path.isdir(target)
                result["success"] = exists
                result["evidence"] = f"المجلد {'موجود' if exists else 'غير موجود'}: {target}"
                result["confidence"] = 1.0 if exists else 0.0

            else:
                result["evidence"] = f"نوع تحقق غير معروف: {vtype}"
                result["confidence"] = 0.0

        except Exception as e:
            result["evidence"] = f"خطأ في التحقق: {e}"
            result["confidence"] = 0.0

        # تسجيل
        self._log(result)
        return result

    def verify_batch(self, checks: list) -> dict:
        """يتحقق من عدة شروط دفعة واحدة."""
        results = []
        for check in checks:
            r = self.verify(
                check.get("action", ""),
                check.get("expected", {}),
                check.get("context", "")
            )
            results.append(r)

        all_passed = all(r["success"] for r in results)
        partial = any(r["success"] for r in results)

        return {
            "all_passed": all_passed,
            "partial": partial and not all_passed,
            "failed": not partial,
            "results": results,
            "summary": f"{sum(r['success'] for r in results)}/{len(results)} تحققت",
        }

    def _log(self, result: dict):
        data = _load()
        data["verifications"].append(result)
        data["verifications"] = data["verifications"][-500:]
        _save(data)

    def false_success_check(self, tool_said_success: bool, actual_check: dict) -> dict:
        """
        False Success Detector:
        Tool قالت SUCCESS لكن هل الواقع يوافق؟
        """
        actual = self.verify(
            "false_success_check",
            actual_check,
            "تحقق من صحة ادعاء النجاح"
        )
        return {
            "tool_claimed_success": tool_said_success,
            "actual_success": actual["success"],
            "false_success_detected": tool_said_success and not actual["success"],
            "evidence": actual["evidence"],
        }


# Singleton
_verifier = RealityVerifier()


def verify(action, expected, context=""):
    return _verifier.verify(action, expected, context)


def verify_batch(checks):
    return _verifier.verify_batch(checks)


def false_success_check(tool_said_success, actual_check):
    return _verifier.false_success_check(tool_said_success, actual_check)


if __name__ == "__main__":
    # اختبار
    r = verify("تحقق من وجود README", {"type": "file_exists", "target": "README.md"})
    print(r)
