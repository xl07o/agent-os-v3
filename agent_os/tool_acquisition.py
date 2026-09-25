"""
tool_acquisition.py - اكتساب الأدوات والقدرات (اكتشاف → طلب موافقة → تسجيل)
============================================================================
اكتشاف أدوات مشروعة (متوفرة أو قابلة للتثبيت) وتسجيلها في سجل الأدوات.

  - يكتشف الموجود (where) بلا تثبيت.
  - المطلوب الغائب يتحول طلب human (external_action) لا تثبيت صامت.
  - يسجل ما اكتُسب في tool_registry.REGISTRY_FILE كقدرة.

الاستخدام:
  python agent_os/tool_acquisition.py discover
  python agent_os/tool_acquisition.py require git
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

KNOWN = {
    "python": ["python", "--version"],
    "git": ["git", "--version"],
    "node": ["node", "--version"],
    "npm": ["npm", "--version"],
    "ffmpeg": ["ffmpeg", "-version"],
    "curl": ["curl", "--version"],
    "tar": ["tar", "--version"],
}


def discover():
    """افحص الأدوات المعروفة وسجّل الحالة — بلا أي تثبيت."""
    found, missing = [], []
    for tool in KNOWN:
        if shutil.which(tool):
            found.append(tool)
        else:
            missing.append(tool)
    record = {"time": C.now_iso(), "found": found, "missing": missing}
    st = C.load_json(os.path.join(C.AGENT_OS_DIR, "tool_discovery.json"), {"rows": []})
    st["rows"].append(record)
    st["rows"] = st["rows"][-50:]
    C.atomic_write(os.path.join(C.AGENT_OS_DIR, "tool_discovery.json"), st)
    return record


def require(tool):
    """طلب أداة غائبة: يحوَّل إلى موافقة بشرية (لا تثبيت صامت أبداً)."""
    if shutil.which(tool):
        return {"ok": True, "tool": tool, "present": True}
    try:
        from agent_os import approval_center
        req = approval_center.create_request(
            f"تثبيت أداة {tool} على الجهاز",
            "أداة غائبة مطلوبة لقدرة جديدة — تثبيت يتطلب قرارك البشري",
            [f"شغّل: pip/installer المناسب", f"أو ارفض وبقيت قدرة الأداة غير مسجلة"],
            kind="external_action", risk="medium")
        return {"ok": False, "tool": tool, "present": False,
                "request_id": req["id"], "note": "طلب موافقة أُنشئ"}
    except Exception as e:
        return {"ok": False, "tool": tool, "present": False, "reason": str(e)[:120]}


def register_capability(name, description, needs_tool=None):
    """سجّل قدرة في سجل الأدوات إن كانت أداتها متوفرة — القائمة البيضاء الداخلية."""
    if needs_tool and not shutil.which(needs_tool):
        return {"ok": False, "reason": f"الأداة {needs_tool} غير متوفرة"}
    try:
        from agent_os import tool_registry
        return tool_registry.register(name, description, "import os\n# قدرة مسجلة بلا كود حي")
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120]}


if __name__ == "__main__":
    import json
    args = sys.argv[1:]
    if not args or args[0] == "discover":
        r = discover()
        print(f"متوفرة: {r['found']} | غائبة: {r['missing']}")
    elif args[0] == "require" and len(args) > 1:
        print(json.dumps(require(args[1]), ensure_ascii=False, indent=1))
    else:
        print("الاستعمال: discover | require <أداة>")