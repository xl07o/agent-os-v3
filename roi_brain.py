"""
roi_brain.py - عقل الأولويات والقيمة (ROI Brain) v1.0
======================================================
كل مهمة تحصل على:
  Expected Value, Urgency, Probability of Success,
  Cost, Risk, Time, Opportunity Cost

يقرر وش أعلى شيء يستحق الوقت الآن.
مو مجرد FIFO queue.

الاستخدام:
  from roi_brain import ROIBrain
  roi = ROIBrain()
  roi.add_task("بناء موقع", value=500, time_hours=2, probability=0.7)
  best = roi.get_best_task()
"""

import datetime
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROI_DIR = os.path.join(BASE_DIR, "data", "roi")
os.makedirs(ROI_DIR, exist_ok=True)
ROI_DB = os.path.join(ROI_DIR, "tasks.json")


def _load():
    if os.path.exists(ROI_DB):
        try:
            with open(ROI_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"tasks": []}


def _save(data):
    tmp = ROI_DB + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ROI_DB)


class ROIBrain:
    """يرتب المهام حسب القيمة الحقيقية."""

    def add_task(self, name: str, value: float = 0, time_hours: float = 1,
                 probability: float = 0.5, urgency: float = 0.5,
                 risk: float = 0.3, cost: float = 0,
                 tags: list = None) -> dict:
        """
        يضيف مهمة مع حساب ROI Score.

        ROI Score = (value * probability * urgency) / (time_hours * (1 + risk) * (1 + cost))
        """
        db = _load()

        # حساب ROI Score
        denominator = max(time_hours, 0.1) * (1 + risk) * (1 + cost)
        roi_score = (value * probability * (0.5 + urgency * 0.5)) / denominator

        task = {
            "id": f"t_{len(db['tasks'])+1:04d}",
            "name": name,
            "value": value,
            "time_hours": time_hours,
            "probability": probability,
            "urgency": urgency,
            "risk": risk,
            "cost": cost,
            "roi_score": round(roi_score, 4),
            "tags": tags or [],
            "status": "pending",
            "created_at": datetime.datetime.now().isoformat(),
        }
        db["tasks"].append(task)
        _save(db)
        return task

    def get_best_task(self, exclude_ids: list = None) -> dict:
        """يرجع المهمة ذات أعلى ROI Score."""
        db = _load()
        pending = [
            t for t in db["tasks"]
            if t["status"] == "pending"
            and (not exclude_ids or t["id"] not in exclude_ids)
        ]
        if not pending:
            return None
        return max(pending, key=lambda t: t["roi_score"])

    def get_ranked_tasks(self, limit: int = 10) -> list:
        """يرجع المهام مرتبة حسب ROI."""
        db = _load()
        pending = [t for t in db["tasks"] if t["status"] == "pending"]
        return sorted(pending, key=lambda t: t["roi_score"], reverse=True)[:limit]

    def complete_task(self, task_id: str, actual_value: float = None):
        """يسجل اكتمال مهمة."""
        db = _load()
        for t in db["tasks"]:
            if t["id"] == task_id:
                t["status"] = "done"
                t["completed_at"] = datetime.datetime.now().isoformat()
                if actual_value is not None:
                    t["actual_value"] = actual_value
                break
        _save(db)

    def morning_brief(self) -> str:
        """ملخص صباحي بأفضل المهام."""
        ranked = self.get_ranked_tasks(5)
        if not ranked:
            return "لا توجد مهام معلقة."

        lines = ["## 🎯 أفضل المهام حسب ROI", ""]
        for i, t in enumerate(ranked, 1):
            lines.append(
                f"{i}. **{t['name']}** | "
                f"قيمة: ${t['value']} | "
                f"وقت: {t['time_hours']}h | "
                f"احتمال: {int(t['probability']*100)}% | "
                f"ROI: {t['roi_score']:.2f}"
            )
        return "\n".join(lines)

    def report(self) -> dict:
        """تقرير كامل."""
        db = _load()
        tasks = db["tasks"]
        done = [t for t in tasks if t["status"] == "done"]
        pending = [t for t in tasks if t["status"] == "pending"]
        total_value = sum(t.get("actual_value", t["value"]) for t in done)
        return {
            "total_tasks": len(tasks),
            "pending": len(pending),
            "done": len(done),
            "total_value_generated": round(total_value, 2),
            "best_pending": self.get_best_task(),
        }


# Singleton
_roi = ROIBrain()


def add_task(name, value=0, time_hours=1, probability=0.5, urgency=0.5, risk=0.3, cost=0, tags=None):
    return _roi.add_task(name, value, time_hours, probability, urgency, risk, cost, tags)


def get_best_task():
    return _roi.get_best_task()


def get_ranked_tasks(limit=10):
    return _roi.get_ranked_tasks(limit)


def morning_brief():
    return _roi.morning_brief()


if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "report"
    if action == "brief":
        print(morning_brief())
    elif action == "report":
        import json
        print(json.dumps(_roi.report(), ensure_ascii=False, indent=2))
    elif action == "best":
        import json
        print(json.dumps(get_best_task(), ensure_ascii=False, indent=2))
    else:
        print("الاستخدام: python roi_brain.py brief | report | best")
