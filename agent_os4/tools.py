"""
الأدوات الحقيقية — تنفيذ فعلي فقط، لا محاكاة. سياسة الموافقة (أي أداة
تحتاج إذناً) قرار kernel.py، لا هذا الملف — هنا فقط الآلية.
"""

import os
import shlex
import subprocess

from . import safety, sandbox

WORKSPACE = os.path.join(os.path.dirname(__file__), "data", "workspace")


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


REGISTRY = {
    "read_file": read_file,
    "write_file": write_file,
    "list_workspace": list_workspace,
    "run_command": run_command,
    "sandbox_create": sandbox_create,
    "sandbox_bash": sandbox_bash,
    "sandbox_destroy": sandbox_destroy,
    "browser_screenshot": browser_screenshot,
}


def run(name: str, args: dict) -> dict:
    os.makedirs(WORKSPACE, exist_ok=True)
    if name not in REGISTRY:
        return {"ok": False, "error": f"أداة غير معروفة: {name}"}
    try:
        return REGISTRY[name](args or {})
    except Exception as e:  # noqa: BLE001 — نُرجع الخطأ كنتيجة، لا نكسر الحلقة
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
