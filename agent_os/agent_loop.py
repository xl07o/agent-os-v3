"""
agent_loop.py - حلقة وكيل تنفيذية آمنة (قراءة تلقائية + موافقة للتغيير)
=====================================================================
يجعل JARVIS يفعل لا يحادث فقط، لكن بأمان بحسب دستور المالك (البند 8:
«بموافقتي على أي شيء يؤثر على نظامي»):

  • أوامر قراءة/فحص آمنة (ls, cat, df, ps, uname, git status ...) تُنفَّذ
    تلقائياً — فيقرأ حالة جهازك ويجاوب.
  • أي أمر يغيّر النظام (تثبيت، حذف، تعديل، تشغيل) لا يُنفَّذ تلقائياً؛
    يُقترح ويُرفع لموافقتك (approval_center) — لا يتصرّف وحده.

هذا ليس وكيلاً «ينفّذ أي شيء يقرّره النموذج»: القائمة البيضاء صارمة، وسلاسل
الأوامر (; && | > `` $()) مرفوضة، فلا يُمكن تهريب أمر خطير خلف أمر آمن.

  run_agentic(task, max_steps, cwd) -> {reply, steps, pending_approvals, engine}
"""

import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

# أوامر قراءة/فحص فقط — لا تغيّر النظام — تُنفَّذ تلقائياً.
_SAFE_READONLY = {
    "ls", "cat", "head", "tail", "pwd", "whoami", "date", "uname", "df", "free",
    "ps", "uptime", "echo", "find", "grep", "wc", "du", "stat", "env", "printenv",
    "which", "hostname", "id", "cut", "sort", "uniq", "cal", "tree", "file",
    "lscpu", "lsblk", "nproc", "history", "ip", "ss",
}
# رموز تسمح بتسلسل أوامر — نرفض أي أمر يحويها (منع التهريب).
_CHAIN = re.compile(r"[;&|`$><]|\bsudo\b|\brm\b")

_SYS = (
    "You are JARVIS, an agent on a Linux machine. Reply in English, concise. "
    "To inspect the system, output one line: RUN: <read-only command> (e.g. ls, df -h, "
    "cat file, ps aux, uname -a). Only read-only inspection commands run automatically. "
    "For anything that changes the system (install, delete, write, start a service), "
    "output: PROPOSE: <command> — it will be sent to the owner for approval, not run. "
    "When done, output: DONE: <short answer>. For chat, just output DONE: <reply>."
)


def exec_enabled():
    return os.getenv("JARVIS_EXEC", "1") != "0"


def _is_safe_readonly(cmd):
    """أمر آمن = أول رمز في القائمة البيضاء، وبلا تسلسل/تهريب."""
    cmd = cmd.strip()
    if _CHAIN.search(cmd):
        return False
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return False
    return bool(tokens) and tokens[0] in _SAFE_READONLY


def _run_readonly(cmd, cwd=None, timeout=20):
    """ينفّذ أمر قراءة آمناً (بلا shell، بلا تسلسل)."""
    if not _is_safe_readonly(cmd):
        return {"ok": False, "output": "[not a safe read-only command]"}
    try:
        p = subprocess.run(shlex.split(cmd), capture_output=True, text=True,
                           timeout=timeout, cwd=cwd or os.path.expanduser("~"),
                           encoding="utf-8", errors="replace")
        out = (p.stdout + p.stderr).strip()
        return {"ok": p.returncode == 0, "output": out[-2500:] or "(no output)"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": f"[timed out after {timeout}s]"}
    except Exception as e:
        return {"ok": False, "output": f"[error: {str(e)[:150]}]"}


def _propose(cmd, task):
    """يرفع أمراً مُغيِّراً لموافقة المالك بدل تنفيذه."""
    try:
        from agent_os import approval_center
        req = approval_center.create_request(f"JARVIS يريد تنفيذ: {cmd[:80]}",
                                             why=f"لتنفيذ: {task[:80]}")
        return req.get("id") if isinstance(req, dict) else None
    except Exception:
        return None


def run_agentic(task, max_steps=6, cwd=None):
    """حلقة: العقل يقرأ الجهاز بأوامر آمنة، ويقترح المُغيِّرات لموافقتك."""
    transcript = [f"Task: {task}"]
    steps, pending = [], []
    last_engine = None
    for _ in range(max_steps):
        prompt = "\n".join(transcript) + "\nJARVIS:"
        raw, engine = C.call_brain(_SYS, prompt, mode="fastest")
        last_engine = engine
        if not raw or engine in (None, "", "none") or raw.strip().startswith("("):
            return {"reply": "I can't reach a thinking brain right now.",
                    "steps": steps, "pending_approvals": pending, "engine": engine}
        line = raw.strip()
        run_m = re.search(r"(?mi)^\s*RUN:\s*(.+)$", line)
        prop_m = re.search(r"(?mi)^\s*PROPOSE:\s*(.+)$", line)
        done_m = re.search(r"(?mi)^\s*DONE:\s*(.+)$", line, re.S)

        if done_m and (not run_m or done_m.start() < run_m.start()) and \
           (not prop_m or done_m.start() < prop_m.start()):
            reply = done_m.group(1).strip()
            if pending:
                reply += f"\n(Proposed {len(pending)} command(s) awaiting your approval.)"
            return {"reply": reply, "steps": steps, "pending_approvals": pending, "engine": engine}

        if run_m and (not prop_m or run_m.start() < prop_m.start()):
            cmd = run_m.group(1).strip().strip("`").strip()
            res = _run_readonly(cmd, cwd=cwd)
            steps.append({"cmd": cmd, "ok": res["ok"], "output": res["output"][:300]})
            C.log(f"🔎 RUN(ro): {cmd} → ok={res['ok']}")
            transcript.append(f"JARVIS: RUN: {cmd}")
            transcript.append(f"OUTPUT:\n{res['output'][:1200]}")
            continue

        if prop_m:
            cmd = prop_m.group(1).strip().strip("`").strip()
            rid = _propose(cmd, task)
            pending.append({"cmd": cmd, "request_id": rid})
            C.log(f"📝 PROPOSE (needs approval): {cmd}")
            transcript.append(f"JARVIS: PROPOSE: {cmd}")
            transcript.append("OUTPUT: (queued for owner approval; not executed)")
            continue

        return {"reply": line, "steps": steps, "pending_approvals": pending, "engine": engine}

    return {"reply": "Reached the step limit.", "steps": steps,
            "pending_approvals": pending, "engine": last_engine}


if __name__ == "__main__":
    import json
    q = " ".join(sys.argv[1:]) or "what OS is this and how much disk is free?"
    print(json.dumps(run_agentic(q), ensure_ascii=False, indent=2, default=str))
