"""
goal_manager.py - النظام 1: مدير الأهداف الذاتي (v3.0)
=======================================================
بدل انتظار مهمة، يمثل الوكيل أهدافاً طويلة ويعالجها تلقائياً:

goal -> strategy -> projects -> tasks -> subtasks -> execution -> verification -> outcome

الاستخدام:
  python agent_os/goal_manager.py add "زيادة دخلي الشهري"
  python agent_os/goal_manager.py list
  python agent_os/goal_manager.py breakdown <id>
  python agent_os/goal_manager.py verify <id>
"""

import os
import sys
import json
import gzip
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C


GOALS_FILE = os.path.join(C.AGENT_OS_DIR, "goals.json")
GOALS_ARCHIVE_DIR = os.path.join(C.AGENT_OS_DIR, "archives")


def _load():
    """_load: لمحة وظيفية مُضافة تلقائياً."""
    return C.load_json(GOALS_FILE, {"goals": [], "next_id": 1})


def _save(state):
    C.atomic_write(GOALS_FILE, state)


def add_goal(title, objective="", priority="medium", auto=True, category="general"):
    """إضافة هدف بسلسلة حياة كاملة."""
    state = _load()
    gid = state["next_id"]
    state["next_id"] += 1
    goal = {
        "id": gid,
        "title": title,
        "objective": objective,
        "priority": priority,
        "category": category,
        "auto": auto,
        "status": "active",            # active / working / paused / achieved / dropped
        "strategy": "",
        "projects": [],
        "tasks": [],
        "verification": {},
        "outcome": "",
        "created": C.now_iso(),
        "updated": C.now_iso(),
    }
    state["goals"].append(goal)
    _save(state)
    C.log(f"🎯 هدف جديد #{gid}: {title}")
    # التحليل التلقائي
    if auto:
        analyze_goal(gid)
    return goal


def analyze_goal(gid):
    """العقل يضع استراتيجية للهدف (وبديل حتمي عند غيابه)."""
    state = _load()
    goal = next((g for g in state["goals"] if g["id"] == gid), None)
    if not goal:
        return None
    raw, engine = C.call_brain(
        "أنت مخطط استراتيجي خبير يحول الأهداف إلى خطط قابلة للتنفيذ.",
        f"الهدف: {goal['title']}\nالوصف: {goal['objective']}\n"
        "اكتب الاستراتيجية ثم قائمة المشاريع بصيغة:\n"
        "STRATEGY: [الخطة العامة بجملة]\nPROJECT: [مشروع 1]\nPROJECT: [مشروع 2]",
    )
    if raw:
        goal["strategy"] = raw[:2000]
        for line in raw.splitlines():
            if line.strip().startswith("PROJECT:"):
                name = line.replace("PROJECT:", "").strip()
                if name:
                    goal["projects"].append({"name": name, "status": "planned"})
    else:
        goal["strategy"] = _fallback_strategy(goal)
    goal["updated"] = C.now_iso()
    _save(state)
    return goal


def _fallback_strategy(goal):
    """خطة حتمية بلا عقل عند غياب الدماغ."""
    return f"استراتيجية: قسم هدف «{goal['title']}» إلى مشاريع صغيرة، نفّذ كل مشروع عبر نواة Agent OS، وتحقق ذاتياً من كل خطوة قبل الانتقال."


def breakdown(gid):
    """تقسيم الهدف إلى مهام جاهزة للتنفيذ (وبديل حتمي بلا عقل)."""
    state = _load()
    goal = next((g for g in state["goals"] if g["id"] == gid), None)
    if not goal:
        return None
    raw, _ = C.call_brain(
        "أنت مقسم ذكي للمهام.",
        f"اقترح قائمة مهام تنفيذية صغيرة للهدف: {goal['title']}\n"
        "كل سطر بصيغة TASK: [مهمة قصيرة قابلة للتنفيذ]",
    )
    if raw:
        goal["tasks"] = []
        for line in raw.splitlines():
            if line.strip().startswith("TASK:"):
                t = line.replace("TASK:", "").strip()
                if t:
                    goal["tasks"].append({"id": f"{goal['id']}-t{len(goal['tasks'])+1}",
                                          "task": t, "status": "pending", "attempts": 0})
        if not goal["tasks"]:
            goal["tasks"] = _fallback_tasks(goal)
    else:
        goal["tasks"] = _fallback_tasks(goal)
    goal["status"] = "working"
    goal["updated"] = C.now_iso()
    _save(state)
    return goal


def _fallback_tasks(goal):
    """قائمة مهام حتمية مقسمة من الاستراتيجية أو العنوان."""
    base = goal.get("strategy") or goal["title"]
    seeds = [goal["title"]]
    if goal.get("projects"):
        seeds = [p["name"] for p in goal["projects"]][:3]
    tasks = []
    nid = 0
    for seed in seeds:
        nid += 1
        tasks.append({"id": f"{goal['id']}-t{nid}", "task": f"جهّز {seed} ووثّقه", "status": "pending", "attempts": 0})
        nid += 1
        tasks.append({"id": f"{goal['id']}-t{nid}", "task": f"قم بإنجاز {seed} بالخطوات المعتمدة", "status": "pending", "attempts": 0})
    nid += 1
    tasks.append({"id": f"{goal['id']}-t{nid}", "task": f"تحقق ذاتياً من نسبة اكتمال {goal['title']}", "status": "pending", "attempts": 0})
    return tasks[:5]


def link_approval(task_id, approval_kind="external_action", why="", steps=None):
    """علّم مهمة كمعلّقة على موافقة بشرية: يفتح طلباً في المركز ويربطه."""
    from agent_os import approval_center
    state = _load()
    task = _find_task(state, task_id)
    if not task:
        return None
    req = approval_center.create_request(
        task["task"][:180], why, steps, kind=approval_kind, risk="medium",
        blocking_task_id=task_id, resume_hint=task["task"],
    )
    task["requires_approval"] = True
    task["approval_kind"] = approval_kind
    task["approval_request_id"] = req["id"]
    task["status"] = "waiting_approval"
    _save(state)
    return req


def _find_task(state, task_id):
    for g in state["goals"]:
        for t in g["tasks"]:
            if t.get("id") == task_id:
                return t
    return None


def next_actionable_task():
    """أهم مهمة الآن جاهزة للتنفيذ — يتخطى ما ينتظر موافقة معلّقة.
    يُفعّل blocking_task_id: لا تُنفَّذ مهمة B حتى تُنجز A (إن رُبطت).
    وتُفرز الأهداف بالأولوية أولاً (رقمية 1-5 أو سلسلة)، ثم الأقدم تحديثاً (عيب 9 + 24)."""
    from agent_os import approval_center
    state = _load()
    order = {"high": 0, "medium": 1, "low": 2}

    def _order_key(g):
        p = g.get("priority")
        if isinstance(p, int):
            base = max(0, p - 1)          # 1 = الأهم
        else:
            base = order.get(str(p), 5)
        return (base, g.get("updated", ""))

    for g in sorted(state["goals"], key=_order_key):
        if g["status"] not in ("active", "working"):
            continue
        for t in g["tasks"]:
            if t["status"] not in ("pending", "waiting_approval"):
                continue
            blocker = t.get("blocking_task_id")
            if blocker:
                bt = _find_task(state, blocker)
                if bt and bt.get("status") != "done":
                    continue  # المعتمِد عليها لم تُنجز بعد — تخطَّ
            if t["status"] == "waiting_approval":
                a = t.get("approval_request_id")
                res = approval_center.check_resolution(a) if a else None
                if res is None:
                    continue  # لا يزال ينتظرك — تخطَّ
                if res["status"] in ("cancelled", "done"):
                    t["status"] = "cancelled" if res["status"] == "cancelled" else "pending"
                _save(state)
                if t["status"] != "pending":
                    continue
            return g, t
    return (None, None)


def mark_done(task_id, result=""):
    state = _load()
    t = _find_task(state, task_id)
    if t:
        t["status"] = "done"
        t["result"] = result
        _save(state)
    return t


def mark_failed(task_id, error="", max_attempts=3):
    """اعتبار المهمة فاشلة مع عداد محاولات — عند الحد يصبح blocked."""
    state = _load()
    t = _find_task(state, task_id)
    if t:
        t["attempts"] = t.get("attempts", 0) + 1
        t["result"] = error
        t["status"] = "blocked" if t["attempts"] >= max_attempts else "pending"
        _save(state)
    return t


def get_active_goals():
    """الأهداف الجارية (active/working) — تُستخدم لتفادي الخمول (عيب 10/22)."""
    return [g for g in _load()["goals"] if g.get("status") in ("active", "working")]


def get_blocked_tasks():
    """المهام المحظورة تنتظر تدخلك — تظهر في الملخص الصباحي (عيب 7)."""
    out = []
    for g in _load()["goals"]:
        for t in g.get("tasks", []):
            if t.get("status") == "blocked":
                out.append({"goal": g.get("title", ""), "title": t.get("task", ""),
                            "blocker": (t.get("result") or "")[:120], "task_id": t.get("id")})
    return out


def run_next_task(gid):
    """تنفيذ أول مهمة معلقة عبر الوكيل، ثم التحقق."""
    state = _load()
    goal = next((g for g in state["goals"] if g["id"] == gid), None)
    if not goal:
        return {"status": "no_goal"}
    for task in goal["tasks"]:
        if task["status"] == "pending":
            C.log(f"⚙️ تنفيذ مهمة: {task['task']}")
            # تنفيذ عبر محرك المهام الحالي
            try:
                import selfrunner
                result = selfrunner.run_task(task["task"])
                task["result"] = str(result)[:500]
            except Exception as e:
                task["result"] = f"فشل: {e}"
            task["status"] = "done"
            goal["updated"] = C.now_iso()
            _save(state)
            verify_goal(gid)
            return {"status": "executed", "task": task}
    return {"status": "no_pending"}


def verify_goal(gid):
    """التحقق الذاتي من الاكتمال."""
    state = _load()
    goal = next((g for g in state["goals"] if g["id"] == gid), None)
    if not goal:
        return None
    done = sum(1 for t in goal["tasks"] if t["status"] == "done")
    total = len(goal["tasks"])
    goal["verification"] = {
        "checked_at": C.now_iso(),
        "tasks_done": done,
        "tasks_total": total,
        "complete_ratio": round(done / total, 2) if total else 1.0,
    }
    if total and done == total:
        goal["status"] = "achieved"
        goal["outcome"] = "كل المهام مكتملة بعد التحقق."
    goal["updated"] = C.now_iso()
    _save(state)
    return goal["verification"]


def list_goals():
    return _load()["goals"]


def priority_next():
    """الأهم الآن: الأولوية (رقمي 1-5 أو سلسلة) ثم أقدم وقت تحديث — عيب 24."""
    goals = [g for g in _load()["goals"] if g["status"] in ("active", "working")]
    order = {"high": 0, "medium": 1, "low": 2}

    def _order_key(g):
        p = g.get("priority")
        return (max(0, p - 1) if isinstance(p, int) else order.get(str(p), 9), g["updated"])

    goals.sort(key=_order_key)
    return goals[0] if goals else None


def advance_all(max_runs=5):
    """حلقة تقدّم ذاتية: نفّذ المهام المعلقة في أعلى الأهداف حتى تتوقف."""
    results = []
    for _ in range(max_runs):
        g = priority_next()
        if not g:
            break
        out = run_next_task(g["id"])
        results.append({"goal": g["title"], **out})
        if out["status"] != "executed":
            break
    return results


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("الاستعمال: add|list|breakdown|verify <id>|run <id>|advance|next|archive")
    elif args[0] == "add":
        add_goal(" ".join(args[1:]))
    elif args[0] == "list":
        for g in list_goals():
            print(f"#{g['id']} [{g['status']}] {g['title']} — {len(g['tasks'])} مهام")
    elif args[0] == "breakdown" and len(args) > 1:
        breakdown(int(args[1]))
        print("مقسم ✓")
    elif args[0] == "run" and len(args) > 1:
        run_next_task(int(args[1]))
    elif args[0] == "verify" and len(args) > 1:
        verify_goal(int(args[1]))
    elif args[0] == "advance":
        print(advance_all())
    elif args[0] == "next":
        g = priority_next()
        print(f"الهدف التالي: {g['title'] if g else 'لا أهداف'}")
    elif args[0] == "archive":
        print(archive_achieved_goals())


# ===== أرشفة برد (cold) بلا حذف: الأهداف المنجزة/المتوقفة تُصان كاملة =====

def _goal_arch_path(month):
    os.makedirs(GOALS_ARCHIVE_DIR, exist_ok=True)
    return os.path.join(GOALS_ARCHIVE_DIR, f"goals_{month}.json.gz")


def read_goal_archive(month):
    """قراءة أرشيف أهداف شهر: يرجع قائمة أهدافه (أو [] إن لم يوجد)."""
    path = _goal_arch_path(month)
    if not os.path.exists(path):
        return []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def archive_achieved_goals(cutoff_days=30):
    """نقل الأهداف achieved/dropped وأقدم من cutoff_days إلى أرشيف الشهر.
    لا حذف إطلاقاً — كل تاريخ الأهداف يُحفظ ويمكن استرجاعه بالشهر."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=cutoff_days)).isoformat()
    state = _load()
    moving, keep = [], []
    for g in state["goals"]:
        created = (g.get("created") or "")[:10]
        if g.get("status") in ("achieved", "dropped") and created and created < cutoff:
            moving.append(g)
        else:
            keep.append(g)
    if not moving:
        return {"moved": 0, "months": []}
    by_month = {}
    for g in moving:
        m = (g.get("created") or "")[:7]
        by_month.setdefault(m, []).append(g)
    for m, items in sorted(by_month.items()):
        combined = read_goal_archive(m) + items
        with gzip.open(_goal_arch_path(m), "wt", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False)
    state["goals"] = keep
    _save(state)
    months = sorted(by_month)
    C.log(f"📦 أُرشفت {len(moving)} أهداف ({', '.join(months)}) — بلا حذف")
    return {"moved": len(moving), "months": months}