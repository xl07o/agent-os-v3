"""
نقطة الدخول الوحيدة. حلقة واحدة: خطة من العقل ← تنفيذ أدوات حقيقية ←
توقف عند أول فشل أو طلب معلّق ← تقرير صادق بالدليل فقط. ما فيه "عقول"
متعددة ولا مسار يتجاوز بوابة الموافقة.
"""

import json
import re

from . import brain, decision, evidence, memory, obsidian, tools

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


def run_task(
    task: str,
    persona: str | None = None,
    allowed_tools: set[str] | None = None,
    proposed_by: str = "owner",
) -> dict:
    """
    persona: تُضاف فوق المهمة قبل أي استدعاء للمخ — تُستخدم من bots.py
    لتخصيص شخصية بوت معيّن، نفس الحلقة بالضبط.
    allowed_tools: لو مُمرَّرة، أي خطوة بأداة خارجها تُرفض فوراً قبل أي
    تنفيذ — تحصر بوتاً بما يحتاج له فعلاً، لا كل الأدوات المتاحة.
    proposed_by: يُسجَّل بـdecision.ledger() — "owner" للمهام المباشرة
    من CLI، أو اسم بوت من bots.py.
    """
    prompt_task = f"{persona}\n\nالمهمة: {task}" if persona else task
    plan_text = brain.ask(_PLAN_PROMPT.format(task=prompt_task))
    steps = _parse_plan(plan_text)

    if not steps:
        reply = brain.ask(prompt_task)
        memory.remember(task, source=proposed_by)
        memory.remember(reply, source="agent")
        return {"goal": task, "steps": [], "verdict": "محادثة — بلا تنفيذ أدوات", "reply": reply}

    results = []
    for step in steps:
        tool, args, why = step.get("tool", ""), step.get("args") or {}, step.get("why", "")
        if allowed_tools is not None and tool not in allowed_tools:
            results.append({"tool": tool, "ok": False, "error": f"أداة غير مسموحة لهذا الدور: {tool}"})
            break
        if tool in NEEDS_APPROVAL:
            proposal = decision.propose(what=f"{tool}({args})", why=why, proposed_by=proposed_by)
            req_id = proposal["request_id"]
            if not _ask_human(f"{tool}({args})", why, extra=proposal.get("independent_review")):
                decision.reject(req_id, decided_by="owner", reason="رفض المستخدم")
                results.append({"tool": tool, "ok": False, "error": "رفض المستخدم"})
                break
            decision.approve(req_id, decided_by="owner")
        result = tools.run(tool, args)
        if tool == "write_file" and result.get("ok"):
            # False Success Detector: لا نصدّق "ok": True من الأداة نفسها
            # — نعيد قراءة الملف من القرص فعلياً ونقارنه بما اتدّعى كتابته.
            check = evidence.verify_write(result["path"], args.get("content", ""))
            if not check["verified"]:
                result = {"ok": False, "error": f"فشل التحقق المستقل: {check['reason']}"}
        results.append({"tool": tool, "ok": result.get("ok"), "why": why, "result": result})
        if not result.get("ok"):
            break  # لا نكمل خطة فشلت منها خطوة — لا ادّعاء نجاح

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
