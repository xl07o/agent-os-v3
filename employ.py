"""
employ.py - أمر واحد يشغّل الموظف كامل الليل (ركن الدمج #1 من تقرير 42%)
=========================================================================
بعد تقرير المقيّم: «selfrunner/mastery و kernel حلقتان منفصلتان، الشات لا يستدعي
النواة — قبل أي موقع: أمر واحد يشغّل الموظف كامل الليل.»

هذا المدخل يجمع الحلقات في تشغيل واحد:
  فحص صحّة → نواة مستمرة بعقل هجين (use_brain=True بكل دورة) →
  تحسين ذاتي → خط إنتاج ليلي → تقرير صباح chief_staff.brief → يفرد تقريراً بصوت
  كل دورة؛ ثم يُطلق مهمة إتقان v2 اختيارية عبر --mission.

قفل pid: لا يعمل سوى مثيل واحد (يمنع تكدس الموظفين الليلة).

الاستخدام:
  python employ.py night [دقائق]      # الموظف كامل الليل (افتراضي 55 د)
  python employ.py once                # دورة واحدة بعقل
  python employ.py state               # حالة سريعة
  python employ.py --schedule 22:30    # تركيب مهمة ويندوز ليلية تجريبية/متكررة
  python employ.py --remove            # إزالة مهمة ويندوز
"""

import datetime
import json
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from agent_os import _common as C

LOCK_FILE = os.path.join(C.AGENT_OS_DIR, "employ.lock")
SCHED_NAME = "AgentOSNightEmploy"


def _already_running():
    """قفل مثيل واحد: يقرأ pid القفل ويتأكد من الحياة قبل الرفض."""
    if not os.path.exists(LOCK_FILE):
        return False
    try:
        data = C.load_json(LOCK_FILE, {})
        pid = data.get("pid")
        if not pid:
            return False
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
            text=True, encoding="utf-8", errors="replace", timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
        return f'"{pid}"' in out
    except Exception:
        return False


def _write_lock():
    C.atomic_write(LOCK_FILE, {"pid": os.getpid(), "started": C.now_iso()})


def _release_lock():
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass


def _morning_brief():
    """تقرير صباح فيتكتبه chief_staff — محفوظ في reports/ للقراءة والجوال."""
    try:
        from agent_os import chief_staff
        brief = chief_staff.brief()
        os.makedirs(os.path.join(BASE, "reports"), exist_ok=True)
        path = os.path.join(BASE, "reports",
                            f"morning_{datetime.datetime.now():%Y%m%d}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(brief if isinstance(brief, str) else json.dumps(brief, ensure_ascii=False, indent=1))
        C.log(f"🌅 تقرير الصباح: {path}")
        return path
    except Exception as e:
        C.log(f"⚠️ تقرير الصباح لم يكتمل: {str(e)[:120]}")
        return None


def run_night(minutes=55.0, mission=None):
    if _already_running():
        return {"ok": False, "reason": "موظف ليلي يعمل بالفعل (قفل pid)"}
    _write_lock()
    try:
        # النواة الموحدة بعقل هجين + تحسين ذاتي + خط إنتاج ليلي
        from agent_os import kernel
        res = kernel.run_nightly(minutes, allow_self_improve=True)
        brief = _morning_brief()
        result = {**res, "brief": brief, "brain": True}
        # وصول اختياري إلى حلقة إتقان v2 (نفس الليل، بلا نواة ثانية متوازية)
        if mission and os.path.exists(os.path.join(BASE, mission)):
            import selfrunner
            done = selfrunner.run_task(
                f"نفّذ مهمة الإتقان: {mission} — انتهت الجولة الأساسية ليلاً.")
            result["mastery_mission"] = bool(done)
        return result
    finally:
        _release_lock()


def install_schedule(hhmm):
    """تركيب مهمة ويندوز عبر schtasks — النواة الواحدة كل ليلة."""
    exe = sys.executable
    args = f'night 300'
    cmd = (["schtasks", "/Create", "/TN", SCHED_NAME, "/SC", "DAILY", "/ST", hhmm,
            "/TR", f'"{exe}" "{os.path.join(BASE, "employ.py")}" {args}', "/F"])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        C.log(f"📅 مهمة ليلية {hhmm}: {out.stdout.strip() or out.stderr.strip()}")
        return {"ok": out.returncode == 0, "output": (out.stdout or out.stderr).strip()[:200]}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120]}


INBOX_SCHED_NAME = "AgentOSInboxWorker"


def run_worker(minutes=1380.0):
    """منفّذ صندوق الوارد المستمر — يلتقط طلبات اللوحة وينفّذها."""
    from agent_os import inbox_worker
    return inbox_worker.run_loop(minutes)


def ensure_worker(restart=True):
    """حارس: إن لم يكن العامل حياً (نبضة قديمة/لا عملية) — أعِده للخدمة."""
    from agent_os import inbox_worker
    alive = inbox_worker.worker_alive(90)
    if alive:
        return {"ok": True, "worker": "alive"}
    d = C.load_json(inbox_worker.STATUS_FILE, {})
    if d.get("pid"):
        try:
            os.kill(int(d["pid"]), 0)
            pid_alive = True
        except Exception:
            pid_alive = False
    else:
        pid_alive = False
    if pid_alive:
        return {"ok": True, "worker": "pid-present-but-stale-tick"}
    if not restart:
        return {"ok": False, "worker": "dead"}
    exe = sys.executable
    subprocess.Popen([exe, os.path.join(BASE, "employ.py"), "worker", "1380"],
                     cwd=BASE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    C.log("🛟 أعاد الحارس العاملَ للخدمة (انسحب سابقاً)")
    return {"ok": True, "worker": "restarted"}


WATCHDOG_SCHED = "AgentOSInboxWatchdog"


def install_watchdog_every(minutes=10):
    """مهمة حراسة: كل بضع دقائق تتحقق أن الـ worker حيّ وتعيده إن لزم."""
    exe = sys.executable
    cmd = (["schtasks", "/Create", "/TN", WATCHDOG_SCHED, "/SC", "MINUTE", "/MO", str(minutes),
            "/TR", f'"{exe}" "{os.path.join(BASE, "employ.py")}" ensure', "/F"])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60)
        C.log(f"🛰️ حارس صندوق الوارد كل {minutes} د: {out.stdout.strip() or out.stderr.strip()}")
        return {"ok": out.returncode == 0, "output": (out.stdout or out.stderr).strip()[:200]}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120]}


def install_inbox_schedule(start="00:00", minutes=1380):
    """مهمة ويندوز شبه دائمة: تلتقط وتنفّذ طلبات اللوحة طوال اليوم."""
    exe = sys.executable
    args = f'worker {minutes}'
    cmd = (["schtasks", "/Create", "/TN", INBOX_SCHED_NAME, "/SC", "DAILY", "/ST", start,
            "/TR", f'"{exe}" "{os.path.join(BASE, "employ.py")}" {args}', "/F"])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        C.log(f"📬 منفّذ صندوق الوارد {start}: {out.stdout.strip() or out.stderr.strip()}")
        return {"ok": out.returncode == 0, "output": (out.stdout or out.stderr).strip()[:200]}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120]}


def remove_inbox_schedule():
    try:
        out = subprocess.run(["schtasks", "/Delete", "/TN", INBOX_SCHED_NAME, "/F"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return {"ok": out.returncode == 0, "output": (out.stdout or out.stderr).strip()[:200]}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120]}


def remove_schedule():
    try:
        out = subprocess.run(["schtasks", "/Delete", "/TN", SCHED_NAME, "/F"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return {"ok": out.returncode == 0, "output": (out.stdout or out.stderr).strip()[:200]}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120]}


def quick_state():
    from agent_os import dashboard
    return dashboard.state()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("night", "run"):
        minutes = float(args[1]) if len(args) > 1 else 55.0
        mission = None
        if "--mission" in args:
            i = args.index("--mission")
            if i + 1 < len(args):
                mission = args[i + 1]
        print(json.dumps(run_night(minutes, mission), ensure_ascii=False, indent=1))
    elif args[0] == "once":
        from agent_os import kernel
        print(json.dumps(kernel.run_loop(0), ensure_ascii=False, indent=1))
    elif args[0] == "worker":
        minutes = float(args[1]) if len(args) > 1 else 1380.0
        print(json.dumps(run_worker(minutes), ensure_ascii=False, indent=1))
    elif args[0] == "ensure":
        print(json.dumps(ensure_worker(), ensure_ascii=False, indent=1))
    elif args[0] == "--watchdog":
        mins = int(args[1]) if len(args) > 1 else 10
        print(json.dumps(install_watchdog_every(mins), ensure_ascii=False, indent=1))
    elif args[0] == "--schedule-inbox":
        start = args[1] if len(args) > 1 else "00:00"
        print(json.dumps(install_inbox_schedule(start), ensure_ascii=False, indent=1))
    elif args[0] == "--remove-inbox":
        print(json.dumps(remove_inbox_schedule(), ensure_ascii=False, indent=1))
    elif args[0] == "state":
        print(json.dumps(quick_state(), ensure_ascii=False, indent=1))
    elif args[0] == "--schedule" and len(args) > 1:
        print(json.dumps(install_schedule(args[1]), ensure_ascii=False, indent=1))
    elif args[0] == "--remove":
        print(json.dumps(remove_schedule(), ensure_ascii=False, indent=1))
    else:
        print("الاستعمال: night [دقائق] | once | state | worker [دقائق] | --schedule HH:MM | --remove | --schedule-inbox | --remove-inbox")