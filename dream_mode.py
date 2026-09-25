"""
dream_mode.py - وضع الحلم (Dream Mode) v1.0
============================================
وأنت نايم، ما ينتظر مهمة.
يأخذ أهدافك الحالية ويعمل:
  Explore → Experiment → Discover → Prepare

ثم يترك لك Overnight Report:
  - اكتشفت X مشاكل
  - بنيت Y حلول
  - الحل Z أسرع بـ 41%
  - جهزت PR يحتاج موافقتك

التشغيل:
  python dream_mode.py run
  python dream_mode.py report
  python dream_mode.py status
"""

import datetime
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DREAM_DIR = os.path.join(BASE_DIR, "data", "dream")
os.makedirs(DREAM_DIR, exist_ok=True)

DREAM_LOG = os.path.join(DREAM_DIR, "dream_log.json")
OVERNIGHT_REPORT = os.path.join(BASE_DIR, "output", "overnight_report.md")
USER_FLAG = os.path.join(BASE_DIR, "output", "user_active.flag")


def _load_log():
    if os.path.exists(DREAM_LOG):
        try:
            with open(DREAM_LOG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"sessions": [], "discoveries": [], "experiments": [], "pending_approvals": []}


def _save_log(data):
    tmp = DREAM_LOG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DREAM_LOG)


def user_present():
    return os.path.exists(USER_FLAG)


def _explore(brain_session, goals):
    """يستكشف المشاكل والفرص في المشروع."""
    discoveries = []
    try:
        import webtools
        for goal in goals[:2]:
            result = webtools.search(f"best practices {goal} 2025", save=False, num=3)
            for r in result.get("results", [])[:2]:
                if isinstance(r, dict) and r.get("title"):
                    discoveries.append({
                        "type": "research",
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", "")[:200],
                        "goal": goal,
                    })
    except Exception as e:
        discoveries.append({"type": "error", "msg": str(e)[:100]})
    return discoveries


def _experiment(brain_session, discoveries):
    """يجرب حلول بناءً على الاكتشافات."""
    experiments = []
    try:
        for d in discoveries[:2]:
            if d.get("type") == "research":
                prompt = (
                    f"بناءً على هذه المعلومة: '{d.get('title')}' - "
                    f"اقترح تحسيناً محدداً للمشروع مع قياس الأداء المتوقع."
                )
                response, engine = brain_session.ask(prompt)
                experiments.append({
                    "hypothesis": d.get("title", ""),
                    "result": response[:500],
                    "engine": engine,
                    "status": "proposed",
                })
    except Exception as e:
        experiments.append({"hypothesis": "خطأ", "result": str(e)[:100], "status": "failed"})
    return experiments


def _prepare_report(session_data):
    """يجهز Overnight Report."""
    discoveries = session_data.get("discoveries", [])
    experiments = session_data.get("experiments", [])
    pending = session_data.get("pending_approvals", [])
    started = session_data.get("started_at", "")
    ended = session_data.get("ended_at", "")

    lines = [
        "╔══════════════════════════════════════╗",
        "║       🌙 OVERNIGHT DREAM REPORT       ║",
        "╚══════════════════════════════════════╝",
        "",
        f"**بدأ:** {started[:19]}",
        f"**انتهى:** {ended[:19]}",
        "",
        f"## 🔍 الاكتشافات ({len(discoveries)})",
    ]
    for d in discoveries[:5]:
        if d.get("type") == "research":
            lines.append(f"- **{d.get('title', '')[:60]}**")
            if d.get("snippet"):
                lines.append(f"  > {d['snippet'][:150]}")
    lines.append("")
    lines.append(f"## 🧪 التجارب ({len(experiments)})")
    for i, e in enumerate(experiments[:3], 1):
        lines.append(f"### تجربة {i}: {e.get('hypothesis', '')[:60]}")
        lines.append(e.get("result", "")[:300])
        lines.append("")
    if pending:
        lines.append(f"## ⚠️ يحتاج موافقتك ({len(pending)})")
        for p in pending:
            lines.append(f"- {p}")
        lines.append("")
    lines.append("---")
    lines.append(f"*تقرير تلقائي من Dream Mode - {datetime.datetime.now():%Y-%m-%d %H:%M}*")

    report = "\n".join(lines)
    os.makedirs(os.path.dirname(OVERNIGHT_REPORT), exist_ok=True)
    with open(OVERNIGHT_REPORT, "w", encoding="utf-8") as f:
        f.write(report)
    return report


def run_dream(goals=None, max_cycles=3):
    """تشغيل Dream Mode."""
    if user_present():
        print("[Dream Mode] المستخدم موجود - لن أبدأ Dream Mode")
        return None

    print("[Dream Mode] 🌙 بدأ وضع الحلم...")
    import brain
    brain_session = brain.Brain(
        "أنت في وضع الحلم. استكشف، جرب، واكتشف تحسينات للمشروع. كن إبداعياً ومحدداً."
    )

    if not goals:
        goals = ["تحسين أداء المشروع", "اكتشاف فرص جديدة", "تحسين جودة الكود"]

    log = _load_log()
    session = {
        "started_at": datetime.datetime.now().isoformat(),
        "goals": goals,
        "discoveries": [],
        "experiments": [],
        "pending_approvals": [],
    }

    for cycle in range(max_cycles):
        if user_present():
            print(f"[Dream Mode] المستخدم عاد - إيقاف بعد {cycle} دورات")
            break

        print(f"[Dream Mode] دورة {cycle+1}/{max_cycles}")

        # Explore
        discoveries = _explore(brain_session, goals)
        session["discoveries"].extend(discoveries)
        print(f"  🔍 اكتشفت {len(discoveries)} معلومة")

        # Experiment
        experiments = _experiment(brain_session, discoveries)
        session["experiments"].extend(experiments)
        print(f"  🧪 جربت {len(experiments)} فكرة")

        time.sleep(2)  # استراحة بين الدورات

    session["ended_at"] = datetime.datetime.now().isoformat()
    log["sessions"].append(session)
    log["sessions"] = log["sessions"][-10:]  # احتفظ بآخر 10 جلسات
    _save_log(log)

    report = _prepare_report(session)
    print(f"[Dream Mode] ✅ انتهى - التقرير في: {OVERNIGHT_REPORT}")
    return report


def get_last_report():
    """يرجع آخر Overnight Report."""
    if os.path.exists(OVERNIGHT_REPORT):
        with open(OVERNIGHT_REPORT, "r", encoding="utf-8") as f:
            return f.read()
    return "لا يوجد تقرير بعد. شغّل: python dream_mode.py run"


def status():
    """حالة Dream Mode."""
    log = _load_log()
    sessions = log.get("sessions", [])
    return {
        "total_sessions": len(sessions),
        "last_session": sessions[-1].get("started_at", "")[:19] if sessions else None,
        "total_discoveries": sum(len(s.get("discoveries", [])) for s in sessions),
        "total_experiments": sum(len(s.get("experiments", [])) for s in sessions),
        "report_exists": os.path.exists(OVERNIGHT_REPORT),
    }


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "run":
        goals = sys.argv[2:] if len(sys.argv) > 2 else None
        run_dream(goals=goals)
    elif action == "report":
        print(get_last_report())
    elif action == "status":
        import json
        print(json.dumps(status(), ensure_ascii=False, indent=2))
    else:
        print("الاستخدام: python dream_mode.py run [goals...] | report | status")
