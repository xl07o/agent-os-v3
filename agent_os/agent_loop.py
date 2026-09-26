"""
agent_loop.py - حلقة وكيل بأدوات: تجعل JARVIS واجهةً لكل قدرات Agent OS
=====================================================================
العقل (Groq/Ollama عبر brain) يقرّر أداةً كل خطوة، والحلقة تنفّذها فعلياً ثم
تعيد له الناتج حتى يكمل. قبل كل مهمة يستدعي ذاكرته (البنود 3/11/12) فيبني
على خبرته. الأدوات تربط الميزات الحقيقية:

  RECALL  <query>            ذاكرة طويلة الأمد (تجارب + معرفة)         [آمن]
  LEARN   <topic>            يتعلّم من الويب ويخزّنه (البند 1)          [آمن]
  FINANCE <idea>|<rev> <cost> <days>  جدوى فرصة (البند 7)             [آمن]
  REMEMBER<fact>             يخزّن معلومة كمرجع (البند 12)             [آمن]
  RUN     <read-only cmd>    يفحص الجهاز (ls/df/cat/ps/uname...)        [آمن]
  PROPOSE <cmd>              أمر يغيّر النظام → لموافقتك (البند 8)      [بموافقة]
  DONE    <answer>           ينهي / يردّ محادثة

الأمان: RUN قراءة فقط (قائمة بيضاء صارمة، بلا تسلسل/تهريب)؛ أي تغيير يُقترَح
ولا يُنفَّذ إلا بموافقتك. يُطفأ التنفيذ بـ JARVIS_EXEC=0 (محادثة فقط).
"""

import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

_SAFE_READONLY = {
    "ls", "cat", "head", "tail", "pwd", "whoami", "date", "uname", "df", "free",
    "ps", "uptime", "echo", "find", "grep", "wc", "du", "stat", "env", "printenv",
    "which", "hostname", "id", "cut", "sort", "uniq", "cal", "tree", "file",
    "lscpu", "lsblk", "nproc", "history", "ip", "ss",
}
_CHAIN = re.compile(r"[;&|`$><]|\bsudo\b|\brm\b")

_SYS = (
    "You are JARVIS, a capable AI agent+employee with real tools and long-term memory. "
    "Reply in English, concise. Each step output ONE line, one of:\n"
    "RECALL: <query>  (search your memory)\n"
    "LEARN: <topic>  (learn it from the web and store it)\n"
    "FINANCE: <idea> | <monthly_revenue> <cost> <effort_days>  (evaluate an opportunity)\n"
    "REMEMBER: <fact>  (store a fact)\n"
    "STATUS: -  (system readiness: brain, memory, voice)\n"
    "SCOPE: <host> | <scope1,scope2>  (security: is host in the authorized scope?)\n"
    "IMPROVE: -  (start a background self-improvement cycle)\n"
    "IDLE: -  (start a background self-learning cycle)\n"
    "RUN: <read-only shell command>  (inspect the machine)\n"
    "PROPOSE: <command>  (a system-changing command; sent to the owner for approval, not run)\n"
    "DONE: <final answer or chat reply>\n"
    "Use tools only when they help; for casual chat reply DONE directly. Never chain shell "
    "commands or use sudo/rm; long processes must be proposed, not run."
)


def exec_enabled():
    return os.getenv("JARVIS_EXEC", "1") != "0"


def _is_safe_readonly(cmd):
    cmd = cmd.strip()
    if _CHAIN.search(cmd):
        return False
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return False
    return bool(tokens) and tokens[0] in _SAFE_READONLY


def _run_readonly(cmd, cwd=None, timeout=20):
    if not _is_safe_readonly(cmd):
        return "[not a safe read-only command]"
    try:
        p = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=timeout,
                           cwd=cwd or os.path.expanduser("~"), encoding="utf-8", errors="replace")
        return ((p.stdout + p.stderr).strip()[-2500:]) or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[timed out after {timeout}s]"
    except Exception as e:
        return f"[error: {str(e)[:150]}]"


# ---- أدوات القدرات (كلها آمنة/غير مدمّرة) ----
def _tool_recall(q):
    try:
        from agent_os.memory import contextual_memory as cm, provenance
        hits = cm.recall(q, limit=3)
        out = [f"- {h.get('task', '')}: {h.get('solution', '')[:100]} ({h.get('outcome')})" for h in hits]
        p = provenance.get(q)
        if p:
            out.append(f"- fact: {str(p.get('value'))[:120]}")
        return "\n".join(out) if out else "(nothing relevant in memory)"
    except Exception as e:
        return f"[recall error: {str(e)[:100]}]"


def _tool_learn(topic):
    try:
        from agent_os.learn import ingest
        r = ingest.learn_query(topic)
        return (f"learned from {len(r.get('ingested', []))} sources about '{topic}'"
                if r.get("ok") else f"couldn't learn '{topic}' (no network/results)")
    except Exception as e:
        return f"[learn error: {str(e)[:100]}]"


def _tool_finance(spec):
    try:
        from agent_os import finance_brain
        idea, _, tail = spec.partition("|")
        nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", tail)]
        rev = nums[0] if nums else 0
        cost = nums[1] if len(nums) > 1 else 0
        days = nums[2] if len(nums) > 2 else 1
        r = finance_brain.evaluate(idea.strip() or "opportunity", cost_usd=cost,
                                   monthly_revenue_usd=rev, effort_days=days)
        return f"verdict={r['verdict']} roi={r['roi']} payback_days={r['payback_days']} — {r['reasons'][0]}"
    except Exception as e:
        return f"[finance error: {str(e)[:100]}]"


def _tool_remember(fact):
    try:
        from agent_os.memory import provenance, contextual_memory as cm
        provenance.record(f"note:{fact[:40]}", fact, source="user", confidence=0.9, kind="fact")
        cm.save_experience(task=fact[:120], approach="note", tools=[], problem="",
                           solution=fact, outcome="stored")
        return "stored to long-term memory"
    except Exception as e:
        return f"[remember error: {str(e)[:100]}]"


def _tool_status(_arg=""):
    try:
        from agent_os import ultra
        d = ultra.cmd_status(None)
        prov = d.get("brain_providers_available") or "none"
        m = d.get("memory", {})
        return (f"brain={prov} · knowledge={m.get('knowledge_items')} · "
                f"experiences={m.get('experiences')} · voice_ready={d.get('voice', {}).get('ready')}")
    except Exception as e:
        return f"[status error: {str(e)[:100]}]"


def _tool_scope(spec):
    """فحص نطاق أمني (البند 18): 'host | scope1,scope2' → مسموح أو مرفوض."""
    try:
        from agent_os import bounty_engine as be
        host, _, sc = spec.partition("|")
        scope = [s.strip() for s in sc.split(",") if s.strip()] or ["example.com"]
        ok, msg = be.in_scope({"scope": scope}, host.strip())
        return f"{'IN SCOPE ✓' if ok else 'OUT OF SCOPE 🚫'} — {msg}"
    except Exception as e:
        return f"[scope error: {str(e)[:100]}]"


def _tool_improve(_arg=""):
    """يشغّل دورة تحسين ذاتي في الخلفية (ثقيلة: sandbox + اختبارات) — البند 9/10."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        return "(self-improvement skipped under test)"
    import threading
    def _bg():
        try:
            from agent_os import self_improve_engine as sic
            sic.improve_once(quiet=True)
        except Exception:
            pass
    threading.Thread(target=_bg, daemon=True).start()
    return "started a self-improvement cycle in the background (sandbox + tests; applies only if green)"


def _tool_idle(_arg=""):
    """يشغّل دورة تعلّم ذاتي في الخلفية (البند 2)."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        return "(self-learning skipped under test)"
    import threading
    def _bg():
        try:
            from agent_os.learn import idle_learner
            from agent_os.memory import conversation
            goals = [p["topic"] for p in conversation.priorities(3)] or None
            idle_learner.idle_learn_cycle(owner_goals=goals)
        except Exception:
            pass
    threading.Thread(target=_bg, daemon=True).start()
    return "started a background self-learning cycle based on your priorities"


def _propose(cmd, task):
    try:
        from agent_os import approval_center
        req = approval_center.create_request(f"JARVIS wants to run: {cmd[:80]}", why=f"for: {task[:80]}")
        return req.get("id") if isinstance(req, dict) else None
    except Exception:
        return None


def _memory_context(task):
    """يستدعي الذاكرة قبل البدء — يبني على الخبرة (البنود 3/11/12)."""
    bits = []
    try:
        from agent_os.memory import contextual_memory as cm, conversation
        hits = cm.recall(task, limit=2)
        if hits:
            bits.append("Relevant memory: " + "; ".join(h.get("solution", "")[:70] for h in hits if h.get("solution")))
        pr = conversation.priorities(3)
        if pr:
            bits.append("Owner priorities: " + ", ".join(p["topic"] for p in pr))
    except Exception:
        pass
    return " | ".join(bits)


def run_agentic(task, max_steps=8, cwd=None):
    """حلقة أدوات: استدعاء ذاكرة → خطوات أدوات → جواب. يعيد ما فعله وما ينتظر موافقة."""
    ctx = _memory_context(task)
    transcript = ([f"(memory) {ctx}"] if ctx else []) + [f"Task: {task}"]
    steps, pending = [], []
    last_engine = None

    handlers = {
        "RECALL": _tool_recall, "LEARN": _tool_learn,
        "FINANCE": _tool_finance, "REMEMBER": _tool_remember,
        "STATUS": _tool_status, "SCOPE": _tool_scope,
        "IMPROVE": _tool_improve, "IDLE": _tool_idle,
    }

    for _ in range(max_steps):
        prompt = "\n".join(transcript) + "\nJARVIS:"
        raw, engine = C.call_brain(_SYS, prompt, mode="fastest")
        last_engine = engine
        if not raw or engine in (None, "", "none") or raw.strip().startswith("("):
            return {"reply": "I can't reach a thinking brain right now.",
                    "steps": steps, "pending_approvals": pending, "engine": engine}
        line = raw.strip()

        done_m = re.search(r"(?mi)^\s*DONE:\s*(.+)$", line, re.S)
        verb_m = re.search(r"(?mi)^\s*(RECALL|LEARN|FINANCE|REMEMBER|STATUS|SCOPE|IMPROVE|IDLE|RUN|PROPOSE):\s*(.*)$", line)

        # DONE قبل أي أداة → انتهى
        if done_m and (not verb_m or done_m.start() < verb_m.start()):
            reply = done_m.group(1).strip()
            if pending:
                reply += f"\n({len(pending)} command(s) await your approval.)"
            return {"reply": reply, "steps": steps, "pending_approvals": pending, "engine": engine}

        if verb_m:
            verb, arg = verb_m.group(1).upper(), verb_m.group(2).strip().strip("`").strip()
            if verb in handlers:
                result = handlers[verb](arg)
                steps.append({"tool": verb, "arg": arg[:60], "ok": True})
                C.log(f"🧰 {verb}: {arg[:60]}")
                transcript.append(f"JARVIS: {verb}: {arg}")
                transcript.append(f"RESULT:\n{result[:1200]}")
                continue
            if verb == "RUN":
                out = _run_readonly(arg, cwd=cwd)
                steps.append({"tool": "RUN", "arg": arg[:60], "ok": not out.startswith("[")})
                C.log(f"🔎 RUN(ro): {arg}")
                transcript.append(f"JARVIS: RUN: {arg}")
                transcript.append(f"OUTPUT:\n{out[:1200]}")
                continue
            if verb == "PROPOSE":
                rid = _propose(arg, task)
                pending.append({"cmd": arg, "request_id": rid})
                C.log(f"📝 PROPOSE (approval): {arg}")
                transcript.append(f"JARVIS: PROPOSE: {arg}")
                transcript.append("RESULT: (queued for owner approval; not executed)")
                continue

        return {"reply": line, "steps": steps, "pending_approvals": pending, "engine": engine}

    return {"reply": "Reached the step limit.", "steps": steps,
            "pending_approvals": pending, "engine": last_engine}


if __name__ == "__main__":
    import json
    q = " ".join(sys.argv[1:]) or "what OS is this and how much disk is free?"
    print(json.dumps(run_agentic(q), ensure_ascii=False, indent=2, default=str))
