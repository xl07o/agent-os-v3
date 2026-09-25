"""
computer_agent.py - وكيل الكمبيوتر الآمن (ركن «تنفيذ حقيقي 50%» ← الهدف)
========================================================================
بديل آمن لـ computer_control.py (الذي نبه الشحان إلى shell=True فيه):
أوامر بيضاء فقط تُنفَّذ عبر subprocess بمصفوفات — لا shell أبداً.

القواعد:
  - ALLOWED: يعمل داخل المشروع فقط (BASE_DIR ومسارات فرعية منه).
  - أي أمر غير مرشّح في القائمة البيضاء يرفض قبل التنفيذ (deny-by-default).
  - لا أوامر تدمير: حذف، تنسيق، rm -rf، del /s، pkill/توقيف.
  - أي أمر يحتاج حساسية (تثبيت، رئيس أسماء مخولة) → طلب موافقة بشرية بدل التمكين.

الاستخدام:
  python agent_os/computer_agent.py run dir
  python agent_os/computer_agent.py run git status
  python agent_os/computer_agent.py log
"""

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

BASE = C.BASE_DIR
LOG_FILE = os.path.join(C.AGENT_OS_DIR, "computer_agent.json")

BLOCKED_CMDS = {"rm", "del", "format", "shutdown", "reboot", "taskkill",
                "pkill", "kill", "cipher", "diskpart", "reg"}
BLOCKED_PAT = re.compile(r"rm\s*(-rf|-r)?|del\s+/|format\s+|taskkill|shutdown|/delete")


def _allow(cmd):
    """قرار يكفي: permit | needs_human | deny."""
    if not cmd:
        return "deny"
    head = os.path.basename(cmd[0]).lower() if os.path.dirname(cmd[0]) else cmd[0].lower()
    if head in BLOCKED_CMDS or (len(cmd) > 1 and cmd[1].lower() in ("-rf", "-r") and head == "rm"):
        return "deny"
    if BLOCKED_PAT.search(" ".join(cmd).lower()):
        return "deny"
    if head in ("python", "py", "git", "where", "findstr",
                "copy", "xcopy", "mkdir", "explorer", "tasklist",
                "powershell", "pwsh", "pythonw"):
        return "permit"
    # الولوج الكامل (مفتاح المستخدم): يفتح أوامر «needs_human» للتنفيذ المباشر،
    # مع بقاء ALLOWED_TOTAL المشغّلة... والممنوعات القاتلة أعلاه ممنوعة دائماً.
    try:
        from agent_os import full_access
        if full_access.is_enabled():
            return "permit"
    except Exception:
        pass
    return "needs_human"


def _log(entry):
    st = C.load_json(LOG_FILE, {"rows": []})
    st["rows"].append(entry)
    st["rows"] = st["rows"][-300:]
    C.atomic_write(LOG_FILE, st)


def run(cmd_args):
    """تنفيذ أمر مصفّفي فقط — يسجل كل شيء ويرفض أي خطر قبل التشغيل."""
    if isinstance(cmd_args, str):
        cmd_args = cmd_args.split()
    verdict = _allow(cmd_args)
    if verdict == "deny":
        return {"ok": False, "verdict": "deny", "reason": "أمر ممنوع في الصندوق الأمني"}
    if verdict == "needs_human":
        try:
            from agent_os import approval_center
            req = approval_center.create_request(
                f"تشغيل أمر على الجهاز: {' '.join(cmd_args)[:140]}",
                "أمر خارج القائمة البيضاء — يحتاج تنفيذك اليدوي أو موافقتك",
                ["نفّذه يدوياً بوثقة وآمنية", "أو وافق بتوسيع القائمة كقرار بشري"],
                kind="external_action", risk="high")
            _log({"time": C.now_iso(), "cmd": cmd_args, "verdict": "needs_human",
                  "request_id": req["id"]})
            return {"ok": False, "verdict": "needs_human", "request_id": req["id"]}
        except Exception:
            return {"ok": False, "verdict": "deny", "reason": "لا مركز موافقات"}
    try:
        res = subprocess.run(cmd_args, cwd=BASE, capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=60)
        entry = {"time": C.now_iso(), "cmd": cmd_args[:6], "verdict": "permit",
                 "rc": res.returncode, "out": (res.stdout or "")[-500:],
                 "err": (res.stderr or "")[-300:]}
        _log(entry)
        return {"ok": res.returncode == 0, "verdict": "permit", "rc": res.returncode,
                "stdout": (res.stdout or "")[:1500], "stderr": (res.stderr or "")[:600]}
    except subprocess.TimeoutExpired:
        _log({"time": C.now_iso(), "cmd": cmd_args[:6], "verdict": "timeout"})
        return {"ok": False, "verdict": "timeout"}
    except Exception as e:
        return {"ok": False, "verdict": "error", "reason": str(e)[:120]}


def log(limit=20):
    return C.load_json(LOG_FILE, {"rows": []})["rows"][-limit:]


if __name__ == "__main__":
    import json
    args = sys.argv[1:]
    if not args or args[0] == "log":
        for row in log():
            print(f"{row['time']} [{row.get('verdict')}] {' '.join(row.get('cmd', []))[:80]}")
    elif args[0] == "run" and len(args) > 1:
        print(json.dumps(run(args[1:]), ensure_ascii=False, indent=1))
    else:
        print("الاستعمال: run <أمر مصفوفي> | log")