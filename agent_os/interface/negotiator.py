"""
negotiator.py - المفاوض الذكي
==============================
بدل ما يقول "ما أقدر" أو يحاول ويفشل — يتفاوض:
"أقدر أسوي 80% بهالطريقة، الباقي يحتاج كذا — موافق؟"
يقسّم المهمة الصعبة لأجزاء ممكنة وأجزاء تحتاج تدخل/موارد.
"""
import os, sys
def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C


def assess_feasibility(task, capabilities=None):
    """يقيّم جدوى مهمة: ما يقدر يسويه مقابل ما يحتاج مساعدة."""
    # قدرات معروفة
    can_do = {"code", "research", "file_ops", "testing", "analysis",
              "automation", "security_scan", "planning", "learning"}
    needs_human = {"payment", "account_creation", "physical_action",
                   "captcha", "legal_agreement", "2fa_setup", "hardware"}
    needs_tools = {"browser_real", "deployment", "database_admin", "email_send"}

    task_lower = task.lower()
    feasible_parts = []
    blocked_parts = []
    partial_parts = []

    for cap in can_do:
        if cap.replace("_", " ") in task_lower or cap in task_lower:
            feasible_parts.append(cap)

    for need in needs_human:
        if need.replace("_", " ") in task_lower or need in task_lower:
            blocked_parts.append({"part": need, "blocker": "human_action"})

    for tool in needs_tools:
        if tool.replace("_", " ") in task_lower or tool in task_lower:
            partial_parts.append({"part": tool, "blocker": "missing_tool"})

    # لو ما تعرّف على أجزاء محددة → المهمة عامة
    if not feasible_parts and not blocked_parts and not partial_parts:
        feasible_parts = ["general_execution"]

    total = len(feasible_parts) + len(blocked_parts) + len(partial_parts)
    feasibility = round(len(feasible_parts) / max(total, 1), 2)

    return {
        "feasibility": feasibility,
        "can_do": feasible_parts,
        "needs_human": blocked_parts,
        "needs_tools": partial_parts,
    }


def negotiate(task):
    """يُرجع عرض تفاوض: ما يقدر يسويه الآن + ما يحتاجه."""
    assessment = assess_feasibility(task)

    if assessment["feasibility"] >= 0.9:
        return {
            "response": "أقدر أسوي هالمهمة كاملة — أبدأ؟",
            "type": "full_capability",
            "assessment": assessment,
        }

    if assessment["feasibility"] >= 0.5:
        human_parts = [b["part"] for b in assessment["needs_human"]]
        tool_parts = [b["part"] for b in assessment["needs_tools"]]
        needs = human_parts + tool_parts
        return {
            "response": f"أقدر أسوي {int(assessment['feasibility']*100)}% من المهمة. "
                        f"الأجزاء اللي أحتاج مساعدتك فيها: {', '.join(needs)}. "
                        f"أبدأ باللي أقدر عليه؟",
            "type": "partial_capability",
            "assessment": assessment,
        }

    return {
        "response": f"هالمهمة تحتاج أشياء ما عندي حالياً: "
                    f"{', '.join(b['part'] for b in assessment['needs_human'] + assessment['needs_tools'])}. "
                    f"أقدر أجهّز الأجزاء التقنية وأترك لك الباقي.",
        "type": "mostly_blocked",
        "assessment": assessment,
    }
