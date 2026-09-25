"""
autopilot.py - الطيار الآلي المتقدم (v2.0)
==========================================
نظام مهام متوازية مع:
  - حماية محسّنة
  - مراقبة الأداء
  - تحسين ذاتي آمن
  - إدارة ذكية للوقت
"""

import os
import sys
import time
import json
import random
import datetime
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PLATFORM_PORT = os.getenv("SELFRUNNER_PORT", "8082")
PLATFORM_URL = os.getenv("SELFRUNNER_PLATFORM", f"http://127.0.0.1:{PLATFORM_PORT}")
SLEEP = int(os.getenv("SELFRUNNER_LOOP_SECONDS", "90"))
ONCE = "--once" in sys.argv

# تبويب المهام
FOCUSES = ["learn", "search", "build", "improve"]
_focus_counter = 0
_focus_lock = threading.Lock()


# ================= واجهة المنصة =================
import urllib.request

_API_TIMEOUT = int(os.getenv("SELFRUNNER_API_TIMEOUT", "10"))

def api_get(path):
    try:
        with urllib.request.urlopen(PLATFORM_URL + path, timeout=_API_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def api_post(path, data):
    try:
        req = urllib.request.Request(
            PLATFORM_URL + path,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_API_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def platform_alive():
    return api_get("/api/tasks") is not None


def log_entry(e_type, status, title, desc=""):
    api_post("/api/save", {
        "type": e_type, "status": status, "title": title,
        "desc": desc,
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })


def log_activity(kind, msg):
    api_post("/api/activity", {"kind": kind, "msg": msg})


def add_suggestion(title, what, desc, code="", state="pending"):
    # الاقتراحات معطّلة — الجهد يصرف نحو التنفيذ
    pass


def chat_send(role, text, kind="chat"):
    api_post("/api/chat/send", {"role": role, "text": text, "kind": kind})


def chat_read(limit=20):
    d = api_get("/api/chat")
    return d if isinstance(d, list) else []


def has_brain():
    try:
        import brain
        return brain.status_report()["total_engines"] > 0
    except Exception:
        return False


# ================= مهمات التناوب =================
def rotational():
    global _focus_counter
    with _focus_lock:
        focus = FOCUSES[_focus_counter % len(FOCUSES)]
        _focus_counter += 1
    return focus


def seat_task(task):
    """تنفيذ مهمة صريحة من المستخدم."""
    import selfrunner
    title = task.get("title", "مهمة")
    print(f"[الأمر المباشر] تنفيذ: {title}")
    log_activity("command", "بدأ تنفيذ أمرك: " + title)
    prompt = title
    if task.get("desc"):
        prompt += "\nالتفاصيل: " + task["desc"]
    try:
        report = selfrunner.run_task(prompt)
        log_entry("report", "done", "أنجز: " + title, f"التقرير: {report}")
        log_activity("done", "أنجز أمرك: " + title)
    except Exception as e:
        log_entry("report", "progress", "فشل: " + title, str(e))
        log_activity("error", "تعذر إنجاز: " + title)
    api_post("/api/task/done", {"id": task.get("id", 0)})


def _run_arm(e_type, prompt):
    """تنفيذ مهمة ذاتية."""
    import selfrunner
    try:
        report = selfrunner.run_task(prompt)
        log_entry(e_type, "progress", "نشاط ذاتي", f"التقرير: {report}")
        log_activity("done", "أنهى نشاطاً ذاتياً")
        return report
    except Exception as e:
        log_entry("note", "progress", "ذاتي (فشل)", str(e))
        log_activity("error", "فشل النشاط الذاتي: " + str(e)[:120])
        return None


def act_learn():
    prompt = "ادرس مفهوماً برمجياً أو مهارة جديدة مفيدة وسجّلها كمهارة."
    log_activity("self", "جارٍ التعلم")
    return _run_arm("skill", prompt)


def act_search():
    prompt = "ابحث عن مصدر/أداة/مكتبة مجانية مفيدة وسجّلها مع رابطها."
    log_activity("self", "جارٍ البحث")
    return _run_arm("search", prompt)


def act_build():
    prompt = "ابنِ أداة/سكريبت ملموس مفيدة واكتبها في مجلد projects/."
    log_activity("self", "جارٍ البناء")
    return _run_arm("project", prompt)


def act_improve():
    """تحسين الكود بشكل آمن — فقط داخل projects/ وليس ملفات النظام نفسه."""
    log_activity("self", "جارٍ تحسين الكود")
    try:
        # تحسين المشاريع المبنية فقط — لا يلمس قلب النظام (selfrunner, brain, ...)
        proj_dir = os.path.join(BASE_DIR, "projects")
        code_files = []
        if os.path.isdir(proj_dir):
            for root, _, files in os.walk(proj_dir):
                for f in files:
                    if f.endswith((".py", ".js", ".ts", ".html", ".css", ".lua")):
                        code_files.append(os.path.join(root, f))
        if code_files:
            target = os.path.relpath(random.choice(code_files), BASE_DIR)
            prompt = f"راجع الملف {target} واقترح تحسينات محددة (أضف type hints، حسّن الأخطاء، أضف logging). اكتب التحسينات فقط ولا تعدّل الملفات."
            return _run_arm("improve", prompt)
        log_activity("self", "لا توجد ملفات مشاريع لتحسينها")
        return None
    except Exception as e:
        log_activity("error", "فشل التحسين: " + str(e)[:120])
        return None


# ================= دورة التحكم =================
def autonomous_step():
    focus = rotational()
    if focus == "learn":
        act_learn()
    elif focus == "search":
        act_search()
    elif focus == "build":
        act_build()
    elif focus == "improve":
        act_improve()


def step():
    # 1) فحص المنصة أولاً
    tasks = api_get("/api/tasks")
    if tasks is not None:
        pending = [t for t in tasks if not t.get("done")]
        pending.sort(key=lambda t: 0 if t.get("priority") == "high" else 1)
        if pending:
            seat_task(pending[0])
            return

    # 2) العمل الذاتي
    if has_brain():
        autonomous_step()
    else:
        print("[!] لا يوجد عقل متاح. أنتظر...")


def main():
    print("=" * 54)
    print("   موظف الليل - الطيار الآلي المتقدم")
    print(f"   المنصة: {PLATFORM_URL}   السكون: {SLEEP} ث")
    print("   المهام: تعلم / بحث / بناء / تحسين")
    print("=" * 54)

    while True:
        try:
            step()
        except Exception as e:
            print(f"[خطأ] {e}")
        if ONCE:
            print("انتهت دورة الاختبار.")
            break
        time.sleep(SLEEP)


if __name__ == "__main__":
    main()
