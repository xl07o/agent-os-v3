"""
الأدوات الحقيقية — تنفيذ فعلي فقط، لا محاكاة. سياسة الموافقة (أي أداة
تحتاج إذناً) قرار kernel.py، لا هذا الملف — هنا فقط الآلية.
"""

import os
import shlex
import subprocess

from . import safety, sandbox, web

WORKSPACE = os.path.join(os.path.dirname(__file__), "data", "workspace")

# وضع الوصول الكامل للجهاز — يعمل على الجهاز الحقيقي فعلياً، لا مجلد
# عمل محصور. معطّل افتراضياً (راجع safety.pc_access_enabled). الجذر
# الافتراضي: المجلد اللي شُغِّل منه agent_os4، لا مجلد ثابت — نفس
# منطق OpenCode/Claude Code (يعمل حيث استُدعي، لا بمجلد خاص مفروض).
PC_ROOT = os.environ.get("OS4_PC_ROOT") or os.getcwd()


def _pc_full_path(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(PC_ROOT, path)


def read_file(args: dict) -> dict:
    path = os.path.join(WORKSPACE, args.get("path", ""))
    ok, reason = safety.validate_path(path, WORKSPACE)
    if not ok:
        return {"ok": False, "error": reason}
    if not os.path.isfile(path):
        return {"ok": False, "error": f"لا يوجد ملف: {path}"}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return {"ok": True, "content": f.read()}


def write_file(args: dict) -> dict:
    path = os.path.join(WORKSPACE, args.get("path", ""))
    ok, reason = safety.validate_path(path, WORKSPACE)
    if not ok:
        return {"ok": False, "error": reason}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(args.get("content", ""))
    return {"ok": True, "path": path, "note": f"كُتب: {path}"}


def list_workspace(args: dict) -> dict:
    """قراءة فقط — يسرد الملفات داخل مساحة العمل، لا يفتح أو يقرأ محتواها."""
    entries = []
    for root, _dirs, files in os.walk(WORKSPACE):
        for name in files:
            full = os.path.join(root, name)
            entries.append(os.path.relpath(full, WORKSPACE))
    return {"ok": True, "files": sorted(entries)}


def browser_screenshot(args: dict) -> dict:
    """لقطة شاشة فقط — بدون أي نقر أو كتابة أو تفاعل مع الصفحة، عمداً:
    هذا يقلّل سطح الهجوم (لا إدخال بيانات اعتماد، لا تنفيذ JS تفاعلي من
    طرفنا) بينما يعطي قدرة حقيقية لرؤية صفحة ويب. يخرج للإنترنت — لهذا
    هو ضمن أدوات تحتاج موافقة."""
    url = args.get("url", "")
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "رابط غير صالح — يجب يبدأ بـhttp:// أو https://"}
    filename = args.get("filename", "screenshot.png")
    out_path = os.path.join(WORKSPACE, filename)
    ok, reason = safety.validate_path(out_path, WORKSPACE)
    if not ok:
        return {"ok": False, "error": reason}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "error": "مكتبة playwright غير مثبتة — شغّل: pip install playwright && playwright install chromium"}
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(url, timeout=20000, wait_until="load")
                page.screenshot(path=out_path)
            finally:
                browser.close()
        return {"ok": True, "path": out_path, "note": f"لقطة شاشة من {url}"}
    except Exception as e:  # noqa: BLE001 — فشل تصفح حقيقي (رابط ميت، مهلة) يُرجَع كنتيجة، لا يكسر الحلقة
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def pc_read_file(args: dict) -> dict:
    """قراءة من الجهاز الحقيقي فعلياً — لا مجلد عمل محصور. معطّلة
    افتراضياً، وتحتاج موافقة (راجع kernel.NEEDS_APPROVAL) لأنها تكشف
    محتوى ملفات حقيقية حساسة محتملة، بعكس read_file المحصورة."""
    if not safety.pc_access_enabled():
        return {"ok": False, "error": "وضع الوصول الكامل للجهاز معطّل — أضف OS4_ALLOW_PC_ACCESS=1 لملف .env لتفعيله"}
    full = _pc_full_path(args.get("path", ""))
    ok, reason = safety.validate_pc_path(full)
    if not ok:
        return {"ok": False, "error": reason}
    if not os.path.isfile(full):
        return {"ok": False, "error": f"لا يوجد ملف: {full}"}
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            return {"ok": True, "content": f.read()}
    except PermissionError as e:
        return {"ok": False, "error": f"صلاحيات مرفوضة: {e}"}


def pc_write_file(args: dict) -> dict:
    """كتابة على الجهاز الحقيقي فعلياً. معطّلة افتراضياً، تحتاج موافقة
    صريحة على كل كتابة — لا استثناء."""
    if not safety.pc_access_enabled():
        return {"ok": False, "error": "وضع الوصول الكامل للجهاز معطّل — أضف OS4_ALLOW_PC_ACCESS=1 لملف .env لتفعيله"}
    full = _pc_full_path(args.get("path", ""))
    ok, reason = safety.validate_pc_path(full)
    if not ok:
        return {"ok": False, "error": reason}
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(args.get("content", ""))
        return {"ok": True, "path": full, "note": f"كُتب على جهازك فعلياً: {full}"}
    except PermissionError as e:
        return {"ok": False, "error": f"صلاحيات مرفوضة: {e}"}


def pc_list_dir(args: dict) -> dict:
    """قراءة فقط — يسرد محتوى مجلد حقيقي على جهازك (لا الملفات نفسها)."""
    if not safety.pc_access_enabled():
        return {"ok": False, "error": "وضع الوصول الكامل للجهاز معطّل — أضف OS4_ALLOW_PC_ACCESS=1 لملف .env لتفعيله"}
    full = _pc_full_path(args.get("path", "."))
    if not os.path.isdir(full):
        return {"ok": False, "error": f"لا يوجد مجلد: {full}"}
    try:
        return {"ok": True, "path": full, "entries": sorted(os.listdir(full))}
    except PermissionError as e:
        return {"ok": False, "error": f"صلاحيات مرفوضة: {e}"}


def pc_run_command(args: dict) -> dict:
    """تنفيذ أمر حقيقي على جهازك عبر shell — لا قائمة بيضاء ضيقة، فقط
    حظر كوارث معروفة (safety.is_safe_pc_command) + موافقتك الصريحة
    على نص الأمر الكامل قبل أي تنفيذ. معطّلة افتراضياً."""
    if not safety.pc_access_enabled():
        return {"ok": False, "error": "وضع الوصول الكامل للجهاز معطّل — أضف OS4_ALLOW_PC_ACCESS=1 لملف .env لتفعيله"}
    cmd = args.get("command", "")
    ok, reason = safety.is_safe_pc_command(cmd)
    if not ok:
        return {"ok": False, "error": reason}
    cwd = _pc_full_path(args.get("cwd", "")) if args.get("cwd") else PC_ROOT
    try:
        r = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=120,
        )
        return {"ok": r.returncode == 0, "stdout": r.stdout[:6000], "stderr": r.stderr[:3000], "returncode": r.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "انتهت المهلة (120 ثانية)"}


def run_command(args: dict) -> dict:
    cmd = args.get("command", "")
    ok, reason = safety.is_safe_command(cmd)
    if not ok:
        return {"ok": False, "error": reason}
    try:
        r = subprocess.run(
            shlex.split(cmd), shell=False, cwd=WORKSPACE,
            capture_output=True, text=True, timeout=60,
        )
        return {"ok": r.returncode == 0, "stdout": r.stdout[:4000], "stderr": r.stderr[:2000]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "انتهت المهلة (60 ثانية)"}


def sandbox_create(args: dict) -> dict:
    sb_id = sandbox.create(label=args.get("label", "os4"))
    return {"ok": True, "sandbox_id": sb_id}


def sandbox_bash(args: dict) -> dict:
    sb_id, cmd = args.get("sandbox_id"), args.get("command")
    if not sb_id or not cmd:
        return {"ok": False, "error": "يحتاج sandbox_id و command"}
    r = sandbox.run_bash(sb_id, cmd)
    return {"ok": r["exit_code"] == 0, "output": str(r["output"])[:2000]}


def sandbox_destroy(args: dict) -> dict:
    sb_id = args.get("sandbox_id")
    if not sb_id:
        return {"ok": False, "error": "يحتاج sandbox_id"}
    sandbox.destroy(sb_id)
    return {"ok": True, "note": "دُمِّر"}


def web_search(args: dict) -> dict:
    """بحث ويب حقيقي (DuckDuckGo) — قراءة فقط، راجع web.py لحواجزه."""
    return web.search(args.get("query", ""), args.get("num", 6))


def web_fetch(args: dict) -> dict:
    """قراءة نص صفحة ويب عامة — GET فقط، لا عناوين داخلية، حجم محدود."""
    return web.fetch(args.get("url", ""))


REGISTRY = {
    "read_file": read_file,
    "write_file": write_file,
    "list_workspace": list_workspace,
    "run_command": run_command,
    "sandbox_create": sandbox_create,
    "sandbox_bash": sandbox_bash,
    "sandbox_destroy": sandbox_destroy,
    "browser_screenshot": browser_screenshot,
    "web_search": web_search,
    "web_fetch": web_fetch,
    "pc_read_file": pc_read_file,
    "pc_write_file": pc_write_file,
    "pc_list_dir": pc_list_dir,
    "pc_run_command": pc_run_command,
}


def run(name: str, args: dict) -> dict:
    os.makedirs(WORKSPACE, exist_ok=True)
    if name not in REGISTRY:
        return {"ok": False, "error": f"أداة غير معروفة: {name}"}
    try:
        return REGISTRY[name](args or {})
    except Exception as e:  # noqa: BLE001 — نُرجع الخطأ كنتيجة، لا نكسر الحلقة
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
