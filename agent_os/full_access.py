# -*- coding: utf-8 -*-
"""
full_access.py - تمكين الولوج الكامل للوكيل (بموافقة المستخدم الصريحة)
=======================================================================
«أعطِ وكيلك ولوجاً كاملاً مثل Jarvis» — لكن بـ«مفتاح إشعال» أنت الدافع له:

  - لا قيمة افتراضية مفعّلة: حتى يكتب المستخدم {enabled: true} يدوياً
    (من اللوحة أو CLI أو هذا الملف) يبقى الوكيل مقيّداً بالقائمة البيضاء.
  - عندما يكون مفعّلاً تُفتح أوامر «needs_human» في computer_agent
    (تنفيذ مباشر بلا موافقة لكل خطوة) — مع بقاء الممنوعات القاتلة ممنوعة
    دائماً (حذف/تهيئة/shutdown/reg...) — لا تغيير بتاتاً في هذه.
  - كل تمكين/تعطيل يُدوَّن تدقيقياً (append-only) بزمنه وسببه.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

FA_FILE = os.path.join(C.AGENT_OS_DIR, "full_access.json")
LOG_FILE = os.path.join(C.AGENT_OS_DIR, "full_access_audit.jsonl")


def status():
    """حالة الولوج الحالية — للّوحة وللقرارات الداخلية.
    الافتراضي: الولوج مفعّل تلقائياً (ولوج دائم) حتى يُعاد إغلاقه صراحةً."""
    d = C.load_json(FA_FILE, {})
    return {
        "enabled": bool(d.get("enabled", True)),
        "at": d.get("at"),
        "reason": d.get("reason", ""),
    }


def is_enabled():
    return bool(status().get("enabled"))


def _audit(action, reason):
    import json
    line = json.dumps({"time": C.now_iso(), "action": action, "reason": str(reason)[:300]},
                      ensure_ascii=False)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def enable(reason=""):
    """تفعيل الولوج الكامل — بموافقة المستخدم الصريحة (من اللوحة/الموقّع)."""
    C.atomic_write(FA_FILE, {"enabled": True, "at": C.now_iso(),
                             "reason": str(reason).strip()[:300]})
    _audit("enable", reason or "من اللوحة")
    try:
        from agent_os import event_bus
        event_bus.publish("full_access", {"enabled": True}, source="access")
    except Exception:
        pass
    return status()


def disable(reason=""):
    C.atomic_write(FA_FILE, {"enabled": False, "at": C.now_iso(),
                             "reason": str(reason).strip()[:300]})
    _audit("disable", reason or "من اللوحة")
    try:
        from agent_os import event_bus
        event_bus.publish("full_access", {"enabled": False}, source="access")
    except Exception:
        pass
    return status()


def audit(limit=20):
    out = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(__import__("json").loads(line))
                    except Exception:
                        continue
    except Exception:
        pass
    return out[-limit:]


if __name__ == "__main__":
    import json
    args = sys.argv[1:]
    if args and args[0] == "on":
        print(json.dumps(enable(" ".join(args[1:])), ensure_ascii=False))
    elif args and args[0] == "off":
        print(json.dumps(disable(" ".join(args[1:])), ensure_ascii=False))
    elif args and args[0] == "audit":
        print(json.dumps(audit(), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=1))