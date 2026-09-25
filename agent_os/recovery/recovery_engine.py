"""
recovery_engine.py - محرك الاسترداد الذاتي (Recovery Engine)
=============================================================
كل فشل:
  DETECT -> ISOLATE -> DIAGNOSE -> SAFE REPAIR -> TEST -> VERIFY -> RESUME

لا يستمر في تخريب النظام.
لا يحتاج تدخل المستخدم إلا إذا أصبح الإصلاح خارج نطاق قدرته.
"""

import datetime
import json
import os
import sys
import traceback

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

RECOVERY_DIR = os.path.join(BASE_DIR, "data", "recovery")
os.makedirs(RECOVERY_DIR, exist_ok=True)
INCIDENTS_FILE = os.path.join(RECOVERY_DIR, "incidents.json")
REPAIRS_FILE = os.path.join(RECOVERY_DIR, "repairs.json")


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


class RecoveryEngine:
    """
    يكتشف الفشل ويحاول الإصلاح تلقائياً.

    استراتيجيات الإصلاح:
    1. إعادة المحاولة (retry)
    2. تبديل المزود (provider_switch)
    3. تبسيط المهمة (simplify)
    4. استخدام checkpoint (resume_checkpoint)
    5. تصعيد للإنسان (escalate)
    """

    STRATEGIES = [
        "retry",
        "provider_switch",
        "simplify",
        "resume_checkpoint",
        "escalate",
    ]

    def handle_failure(self, task: str, error: str, context: dict = None,
                       attempt: int = 1) -> dict:
        """
        يعالج فشل مهمة.
        يرجع: {action, strategy, result, escalate}
        """
        incident = self._create_incident(task, error, context, attempt)
        diagnosis = self._diagnose(error, attempt)
        strategy = self._select_strategy(diagnosis, attempt)
        result = self._apply_strategy(strategy, task, error, context)

        incident["diagnosis"] = diagnosis
        incident["strategy"] = strategy
        incident["result"] = result
        incident["resolved"] = result.get("success", False)
        self._save_incident(incident)

        # تعلم من الفشل
        try:
            from failure_learning import record_failure
            record_failure(
                task=task[:60],
                error=error[:200],
                cause=diagnosis.get("cause", ""),
                fix=strategy,
                context=context,
            )
        except Exception:
            pass

        return {
            "action": strategy,
            "result": result,
            "escalate": strategy == "escalate",
            "incident_id": incident["id"],
        }

    def _diagnose(self, error: str, attempt: int) -> dict:
        """يشخص سبب الفشل."""
        error_lower = error.lower()
        cause = "unknown"
        category = "unknown"

        if "timeout" in error_lower or "timed out" in error_lower:
            cause = "timeout"
            category = "network"
        elif "connection" in error_lower or "network" in error_lower:
            cause = "network_error"
            category = "network"
        elif "permission" in error_lower or "denied" in error_lower or "403" in error:
            cause = "permission_denied"
            category = "auth"
        elif "not found" in error_lower or "404" in error:
            cause = "resource_not_found"
            category = "resource"
        elif "memory" in error_lower or "ram" in error_lower:
            cause = "memory_exhaustion"
            category = "resource"
        elif "rate limit" in error_lower or "429" in error:
            cause = "rate_limited"
            category = "api"
        elif "api" in error_lower or "key" in error_lower:
            cause = "api_error"
            category = "api"
        elif "syntax" in error_lower or "parse" in error_lower:
            cause = "syntax_error"
            category = "code"
        elif attempt > 2:
            cause = "persistent_failure"
            category = "unknown"

        return {
            "cause": cause,
            "category": category,
            "attempt": attempt,
            "severity": "high" if attempt > 2 else "medium",
        }

    def _select_strategy(self, diagnosis: dict, attempt: int) -> str:
        """يختار استراتيجية الإصلاح."""
        cause = diagnosis.get("cause", "unknown")
        category = diagnosis.get("category", "unknown")

        if attempt >= 4:
            return "escalate"

        if cause == "timeout" and attempt <= 2:
            return "retry"
        elif cause == "rate_limited":
            return "retry"  # مع تأخير
        elif cause == "network_error" and attempt <= 2:
            return "retry"
        elif category == "api" and attempt == 2:
            return "provider_switch"
        elif cause == "resource_not_found":
            return "simplify"
        elif cause == "persistent_failure":
            return "resume_checkpoint"
        elif attempt == 3:
            return "escalate"
        else:
            return "retry"

    def _apply_strategy(self, strategy: str, task: str, error: str, context: dict) -> dict:
        """يطبق استراتيجية الإصلاح."""
        if strategy == "retry":
            return {
                "success": True,
                "action": "retry",
                "message": "سيتم إعادة المحاولة",
            }

        elif strategy == "provider_switch":
            try:
                import brain
                available = brain.available_engines()
                if len(available) > 1:
                    return {
                        "success": True,
                        "action": "provider_switch",
                        "message": f"تبديل للمزود: {available[1]['id']}",
                        "new_provider": available[1]["id"],
                    }
            except Exception:
                pass
            return {"success": False, "action": "provider_switch", "message": "لا يوجد مزود بديل"}

        elif strategy == "simplify":
            return {
                "success": True,
                "action": "simplify",
                "message": "تبسيط المهمة وإعادة المحاولة",
                "simplified_task": task[:100] + " (مبسط)",
            }

        elif strategy == "resume_checkpoint":
            try:
                from checkpoint_system import CheckpointManager
                import hashlib
                task_id = hashlib.md5(task.encode()).hexdigest()[:12]
                cp = CheckpointManager(task_id)
                existing = cp.load()
                if existing:
                    return {
                        "success": True,
                        "action": "resume_checkpoint",
                        "message": f"استئناف من الخطوة {existing.get('step', 0)}",
                        "checkpoint": existing,
                    }
            except Exception:
                pass
            return {"success": False, "action": "resume_checkpoint", "message": "لا يوجد checkpoint"}

        elif strategy == "escalate":
            self._create_human_request(task, error)
            return {
                "success": False,
                "action": "escalate",
                "message": "تم تصعيد المشكلة للمستخدم",
                "requires_human": True,
            }

        return {"success": False, "action": "unknown", "message": "استراتيجية غير معروفة"}

    def _create_incident(self, task: str, error: str, context: dict, attempt: int) -> dict:
        """ينشئ سجل حادثة."""
        incidents = _load(INCIDENTS_FILE, {"incidents": []})
        incident = {
            "id": f"inc_{len(incidents['incidents'])+1:04d}",
            "task": task[:100],
            "error": error[:300],
            "context": context or {},
            "attempt": attempt,
            "created_at": datetime.datetime.now().isoformat(),
            "resolved": False,
            "diagnosis": {},
            "strategy": "",
            "result": {},
        }
        return incident

    def _save_incident(self, incident: dict):
        incidents = _load(INCIDENTS_FILE, {"incidents": []})
        incidents["incidents"].append(incident)
        _save(INCIDENTS_FILE, incidents)

    def _create_human_request(self, task: str, error: str):
        """ينشئ طلب للمستخدم في pending_requests."""
        requests_dir = os.path.join(BASE_DIR, "data", "requests", "pending")
        os.makedirs(requests_dir, exist_ok=True)
        req = {
            "request_id": f"req_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "reason": f"فشل متكرر في: {task[:60]}",
            "error": error[:200],
            "instructions": ["راجع الخطأ", "أعد تشغيل المهمة يدوياً إذا لزم"],
            "priority": "high",
            "created_at": datetime.datetime.now().isoformat(),
            "status": "pending",
        }
        path = os.path.join(requests_dir, f"{req['request_id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(req, f, ensure_ascii=False, indent=2)

    def get_incidents(self, limit: int = 20) -> list:
        """يرجع آخر الحوادث."""
        incidents = _load(INCIDENTS_FILE, {"incidents": []})
        return incidents["incidents"][-limit:][::-1]

    def postmortem(self, incident_id: str) -> str:
        """يولد تقرير postmortem لحادثة."""
        incidents = _load(INCIDENTS_FILE, {"incidents": []})
        incident = next((i for i in incidents["incidents"] if i["id"] == incident_id), None)
        if not incident:
            return f"لا توجد حادثة بالمعرف: {incident_id}"

        lines = [
            f"# Postmortem: {incident_id}",
            f"**المهمة:** {incident['task']}",
            f"**الخطأ:** {incident['error']}",
            f"**التشخيص:** {incident.get('diagnosis', {}).get('cause', 'غير معروف')}",
            f"**الاستراتيجية:** {incident.get('strategy', '')}",
            f"**النتيجة:** {'نجح' if incident.get('resolved') else 'فشل'}",
            f"**الوقت:** {incident['created_at'][:19]}",
        ]
        return "\n".join(lines)


# Singleton
_engine = RecoveryEngine()


def handle_failure(task, error, context=None, attempt=1):
    return _engine.handle_failure(task, error, context, attempt)


def get_incidents(limit=20):
    return _engine.get_incidents(limit)


def postmortem(incident_id):
    return _engine.postmortem(incident_id)


if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    if action == "list":
        import json
        print(json.dumps(get_incidents(10), ensure_ascii=False, indent=2))
