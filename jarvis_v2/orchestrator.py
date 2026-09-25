# -*- coding: utf-8 -*-
"""حلقة جارفيس v2: الهدف ← خطة (عقل حقيقي) ← تنفيذ حقيقي باليَد ← تحقق ← تقرير بأدلة."""
import json
import os
import re
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # جذر المشروع
from brain import Brain  # noqa: E402

from . import config, evidence, honesty  # noqa: E402
from .tools import TOOLS, DESCRIPTIONS, run as tool_run  # noqa: E402

_PLAN_PROMPT = (
    "أنت عقل وكيل تنفيذ حقيقي على كمبيوتر المستخدم (Windows/PowerShell، جذر العمل: {base}).\n"
    "المهمة تساعدك أدوات حقيقية تُعدّل ملفات وتشغّل أوامر. القاعدة الذهبية: لا تختلق — "
    "قبل أي ادعاء ناجح يجب تنفيذ أداة حقيقية.\n"
    "ردّك يجب أن يكون JSON فقط (بلا صندوق، بلا نص خارجي) بهذا الشكل:\n"
    '{{"goal":"...", "steps":[{{"tool":"read_file|write_file|edit_file|glob|grep|bash|fetch_url",'
    '"args":{{...}}, "why":"لماذا هذه الخطوة"}}]}}\n'
    "اختر خطوات قليلة فاعلة (1-6). اقرأ ما تحتاجه أولاً. لكتابة/تعديل استخدم مسارات نسبية. "
    "للتحقق بعد الكتابة أضف خطوة bash آمنة مثل 'python -m py_compile <ملف>'.\n"
    "الأدوات: {tools}\n"
    "المهمة: قلب المهمة: {task}\n"
    "لا تكتب أي شيء غير JSON."
)


def _strip_fences(text):
    m = re.search(r"\{.*\}", text, re.S)
    return m.group(0) if m else text


def _parse_plan(text):
    cleaned = _strip_fences(text).strip()
    try:
        obj = json.loads(cleaned)
    except Exception:
        # محاولة استخراج من [[...]]
        m = re.search(r"\{.*\}", cleaned, re.S)
        obj = json.loads(m.group(0)) if m else None
    if not obj or not isinstance(obj, dict):
        raise ValueError("خطة غير صالحة من العقل")
    steps = obj.get("steps") or []
    return obj.get("goal", ""), steps


class Orchestrator:
    def __init__(self, approver=None):
        self.brain = None
        self.approver = approver

    def _get_brain(self):
        if self.brain is None:
            self.brain = Brain(_PLAN_PROMPT.replace("{base}", config.BASE))
        return self.brain

    def run(self, task):
        session = evidence.begin_session("مهمة: " + task[:60])
        goal = None
        steps = []
        # 1) الخطة من العقل
        try:
            plan_text, _ = self._get_brain().ask(_PLAN_PROMPT.format(
                base=config.BASE,
                tools=", ".join("%s(%s)" % (k, DESCRIPTIONS[k]) for k in TOOLS),
                task=task), mode=config.MODEL_MODE)
            goal, steps = _parse_plan(plan_text)
            evidence.append("plan", "brain", "ok" if steps else "fail",
                            note="خطة من العقل: %d خطوات" % len(steps), artifact=None)
        except Exception as ex:
            evidence.append("plan", "brain", "fail", note="الفشل في صنع الخطة: %s" % str(ex)[:200])
            goal, steps = task, []
            print("[بوابة الصدق] العقل عجز عن إنتاج خطة JSON صالحة: %s" % str(ex)[:150])

        if not steps:
            return {"session": session, "goal": goal or task, "steps": [],
                    "verdict": honesty.final_verdict([], task), "report": None}

        # 2) التنفيذ الحقيقي خطوة بخطوة
        results = []
        for i, step in enumerate(steps[: config.MAX_STEPS], 1):
            tool = step.get("tool")
            args = step.get("args") or {}
            why = step.get("why") or ""
            print("\n[{i}/{n}] {tool} — {why}".format(i=i, n=min(len(steps), config.MAX_STEPS),
                                                      tool=tool, why=why[:100]))
            try:
                res = tool_run(tool, args, self.approver)
            except Exception as ex:
                res = {"ok": False, "error": traceback.format_exc(limit=1).splitlines()[-1][:200]}
            status = "ok" if res.get("ok") else "fail"
            evidence.append("step", tool, status,
                            note="%s. %s" % (why, res.get("note") or res.get("error") or ""),
                            artifact=res.get("artifact"),
                            args=config.short_args(args), exit=res.get("exit"))
            out = res.get("stdout") or res.get("content") or res.get("matches") or res.get("error") or res.get("note") or ""
            if isinstance(out, (list, dict)):
                out = json.dumps(out, ensure_ascii=False)[:800]
            print(("  [%s] " % status.upper()) + str(out)[:600].replace("\n", " ")[:600])
            results.append({"tool": tool, "ok": res.get("ok"), "why": why, "note": status,
                            "cmd": (str((args or {}).get("command") or ""))[:1000],
                            "out": (str(res.get("stdout") or res.get("content") or ""))[:4000],
                            **({"error": res.get("error")} if not res.get("ok") else {})})
            if not res.get("ok"):
                # لا نواصل خطةً فشل منها عمودُها — أوقف وأفصح
                print("  ⛔ توقّف: خطوة فشلت — أتوقف ولا أدّعي المتابعة.")
                break

        # 3) التقرير الصادق + ملف
        verdict = honesty.final_verdict(results, task)
        report_path = self._write_report(task, goal, steps, results, verdict, session)
        evidence.append("report", "jarvis_v2", "ok",
                        note=verdict, artifact=report_path, goal=str(goal)[:200])
        print("\n" + "=" * 60)
        print("الحكم: " + verdict)
        if report_path:
            print("التقرير: %s" % report_path)
        return {"session": session, "goal": goal, "steps": results, "verdict": verdict,
                "report": report_path}

    def _write_report(self, task, goal, steps, results, verdict, session):
        path = os.path.join(config.EVID_DIR, "report_%s.md" % session)
        lines = ["# تقرير جارفيس v2 — %s" % session, "",
                 "**المهمة**: %s" % task, "",
                 "**الهدف المخطّط**: %s" % (goal or "-"), "",
                 "## الخطوات المنجزة (دليل حقيقي فقط)", ""]
        for r in results:
            mark = "✔" if r.get("ok") else "✘"
            lines.append("- %s **%s**: %s %s" % (mark, r.get("tool"), r.get("why"),
                                                 "" if r.get("ok") else "← " + str(r.get("error", ""))[:200]))
        lines += ["", "## الحكم الصادق", "", verdict, "",
                  "## سجل الإثبات", "ادعاء لا يسنده دليل أداة = حشو ولا يُكتب.",
                  "السجل: `%s`" % evidence.path()]
        if results:
            lines.append("أدلة فعلية: " + ", ".join(
                "`%s`" % a for a in evidence.since(session) if a.get("artifact") and a.get("status") == "ok"))
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return path
        except Exception:
            return None