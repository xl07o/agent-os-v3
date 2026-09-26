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
    "WRITE: <path> | <file content>  (create/write a file in the home folder — really does it)\n"
    "MKDIR: <path>  (create a folder in the home folder)\n"
    "OPEN: <url or site>  (open a website in the owner's browser, e.g. OPEN: youtube)\n"
    "STATUS: -  (system readiness: brain, memory, voice)\n"
    "TEST: <file or 'all'>  (run the project tests and report pass/fail)\n"
    "SCOPE: <host> | <scope1,scope2>  (security: is host in the authorized scope?)\n"
    "IMPROVE: -  (start a background self-improvement cycle)\n"
    "IDLE: -  (start a background self-learning cycle)\n"
    "RUN: <shell command>  (run a command; to OPEN a Windows program from WSL use "
    "'cmd.exe /c start <program>' e.g. RUN: cmd.exe /c start notepad)\n"
    "PROPOSE: <command>  (a system-changing command; sent to the owner for approval, not run)\n"
    "DONE: <final answer or chat reply>\n"
    "Use tools only when they help; for casual chat reply DONE directly. Never chain shell "
    "commands or use sudo/rm; long processes must be proposed, not run. "
    "IMPORTANT: before DONE, VERIFY your work — after WRITE re-read the file (RUN: cat <path>) "
    "to confirm it was written correctly; after an action, re-check the result once. Never "
    "claim success without checking."
)


def exec_enabled():
    return os.getenv("JARVIS_EXEC", "1") != "0"


def _brain_with_retry(sysmsg, prompt, tries=3):
    """يستدعي العقل مع إعادة محاولة قصيرة — يتجاوز فشل rate-limit اللحظي بدل
    الاستسلام بـ«لا عقل»."""
    import time as _t
    raw = engine = None
    for i in range(tries):
        raw, engine = C.call_brain(sysmsg, prompt, mode="fastest")
        if raw and engine not in (None, "", "none") and not raw.strip().startswith("("):
            return raw, engine
        if os.getenv("PYTEST_CURRENT_TEST"):
            break  # لا مهلات أثناء الاختبار
        _t.sleep(1.5 * (i + 1))  # مهلة قصيرة لتعافي الحد ثم إعادة المحاولة
    return raw, engine


def _allowed_cmds():
    """القائمة الآمنة + أي أوامر يضيفها المالك بنفسه عبر JARVIS_EXTRA_CMDS
    (قراره على جهازه). مثال: JARVIS_EXTRA_CMDS="git,mkdir,cp,mv,python3,pip,node,npm"."""
    base = set(_SAFE_READONLY)
    for c in re.split(r"[,\s]+", os.getenv("JARVIS_EXTRA_CMDS", "")):
        c = c.strip()
        if c:
            base.add(c)
    return base


def _is_safe_readonly(cmd):
    cmd = cmd.strip()
    if _CHAIN.search(cmd):   # منع التسلسل/التهريب يبقى دائماً (; && | > ` $ sudo rm)
        return False
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return False
    return bool(tokens) and tokens[0] in _allowed_cmds()


def _tool_test(target=""):
    """يشغّل فحوص المشروع عبر JARVIS ويعيد النتيجة (البند: تست لكل عملية)."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        return "(test tool skipped under test)"
    t = (target or "").strip()
    path = "tests/" if t.lower() in ("all", "full", "") else t
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", path, "-q", "-p", "no:cacheprovider"],
                           capture_output=True, text=True, timeout=180,
                           cwd=C.BASE_DIR, encoding="utf-8", errors="replace")
        lines = (p.stdout + p.stderr).strip().splitlines()
        tail = [ln for ln in lines if "passed" in ln or "failed" in ln or "error" in ln.lower()]
        return (tail[-1] if tail else (lines[-1] if lines else "(no output)"))
    except subprocess.TimeoutExpired:
        return "[tests timed out after 180s]"
    except Exception as e:
        return f"[test error: {str(e)[:120]}]"


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


_HOME = os.path.expanduser("~")


def _safe_home_path(rel):
    """يحصر المسار داخل مجلد المستخدم فقط (لا يخرج عنه) — أمان بالبناء."""
    rel = rel.strip().strip("`").strip()
    full = os.path.abspath(rel if os.path.isabs(rel) else os.path.join(_HOME, rel))
    try:
        if os.path.commonpath([_HOME, full]) != _HOME:
            return None
    except ValueError:
        return None
    return full


def _tool_write(spec):
    """ينشئ/يكتب ملفاً داخل مجلد المستخدم فقط (بلا shell، بلا تنفيذ) — «يسوّي» بأمان."""
    path, _, content = spec.partition("|")
    full = _safe_home_path(path)
    if not full:
        return "[refused: path must be inside your home folder]"
    try:
        os.makedirs(os.path.dirname(full) or _HOME, exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content.lstrip("\n"))
        return f"wrote {len(content)} chars to {full}"
    except Exception as e:
        return f"[write error: {str(e)[:120]}]"


def _tool_mkdir(path):
    """ينشئ مجلداً داخل مجلد المستخدم فقط."""
    full = _safe_home_path(path)
    if not full:
        return "[refused: path must be inside your home folder]"
    try:
        os.makedirs(full, exist_ok=True)
        return f"created folder {full}"
    except Exception as e:
        return f"[mkdir error: {str(e)[:120]}]"


def _normalize_url(target):
    """يحوّل «youtube» أو «youtube.com» أو رابطاً كاملاً إلى رابط http(s) صالح."""
    t = target.strip().strip("`").strip().strip("<>").strip()
    if not t:
        return None
    if t.startswith(("http://", "https://")):
        url = t
    elif "." in t.split()[0]:
        url = "https://" + t
    else:
        # كلمة مفردة (youtube/google) → موقعها المعروف
        url = f"https://www.{t.split()[0].lower()}.com"
    # تحقّق صارم: http(s) ومضيف معقول فقط (لا حقن)
    import urllib.parse as _up
    p = _up.urlparse(url)
    if p.scheme in ("http", "https") and re.match(r"^[A-Za-z0-9.\-]+(\:\d+)?$", p.netloc or ""):
        return url
    return None


def _tool_open(target):
    """يفتح موقعاً في متصفح المستخدم (ويندوز عبر WSL، أو Linux/Mac) — فتح رابط فقط، آمن."""
    url = _normalize_url(target)
    if not url:
        return f"[refused: '{target}' is not a valid http(s) URL]"
    import shutil
    # ويندوز عبر WSL أولاً، ثم مشغّلات Linux/Mac — نمرّر الرابط كوسيط واحد (بلا shell).
    openers = [["cmd.exe", "/c", "start", "", url], ["wslview", url],
               ["xdg-open", url], ["open", url]]
    for cmd in openers:
        exe = shutil.which(cmd[0]) or (cmd[0] if os.path.exists("/mnt/c") and cmd[0] == "cmd.exe" else None)
        if not exe:
            continue
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"opened {url} in your browser"
        except Exception:
            continue
    return f"[couldn't reach a browser launcher; URL is: {url}]"


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
        "WRITE": _tool_write, "MKDIR": _tool_mkdir, "OPEN": _tool_open,
        "STATUS": _tool_status, "SCOPE": _tool_scope, "TEST": _tool_test,
        "IMPROVE": _tool_improve, "IDLE": _tool_idle,
    }

    for _ in range(max_steps):
        prompt = "\n".join(transcript) + "\nJARVIS:"
        raw, engine = _brain_with_retry(_SYS, prompt)
        last_engine = engine
        if not raw or engine in (None, "", "none") or raw.strip().startswith("("):
            return {"reply": "My brain is briefly rate-limited. Give me a moment and try again, "
                             "or add another free key (OpenRouter/NVIDIA) to .env for backup.",
                    "steps": steps, "pending_approvals": pending, "engine": engine}
        line = raw.strip()

        done_m = re.search(r"(?mi)^\s*DONE:\s*(.+)$", line, re.S)
        verb_m = re.search(r"(?mi)^\s*(RECALL|LEARN|FINANCE|REMEMBER|WRITE|MKDIR|OPEN|STATUS|SCOPE|TEST|IMPROVE|IDLE|RUN|PROPOSE):\s*(.*)$", line, re.S)

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
