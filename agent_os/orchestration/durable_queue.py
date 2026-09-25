"""
durable_queue.py - طابور مهام دائم (Durable Task Queue)
=========================================================
المهام لا تضيع عند crash أو restart.
كل مهمة لها State Machine كامل.

الحالات:
  CREATED -> PLANNED -> APPROVED -> RUNNING -> VERIFYING
  -> SUCCESS | FAILED | RECOVERING | PAUSED | CANCELLED
"""

import datetime
import hashlib
import json
import os
import sys
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

QUEUE_DIR = os.path.join(BASE_DIR, "data", "task_queue")
os.makedirs(QUEUE_DIR, exist_ok=True)
QUEUE_FILE = os.path.join(QUEUE_DIR, "queue.json")
HISTORY_FILE = os.path.join(QUEUE_DIR, "history.json")


ALLOWED_TRANSITIONS = {
    "CREATED": {"PLANNED", "CANCELLED", "PAUSED"},
    "PLANNED": {"APPROVED", "RUNNING", "CANCELLED", "PAUSED"},
    "APPROVED": {"RUNNING", "CANCELLED", "PAUSED"},
    "RUNNING": {"VERIFYING", "FAILED", "RECOVERING", "PAUSED", "CANCELLED"},
    "VERIFYING": {"SUCCESS", "FAILED", "RECOVERING", "PAUSED"},
    "RECOVERING": {"CREATED", "FAILED", "PAUSED", "CANCELLED"},
    "PAUSED": {"CREATED", "PLANNED", "APPROVED", "CANCELLED"},
    "FAILED": {"RECOVERING", "ARCHIVED", "CREATED"},
    "SUCCESS": {"ARCHIVED"},
    "CANCELLED": {"ARCHIVED"},
    "ARCHIVED": set(),
}

VALID_STATES = [
    "CREATED", "PLANNED", "APPROVED", "RUNNING",
    "VERIFYING", "SUCCESS", "FAILED", "RECOVERING",
    "PAUSED", "CANCELLED", "ARCHIVED"
]

_lock = threading.Lock()


def _load_queue():
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"tasks": []}


def _save_queue(data):
    tmp = QUEUE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, QUEUE_FILE)


def _load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"tasks": []}


def _save_history(data):
    tmp = HISTORY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_FILE)


class DurableTaskQueue:
    """
    طابور مهام دائم - المهام تبقى حتى بعد restart.

    ميزات:
    - State Machine كامل لكل مهمة
    - Idempotency: لا تكرار للعمليات الخطرة
    - Priority Queue: الأهم أولاً
    - Checkpoint: استئناف من آخر نقطة
    - History: سجل كامل لا يُحذف
    """

    def enqueue(self, name: str, payload: dict = None, priority: int = 5,
                idempotency_key: str = None, requires_approval: bool = False,
                tags: list = None) -> dict:
        """
        يضيف مهمة للطابور.
        priority: 1 (أعلى) - 10 (أدنى)
        idempotency_key: إذا موجود، لا يضيف نفس المهمة مرتين
        """
        with _lock:
            queue = _load_queue()

            # Idempotency check
            if idempotency_key:
                for t in queue["tasks"]:
                    if t.get("idempotency_key") == idempotency_key and \
                       t["state"] not in ("SUCCESS", "CANCELLED", "ARCHIVED"):
                        return {"status": "already_exists", "task": t}

            task_id = hashlib.md5(
                f"{name}{datetime.datetime.now().isoformat()}".encode()
            ).hexdigest()[:12]

            task = {
                "id": task_id,
                "name": name,
                "payload": payload or {},
                "priority": priority,
                "state": "CREATED",
                "idempotency_key": idempotency_key,
                "requires_approval": requires_approval,
                "tags": tags or [],
                "created_at": datetime.datetime.now().isoformat(),
                "updated_at": datetime.datetime.now().isoformat(),
                "attempts": 0,
                "max_attempts": 3,
                "checkpoint": None,
                "result": None,
                "error": None,
                "evidence": [],
            }

            queue["tasks"].append(task)
            _save_queue(queue)
            return {"status": "enqueued", "task": task}

    def next_task(self, state: str = "CREATED") -> dict:
        """اختيار + claim ذري داخل lock لمنع عاملين من تنفيذ نفس المهمة."""
        with _lock:
            queue = _load_queue()
            candidates = [t for t in queue["tasks"] if t["state"] == state and not t.get("requires_approval", False)]
            if not candidates: return None
            task=min(candidates,key=lambda t:(t["priority"],t["created_at"]))
            if state in ("CREATED","PLANNED"):
                task["state"]="RUNNING"
                task["claimed_at"]=datetime.datetime.now().isoformat()
                task["updated_at"]=task["claimed_at"]
                _save_queue(queue)
            return dict(task)

    def transition(self, task_id: str, new_state: str,
                   result=None, error=None, checkpoint=None, evidence=None) -> bool:
        """ينقل مهمة لحالة جديدة."""
        if new_state not in VALID_STATES:
            return False

        with _lock:
            queue = _load_queue()
            for task in queue["tasks"]:
                if task["id"] == task_id:
                    old_state = task["state"]
                    if new_state != old_state and new_state not in ALLOWED_TRANSITIONS.get(old_state, set()):
                        return False
                    task["state"] = new_state
                    task["updated_at"] = datetime.datetime.now().isoformat()
                    if result is not None:
                        task["result"] = result
                    if error is not None:
                        task["error"] = error
                    if checkpoint is not None:
                        task["checkpoint"] = checkpoint
                    if evidence:
                        task["evidence"].extend(evidence if isinstance(evidence, list) else [evidence])
                    if new_state in ("SUCCESS", "CANCELLED", "ARCHIVED"):
                        # نقل للتاريخ
                        self._archive_task(task)
                        queue["tasks"] = [t for t in queue["tasks"] if t["id"] != task_id]
                    _save_queue(queue)
                    return True
            return False

    def _archive_task(self, task: dict):
        """ينقل المهمة المكتملة للتاريخ الدائم."""
        history = _load_history()
        history["tasks"].append(task)
        # لا نحذف التاريخ - ينمو إلى الأبد
        _save_history(history)

    def fail_and_retry(self, task_id: str, error: str) -> dict:
        """يسجل فشل ويقرر إعادة المحاولة أو الإيقاف."""
        with _lock:
            queue = _load_queue()
            for task in queue["tasks"]:
                if task["id"] == task_id:
                    task["attempts"] = task.get("attempts", 0) + 1
                    task["error"] = error
                    task["updated_at"] = datetime.datetime.now().isoformat()
                    if task["attempts"] >= task.get("max_attempts", 3):
                        task["state"] = "FAILED"
                        self._archive_task(task)
                        queue["tasks"] = [t for t in queue["tasks"] if t["id"] != task_id]
                        _save_queue(queue)
                        return {"action": "failed", "attempts": task["attempts"]}
                    else:
                        task["state"] = "CREATED"  # إعادة للطابور
                        _save_queue(queue)
                        return {"action": "retry", "attempts": task["attempts"]}
            return {"action": "not_found"}

    def get_task(self, task_id: str) -> dict:
        """يرجع مهمة بالـ ID."""
        queue = _load_queue()
        for task in queue["tasks"]:
            if task["id"] == task_id:
                return task
        # ابحث في التاريخ
        history = _load_history()
        for task in history["tasks"]:
            if task["id"] == task_id:
                return task
        return None

    def list_tasks(self, state: str = None) -> list:
        """يرجع قائمة المهام."""
        queue = _load_queue()
        tasks = queue["tasks"]
        if state:
            tasks = [t for t in tasks if t["state"] == state]
        return sorted(tasks, key=lambda t: (t["priority"], t["created_at"]))

    def stats(self) -> dict:
        """إحصائيات الطابور."""
        queue = _load_queue()
        history = _load_history()
        by_state = {}
        for t in queue["tasks"]:
            s = t["state"]
            by_state[s] = by_state.get(s, 0) + 1
        return {
            "active": len(queue["tasks"]),
            "history": len(history["tasks"]),
            "by_state": by_state,
        }


# Singleton
_queue = DurableTaskQueue()


def enqueue(name, payload=None, priority=5, idempotency_key=None,
            requires_approval=False, tags=None):
    return _queue.enqueue(name, payload, priority, idempotency_key, requires_approval, tags)


def next_task(state="CREATED"):
    return _queue.next_task(state)


def transition(task_id, new_state, result=None, error=None, checkpoint=None, evidence=None):
    return _queue.transition(task_id, new_state, result, error, checkpoint, evidence)


def fail_and_retry(task_id, error):
    return _queue.fail_and_retry(task_id, error)


def stats():
    return _queue.stats()


if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if action == "stats":
        import json
        print(json.dumps(stats(), ensure_ascii=False, indent=2))
    elif action == "list":
        import json
        print(json.dumps(_queue.list_tasks(), ensure_ascii=False, indent=2))
