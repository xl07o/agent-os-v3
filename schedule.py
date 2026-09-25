"""
schedule.py - جدولة التشغيل التلقائي (v2.0)
===========================================
جدولة ذكية مع:
  - تاريخ ديناميكي
  - حماية من التعارض
  - دعم Windows Task Scheduler
"""

import argparse
import datetime
import os
import subprocess
import sys
import xml.sax.saxutils as saxutils

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(BASE_DIR, "selfrunner.py")
TASK_NAME = "SelfRunnerNightly"

# تطهير كل ما يُدرج في XML — يمنع حقن عناصر أو أوامر إضافية
_XML_ESCAPE_ATTR = lambda s: saxutils.escape(s, {'"': "&quot;", "'": "&apos;"})

TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <TimeTrigger>
      <StartBoundary>{START}</StartBoundary>
      <Enabled>true</Enabled>
      <Repetition><Interval>P1D</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
    </TimeTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>{LIMIT}</ExecutionTimeLimit>
  </Settings>
  <Actions>
    <Exec>
      <Command>cmd</Command>
      <Arguments>/c "cd /d &quot;{DIR}&quot; &amp;&amp; pythonw selfrunner.py &quot;{TASK}&quot;"</Arguments>
      <WorkingDirectory>{DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def _build_xml(start, task):
    """بناء XML للمهمة مع تطهير كل القيم ضد حقن XML/أوامر."""
    # حد زمني سخي لا يقطع المهمة قبل اكتمالها (قابل للتخصيص)
    limit = os.getenv("SELFRUNNER_TASK_LIMIT", "PT71H")
    return (
        TASK_XML
        .replace("{START}", _XML_ESCAPE_ATTR(start))
        .replace("{DIR}", _XML_ESCAPE_ATTR(BASE_DIR))
        .replace("{TASK}", _XML_ESCAPE_ATTR(task))
        .replace("{LIMIT}", limit)
    )


def create_task(time_str, task):
    """إنشاء مهمة مجدولة — يرجع {"ok": bool, "task_name": str, "error": str}."""
    result = {"ok": False, "task_name": TASK_NAME, "error": ""}
    try:
        # استخدام التاريخ الحالي بدل ثابت
        now = datetime.datetime.now()
        start = f"{now:%Y-%m-%d}T{time_str}:00"
        xml = _build_xml(start, task)
        xml_path = os.path.join(BASE_DIR, "_task_temp.xml")
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(xml)
    except Exception as e:
        result["error"] = str(e)[:200]
        return result
    try:
        subprocess.run(
            ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", xml_path, "/F"],
            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60,
        )
        print(f"تم إنشاء المهمة '{TASK_NAME}' لتشغيل الساعة {time_str} كل ليلة.")
        result["ok"] = True
    except FileNotFoundError:
        result["error"] = "schtasks غير متاح. تأكد أنك على Windows."
        print(result["error"])
    except subprocess.TimeoutExpired:
        result["error"] = f"انتهت مهلة schtasks أثناء إنشاء '{TASK_NAME}'"
        print(result["error"])
    except Exception as e:
        result["error"] = str(e)[:200]
        print(f"فشل إنشاء المهمة: {e}")
    finally:
        if os.path.exists(xml_path):
            try:
                os.remove(xml_path)
            except Exception:
                pass
    return result


def list_tasks():
    """يرجع قائمة المهام كعناصر dict (تُقرأ من Task Scheduler) — أو [] عند الغياب/الخطأ."""
    try:
        r = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60,
        )
    except FileNotFoundError:
        print("schtasks غير متاح. تأكد أنك على Windows.")
        return []
    except Exception as e:
        print(f"خطأ في الاستعلام عن المهام: {e}")
        return []
    if r.returncode != 0:
        # المهمة غير موجودة أو الاستعلام غير مدعوم — ليست حالة تعطل
        return []
    items, entry = [], {}
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            if entry:
                items.append(entry)
                entry = {}
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            entry[k.strip()] = v.strip()
    if entry:
        items.append(entry)
    return items


def delete_task():
    """حذف المهمة المجدولة — يرجع True عند النجاح وإلا False."""
    try:
        r = subprocess.run(
            ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60,
        )
    except FileNotFoundError:
        print("schtasks غير متاح. تأكد أنك على Windows.")
        return False
    except Exception as e:
        print(f"خطأ: {e}")
        return False
    if r.returncode == 0:
        print(f"تم حذف مهمة '{TASK_NAME}'.")
        return True
    msg = (r.stderr or r.stdout or "").strip()[:200]
    print(f"لم يُحذف '{TASK_NAME}': {msg}")
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SelfRunner scheduler")
    parser.add_argument("--time", default="02:00", help="الوقت اليومي (HH:MM)")
    parser.add_argument(
        "--task",
        default="نفّذ المهام التالية: نظف، أصلح، حسن، ثم بنِ مشروعاً جديداً.",
        help="مهمة الليل",
    )
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--delete", action="store_true")
    args = parser.parse_args()

    if args.list:
        entries = list_tasks()
        if not entries:
            print(f"لا توجد مهمة مجدولة باسم '{TASK_NAME}'.")
        for it in entries:
            print(" | ".join(f"{k}: {v}" for k, v in it.items()))
    elif args.delete:
        delete_task()
    else:
        create_task(args.time, args.task)
