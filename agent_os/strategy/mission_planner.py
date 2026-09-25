"""
mission_planner.py - مخطط المهام الاستراتيجي (Mission Planner)
===============================================================
إذا لم توجد أوامر:
  What is the highest-value thing I can do now?

يختار بناءً على:
  Owner Goals, Expected Value, Learning Value,
  Revenue Potential, Urgency, Dependencies, Risk, Time
"""

import datetime
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

MISSION_DIR = os.path.join(BASE_DIR, "data", "missions")
os.makedirs(MISSION_DIR, exist_ok=True)
MISSIONS_FILE = os.path.join(MISSION_DIR, "missions.json")
OWNER_GOALS_FILE = os.path.join(MISSION_DIR, "owner_goals.json")


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


# مهام افتراضية عندما لا توجد أوامر (Boredom Mode)
DEFAULT_MISSIONS = [
    {
        "id": "learn_new_skill",
        "title": "تعلم مهارة جديدة ذات قيمة عالية",
        "type": "learn",
        "value": 0.7,
        "urgency": 0.3,
        "risk": 0.1,
        "time_hours": 1.0,
    },
    {
        "id": "discover_opportunities",
        "title": "اكتشاف فرص جديدة",
        "type": "research",
        "value": 0.8,
        "urgency": 0.4,
        "risk": 0.1,
        "time_hours": 0.5,
    },
    {
        "id": "improve_system",
        "title": "تحسين أداء النظام",
        "type": "improve",
        "value": 0.6,
        "urgency": 0.2,
        "risk": 0.2,
        "time_hours": 1.5,
    },
    {
        "id": "discover_tools",
        "title": "اكتشاف أدوات وAPIs جديدة",
        "type": "discover",
        "value": 0.65,
        "urgency": 0.2,
        "risk": 0.1,
        "time_hours": 0.5,
    },
    {
        "id": "benchmark_self",
        "title": "قياس الأداء الذاتي",
        "type": "benchmark",
        "value": 0.5,
        "urgency": 0.1,
        "risk": 0.05,
        "time_hours": 0.5,
    },
]


class MissionPlanner:
    """يختار أفضل مهمة تلقائياً بناءً على القيمة المتوقعة."""

    def score_mission(self, mission: dict) -> float:
        """
        يحسب درجة الأولوية:
        Score = (value * urgency_boost) / (time * (1 + risk))
        """
        value = mission.get("value", 0.5)
        urgency = mission.get("urgency", 0.3)
        risk = mission.get("risk", 0.2)
        time_h = max(mission.get("time_hours", 1.0), 0.1)
        revenue = mission.get("revenue_potential", 0.0)

        urgency_boost = 1.0 + urgency
        score = (value + revenue * 0.5) * urgency_boost / (time_h * (1 + risk))
        return round(score, 4)

    def get_best_mission(self, available_missions: list = None) -> dict:
        """يرجع أفضل مهمة متاحة."""
        missions = available_missions or self._load_pending_missions()

        if not missions:
            missions = DEFAULT_MISSIONS

        # إضافة درجة لكل مهمة
        scored = []
        for m in missions:
            score = self.score_mission(m)
            scored.append({**m, "score": score})

        # الأعلى درجة
        best = max(scored, key=lambda x: x["score"])
        return best

    def _load_pending_missions(self) -> list:
        """يحمل المهام المعلقة."""
        data = _load(MISSIONS_FILE, {"missions": []})
        return [
            m for m in data["missions"]
            if m.get("status", "pending") == "pending"
        ]

    def add_mission(self, title: str, mission_type: str = "general",
                    value: float = 0.5, urgency: float = 0.3,
                    risk: float = 0.2, time_hours: float = 1.0,
                    revenue_potential: float = 0.0) -> dict:
        """يضيف مهمة جديدة."""
        data = _load(MISSIONS_FILE, {"missions": []})
        mission = {
            "id": f"m_{len(data['missions'])+1:04d}",
            "title": title,
            "type": mission_type,
            "value": value,
            "urgency": urgency,
            "risk": risk,
            "time_hours": time_hours,
            "revenue_potential": revenue_potential,
            "status": "pending",
            "created_at": datetime.datetime.now().isoformat(),
        }
        data["missions"].append(mission)
        _save(MISSIONS_FILE, data)
        return mission

    def complete_mission(self, mission_id: str, result: str = ""):
        """يسجل اكتمال مهمة."""
        data = _load(MISSIONS_FILE, {"missions": []})
        for m in data["missions"]:
            if m["id"] == mission_id:
                m["status"] = "completed"
                m["result"] = result
                m["completed_at"] = datetime.datetime.now().isoformat()
                break
        _save(MISSIONS_FILE, data)

    def set_owner_goals(self, goals: list):
        """يحفظ أهداف المالك."""
        data = {
            "goals": goals,
            "updated_at": datetime.datetime.now().isoformat(),
        }
        _save(OWNER_GOALS_FILE, data)

    def get_owner_goals(self) -> list:
        """يرجع أهداف المالك."""
        data = _load(OWNER_GOALS_FILE, {"goals": []})
        return data.get("goals", [])

    def night_mode_plan(self) -> list:
        """
        يخطط لليلة كاملة:
        DISCOVER -> RESEARCH -> PLAN -> BUILD -> TEST -> VERIFY -> IMPROVE -> REPORT
        """
        owner_goals = self.get_owner_goals()
        plan = []

        # مهام ثابتة كل ليلة
        plan.append({
            "step": 1, "type": "discover",
            "title": "اكتشاف فرص وأدوات جديدة",
            "duration_minutes": 15,
        })
        plan.append({
            "step": 2, "type": "research",
            "title": "بحث في أهداف المالك",
            "context": owner_goals[:3],
            "duration_minutes": 20,
        })
        plan.append({
            "step": 3, "type": "improve",
            "title": "تحسين النظام الذاتي",
            "duration_minutes": 30,
        })
        plan.append({
            "step": 4, "type": "benchmark",
            "title": "قياس الأداء",
            "duration_minutes": 10,
        })
        plan.append({
            "step": 5, "type": "report",
            "title": "إعداد تقرير الصباح",
            "duration_minutes": 10,
        })

        return plan


# Singleton
_planner = MissionPlanner()


def get_best_mission(available=None):
    return _planner.get_best_mission(available)


def add_mission(title, mission_type="general", value=0.5, urgency=0.3,
                risk=0.2, time_hours=1.0, revenue_potential=0.0):
    return _planner.add_mission(title, mission_type, value, urgency, risk, time_hours, revenue_potential)


def night_mode_plan():
    return _planner.night_mode_plan()


def set_owner_goals(goals):
    _planner.set_owner_goals(goals)


def get_owner_goals():
    return _planner.get_owner_goals()


if __name__ == "__main__":
    import json
    best = get_best_mission()
    print("أفضل مهمة الآن:")
    print(json.dumps(best, ensure_ascii=False, indent=2))
    print("\nخطة الليل:")
    for step in night_mode_plan():
        print(f"  {step['step']}. {step['title']} ({step['duration_minutes']} دقيقة)")
