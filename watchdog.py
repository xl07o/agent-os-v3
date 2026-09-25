"""
watchdog.py - الحارس الخارجي للنواة المستمرة (عيب 21)
========================================================
يراقب نبض النواة (data/agent_os/heartbeat.json) ويعيد تشغيلها لو سكت:

  - heartbeats تُكتب في كل دورة من agent_os/kernel.py.
  - لو النبض أقدم من STALE_SECONDS (10 دقائق) → إعادة تشغيل عبر
    `python -m agent_os.kernel <دقائق>`.
  - يفحص كل 5 دقائق في حلقة، أو مرة واحدة بـ "once".

الاستخدام:
  python watchdog.py                # حلقة دائمة (Task Scheduler ينصح بها)
  python watchdog.py once           # فحص واحد ثم خروج
  python watchdog.py now            # إعادة تشغيل فورية إن كان النبض قديماً
"""

import datetime
import os
import subprocess
import sys
import time

PARENT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PARENT)
from agent_os import _common as C

HEARTBEAT_FILE = os.path.join(C.AGENT_OS_DIR, "heartbeat.json")
STALE_SECONDS = 600        # أقدم من 10 دقائق = النواة ماتت
CHECK_EVERY = 300          # افحص كل 5 دقائق
RUN_MINUTES = 55           # مدة كل تشغيل نواة (لدورة لا تنتهي سريعاً)


def heartbeat_age():
    """عمر النبض بالثواني، أو None إن كان مفقوداً."""
    try:
        import json
        with open(HEARTBEAT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = float(data.get("ts", 0))
        if not ts:
            return None
        return time.time() - ts
    except Exception:
        return None


def _pid_alive(pid):
    """تحقق هل العملية ذات الرقم pid على قيد الحياة؟ (tasklist لا يحتاج صلاحيات)."""
    if not pid:
        return False
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            text=True, encoding="utf-8", errors="replace", timeout=10,
        )
        return f'"{pid}"' in out
    except Exception:
        # شك: لا نثق — إن لم نستطع التحقق لا نُكرر الإطلاق (الأمان في عدم التراكم)
        return True


def restart_kernel():
    """إعادة تشغيل النواة المستمرة في عملية مستقلة — بلا تكديس نوى."""
    hb = C.load_json(HEARTBEAT_FILE, {})
    pid = hb.get("pid")
    if _pid_alive(pid):
        C.log(f"🐕 النواة حية (pid {pid}) لكن النبض قديم — لا نطلق نسخة ثانية")
        return "noop_alive"
    C.log("🐕 heartbeat قديم والـpid ميت — إعادة تشغيل النواة")
    cmd = [sys.executable, "-m", "agent_os.kernel", str(RUN_MINUTES)]
    flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS \
        if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    try:
        subprocess.Popen(cmd, cwd=PARENT, creationflags=flags)
        return "relaunched"
    except Exception as e:
        C.log(f"🚨 فشل إعادة تشغيل النواة: {str(e)[:120]}")
        return "fail"


def check_once(force=False):
    """فحص واحد: إن كان النبض قديماً أو مفقوداً (أو force) — أعد التشغيل."""
    age = heartbeat_age()
    if age is None or age > STALE_SECONDS or force:
        if age is None:
            C.log("🐕 لا نبض (heartbeat مفقود) — النواة لم تبدأ أو ماتت")
        elif age > STALE_SECONDS:
            C.log(f"🐕 النبض قديم ({int(age)} ثانية)")
        restart_kernel()
        return "restarted"
    return "alive"


def run():
    """الحلقة الدائمة: افحص كل 5 دقائق."""
    C.log("🐕 الحارس يعمل — يفحص النبض كل 5 دقائق")
    while True:
        try:
            check_once()
        except Exception as e:
            C.log(f"⚠️ خطأ فحص: {str(e)[:120]}")
        time.sleep(CHECK_EVERY)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "once":
        print(check_once())
    elif args and args[0] == "now":
        print(check_once(force=True))
    else:
        run()