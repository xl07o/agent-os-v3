"""
agent_os.py - نواة Agent OS: الموجّه (v3.0)
=============================================
السلسلة الكاملة لكل مهمة:

    ROUTER -> PLANNER -> EXECUTOR -> CRITIC -> VERIFIER

  روتير:   يصفّي القصد (بحث/برمجة/بناء/تشغيل/تقرير/استشاري)
  مُخطِّط:  يخرج خطوات قابلة للتنفيذ
  مُنفِّذ:  ينفذها عبر الأنظمة الفرعية (كلها بلا shell)
  ناقد:    يفحص النتائج ضد الأخطاء واحترام القيود الأمنية
  محقق:    يقرر القبول / إعادة مراجعة / إمساك إنسان

يعمل دون شبكة: جميع الأنظمة الفرعية بديلة حتمية عند غياب الدماغ.

الاستخدام:
  python agent_os/agent_os.py run "مهمة"
  python agent_os/agent_os.py systems
  python agent_os/agent_os.py status
"""

import os
import re
import sys
import html as _html
import urllib.parse
import datetime
import random as _random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

RUNS_FILE = os.path.join(C.AGENT_OS_DIR, "nucleus_runs.json")

# روتير: تصنيف القصد من عبارات.
INTENT_KEYWORDS = {
    "research": ["ابحث", "بحث", "تحقيق", "استطلاع", "فكرة", "مقترح", "معلومة"],
    "code": ["اكتب", "برمج", "كود", "إصلاح", "ميزة", "دالة", "module", "normalize", "bug"],
    "build": ["ابنِ", "منتج", "مشروع", "نشر", "deploy", "MVP", "لوحة", "تطبيق"],
    "operate": ["شغّل", "نفّذ", "أتمتة", "جدولة", "مراقبة", "تشغيل", "سجل هدف", "سجّل هدف", "هدف", "خطة", "أهداف", "خطط", "خطة عمل"],
    "open": ["افتح", "اِفتح", "فتح", "موقع", "المتصفح", "اذهب إلى", "روّح", "open"],
    "device": ["شغّل", "شغل", "تشغيل", "أغلق", "أوقف", "أطفئ", "تحكم", "افحص", "العمليات", "جهازي", "افتح ملف", "افتح مجلد", "افتح برنامج", "إدارة المهام", "ادارة المهام", "رن"],
    "finance": ["إيراد", "مصروف", "ربح", "مالية", "فورة", "دخل", "$"],
    "report": ["تقرير", "ملخص", "brief", "حالة", "ملاح HTML", "توثيق", "وثّق", "وثق", "وثّق", "دليل", "شرح", "readme", "معالجة"],
    "security": ["ثغرة", "بجتي", "bounty", "باونتي", "bug bounty", "نطاق", "اختبار أمن", "vulnerability", "بواج", "باقتي"],
    "improve": ["حسّن", "تطوير ذاتي", "تحسين", "self", "قياس", "أطور", "طور", "طورني", "اطور", "نفسي", "تحسين ذاتي"],
    "learn": ["تعلّم", "تعلم", "اتعلم", "استوعب", "ادرس", "درّب نفسك", "learn", "اقرأ عن", "تثقّف", "تثقف", "اعرف عن"],
}

# أغراض تُنتج مَخرَجاً ملموساً (كود/بناء/تقرير/بحث/مالية/أمن): يجب دليل فعلي
# حتى يُعلَن نجاح — قلب "لا اكتمال وهمي" (المواصفة §106).
DELIVERABLE_INTENTS = {"code","build","report","research","finance","security"}


def _load_runs():
    return C.load_json(RUNS_FILE, {"runs": []})


def _save_runs(s):
    C.atomic_write(RUNS_FILE, s)


# ===== ROUTER =====

def router(task):
    """تصنيف القصد + تحديد الأنظمة الفرعية المناسبة."""
    low = (task or "").lower()
    # أمر أمني صريح (بونتات/باونتي) → security أولاً مهما وُجد «سو/ابن» معه
    if any(b in low for b in ("bug bounty", "bounty", "بجتي", "باونتي", "بواج", "باقتي", "ثغرة", "اختبار امن")):
        return {"intent": "security", "subsystems": ["bounty_engine", "world_model"]}
    scores = {intent: sum(1 for k in keys if k.lower() in low) for intent, keys in INTENT_KEYWORDS.items()}
    intent = max(scores, key=scores.get) if max(scores.values()) else "unknown"
    mapping = {
        "research": ["news_intel", "browser_agent", "world_model"],
        "code": ["goal_manager", "tool_registry", "self_improve_engine"],
        "build": ["product_factory", "devops_agent", "browser_agent"],
        "open": ["browser_agent"],
        "device": ["computer_agent", "approval_center"],
        "operate": ["chief_staff", "goal_manager", "approval_center"],
        "finance": ["finance_intel", "world_model"],
        "report": ["chief_staff", "finance_intel", "benchmark", "world_model"],
        "security": ["bounty_engine", "world_model"],
        "improve": ["self_improve_engine", "benchmark"],
        "learn": ["learn_topic"],
        "unknown": ["world_model"],
    }
    return {"intent": intent, "subsystems": mapping[intent]}


# ===== PLANNER =====

def plan(task, intent, subsystems):
    """خطة خطوة-بخطوة — بديلة حتمية إن غاب الدماغ."""
    def step(action, target):
        return {"action": action, "target": target, "done": False, "output": None}

    if intent == "research":
        st = [step("news_intel", "استطلاع"), step("browser_agent", "تصفح المصادر"), step("world_model", "تلخيص النتائج")]
    elif intent == "code":
        st = [step("goal_manager", "تسجيل الهدف"), step("tool_registry", "تجهيز الأدوات"), step("self_improve_engine", "تنفيذ التعديل")]
    elif intent == "build":
        st = [step("product_factory", "بناء المنتج"), step("devops_agent", "نشر/فحص صحي"), step("browser_agent", "تحقق من الواجهة")]
    elif intent == "open":
        st = [step("open_url", "فتح الموقع في المتصفح الافتراضي")]
    elif intent == "device":
        st = [step("device_action", "تنفيذ/فتح على الجهاز (باب الولوج الكامل)")]
    elif intent == "operate":
        st = [step("chief_staff", "إيقاظ"), step("goal_manager", "ترتيب المهام"), step("approval_center", "فحص ما يحتاج الإنسان")]
    elif intent == "finance":
        st = [step("finance_intel", "قراءة المالية")]
    elif intent == "report":
        st = [step("benchmark", "قياس الحالة"), step("finance_intel", "قراءة المالية")]
    elif intent == "security":
        st = [step("bounty_intel", "فحص حالة البجتي والتفويض")]
    elif intent == "improve":
        st = [step("benchmark", "قياس الضعف")]
    elif intent == "learn":
        st = [step("learn_topic", "التعلّم من مصادر عامة وتخزينه بالذاكرة")]
    elif intent == "operate":
        st = [step("goal_manager", "تسجيل الهدف")]
    else:
        st = [step("world_model", "بناء الصورة")]
    raw, _ = None, None
    if intent not in ("open", "device", "finance", "report", "security", "improve", "operate", "learn"):
        raw, _ = C.call_brain(
            "مخطط مهام دقيق.",
            f"ضع خطة 3-5 خطوات للمهمة: «{task}» — كل سطر: STEP: الإجراء",
            mode="fastest",
        )
    if raw:
        extra = [{"action": l[5:].strip().split(":")[0][:30], "target": l[5:].strip(), "done": False, "output": None}
                 for l in raw.splitlines() if l.startswith("STEP:")]
        if extra:
            st = extra
    # أي قصد إنتاجي يجب أن ينتهي بخطوة «مخرَج ملموس» — لا اكتمال وهمي (§106)
    if intent in DELIVERABLE_INTENTS:
        st.append(step("produce_artifact", "تأمين المخرَج الملموس"))
    return st


# ===== EXECUTOR =====

ARTIFACT_ROOTS = ("output", "data", "projects", "reports")


def _artifact_path_from_task(task):
    """استخراج مسار مخرَج مطلوب من نص المهمة (مثل: output/note.md) إن وُجد."""
    m = re.search(
        r"(?<![A-Za-z0-9])(?:" + "|".join(ARTIFACT_ROOTS) +
        r")[\\/][A-Za-z0-9_\-./\\ \u0600-\u06FF]+\.(?:md|txt|html|json|csv|py)(?![A-Za-z0-9])",
        task or "", re.I)
    if not m:
        return None
    return m.group(0).replace("\\", os.sep).replace("/", os.sep)


def _safe_resolve(rel):
    """تحويل مسار نسبي إلى مطلق داخل ROOT فقط — يرفض أي خروج (± عبور) خارجها."""
    root = os.path.abspath(C.BASE_DIR)
    full = os.path.abspath(os.path.join(root, rel))
    if os.path.commonpath([root, full]) != root:
        return None
    return full


def _html_escape_page(task, intent):
    t = _html.escape(task or "")
    return ("<!DOCTYPE html>\n<html lang=\"ar\"><head><meta charset=\"utf-8\">"
            f"<title>{t[:60]}</title></head>\n<body><h1>{t}</h1>"
            f"<p>القصد: {_html.escape(intent or '')}</p></body></html>\n")


INTENT_DIRS = {
    "report": "reports", "research": "reports", "notes": "notes",
    "data": "data", "code": "projects", "build": "output/builds",
}


def _strip_fences(text):
    """يزيل أسوار ```lang … ``` إن أحاطت المحتوى."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```\s*$", "", t)
    return t.strip()


def _brain_deliverable(task, intent, ext):
    """يولّد محتوى مخرَج حقيقياً عبر العقل حسب النوع (البند 4).
    يرجع None حين لا مزوّد — فتُستعمل السقالة الصادقة بدلاً منه (لا تلفيق)."""
    if ext == ".py":
        sysmsg = "أنت مبرمج خبير. اكتب كوداً كاملاً قابلاً للتشغيل. أخرِج الكود فقط بلا شرح."
        prompt = f"اكتب برنامج Python كاملاً للمهمة: «{task}». ابدأ مباشرةً بالكود."
    elif ext in (".md", ".txt", ""):
        sysmsg = "أنت كاتب تقني دقيق. اكتب تقريراً/محتوى حقيقياً ومفيداً بالعربية."
        prompt = (f"أنتج محتوى ماركداون حقيقياً ومكتملاً للمهمة: «{task}» (القصد: {intent}). "
                  "عناوين وفقرات فعلية، لا عبارات نائبة مثل «هنا».")
    elif ext == ".html":
        sysmsg = "أنت مطوّر ويب. أخرِج صفحة HTML كاملة صالحة فقط."
        prompt = f"اكتب صفحة HTML كاملة للمهمة: «{task}». أخرِج الوسم فقط."
    else:
        return None  # json/csv تبقى منظّمة حتمياً

    raw, engine = C.call_brain(sysmsg, prompt, mode="smart")
    if not raw or engine in (None, "", "none") or raw.strip().startswith("("):
        return None
    content = _strip_fences(raw)
    if len(content) < 40:
        return None
    C.log(f"🧠 مخرَج مولّد بالعقل ({engine}) — {len(content)} حرفاً")
    return content


def _write_deliverable(task, intent="output", asked_path=None):
    """كتابة مخرَج ملموس آمن: ملف ضمن ROOT فقط، حسب النوع (py/json/csv/html/md).
    القصد يوجّه الملف إلى مجلده الطبيعي (تقرير → reports، بيانات → data، إلخ)
    حين لا يحدد المستخدم مساراً صريحاً في نص المهمة."""
    rel = asked_path or _artifact_path_from_task(task)
    if rel:
        path = _safe_resolve(rel)
        if not path:
            return {"error": f"مسار خارج النطاق المسموح: {rel}", "path": "", "kind": "artifact"}
    else:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        _dir = INTENT_DIRS.get((intent or "output").lower(), "output")
        path = _safe_resolve(os.path.join(_dir, "artifacts", f"{intent}_{stamp}.md"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ext = os.path.splitext(path)[1].lower()
    now = C.now_iso()
    # محتوى حقيقي بالعقل أولاً (البند 4)؛ وإلا سقالة صادقة تُعلَّم «غير مكتملة».
    content = _brain_deliverable(task, intent, ext)
    if content is not None:
        pass
    elif ext == ".py":
        content = (f'"""مخرج مولّد تلقائياً — مهمة: {task[:120]}\n'
                   f"القصد: {intent} | {now}\n\"\"\"\n\n"
                   "def main():\n    print('تم تنفيذ المهمة')\n\n"
                   "if __name__ == '__main__':\n    main()\n")
    elif ext == ".json":
        import json as _json
        content = _json.dumps({"task": task, "intent": intent, "created": now},
                              ensure_ascii=False, indent=2)
    elif ext == ".csv":
        import csv as _csv
        import io as _io
        _buf = _io.StringIO()
        _w = _csv.writer(_buf)
        _w.writerow(["created", "intent", "task"])
        _w.writerow([now, intent, task or ""])
        content = _buf.getvalue()
    elif ext == ".html":
        content = _html_escape_page(task, intent)
    else:
        _intent = (intent or "output").lower()
        content = (f"# مهمة: {task}\n\n"
                   f"- **القصد:** {intent}\n"
                   f"- **التاريخ:** {now}\n"
                   f"- **المسار:** {path}\n\n"
                   f"## ملخص التنفيذ\n\nتم توليد هذا المخرَج تلقائياً بواسطة نواة Agent OS.\n")
        if _intent in ("report", "research"):
            content += ("\n## الخلاصة\n\n- ملاحظة/عرض المخرجات هنا.\n"
                        "\n## التفاصيل\n\n- قائمة النتائج والعيوب هنا.\n")
        elif _intent == "data":
            content += ("\n## جدول البيانات\n\n| حقل | قيمة |\n"
                        "| --- | --- |\n| مسار المخرَج | `%s` |\n| النوع | %s |\n" % (path, ext or "md"))
        elif _intent == "notes":
            content += ("\n## الملاحظات\n\n- سجّل النقاط المستخلصة هنا.\n"
                        "\n## القرارات\n\n- القرارات وأسبابها هنا.\n")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        size = os.path.getsize(path)
        if size <= 0:
            return {"error": "الملف فُتح فارغاً", "path": path, "kind": "artifact"}
        C.log(f"📦 مخرَج ملموس: {path}")
        return {"path": path, "size": size, "kind": "artifact", "format": ext.lstrip(".") or "md"}
    except Exception as e:
        return {"error": f"تعذّرت الكتابة: {e}", "path": "", "kind": "artifact"}


def _consult_brain(task, ctx=None):
    """يسأل العقل (Claude/DeepSeek/Gemini عبر brain) عن حلّ/أدوات عند العجز،
    ويخزّن الاقتراح في الذاكرة كمعرفة (البند 17). فشل غير قاتل، وبلا تلفيق:
    إن لم يوجد مزوّد يُعيد ok=False مع سبب صريح."""
    lessons = (ctx or {}).get("lessons") or []
    hint = ("\nدروس سابقة يجب تفاديها:\n- " + "\n- ".join(lessons[:3])) if lessons else ""
    raw, engine = C.call_brain(
        "أنت مستشار تقني للوكيل. اقترح خطوات عملية وأدوات مفتوحة/مجانية محددة لتنفيذ المهمة.",
        f"المهمة التي عجز الوكيل عنها: «{task}».{hint}\n"
        "أعطِ 3-6 خطوات عملية وأسماء أدوات/حزم يمكن تركيبها.",
        mode="smart",
    )
    # brain يعيد رسالة خطأ نصية (تبدأ بـ«(» وengine=none) لا None — لا نعاملها
    # كاقتراح حقيقي (البند 5: ممنوع تلفيق نجاح من رسالة فشل).
    if not raw or engine in (None, "", "none") or raw.strip().startswith("("):
        return {"ok": False, "reason": (raw or engine or "لا مزوّد عقل متاح").strip("()")[:120]}
    suggestion = raw.strip()[:1500]
    try:
        from agent_os.memory import provenance
        provenance.record(f"consult:{task[:50]}", suggestion,
                          source=f"brain:{engine}", confidence=0.55, kind="fact")
    except Exception:
        pass
    return {"ok": True, "suggestion": suggestion, "engine": engine}


def execute_step(step, task, ctx):
    """تنفيذ خطوة في الأنظمة الفرعية بالأدوات الآمنة."""
    action = step["action"]
    ok = False
    out = None
    try:
        if action == "open_url":
            import webbrowser
            url = _resolve_url(task or step.get("target", ""))
            if not url:
                step["done"] = False
                step["output"] = {"error": "ما الرابط الذي تريد فتحه؟", "held": True}
                return step
            webbrowser.open(url)
            out = {"opened": True, "url": url, "via": "default-browser"}
            ok = True
        elif action == "bounty_intel":
            try:
                from agent_os import bounty_engine
                st = bounty_engine._load() if hasattr(bounty_engine, "_load") \
                    else C.load_json(os.path.join(C.AGENT_OS_DIR, "bounty_programs.json"), {})
                programs = st.get("programs", [])
                findings = st.get("findings", []) or st.get("results", [])
                drafts = st.get("drafts", []) or []
                authorized = [p for p in programs if p.get("authorization_source") or p.get("authorization_status") == "owner_confirmed"]
                out = {
                    "programs": len(programs),
                    "authorized_scope": len(authorized),
                    "findings": len(findings),
                    "draft_reports": len(drafts),
                    "note": "المسح لا يجري إلا على نطاق مصرّح لك — الرفع يدوي دائماً",
                }
                ok = True
            except Exception as bidx:
                out = {"error": f"خطأ في قراءة حالة البجتي: {bidx}", "held": True}
                ok = False
        elif action == "device_action":
            res = _device_action(task or step.get("target", ""))
            if res.get("held"):
                step["done"] = False
                step["output"] = {"held": True, "note": res.get("note", ""), "reason": res.get("reason", "")}
                return step
            out = {"device": res}
            ok = bool(res.get("ok"))
        elif action == "news_intel":
            import news_intel
            data = news_intel.get_latest_intel()
            out = {k: len(v) for k, v in data.items()} if data else {}
            ok = True
        elif action == "browser_agent":
            from agent_os import browser_agent
            b = browser_agent.BrowserAgent("http")
            st = b.state()
            # لا "ready": True مُلفّقة — الجاهزية من الحالة الفعلية.
            out = {"state": st, "ready": bool(st)}
            ok = bool(st)
        elif action == "world_model":
            from agent_os import world_model
            wm = world_model.build()
            out = {"day": wm.get("day"), "goals": len(wm.get("goals", [])),
                   "path": world_model.WORLD_FILE if hasattr(world_model, "WORLD_FILE")
                   else os.path.join(C.AGENT_OS_DIR, "world_state.json")}
            ok = True
        elif action == "goal_manager":
            from agent_os import goal_manager
            g = goal_manager.add_goal(task[:80], ctx.get("why", "") if ctx.get("why") else "")
            out = {"goal_id": g.get("id") if isinstance(g, dict) else None}
            ok = True
        elif action == "tool_registry":
            from agent_os import tool_registry
            # عدد الأدوات الحقيقي — بلا «+1» اعتباطي كان يزوّر الرقم.
            out = {"tools": len(tool_registry.list_tools())}
            ok = True
        elif action == "self_improve_engine":
            from agent_os import self_improve_engine as sic
            out = sic.improve_once(quiet=True)
            # تحسين حرج ينتظر موافقة المالك = إمساك بشري، لا نجاح ولا فشل.
            if out.get("status") == "pending_approval":
                step["done"] = False
                step["output"] = {"held": True,
                                  "note": "تحسين ذاتي حرج ينتظر موافقتك", **out}
                return step
            # ok حقيقي: طُبّق التحسين فعلاً (committed) — لا True ثابتة.
            ok = bool(out.get("ok"))
        elif action == "product_factory":
            import json as _json
            from agent_os import product_factory
            dest = ctx.get("workdir") or os.path.join(C.BASE_DIR, "output", "builds")
            os.makedirs(dest, exist_ok=True)
            _t = (task or "منتج").strip()
            _name = _t[:40]
            _spec = _json.dumps({
                "name": _name,
                "title": _t[:80],
                "tagline": _t[:120],
                "cta": "اطلب الآن",
            }, ensure_ascii=False)
            p = product_factory.build_product(ctx.get("ptype") or "web", _name, dest, spec=_spec)
            out = {"product": p.get("name"), "path": p.get("path")}
            ok = True
        elif action == "devops_agent":
            from agent_os import devops_agent
            out = devops_agent.health_check(ctx.get("workdir") or os.path.abspath("."))
            ok = True
        elif action == "chief_staff":
            from agent_os import chief_staff
            out = chief_staff.wake()
            ok = True
        elif action == "approval_center":
            from agent_os import approval_center
            req = approval_center.create_request(task[:80], ctx.get("why", ""))
            out = {"request_id": req.get("id")}
            ok = True
        elif action == "finance_intel":
            from agent_os import finance_intel
            out = finance_intel.report()
            ok = True
        elif action == "benchmark":
            from agent_os import benchmark
            out = benchmark.summary()
            ok = True
        elif action == "bounty_engine":
            from agent_os import bounty_engine
            prog = bounty_engine.add_program("auto", [ctx.get("host", "example.com")], None)
            out = {"program_id": prog.get("id")}
            ok = True
        elif action == "learn_topic":
            # يتعلّم من مصادر عامة ويخزّنه بالذاكرة (البند 1).
            from agent_os.learn import ingest
            res = ingest.learn_query(task)
            out = res
            ok = bool(res.get("ok"))
        elif action == "consult":
            # يسأل العقل (Claude/DeepSeek/Gemini) عند العجز — البند 17.
            out = _consult_brain(task, ctx)
            ok = bool(out.get("ok"))
        else:
            # عاجز عن تنفيذ الفعل مباشرة → يستشير العقل (البند 17) بدل الاستسلام.
            consult = _consult_brain(task, ctx)
            if consult.get("ok"):
                out = {"note": f"لا منفذ مباشر لـ {action} — استشارة العقل:",
                       "suggestion": consult.get("suggestion"), "held": True}
            else:
                out = {"note": f"لا منفذ مباشر لـ {action}، وتعذّرت استشارة العقل "
                               f"({consult.get('reason', 'لا مزوّد')}) — يحتاج إنساناً", "held": True}
    except Exception as e:
        out = {"error": str(e)[:200]}
    step["done"] = ok
    step["output"] = out
    return step


# ===== CRITIC =====

SECURITY_RULES = [
    (r"shell=True", "استخدام shell=True ممنوع"),
    (r"\beval\s*\(", "eval ممنوع"),
    (r"\bexec\s*\(", "exec ممنوع"),
    (r"subprocess.\w+\([^)]*shell", "subprocess+shell"),
    (r"'/\s*&&", "سلاسل حاوية"),
    (r"0\.0\.0\.0", "ربط بكل العناوين"),
]


import ast as _ast

# علامات السقالة التلقائية — نصوص يضعها مولّد المخرَج حين لا محتوى حقيقي.
_SCAFFOLD_MARKERS = (
    "print('تم تنفيذ المهمة')",
    'print("تم تنفيذ المهمة")',
    "تم توليد هذا المخرَج تلقائياً بواسطة نواة Agent OS",
    "عرض المخرجات هنا",
    "قائمة النتائج والعيوب هنا",
    "سجّل النقاط المستخلصة هنا",
    "القرارات وأسبابها هنا",
)


def _is_scaffold_deliverable(path):
    """هل الملف مجرّد سقالة مولّدة تلقائياً بلا مضمون حقيقي؟
    البند 5: لا نعتبر ملفاً «دليلاً» لمجرد وجوده — لا بد أن يحمل محتوى فعلياً."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        return False
    ext = os.path.splitext(path)[1].lower()
    marker_hit = any(m in text for m in _SCAFFOLD_MARKERS)

    if ext == ".py":
        try:
            tree = _ast.parse(text)
        except SyntaxError:
            return False  # كود مكتوب فعلاً (وإن كان مكسوراً) ليس سقالة فارغة
        real = any(isinstance(n, _ast.ClassDef) for n in tree.body)
        for fn in [n for n in tree.body if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))]:
            body = [b for b in fn.body
                    if not (isinstance(b, _ast.Expr) and isinstance(b.value, _ast.Constant))]  # تجاهل docstring
            if len(body) == 1 and isinstance(body[0], _ast.Expr) \
                    and isinstance(body[0].value, _ast.Call) \
                    and getattr(body[0].value.func, "id", "") == "print":
                continue  # دالة طباعة فقط = سقالة
            if body:
                real = True
        return marker_hit or not real

    # نصوص/ماركداون: سقالة إن ضربت العلامات وقلّ المحتوى الحقيقي بعد إزالة القوالب.
    if marker_hit:
        body_lines = [ln for ln in text.splitlines()
                      if ln.strip() and not ln.lstrip().startswith("#")
                      and "هنا" not in ln and not ln.strip().startswith("- **")]
        return len(" ".join(body_lines)) < 80
    return False


def _has_material_evidence(steps_output):
    """دليل ملموس = ملف موجود فعلاً *وبمحتوى حقيقي* (لا سقالة) أو ناتج نصي ذو مضمون."""
    for s in steps_output:
        out = s.get("output")
        if not s.get("done") or not out:
            continue
        if isinstance(out, dict):
            for key in ("path", "product", "site", "project", "bin", "dest"):
                val = out.get(key)
                if val and os.path.exists(str(val)) and not _is_scaffold_deliverable(str(val)):
                    return True
        if isinstance(out, str) and len(out.strip()) >= 40:
            return True
    return False


def critic(task, steps_output, intent="unknown"):
    """نقد نتائج التنفيذ: أخطاء + خرق قيود + نقص تغطية + نقص دليل (§106)."""
    issues, warnings = [], []
    done = 0
    for s in steps_output:
        out = s.get("output") or {}
        if s["done"]:
            done += 1
        if out.get("held"):
            warnings.append(f"الخطوة «{s['action']}» تحتاج إنساناً")
        if out.get("error"):
            issues.append(f"خطأ في «{s['action']}»: {out['error']}")
        for pat, note in SECURITY_RULES:
            # لا نُصغّر النص (كان يقتل قاعدة shell=True ذات الحرف الكبير)؛
            # نطابق بلا حساسية لحالة الأحرف عبر re.I بدلاً من ذلك.
            if re.search(pat, str(out), re.I):
                issues.append(f"ثغرة أمنية في المخرجات: {note}")
    if done == 0:
        issues.append("لا خطوة نُفِّذت فعلياً")
    # المهمة الإنتاجية بلا دليل ملموس = اكتمال وهمي؛ لا يُعلن نجاح (§106)
    if done > 0 and intent in DELIVERABLE_INTENTS and not _has_material_evidence(steps_output):
        issues.append("مهمة إنتاج دون مخرَج ذي محتوى حقيقي (سقالة فارغة لا تكفي) — "
                       "لا يُعلَن اكتمال بلا دليل؛ يلزم عقل/أدوات لإنتاج محتوى فعلي (§106)")
    verdict = {"grade": "ok" if not issues else ("risky" if warnings else "needs_revision"), "issues": issues, "warnings": warnings}
    return verdict


# ===== VERIFIER =====

def verifier(task, verdict):
    """محكّم: القبول أو الفشل أو الإمساك البشري."""
    if not verdict["issues"] and not verdict["warnings"]:
        return {"status": "verified", "grade": "A"}
    if verdict["grade"] == "risky":
        return {"status": "needs_human", "grade": "risky", "issues": verdict["issues"], "warnings": verdict["warnings"]}
    return {"status": "revised", "grade": "B", "issues": verdict["issues"]}


# ===== OPEN & DEVICE — مسارات حتمية بلا عقل (لا تأخير ولا سوء فهم) =====

OPEN_BRANDS = {
    "نتفلكس": "https://www.netflix.com", "نتفليكس": "https://www.netflix.com", "netflix": "https://www.netflix.com",
    "يوتيوب": "https://www.youtube.com", "يويتوب": "https://www.youtube.com", "youtube": "https://www.youtube.com",
    "انستقرام": "https://www.instagram.com", "انستغرام": "https://www.instagram.com", "instagram": "https://www.instagram.com",
    "فيسبوك": "https://www.facebook.com", "facebook": "https://www.facebook.com",
    "تويتر": "https://x.com", "twitter": "https://x.com", "x.com": "https://x.com", "X.com": "https://x.com",
    "واتساب": "https://web.whatsapp.com", "واتس اب": "https://web.whatsapp.com", "whatsapp": "https://web.whatsapp.com",
    "جيميل": "https://mail.google.com", "gmail": "https://mail.google.com",
    "مابس": "https://maps.google.com", "خرائط": "https://maps.google.com", "maps": "https://maps.google.com",
    "جوجل": "https://www.google.com", "google": "https://www.google.com",
    "درايف": "https://drive.google.com", "drive": "https://drive.google.com",
    "جيت هاب": "https://github.com", "جيتهاب": "https://github.com", "github": "https://github.com",
    "جي بي تي": "https://chatgpt.com", "شات جي بي تي": "https://chatgpt.com", "chatgpt": "https://chatgpt.com", "openai": "https://openai.com",
    "أمازون": "https://www.amazon.com", "امازون": "https://www.amazon.com", "amazon": "https://www.amazon.com",
    "تيك توك": "https://www.tiktok.com", "tiktok": "https://www.tiktok.com",
    "سناب": "https://www.snapchat.com", "snapchat": "https://www.snapchat.com",
    "لينكد إن": "https://www.linkedin.com", "لينكدإن": "https://www.linkedin.com", "linkedin": "https://www.linkedin.com",
    "ويكيبيديا": "https://ar.wikipedia.org", "wikipedia": "https://ar.wikipedia.org",
}
OPEN_VERBS = ("افتحلي", "افتح لي", "اِفتح", "افتح", "فتح", "روّح", "العب", "اذهب إلى", "اذهب لموقع", "وقّع في")
DEVICE_VERBS = ("شغّل", "شغل", "تشغيل", "أغلق", "أوقف", "أطفئ", "تحكم", "افحص", "العمليات", "جهازي",
                "إدارة المهام", "ادارة المهام", "افتح ملف", "افتح مجلد", "افتح برنامج")
APP_HINTS = ("ملف", "مجلد", "برنامج", "المفكرة", "نوت باد", "الحاسبة", "المستكشف", "فيسكود", "كروم",
             "فوتوشوب", "سبوتيفاي", "صفحة", "مستند", "الباوند", "مسار")
AGENT_SELF_NOISE = ("الاختبارات", "الوكيل", "نظام", "تعلّم", "تعلم", "دورة", "جدولة", "مراقبة", "خلفية")


def _app_hints():
    """أسماء التطبيقات المحلية المعروفة (مفاتيح AVAILABLE_APPS + قوائم ملاحظة)."""
    try:
        return tuple(APP_HINTS) + tuple(AVAILABLE_APPS.keys())
    except Exception:
        return APP_HINTS


def _is_open_request(task):
    low = (task or "").strip().lower()
    if "://" in low or low.startswith("www."):
        return True
    if any(b in low for b in OPEN_BRANDS):
        return True
    if any(v in low for v in OPEN_VERBS):
        if any(n in low for n in AGENT_SELF_NOISE):
            return False
        if any(a in low for a in _app_hints()):
            return False
        if any(f in low for f in ("اكتب", "انسخ", "الطبع", "احفظ في")):
            return False
        return True
    return False


def _is_device_request(task):
    low = (task or "").strip().lower()
    if any(n in low for n in AGENT_SELF_NOISE):
        return False
    # «افتح/شغّل» + شيء محلي (ملف/مجلد/برنامج/تطبيق) = جهاز
    if any(v in low for v in OPEN_VERBS) and any(a in low for a in _app_hints()):
        return True
    # كتابة/نسخ إلى تطبيق معلوم («اكتب اسمك لي في المفكرة») = جهاز
    if any(a in low for a in _app_hints()) and any(k in low for k in ("اكتب", "انسخ", "الطبع")):
        return True
    if any(v in low for v in DEVICE_VERBS):
        if any(b in low for b in OPEN_BRANDS) or any(d in low for d in ("موقع", "المتصفح", "http", "www.")):
            return False
        return True
    return False


def _pre_route(task):
    if _is_open_request(task):
        return {"intent": "open", "subsystems": ["browser_agent"]}
    if _is_device_request(task):
        return {"intent": "device", "subsystems": ["computer_agent", "approval_center"]}
    return None


def _resolve_url(task):
    """استخراج رابط من المهمة: اسم موقع معرّف أو رابط صريح أو اسم حر → domain.com."""
    low = (task or "").strip().lower()
    m = re.search(r"https?://[^\s]+", low)
    if m:
        return m.group(0)
    m = re.search(r"\b(?:www\.)?[a-z0-9][a-z0-9\-]+\.[a-z]{2,}(?:/[^\s]*)?", low)
    if m:
        return m.group(0) if m.group(0).startswith("http") else "https://" + m.group(0)
    for key, url in OPEN_BRANDS.items():
        if key in low:
            return url
    return "https://www.google.com/search?q=" + urllib.parse.quote((task or "").strip()[:80])


AVAILABLE_APPS = {
    "المفكرة": "notepad", "نوت باد": "notepad", "notepad": "notepad",
    "الحاسبة": "calc", "calc": "calc",
    "الطرفية": "cmd", "الموجه": "cmd", "الأوامر": "cmd", "cmd": "cmd",
    "المستكشف": "explorer", "مستكشف الملفات": "explorer", "explorer": "explorer",
    "فيسكود": "Code", "كود": "Code", "code": "Code", "vscode": "Code",
    "كروم": "chrome", "chrome": "chrome",
    "فوتوشوب": "photoshop", "photoshop": "photoshop",
    "سبوتيفاي": "spotify", "spotify": "spotify",
}


def _send_keys_into(text, timeout=15):
    """كتابة نص إلى النافذة النشطة (المفكرة والعائلة) عبر SendKeys مشفَّر بلا تشوه ترميز."""
    import base64, json as _json, subprocess
    braced = str(text).replace("{", "{{").replace("}", "}}")
    ps = (
        "$id = (Get-Process -Name notepad -ErrorAction SilentlyContinue | Select-Object -Last 1).Id; "
        "$ws = New-Object -ComObject wscript.shell; "
        "if(!$id){ exit 2 }; $null = $ws.AppActivate($id); Start-Sleep -Milliseconds 600; "
        "$ws.SendKeys(" + _json.dumps(braced) + "); exit 0"
    )
    enc = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
            capture_output=True, timeout=timeout)
        return r.returncode == 0
    except Exception:
        return False


AGENT_NAME = "Agent OS"

_TYPING_VERBS = ("اكتبي", "اكتب", "انسخي", "انسخ", "اكتب لي", "انسخ لي", "الطبع", "الطباعة")


def _run_open_seg(seg):
    """فتح عنصر محلي واحد: مسار/ملف/مجلد أو تطبيق معروف. يعيد {ok, via, note}."""
    import shutil as _sh
    seg = (seg or "").strip()
    for verb in ("افتح", "اِفتح", "افتحلي", "شغّل", "شغل", "اطلع على", "فتح"):
        if seg.startswith(verb):
            seg = seg[len(verb):].strip().strip(":، ").strip()
            break
    if not seg:
        return {"ok": False, "via": "empty", "note": "لا يوجد عنصر للفتح"}
    if seg.lower().startswith(("http://", "https://", "www.")):
        import webbrowser
        webbrowser.open(seg if seg.startswith("http") else "https://" + seg)
        return {"ok": True, "via": "url", "note": "فُتح الرابط"}
    m = re.search(r"[A-Za-z]:[\\/][^\s\"']+|[\\/](?:output|data|projects|reports)[\\/][\w\u0600-\u06FF\-\./ ]+", seg)
    if m:
        p = m.group(0).strip()
        cand = p if os.path.isabs(p) else os.path.join(C.BASE_DIR, p)
        if os.path.exists(cand):
            os.startfile(cand)
            return {"ok": True, "via": "startfile", "note": f"فُتح: {cand}"}
    for key, app in AVAILABLE_APPS.items():
        if key.lower() in seg.lower():
            loc = _sh.which(app) or app if app in ("notepad", "calc", "cmd", "explorer") else _sh.which(app)
            started = os.startfile(loc) if loc else None
            if loc:
                return {"ok": True, "via": "startfile", "app": app, "note": f"أُطلق {app}"}
            return {"ok": False, "via": "app-lookup", "note": f"«{app}» غير متاح في PATH"}
    return {"ok": False, "via": "unresolved", "note": "لا أعرف هذا العنصر المحلي"}


def _device_action(task):
    """فكّ «شغّل/افتح/تحكم» إلى فعل جهاز حقيقي — يحترم صندوق computer_agent المفعَّل باب الولوج الكامل."""
    import shutil as _sh
    from agent_os import computer_agent
    low = (task or "").strip()

    # (0) أمر مركب: «افتح <تطبيق> واكتب...» — العرب «واكتب» ملتصقة؛ نفصّل على الواو قبل فعلٍ معروف
    _connector = (r"\s+(?:و)(?=(?:اكتبي|اكتب|انسخي|انسخ|اطبع|ضع|حط|افتح|شغّل|شغل|فعّل|أطفئ|أوقف|اقفل|سوّي|سو|"
                  "ابن|قاس|نفّذ|ارفع|اطلع|بيني|مدني|خلني|دخِّلني|اكتبلي|انسخني))"
                  r"|\s+(?:ثم|بعدين)\s+")
    parts = re.split(_connector, low)
    if len(parts) > 1 and any(k in low for k in _TYPING_VERBS + ("شبك", "قص", "لصق")):
        opened = _run_open_seg(parts[0])
        actions = []
        for seg in parts[1:]:
            s2 = seg.strip()
            mt = re.match(r"^(?:اكتبي|اكتب|انسخي|انسخ|اكتب لي|انسخ لي|الطبع|الطباعة)[\s:：]+(.+)$", s2)
            if mt:
                txt = mt.group(1).strip().rstrip("؟؟! .")
                if txt in ("اسمك", "اسمك انت", "اسمك كامل", "اسمي"):
                    txt = AGENT_NAME
                actions.append({"step": s2[:40], "typed": txt[:40], "ok": _send_keys_into(txt)})
                continue
            if re.match(r"^(?:شبك|قص|انسخ الكل|تحديد الكل)", s2):
                actions.append({"step": s2[:40], "ok": _send_keys_into("^a") if "الكل" in s2 or "تحديد" in s2 else True, "shortcut": True})
                continue
            r2 = computer_agent.run(s2.split())
            actions.append({"step": s2[:40], "ok": r2.get("ok"), "held": r2.get("verdict") == "needs_human"})
        return {"ok": True, "via": "compound", "open": opened, "actions": actions,
                "note": "فُتح الأول ثم تابعت الأوامر على الجهاز"} if opened.get("ok") else {**opened, "actions": actions}

    # (0.5) عرض العمليات (بصيغته المختلفة: اعرض/بيني/افحص/شو عمليات)
    if "عمليات" in low:
        return computer_agent.run(["tasklist"])

    def _try_run(rest):
        if not rest:
            return {"held": True, "note": "اكتب الأمر بوضوح بعد شغّل/افحص"}
        if rest.lower().startswith(("http", "www")):
            return {"ok": True, "via": "url", "path": rest}
        return computer_agent.run(rest.split())

    # (1) أمر نظام صريح: «شغّل <أمر>» / «افحص...»
    for verb in ("شغّل", "شغل", "افحص", "تشغيل"):
        i = low.lower().find(verb)
        if i >= 0:
            rest = low[i + len(verb):].strip(": ")
            if rest:
                head = rest.split()[0].lower()
                if verb == "افحص" and "عمليات" in rest:
                    return computer_agent.run(["tasklist"])
                if _sh.which(head) or head in ("tasklist", "findstr", "where", "dir", "type", "echo", "whoami", "netstat", "systeminfo", "net"):
                    res = _try_run(rest)
                    if res.get("held"):
                        return res
    # (2) مسار/ملف/مجلد موجود (مطلق أو نسبي من جذر المشروع)
    m = re.search(
        r"[A-Za-z]:[\\/][^\s\"']+|"
        r"(?:[\\/]|(?<![A-Za-z0-9]))(?:output|data|projects|reports)[\\/][\w\u0600-\u06FF\-\./ ]+|"
        r"(?<![A-Za-z0-9])[\w\u0600-\u06FF\-]+\.(?:txt|md|json|py|html?|css|js|log|ini)(?=$|\s|\.)", low)
    if m:
        p = m.group(0).strip()
        cand = p if os.path.isabs(p) else os.path.join(C.BASE_DIR, p.lstrip("\\/"))
        if os.path.exists(cand):
            os.startfile(cand)
            return {"ok": True, "via": "startfile", "path": cand, "note": "فُتح بالمعالِج الافتراضي"}
    # (3) تطبيق معروف
    for key, app in AVAILABLE_APPS.items():
        if key in low:
            loc = _sh.which(app) or ({'notepad': 'notepad', 'calc': 'calc', 'cmd': 'cmd', 'explorer': 'explorer'} or {}).get(app)
            if loc:
                os.startfile(loc)
                return {"ok": True, "via": "startfile", "path": app, "note": "أُطلق البرنامج"}
            return {"ok": False, "via": "app-lookup", "note": f"«{app}» غير متاح في PATH"}
    # (4) الولوج الكامل مفعّل؟ نفّذ ما يُقال حرفياً (ما عدا القائمة القاتلة — يرفضها computer_agent)
    try:
        from agent_os import full_access
        opened = full_access.is_enabled()
    except Exception:
        opened = False
    if opened:
        res = computer_agent.run(low.split())
        if not res.get("ok"):
            res["held"] = res.get("verdict") == "needs_human"
            return res
        return res
    # (5) خارج الولوج الكامل — يُرفع للموافقة
    return {"held": True, "note": "أعد الصياغة: «شغّل <أمر>» أو «افتح <مسار/برنامج>» (أو فعّل الولوج الكامل في اللوحة)"}


def _parse_cli_kwargs(tail):
    """تحليل وسائط ‎--key value‎ في مرور واحد.
    يصحّح عيبين: القديم كان يُسقط ‎--why‎ (لأن ‎"--" in list‎ يبحث عن عنصر
    مطابق تماماً لا يبدأ بـ‎--‎)، ويعلّق للأبد على رمز ‎--‎ منفرد."""
    kw = {}
    i = 0
    while i < len(tail):
        tok = tail[i]
        if tok.startswith("--") and len(tok) > 2:
            name = tok[2:]
            if i + 1 < len(tail) and not tail[i + 1].startswith("--"):
                kw[name] = tail[i + 1]
                i += 2
            else:
                kw[name] = True
                i += 1
        else:
            i += 1
    return kw


def _recall_memory(task, intent):
    """يقرأ الذاكرة قبل المحاولة: تجارب مشابهة + دروس فشل سابقة + أفضل استراتيجية.
    مركز الثقل — «يُقرأ قبل كل محاولة؛ لا يتكرّر خطأ واحد مرتين»."""
    recalled = {"similar": [], "lessons": [], "recommended_strategy": None}
    try:
        from agent_os.memory import contextual_memory as cm
        for exp in cm.recall(task, limit=3):
            recalled["similar"].append({"task": exp.get("task"),
                                        "outcome": exp.get("outcome"),
                                        "solution": exp.get("solution")})
            # درس صريح من كل تجربة فشل مشابهة — لتجنّب تكرارها.
            if exp.get("outcome") not in ("success", "verified") and exp.get("problem"):
                recalled["lessons"].append(exp["problem"])
    except Exception:
        pass
    try:
        from agent_os.memory import strategy_memory as sm
        best = sm.best_strategy(intent)
        if best:
            recalled["recommended_strategy"] = best
    except Exception:
        pass
    if recalled["lessons"]:
        C.log(f"🧠 دروس سابقة ({len(recalled['lessons'])}) محمّلة قبل التنفيذ")
    return recalled


def _remember_run(task, intent, result, steps, verd):
    """يكتب الذاكرة بعد المحاولة: تجربة + نتيجة استراتيجية + دروس الفشل.
    كل فشل يصبح درساً دائماً يُقرأ في المحاولات القادمة (البنود 3/11/12)."""
    status = result.get("status")
    success = status == "verified"
    problem = "؛ ".join(verd.get("issues", []))[:300]
    artifact = next((s.get("output", {}).get("path") for s in steps
                     if (s.get("output") or {}).get("kind") == "artifact"
                     and (s.get("output") or {}).get("path")), None)
    try:
        from agent_os.memory import contextual_memory as cm
        cm.save_experience(
            task=task[:200], approach=intent,
            tools=[s["action"] for s in steps],
            problem=problem, solution=artifact or "", outcome=status,
        )
    except Exception:
        pass
    try:
        from agent_os.memory import strategy_memory as sm
        sm.record_outcome(intent, "kernel_default", success)
    except Exception:
        pass
    try:
        from agent_os.memory import provenance as prov
        if not success and problem:
            prov.record(f"lesson:{intent}:{task[:50]}", problem,
                        source="run_task", confidence=0.6, kind="fact")
    except Exception:
        pass


def run_task(task, why="", workdir=None, host=None, ptype=None, use_brain=False):
    """نشّط السلسلة كاملة على مهمة (مع حلقة مراجعة حتى 2 وتصعيد بشري)."""
    r = _pre_route(task) or router(task)
    recalled = _recall_memory(task, r["intent"])
    steps = plan(task, r["intent"], r["subsystems"])
    ctx = {"why": why, "workdir": workdir, "host": host, "ptype": ptype,
           "use_brain": use_brain, "intent": r["intent"],
           "lessons": recalled["lessons"], "recalled": recalled}
    for _ in range(2):  # حلقة مراجعة: أعد تنفيذ الخطوات الفاشلة فقط
        for s in steps:
            if s["done"]:
                continue
            execute_step(s, task, ctx)
        verd = critic(task, steps, r["intent"])
        if verd["grade"] != "needs_revision":
            break
    result = verifier(task, verd)

    artifact = None
    for s in steps:
        o = s.get("output") or {}
        if o.get("kind") == "artifact" and o.get("path"):
            artifact = os.path.normpath(o["path"])
            break

    # تصعيد بشري تلقائي حين تحتاج المهمة إنساناً
    if result["status"] == "needs_human":
        try:
            from agent_os import approval_center
            approval_center.create_request(
                task[:120],
                why or "النواة صحّحت أن المهمة تحتاج تدخلاً بشرياً",
                [f"check #{i+1}: {w}" for i, w in enumerate(verd.get("warnings", []))],
                resume_hint=task,
            )
        except Exception:
            pass

    record = {
        "date": C.now_iso(),
        "task": task[:120],
        "intent": r["intent"],
        "steps": [{"action": s["action"], "done": s["done"]} for s in steps],
        "verdict": result,
        "artifact": artifact,
    }
    state = _load_runs()
    state["runs"].insert(0, record)
    state["runs"] = state["runs"][:100]
    _save_runs(state)
    _remember_run(task, r["intent"], result, steps, verd)
    C.log(f"🎯 مهمة [{r['intent']}] → {result['status']}")
    _write_report(task, record)
    return {"task": task, "intent": r["intent"], "steps": record["steps"],
            "result": result, "artifact": artifact,
            "recalled": {"similar": len(recalled["similar"]),
                         "lessons": recalled["lessons"],
                         "recommended_strategy": recalled["recommended_strategy"]}}


def _write_report(task, record):
    """تقرير markdown لكل مهمة في output/agent_os/."""
    out_dir = os.path.join(C.BASE_DIR, "output", "agent_os")
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # لاحقة فريدة تمنع التصادم عند تشغيلين في نفس الثانية (اسم عرض يبقى بالثانية)
    uniq = f"{stamp}_{os.urandom(3).hex()}"
    path = os.path.join(out_dir, f"run_{uniq}.md")
    lines = [
        f"# تقرير مهمة — {stamp}",
        "",
        f"**المهمة:** {task}",
        f"**القصد:** {record['intent']}",
        "",
        "## الخطوات",
    ]
    for s in record["steps"]:
        lines.append(f"- {s['action']}: {'✓' if s['done'] else '✗'}")
    lines.append("")
    lines.append(f"## الحكم: {record['verdict']['status']} ({record['verdict'].get('grade', '')})")
    for i in record["verdict"].get("issues", []):
        lines.append(f"- ⚠ {i}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    C.log(f"📄 تقرير: {path}")


def status():
    runs = _load_runs()["runs"]
    ok = sum(1 for r in runs if r["verdict"]["status"] == "verified")
    return {"total": len(runs), "verified": ok, "last": runs[0]["verdict"]["status"] if runs else None}


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("الاستعمال: run <مهمة> [--why سبب] [--workdir مسار] [--host مضيف] | systems | status")
    elif args[0] == "systems":
        import inspect
        for f in sorted(os.listdir(os.path.dirname(os.path.abspath(__file__)))):
            if f.endswith(".py") and f != "_common.py":
                print("  " + f.replace(".py", ""))
    elif args[0] == "status":
        print(status())
    elif args[0] == "run":
        tail = args[1:]
        kw = _parse_cli_kwargs(tail)
        task_text = " ".join(a for a in tail if not a.startswith("--"))
        if task_text:
            print(run_task(task_text, **{k: v for k, v in kw.items() if isinstance(v, str)}))
        else:
            print("أدخل مهمة")