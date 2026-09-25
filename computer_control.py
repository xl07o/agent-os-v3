"""
computer_control.py - نظام التحكم الكامل بالجهاز (v1.0)
=====================================================
وصول كامل للجهاز: ماوس، كيبورد، نوافذ، ملفات، برامج، إنترنت
يتعلم من الجهاز ويتكيف مع عاداتك
"""

import os
import sys
import json
import time
import datetime
import subprocess
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
try:
    from agent_os import security_kernel as _auth
except Exception:
    _auth = None

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CONTROL_LOG = os.path.join(BASE_DIR, "logs", "computer_control.log")
LEARN_FILE = os.path.join(BASE_DIR, "data", "computer_learned.json")
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

# ===== طبقة الأمان (عيب حرج #1) =====
# سابقاً كانت run_command/write_file/delete_file تعمل بلا أي تحقق وعبر الصدفة،
# مما يلتف على كل حماية selfrunner. الآن كل عملية خطرة تمرّ بنفس الفحص.
try:
    import selfrunner as _sr
    _is_safe_command = _sr._is_safe_command
    _validate_path = _sr._validate_path
    _split_args = _sr._split_args
except Exception:
    # نسخة مستقلة احتياطية لو استُدعي الملف وحده (بلا selfrunner)
    import shlex as _shlex

    _SAFE = {
        "python", "python3", "pythonw", "pip", "pip3",
        "node", "npm", "npx", "git", "ls", "dir", "mkdir",
        "cat", "type", "echo", "pwd", "where", "which",
        "code", "notepad",
    }
    _FORBIDDEN = {"curl", "wget", "sh", "bash", "cmd", "powershell",
                 "pwsh", "telnet", "nc", "rm", "del", "rd", "rmdir",
                 "format", "diskpart", "shred", "reg", "schtasks",
                 "taskkill", "shutdown", "net", "sudo", "su", "dd",
                 "chmod", "chown", "mv"}
    _EVAL_FLAGS = {"-c", "-e", "-m", "-p", "-i", "-I", "-", "--eval",
                  "--module", "--interactive", "--command", "--print",
                  "--run", "--execute"}

    def _split_args(cmd):
        try:
            return _shlex.split(cmd)
        except ValueError:
            return []

    def _is_safe_command(cmd):
        cmd = (cmd or "").strip()
        if not cmd:
            return False
        if any(op in cmd for op in ["&&", "||", ";", "|", "`", "$(", "$[", "<("]):
            return False
        args = _split_args(cmd)
        if not args:
            return False
        main = os.path.splitext(os.path.basename(args[0].lower()))[0] or args[0].lower()
        if main in _FORBIDDEN:
            return False
        if main not in _SAFE:
            return False
        if main in {"python", "python3", "pythonw", "node", "npm", "npx"}:
            if len(args) > 1 and args[1].lower() in _EVAL_FLAGS:
                return False
        return True

    def _validate_path(path):
        try:
            abs_path = os.path.realpath(path)
        except Exception:
            return False, "مسار غير صالح"
        for blocked in ("C:\\Windows", "C:\\Program Files", "/usr", "/bin",
                        "/sbin", "/etc", "/var"):
            if abs_path.lower().startswith(os.path.realpath(blocked).lower()):
                return False, f"المسار محظور: {blocked}"
        if os.path.basename(abs_path) in {".env", ".env.local",
                                          ".env.production", ".env.development"}:
            return False, "ملف .env محظور"
        return True, abs_path

# ===== فحص المكتبات =====

def _has(lib):
    try:
        __import__(lib)
        return True
    except Exception:
        # Optional GUI packages can fail at import time when no display/session exists.
        # This must never make the entire Agent OS unimportable.
        return False

HAS_PYAUTOGUI = _has("pyautogui")
HAS_PYGETWINDOW = _has("pygetwindow")
HAS_PSUTIL = _has("psutil")
HAS_PIL = _has("PIL")


def install_deps():
    """تثبيت المكتبات اللازمة تلقائياً."""
    pkgs = []
    if not HAS_PYAUTOGUI:
        pkgs.append("pyautogui")
    if not HAS_PYGETWINDOW:
        pkgs.append("pygetwindow")
    if not HAS_PSUTIL:
        pkgs.append("psutil")
    if not HAS_PIL:
        pkgs.append("Pillow")
    if pkgs:
        print(f"جارٍ تثبيت: {', '.join(pkgs)}")
        subprocess.run([sys.executable, "-m", "pip", "install"] + pkgs, check=False)
        print("تم التثبيت ✅")


# ===== سجل =====

def _log(msg):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    try:
        with open(CONTROL_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ===== التحكم بالماوس والكيبورد =====

def move_mouse(x, y):
    if not HAS_PYAUTOGUI:
        return "خطأ: pyautogui غير مثبت"
    import pyautogui
    pyautogui.moveTo(x, y, duration=0.3)
    return f"تحرك الماوس إلى ({x}, {y})"


def click(x=None, y=None, button="left", double=False):
    if not HAS_PYAUTOGUI:
        return "خطأ: pyautogui غير مثبت"
    import pyautogui
    if x and y:
        pyautogui.moveTo(x, y, duration=0.2)
    if double:
        pyautogui.doubleClick()
    else:
        pyautogui.click(button=button)
    return f"ضغط {'مزدوج' if double else ''} {button} عند ({x},{y})"


def type_text(text, interval=0.05):
    if not HAS_PYAUTOGUI:
        return "خطأ: pyautogui غير مثبت"
    import pyautogui
    pyautogui.write(text, interval=interval)
    return f"كتب: {text[:50]}..."


def press_key(key):
    if not HAS_PYAUTOGUI:
        return "خطأ: pyautogui غير مثبت"
    import pyautogui
    pyautogui.press(key)
    return f"ضغط مفتاح: {key}"


def hotkey(*keys):
    if not HAS_PYAUTOGUI:
        return "خطأ: pyautogui غير مثبت"
    import pyautogui
    pyautogui.hotkey(*keys)
    return f"اختصار: {'+'.join(keys)}"


def screenshot(save_path=None):
    if not HAS_PYAUTOGUI:
        return None, "خطأ: pyautogui غير مثبت"
    import pyautogui
    if not save_path:
        save_path = os.path.join(BASE_DIR, "output", f"screenshot_{int(time.time())}.png")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    img = pyautogui.screenshot()
    img.save(save_path)
    return save_path, f"صورة محفوظة: {save_path}"


def get_screen_size():
    if not HAS_PYAUTOGUI:
        return None
    import pyautogui
    return pyautogui.size()


# ===== إدارة النوافذ =====

def list_windows():
    if not HAS_PYGETWINDOW:
        return []
    import pygetwindow as gw
    return [w.title for w in gw.getAllWindows() if w.title.strip()]


def focus_window(title):
    if not HAS_PYGETWINDOW:
        return "خطأ: pygetwindow غير مثبت"
    import pygetwindow as gw
    wins = gw.getWindowsWithTitle(title)
    if wins:
        wins[0].activate()
        return f"تم فتح النافذة: {title}"
    return f"لم توجد نافذة: {title}"


def close_window(title):
    if not HAS_PYGETWINDOW:
        return "خطأ: pygetwindow غير مثبت"
    import pygetwindow as gw
    wins = gw.getWindowsWithTitle(title)
    if wins:
        wins[0].close()
        return f"تم إغلاق: {title}"
    return f"لم توجد: {title}"


# ===== تشغيل البرامج =====

def open_app(app_name):
    """فتح برنامج بالاسم."""
    apps = {
        "chrome": "chrome",
        "firefox": "firefox",
        "notepad": "notepad",
        "calculator": "calc",
        "explorer": "explorer",
        "vscode": "code",
        "word": "winword",
        "excel": "excel",
        "paint": "mspaint",
        "task manager": "taskmgr",
    }
    cmd = apps.get(app_name.lower(), app_name)
    # قصر الفتح على أسماء برامج معروفة فقط — لا سلاسل عشوائية مع shell (عيب #1)
    if app_name.lower() not in apps:
        # نسمح باسم برنامج بسيط فقط (بلا مسافات/فواصل/رموز صدفة)
        if not str(cmd).replace(".", "").replace("_", "").replace("-", "").isalnum():
            _log(f"رُفض فتح برنامج غير معروف: {app_name}")
            return f"خطأ: اسم برنامج غير مسموح: {app_name}"
    try:
        subprocess.Popen([cmd], shell=False)
        return f"تم فتح: {app_name}"
    except FileNotFoundError:
        return f"خطأ: البرنامج غير موجود: {app_name}"
    except Exception as e:
        return f"خطأ فتح {app_name}: {e}"


def run_command(cmd, timeout=30):
    """تشغيل أمر بأمان: قائمة بيضاء + argv بلا shell (عيب حرج #1).

    كان التنفيذ سابقاً عبر الصدفة (shell) بلا تحقق يسمح بأوامر عشوائية عبر CONTROL.
    الآن يمرّ الأمر بنفس فحص selfrunner، ويُنفّذ عبر قائمة argv بلا shell.
    """
    if not _is_safe_command(cmd):
        _log(f"رُفض أمر غير آمن: {cmd}")
        return {"error": "الأمر محظور لأسباب أمان", "cmd": cmd}
    args = _split_args(cmd)
    if not args:
        return {"error": "أمر فارغ"}
    try:
        result = subprocess.run(
            args, shell=False, capture_output=True,
            text=True, timeout=timeout, encoding="utf-8", errors="replace"
        )
        return {
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:500],
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": "انتهت المهلة"}
    except FileNotFoundError:
        return {"error": f"الأمر غير موجود: {args[0]}"}
    except Exception as e:
        return {"error": str(e)}


def open_url(url):
    """فتح رابط في المتصفح بعد فحص سياسة الشبكة."""
    if _auth is not None:
        _auth.url_guard(url)
    if _auth is not None:
        _auth.url_guard(url)
    import webbrowser
    webbrowser.open(url)
    return f"تم فتح: {url}"


# ===== إدارة الملفات =====

def read_file(path):
    ok, resolved = _validate_path(path)
    if not ok:
        _log(f"رُفضت قراءة لمسار محظور: {path} — {resolved}")
        return f"خطأ: {resolved}"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"خطأ: {e}"


def write_file(path, content):
    ok, resolved = _validate_path(path)
    if not ok:
        _log(f"رُفضت كتابة لمسار محظور: {path} — {resolved}")
        return f"خطأ: {resolved}"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"تم الحفظ: {path}"
    except Exception as e:
        return f"خطأ: {e}"


def list_dir(path="."):
    ok, resolved = _validate_path(path)
    if not ok:
        return {"error": resolved}
    try:
        items = os.listdir(resolved)
        return {"path": path, "items": items, "count": len(items)}
    except Exception as e:
        return {"error": str(e)}


def delete_file(path):
    ok, resolved = _validate_path(path)
    if not ok:
        _log(f"رُفض حذف لمسار محظور: {path} — {resolved}")
        return f"خطأ: {resolved}"
    try:
        if os.path.isfile(path):
            os.remove(path)
            return f"تم حذف: {path}"
        return "الملف غير موجود"
    except Exception as e:
        return f"خطأ: {e}"


def copy_file(src, dst):
    import shutil
    ok_s, rs = _validate_path(src)
    ok_d, rd = _validate_path(dst)
    if not ok_s:
        return f"خطأ (مصدر): {rs}"
    if not ok_d:
        return f"خطأ (وجهة): {rd}"
    try:
        shutil.copy2(src, dst)
        return f"تم نسخ: {src} → {dst}"
    except Exception as e:
        return f"خطأ: {e}"


# ===== معلومات الجهاز =====

def system_info():
    info = {
        "os": os.name,
        "platform": sys.platform,
        "python": sys.version,
        "cwd": os.getcwd(),
        "user": os.environ.get("USERNAME", "unknown"),
        "home": os.path.expanduser("~"),
        "time": datetime.datetime.now().isoformat(),
    }
    if HAS_PSUTIL:
        import psutil
        info["cpu_percent"] = psutil.cpu_percent(interval=1)
        info["ram_percent"] = psutil.virtual_memory().percent
        info["ram_total_gb"] = round(psutil.virtual_memory().total / 1e9, 1)
        info["disk_free_gb"] = round(psutil.disk_usage(".").free / 1e9, 1)
        info["processes"] = len(psutil.pids())
    return info


def list_processes():
    if not HAS_PSUTIL:
        return []
    import psutil
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except Exception:
            pass
    return sorted(procs, key=lambda x: x.get("cpu_percent", 0), reverse=True)[:20]


def kill_process(name_or_pid):
    if str(name_or_pid).lower() in {"system", "init", "explorer.exe", "winlogon.exe", "lsass.exe", "services.exe"}:
        return "رفض: عملية نظام حساسة"
    if not HAS_PSUTIL:
        return "خطأ: psutil غير مثبت"
    import psutil
    killed = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            if str(p.pid) == str(name_or_pid) or p.name().lower() == str(name_or_pid).lower():
                p.kill()
                killed.append(p.name())
        except Exception:
            pass
    return f"تم إيقاف: {killed}" if killed else "لم يوجد"


# ===== التعلم من الجهاز =====

def learn_from_system():
    """يتعلم من الجهاز: البرامج، الملفات، العادات."""
    learned = {}

    # البرامج المثبتة
    if HAS_PSUTIL:
        import psutil
        procs = set()
        for p in psutil.process_iter(["name"]):
            try:
                procs.add(p.name())
            except Exception:
                pass
        learned["running_apps"] = list(procs)

    # متغيرات البيئة
    learned["env_vars"] = list(os.environ.keys())

    # المجلدات المهمة
    home = os.path.expanduser("~")
    important_dirs = []
    for d in ["Desktop", "Documents", "Downloads", "OneDrive"]:
        p = os.path.join(home, d)
        if os.path.exists(p):
            important_dirs.append(p)
    learned["important_dirs"] = important_dirs

    # حجم الملفات
    learned["system"] = system_info()
    learned["learned_at"] = datetime.datetime.now().isoformat()

    # حفظ
    tmp = LEARN_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(learned, f, ensure_ascii=False, indent=2)
    os.replace(tmp, LEARN_FILE)

    _log(f"تعلم من الجهاز: {len(learned.get('running_apps', []))} برنامج، {len(important_dirs)} مجلد")
    return learned


def get_learned():
    """جلب ما تعلمه عن الجهاز."""
    if os.path.exists(LEARN_FILE):
        try:
            with open(LEARN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ===== واجهة الوكيل للتحكم =====

def execute_action(action, params=None):
    """تنفيذ أي أمر بالجهاز."""
    params = params or {}
    _log(f"تنفيذ: {action} | معاملات: {params}")

    actions = {
        "screenshot": lambda: screenshot()[1],
        "system_info": lambda: json.dumps(system_info(), ensure_ascii=False),
        "list_windows": lambda: str(list_windows()),
        "list_processes": lambda: str(list_processes()[:5]),
        "learn_from_system": lambda: str(learn_from_system()),
        "move_mouse": lambda: move_mouse(params.get("x", 0), params.get("y", 0)),
        "click": lambda: click(params.get("x"), params.get("y"), params.get("button", "left"), params.get("double", False)),
        "type_text": lambda: type_text(params.get("text", "")),
        "press_key": lambda: press_key(params.get("key", "")),
        "hotkey": lambda: hotkey(*params.get("keys", [])),
        "open_app": lambda: open_app(params.get("app", "")),
        "open_url": lambda: open_url(params.get("url", "")),
        "run_command": lambda: str(run_command(params.get("cmd", ""))),
        "read_file": lambda: read_file(params.get("path", "")),
        "write_file": lambda: write_file(params.get("path", ""), params.get("content", "")),
        "list_dir": lambda: str(list_dir(params.get("path", "."))),
        "delete_file": lambda: delete_file(params.get("path", "")),
        "focus_window": lambda: focus_window(params.get("title", "")),
        "close_window": lambda: close_window(params.get("title", "")),
        "kill_process": lambda: kill_process(params.get("name", "")),
    }

    fn = actions.get(action)
    if fn:
        try:
            result = fn()
            _log(f"نتيجة: {str(result)[:200]}")
            return result
        except Exception as e:
            _log(f"خطأ: {e}")
            return f"خطأ: {e}"
    return f"أمر غير معروف: {action}"


# ===== الواجهة الرئيسية =====

if __name__ == "__main__":
    print("🖥️ نظام التحكم الكامل بالجهاز")
    print("=" * 50)

    if "--install" in sys.argv:
        install_deps()

    elif "--info" in sys.argv:
        info = system_info()
        for k, v in info.items():
            print(f"  {k}: {v}")

    elif "--learn" in sys.argv:
        print("🧠 جارٍ التعلم من الجهاز...")
        data = learn_from_system()
        print(f"✅ تعلم: {len(data.get('running_apps', []))} برنامج")
        print(f"📁 مجلدات: {data.get('important_dirs', [])}")

    elif "--windows" in sys.argv:
        wins = list_windows()
        print(f"النوافذ المفتوحة ({len(wins)}):")
        for w in wins:
            print(f"  - {w}")

    elif "--screenshot" in sys.argv:
        path, msg = screenshot()
        print(msg)

    else:
        print("الأوامر:")
        print("  python computer_control.py --install     تثبيت المكتبات")
        print("  python computer_control.py --info        معلومات الجهاز")
        print("  python computer_control.py --learn       تعلم من الجهاز")
        print("  python computer_control.py --windows     النوافذ المفتوحة")
        print("  python computer_control.py --screenshot  صورة شاشة")
