"""
checkpoint_system.py - نظام الـ Checkpoint والـ Resume (v1.0)
=============================================================
يحفظ حالة كل مهمة خطوة بخطوة.
لو طفى الجهاز أو انقطع الكود، يرجع ويكمل من نفس الخطوة.

الاستخدام:
  from checkpoint_system import CheckpointManager
  cp = CheckpointManager(task_id="task_123")
  cp.save(step=3, data={...})
  state = cp.load()  # يرجع آخر checkpoint
  cp.complete()      # يحذف الـ checkpoint بعد الانتهاء
"""

import datetime
import hashlib
import json
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKPOINT_DIR = os.path.join(BASE_DIR, "data", "checkpoints")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

# حالات المهمة
STATES = [
    "CREATED", "PLANNED", "APPROVED", "RUNNING",
    "VERIFYING", "SUCCESS", "FAILED", "RECOVERING",
    "PAUSED", "CANCELLED", "ARCHIVED"
]


class CheckpointManager:
    """مدير الـ Checkpoint لمهمة واحدة."""

    def __init__(self, task_id: str):
        safe = hashlib.md5(task_id.encode()).hexdigest()[:12]
        self.task_id = task_id
        self.path = os.path.join(CHECKPOINT_DIR, f"cp_{safe}.json")

    def save(self, step: int, data: dict, state: str = "RUNNING", total_steps: int = 0):
        """حفظ checkpoint للخطوة الحالية."""
        cp = {
            "task_id": self.task_id,
            "step": step,
            "total_steps": total_steps,
            "state": state if state in STATES else "RUNNING",
            "data": data,
            "saved_at": datetime.datetime.now().isoformat(),
            "version": 1,
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cp, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
        return cp

    def load(self):
        """تحميل آخر checkpoint. يرجع None لو ما في checkpoint."""
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def exists(self):
        """هل في checkpoint محفوظ؟"""
        return os.path.exists(self.path)

    def complete(self):
        """احذف الـ checkpoint بعد اكتمال المهمة."""
        if os.path.exists(self.path):
            os.remove(self.path)

    def fail(self, reason: str = ""):
        """سجّل فشل المهمة."""
        cp = self.load() or {}
        cp["state"] = "FAILED"
        cp["failed_at"] = datetime.datetime.now().isoformat()
        cp["fail_reason"] = reason
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cp, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def pause(self):
        """إيقاف مؤقت."""
        cp = self.load() or {}
        cp["state"] = "PAUSED"
        cp["paused_at"] = datetime.datetime.now().isoformat()
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cp, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


def list_checkpoints():
    """قائمة كل الـ checkpoints الموجودة."""
    result = []
    for f in os.listdir(CHECKPOINT_DIR):
        if f.startswith("cp_") and f.endswith(".json"):
            path = os.path.join(CHECKPOINT_DIR, f)
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                result.append({
                    "file": f,
                    "task_id": data.get("task_id", ""),
                    "step": data.get("step", 0),
                    "state": data.get("state", ""),
                    "saved_at": data.get("saved_at", ""),
                })
            except Exception:
                pass
    result.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
    return result


def resume_or_start(task_id: str, task_fn, *args, **kwargs):
    """
    يحاول يكمل مهمة من آخر checkpoint.
    لو ما في checkpoint يبدأ من الأول.
    task_fn يجب أن يقبل: task_fn(checkpoint=None, *args, **kwargs)
    """
    cp = CheckpointManager(task_id)
    existing = cp.load()
    if existing and existing.get("state") not in ("SUCCESS", "CANCELLED", "ARCHIVED"):
        print(f"[Checkpoint] استئناف المهمة من الخطوة {existing.get('step', 0)}")
        return task_fn(checkpoint=existing, *args, **kwargs)
    else:
        print(f"[Checkpoint] بدء مهمة جديدة: {task_id}")
        return task_fn(checkpoint=None, *args, **kwargs)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        cps = list_checkpoints()
        if cps:
            for c in cps:
                print(f"[{c['state']}] {c['task_id'][:40]} - خطوة {c['step']} - {c['saved_at'][:19]}")
        else:
            print("لا توجد checkpoints محفوظة.")
    else:
        print("الاستخدام: python checkpoint_system.py list")
