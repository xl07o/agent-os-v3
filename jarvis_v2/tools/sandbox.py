# -*- coding: utf-8 -*-
"""أداة sandbox محوسب — تمدّ Hermes بيدين حقيقيتين، لكن دائماً داخل sandbox
Daytona معزول تماماً عن هذا الجهاز (agent_os/computer_sandbox.py). نفس قاعدة
المشروع: لا صدفة غير مقيدة على الجهاز الحقيقي — أبداً."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import computer_sandbox as _cs  # noqa: E402


def sandbox_create(args):
    label = (args.get("label") if isinstance(args, dict) else None) or "hermes"
    sb_id = _cs.create(label=str(label)[:40])
    return {"ok": True, "sandbox_id": sb_id, "note": "sandbox جديد ومعزول"}


def sandbox_bash(args):
    if not isinstance(args, dict) or not args.get("sandbox_id") or not args.get("command"):
        return {"ok": False, "error": "يحتاج sandbox_id و command"}
    result = _cs.run_bash(args["sandbox_id"], args["command"])
    return {"ok": True, "exit_code": result.get("exit_code"), "output": str(result.get("output", ""))[:2000]}


def sandbox_screenshot(args):
    if not isinstance(args, dict) or not args.get("sandbox_id"):
        return {"ok": False, "error": "يحتاج sandbox_id"}
    png = _cs.screenshot(args["sandbox_id"])
    return {"ok": True, "bytes": len(png) if png else 0, "note": "لقطة شاشة أُخذت من داخل الـsandbox"}


def sandbox_click(args):
    if not isinstance(args, dict) or "x" not in args or "y" not in args or not args.get("sandbox_id"):
        return {"ok": False, "error": "يحتاج sandbox_id و x و y"}
    _cs.click(args["sandbox_id"], int(args["x"]), int(args["y"]))
    return {"ok": True, "note": "كليك ok"}


def sandbox_type(args):
    if not isinstance(args, dict) or not args.get("sandbox_id") or "text" not in args:
        return {"ok": False, "error": "يحتاج sandbox_id و text"}
    _cs.type_text(args["sandbox_id"], str(args["text"]))
    return {"ok": True, "note": "كتابة ok"}


def sandbox_destroy(args):
    if not isinstance(args, dict) or not args.get("sandbox_id"):
        return {"ok": False, "error": "يحتاج sandbox_id"}
    _cs.destroy(args["sandbox_id"])
    return {"ok": True, "note": "sandbox دُمِّر"}


def sandbox_list(args):
    return {"ok": True, "active": _cs.active_sandboxes()}
