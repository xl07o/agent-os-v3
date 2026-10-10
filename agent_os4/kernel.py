"""
نقطة الدخول الوحيدة. حلقة واحدة: خطة من العقل ← تنفيذ أدوات حقيقية ←
تحقق مستقل من الدليل ← توقف عند أول فشل أو طلب معلّق ← تقرير صادق.
ما فيه "عقول" متعددة ولا مسار يتجاوز بوابة الموافقة.

interactive=True (الافتراضي، يناسب cli.py): يحجب على input() بالطرفية
عند أي خطوة تحتاج موافقة — نفس السلوك القديم تماماً.
interactive=False (يناسب web_chat.py): لا يحجب أي خيط أبداً — يحفظ
مكانه بالضبط ويرجع فوراً بـ"pending_request_id"؛ resume_task() يكمل من
هناك حرفياً بعد ما تُحسم الموافقة خارجياً، لا يعيد الخطة من الصفر. هذا
أول "Durable Workflow Engine" حقيقي بالنظام — بُني لأنه احتاجه web_chat
فعلياً، لا تخميناً.
"""

import json
import os
import re

from . import approval, brain, decision, evidence, memory, obsidian, tools

_PLAN_PROMPT = """أنت وكيل تنفيذ حقيقي. لديك هذه الأدوات فقط:
- read_file(path), write_file(path, content), list_workspace()
- run_command(command)
- sandbox_create(label), sandbox_bash(sandbox_id, command), sandbox_destroy(sandbox_id)
- browser_screenshot(url, filename) — لقطة شاشة فقط، بدون أي تفاعل مع الصفحة

ردّك JSON فقط بهذا الشكل، بلا أي نص خارجي:
{{"steps": [{{"tool": "...", "args": {{...}}, "why": "..."}}]}}

لو المهمة محادثة عادية بلا حاجة لأي أداة، أرجع: {{"steps": []}}

المهمة: {task}"""

# أي أداة لها أثر فعلي أو تخرج للإنترنت (كتابة/تنفيذ/sandbox/تصفح) —
# تحتاج موافقة. القراءة المحلية فقط (read_file, list_workspace) تلقائية.
NEEDS_APPROVAL = {"write_file", "run_command", "sandbox_create", "sandbox_bash", "browser_screenshot"}

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_PENDING_FILE = os.path.join(_DATA_DIR, "pending_tasks.json")


def _parse_plan(text: str) -> list[dict]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return []
    try:
        return json.loads(match.group(0)).get("steps", [])
    except (json.JSONDecodeError, AttributeError):
        return []


def _ask_human(what: str, why: str, extra: str | None = None) -> bool:
    print(f"\n⚠️  يحتاج موافقتك: {what}\n   السبب: {why}")
    if extra:
        print(f"   رأي المراجع المستقل: {extra}")
    return input("   موافق؟ (y/n): ").strip().lower() == "y"


def _load_pending() -> dict:
    if not os.path.exists(_PENDING_FILE):
        return {}
    with open(_PENDING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_pending(data: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _PENDING_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _PENDING_FILE)


def _run_tool_with_evidence_check(tool: str, args: dict) -> dict:
    result = tools.run(tool, args)
    if tool == "write_file" and result.get("ok"):
        # False Success Detector: لا نصدّق "ok": True من الأداة نفسها —
        # نعيد قراءة الملف من القرص فعلياً ونقارنه بما اتدّعى كتابته.
        check = evidence.verify_write(result["path"], args.get("content", ""))
        if not check["verified"]:
            result = {"ok": False, "error": f"فشل التحقق المستقل: {check['reason']}"}
    return result


def _finalize(task: str, results: list[dict], proposed_by: str) -> dict:
    fails = [r for r in results if not r["ok"]]
    if not results:
        verdict = "لم يتم — صفر خطوات"
    elif not fails:
        verdict = f"تمام — {len(results)} خطوات نجحت كلها"
    else:
        verdict = f"جزئي — {len(results) - len(fails)}/{len(results)} نجحت"

    obsidian.write_note("projects", task[:60], f"**الحكم:** {verdict}\n\n" + json.dumps(results, ensure_ascii=False, indent=2), tags=["os4", proposed_by])
    memory.remember(f"مهمة[{proposed_by}]: {task} → {verdict}", source="task")
    return {"goal": task, "steps": results, "verdict": verdict}


def _execute_steps(
    task: str,
    steps: list[dict],
    start_index: int,
    results: list[dict],
    persona: str | None,
    allowed_tools: set[str] | None,
    proposed_by: str,
    interactive: bool,
) -> dict:
    for i in range(start_index, len(steps)):
        step = steps[i]
        tool, args, why = step.get("tool", ""), step.get("args") or {}, step.get("why", "")
        if allowed_tools is not None and tool not in allowed_tools:
            results.append({"tool": tool, "ok": False, "error": f"أداة غير مسموحة لهذا الدور: {tool}"})
            break
        if tool in NEEDS_APPROVAL:
            proposal = decision.propose(what=f"{tool}({args})", why=why, proposed_by=proposed_by)
            req_id = proposal["request_id"]
            if interactive:
                approved = _ask_human(f"{tool}({args})", why, extra=proposal.get("independent_review"))
            else:
                # غير تفاعلي: لا نحجب أي خيط بـinput() أبداً. نحفظ الحالة
                # كاملة ونرجع فوراً — resume_task() يكمل من نفس النقطة
                # حرفياً بعد ما تُحسم الموافقة من مكان آخر (مثلاً web_chat).
                pending = _load_pending()
                pending[req_id] = {
                    "task": task, "steps": steps, "index": i, "results": results,
                    "persona": persona,
                    "allowed_tools": sorted(allowed_tools) if allowed_tools is not None else None,
                    "proposed_by": proposed_by,
                }
                _save_pending(pending)
                return {
                    "goal": task, "steps": results, "verdict": "معلّق — بانتظار موافقتك",
                    "pending_request_id": req_id, "what": f"{tool}({args})", "why": why,
                    "independent_review": proposal.get("independent_review"),
                }
            if not approved:
                decision.reject(req_id, decided_by="owner", reason="رفض المستخدم")
                results.append({"tool": tool, "ok": False, "error": "رفض المستخدم"})
                break
            decision.approve(req_id, decided_by="owner")
        result = _run_tool_with_evidence_check(tool, args)
        results.append({"tool": tool, "ok": result.get("ok"), "why": why, "result": result})
        if not result.get("ok"):
            break  # لا نكمل خطة فشلت منها خطوة — لا ادّعاء نجاح

    return _finalize(task, results, proposed_by)


def run_task(
    task: str,
    persona: str | None = None,
    allowed_tools: set[str] | None = None,
    proposed_by: str = "owner",
    interactive: bool = True,
) -> dict:
    """
    persona: تُضاف فوق المهمة قبل أي استدعاء للمخ — تُستخدم من bots.py
    لتخصيص شخصية بوت معيّن، نفس الحلقة بالضبط.
    allowed_tools: لو مُمرَّرة، أي خطوة بأداة خارجها تُرفض فوراً قبل أي
    تنفيذ — تحصر بوتاً بما يحتاج له فعلاً، لا كل الأدوات المتاحة.
    proposed_by: يُسجَّل بـdecision.ledger() — "owner" للمهام المباشرة
    من CLI، أو اسم بوت من bots.py.
    interactive: False لواجهة لا تقدر تحجب على input() (مثل web_chat) —
    راجع resume_task().
    """
    prompt_task = f"{persona}\n\nالمهمة: {task}" if persona else task
    plan_text = brain.ask(_PLAN_PROMPT.format(task=prompt_task))
    steps = _parse_plan(plan_text)

    if not steps:
        reply = brain.ask(prompt_task)
        memory.remember(task, source=proposed_by)
        memory.remember(reply, source="agent")
        return {"goal": task, "steps": [], "verdict": "محادثة — بلا تنفيذ أدوات", "reply": reply}

    return _execute_steps(task, steps, 0, [], persona, allowed_tools, proposed_by, interactive)


def resume_task(request_id: str) -> dict:
    """تُستدعى بعد ما طلب معلّق من run_task(interactive=False) يُحسم
    (decision.approve/reject) — تكمل باقي الخطة من حيث وقفت بالضبط، لا
    تعيدها من الصفر ولا تكرر خطوات نُفِّذت فعلاً."""
    record = approval.get(request_id)
    if not record:
        return {"ok": False, "error": "طلب غير موجود"}

    pending = _load_pending()
    state = pending.get(request_id)
    if not state:
        return {"ok": False, "error": "لا حالة معلّقة محفوظة لهذا الطلب"}

    if record["status"] == "pending":
        return {"ok": False, "error": "الطلب لسا معلّقاً — وافق أو ارفض أولاً"}

    del pending[request_id]
    _save_pending(pending)

    allowed_tools = set(state["allowed_tools"]) if state["allowed_tools"] is not None else None

    if record["status"] != "approved":
        results = state["results"] + [{"tool": state["steps"][state["index"]].get("tool", ""), "ok": False, "error": "رفض المستخدم"}]
        return _finalize(state["task"], results, state["proposed_by"])

    step = state["steps"][state["index"]]
    tool, args, why = step.get("tool", ""), step.get("args") or {}, step.get("why", "")
    result = _run_tool_with_evidence_check(tool, args)
    results = state["results"] + [{"tool": tool, "ok": result.get("ok"), "why": why, "result": result}]
    if not result.get("ok"):
        return _finalize(state["task"], results, state["proposed_by"])

    return _execute_steps(
        state["task"], state["steps"], state["index"] + 1, results,
        state.get("persona"), allowed_tools, state["proposed_by"], interactive=False,
    )


def pending_tasks() -> list[dict]:
    """لعرض/تشخيص فقط — المهام المعلّقة بانتظار موافقة عبر resume_task()."""
    return [{"request_id": k, "task": v["task"], "proposed_by": v["proposed_by"]} for k, v in _load_pending().items()]
