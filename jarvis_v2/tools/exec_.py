# -*- coding: utf-8 -*-
"""تشغيل أوامر PowerShell حقيقية — التقاط stdout/stderr/رمز الخروج. على المستخدم تأكيد المخاطر."""
import os
import subprocess

from .. import config

def run_bash(args):
    cmd = args.get("command") if isinstance(args, dict) else args
    if not cmd or not isinstance(cmd, str):
        return {"ok": False, "error": "تحتاج command نصّياً"}
    # قيود حماية إجبارية — لا نحذف جذوراً ولا بيانات زبائن
    low = cmd.strip().lower()
    for guard in ("remove-item", "rm -r", "rmdir /s", "del /f /q", "format "):
        if low.startswith(guard):
            return {"ok": False, "error": "أمر محظور في هذه الطبقة: %s" % guard}
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; " + cmd],
            capture_output=True, text=True, timeout=config.BASH_TIMEOUT,
            cwd=config.BASE, encoding="utf-8", errors="replace")
        out = (p.stdout or "")[:8000]
        err = (p.stderr or "")[:2000]
        return {"ok": p.returncode == 0, "exit": p.returncode, "stdout": out, "stderr": err,
                "note": "خرج بوضع %d" % p.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "انتهت المهلة (%s ث)" % config.BASH_TIMEOUT}
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:300]}