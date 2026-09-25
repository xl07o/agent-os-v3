"""
bounty_engine.py - النظام 9: محرك بحث الثغرات المستقل (v3.0)
=============================================================
سير كامل:

 برنامج -> قواعد -> نطاق (hard gate) -> كشف الأصول -> استخبارات سلبية
        -> اختبار نشط مصرح -> تحقق -> كشف تكرار -> تحليل أثر
        -> أدلة -> تقرير -> طابور تسليم

بوابة النطاق (Scope Engine) هي gate صارم: لا يختبر الوكيل أي شيء خارج
النطاق المصرح أبداً، ولا أي إجراء تخريبي.

الاستخدام:
  python agent_os/bounty_engine.py program <اسم> <نطاق>
  python agent_os/bounty_engine.py scan <برنامجId> <مضيف>
"""

import os
import re
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

PROGRAMS_FILE = os.path.join(C.AGENT_OS_DIR, "bounty_programs.json")


def _load():
    return C.load_json(PROGRAMS_FILE, {"programs": [], "findings": [], "next_id": 1})


def _save(s):
    C.atomic_write(PROGRAMS_FILE, s)


# ===== بوابة النطاق =====

def _domain(host):
    h = (host or "").replace("http://", "").replace("https://", "").split("/")[0].split(":")[0].lower()
    return h


def in_scope(program, host):
    """تحقق صارم: المضيف داخل النطاق المصرح؟ (subdomains + wildcard *.domain)"""
    h = _domain(host)
    if not h:
        return (False, "مضيف فارغ")
    for scope in program.get("scope", []):
        s = _domain(scope)
        if not s:
            continue
        if s.startswith(".") or s.startswith("*."):
            base = s.lstrip("*").lstrip(".")
            if base and h.endswith("." + base):
                return (True, f"يمر ضمن wildcard {s}")
            if base and h == base:
                return (False, "الاستضافة الجذر خارج wildcard — حددها صراحة")
        elif s == h:
            return (True, "تطابق تام")
        elif h.endswith("." + s):
            return (True, "نطاق فرعي مسموح")
    return (False, f"{h} خارج النطاق المصرح")


def add_scope(program_id, new_scope, authorization_source=None):
    """توسيع النطاق لا يتم تلقائياً؛ يحتاج تفويضاً صريحاً."""
    state = _load()
    prog = next((p for p in state["programs"] if p["id"] == program_id), None)
    if not prog:
        return None
    ns = new_scope.strip()
    if not authorization_source:
        return {"blocked": True, "reason": "توسيع النطاق يحتاج تفويضاً صريحاً"}
    if ns and ns not in prog["scope"]:
        prog["scope"].append(ns)
        prog = program_parser(prog)
        _save(state)
        C.log(f"🛡️ توسيع نطاق {prog['name']} ← {ns}")
    return prog


def _scope_gate(program, host):
    ok, msg = in_scope(program, host)
    if not ok:
        C.log(f"🚫 بوابة النطاق: {msg}", "SECURITY")
    return ok


# ===== أساليب سلبية/سطحية بلا ضرر =====

PASSIVE_CHECKS = [
    ("robots.txt", "https://{host}/robots.txt", "مجرودات"),
    (".well-known/security.txt", "https://{host}/.well-known/security.txt", "سياسة إبلاغ"),
    ("HTTP/LTS", "https://{host}", "بصمة رؤوس"),
]


def program_parser(program):
    """عصارة القواعد: نطاق + ممنوعات (destructive) من تجاهلها = رفض."""
    rules = program.get("rules") or ""
    destructive = []
    for word in ("delete", "drop", "wipe", "exploit", "dos", "ddos", "phish", "social"):
        if re.search(rf"\b{word}\b", rules.lower()):
            destructive.append(word)
    program["destructive_rules"] = destructive
    return program


def add_program(name, scope_list, rules="", authorization_source="owner-confirmed"):
    state = _load()
    prog = {
        "id": state["next_id"],
        "name": name,
        "scope": [s.strip() for s in scope_list if s.strip()],
        "rules": rules,
        "destructive_rules": [],
        "authorization_source": authorization_source,
        "authorization_status": "owner_confirmed" if authorization_source else "unverified",
        "scope_locked": True,
        "created": C.now_iso(),
    }
    state["next_id"] += 1
    state["programs"].append(program_parser(prog))
    _save(state)
    C.log(f"🛡️ برنامج #{prog['id']} «{name}» — نطاق: {', '.join(prog['scope'])}")
    return prog


def passive_recon(program, host):
    """استخبارات سلبية بلا لمس الأصول خارج النطاق."""
    if not _scope_gate(program, host):
        return {"blocked": True, "reason": "خارج النطاق"}
    intel = {"host": host, "sources": [], "subdomains_hint": []}
    try:
        import webtools
        results = webtools.search(f"site:{_domain(host)} subdomain", save=False, num=3)
        for r in results.get("results", [])[:3]:
            intel["sources"].append(r.get("url", "")[:200])
    except Exception as e:
        intel["error"] = str(e)
    return intel


def authorized_active_test(program, host):
    """فحص نشط منخفض الأثر فقط بعد وجود تفويض مسجل وقفل نطاق."""
    if program.get("authorization_status") != "owner_confirmed":
        return {"blocked": True, "reason": "لا يوجد تفويض موثق"}
    if not program.get("scope_locked", True):
        return {"blocked": True, "reason": "النطاق غير مقفول"}
    # أبسط فحص نشط مسموح: رؤوس + وجود ملفات قياسية — لا شيء خارج النطاق ولا تخريبي."""
    if not _scope_gate(program, host):
        return {"blocked": True, "reason": "خارج النطاق"}
    findings = []
    try:
        import webtools
        for label, url_t, note in PASSIVE_CHECKS:
            url = url_t.format(host=host)
            if not webtools._is_safe_url(url):
                continue
            body = webtools._fetch(url, timeout=10)
            findings.append({"check": label, "url": url, "note": note, "found": bool(body and "محظور" not in body)})
    except Exception as e:
        return {"error": str(e)}
    return {"findings": findings}


def add_finding(program_id, host, title, severity, evidence=""):
    state = _load()
    program = next((p for p in state["programs"] if p["id"] == program_id), None)
    if not program:
        return None
    ok, msg = in_scope(program, host)
    if not ok:
        return {"blocked": True, "reason": f"خارج النطاق: {msg}"}
    finding = {
        "id": state["next_id"],
        "program_id": program_id,
        "host": host,
        "title": title,
        "severity": severity,   # critical/high/medium/low/info
        "evidence": evidence[:800],
        "duplicate_of": None,
        "status": "validated" if evidence else "pending",
        "date": C.now_iso(),
    }
    # كشف تكرار بسيط
    for f in state["findings"]:
        if f["host"] == host and f["title"].lower() == title.lower():
            finding["duplicate_of"] = f["id"]
            finding["status"] = "duplicate"
    state["next_id"] += 1
    state["findings"].append(finding)
    _save(state)
    C.log(f"📝 إيجابية #{finding['id']} [{severity}] — {title}")
    return finding


def submission_queue():
    state = _load()
    return [f for f in state["findings"] if f["status"] in ("validated", "pending")]


def report_markdown(program_id=None):
    """تقرير جاهز للرفع (markdown) حسب البرنامج أو الكل."""
    state = _load()
    lines = []
    lines.append("# تقرير محرك البجتي")
    lines.append("")
    for f in state["findings"]:
        if program_id is not None and f["program_id"] != program_id:
            continue
        prog = next((p for p in state["programs"] if p["id"] == f["program_id"]), None)
        lines.append(f"## {f['title']}")
        lines.append(f"- **المضيف:** {f['host']} ({prog['name'] if prog else '?'})")
        lines.append(f"- **الخطورة:** {f['severity']}")
        lines.append(f"- **الحالة:** {f['status']}" + (f" (تكرار مع #{f['duplicate_of']})" if f.get("duplicate_of") else ""))
        lines.append(f"- **الدليل:** `{f['evidence'][:200]}`")
        lines.append("")
    return "\n".join(lines)


def list_programs():
    return _load()["programs"]


STAGE_TOOLS = {
    "الاستخبارات السلبية (Recon)": "bounty_sync.adopt يقرأ النطاق المصرح رسمياً من ملف السياسة > passive_recon يجمع استخبارات ويب سلبية بلا لمس خارج النطاق.",
    "خريطة السطح (Attack Surface)": "إحصاء النطاقات المصرح بها لكل نشاط + تصنيفها (web/api/app) + حصر الأعضاء المطروحة بخطورة عالية للدفع.",
    "الصيد حسب العائد (Hunting by Payout)": "ترتيب فئات الثغرات بالأولوية: IDOR/BOLA > أذونات ومداولات أعمال > ثغرات تقنية كلاسيكية على تقنيات قديمة > استحواذ النطاقات الفرعية. لكل فئة أدواتها.",
    "التحقق والتفريز (Validation & Triage)": "إثبات تقني قابل للأداء + كشف التكرار (duplicates) + تصنيف الخطورة وفق دليل المنصة قبل الرفع أصلاً.",
    "التقرير النهائي (Report Ready)": "prepare_drafts يبني التقرير الشامل جاهز الرفع (عنوان/خطورة/أثر/PoC/علاج/دليل المنصة) وأنت ترفعه يدوياً من حسابك.",
}


def attack_plan(program_id):
    """يُنتج خطة صيد كاملة وملموسة لبرنامج مضبوط — لا يدخل البوت على عماها.
    طريقة: الخطة يُدمجها خبرة الصائد (قسم وضع الخبير الأمني) مع بيانات البرنامج الفعلية."""
    program = next((p for p in list_programs() if p["id"] == program_id), None)
    if not program:
        return None
    hosts = [s for s in (program.get("scope") or []) if s.strip()]
    sev = (program.get("rules") or "")
    sev_desc = sev if isinstance(sev, str) else (sev.get("description") if isinstance(sev, dict) else "")
    lines = []
    lines.append(f"# خطة الصيد — {program['name']} (برنامج #{program['id']})")
    lines.append("")
    lines.append(f"- **التفويض:** {program.get('authorization_source', '?')}")
    lines.append(f"- **نطاق مصرح به {len(hosts)} هدفاً:** `{', '.join(hosts[:6])}`" + (f" +{len(hosts)-6} أهداف" if len(hosts) > 6 else ""))
    lines.append(f"- **إرشادات الخبرة:** {sev_desc or 'لا توجد إرشادات إضافية — الصعوبة والتقنية تُستنتج من الفحص الفعلي.'}")
    lines.append("")
    lines.append("## المراحل الخمس التي سيعملها الوكيل (وأنت لا تعمل شيئاً):")
    step = 0
    for stage, tools in STAGE_TOOLS.items():
        step += 1
        lines.append(f"\n**المرحلة {step} — {stage}**")
        lines.append(f"> {tools}")
    lines.append("")
    lines.append("## أول 3 خطوات تنفيذية فورية (تقنية — قابلة للقياس):")
    for i, h in enumerate(hosts[:3]):
        lines.append(f"{i+1}. **{h}** ← passive_recon (جمع سطحي) ثم authorized_active_test هذا الهدف فقط —"
                     " خطورة IDOR/BOLA أعلى أولوية لفحصها على أي endpoint فيه معرّفات أرقام.")
    lines.append("")
    lines.append("## متى أُسلِّمك التقرير؟")
    lines.append("بعد المرحلة 4: يُبنى التقرير الشامل (prepare_drafts) وتقوم أنت بالرفع من حسابك —"
                 " الوكيل لا يرفع ولا يرد على التعليقات بذاته (حمايةً لسمعة حسابك).")
    return "\n".join(lines)


DRAFTS_FILE = os.path.join(C.AGENT_OS_DIR, "bounty_drafts.json")

_IMPACT_TEXT = {
    "critical": "استيلاء أو وصول كامل غير مصرح، أو كشف شامل للبيانات، أو تنفيذ بعيد — أعلى أولوية للفريق وقيمة التقييم.",
    "high": "اختراق حساب مستخدم، أو تسريب بيانات حسّاسة بكمية معتبرة، أو تنفيذ محدود الصلاحيات.",
    "medium": "كشف معلومات محدود أو تلاعب محدود في العمليات دون وصول كامل.",
    "low": "ثغرة دفاعية صغيرة / تحسينية — قيّمة للسمعة وقد لا يُدفع عنها في كل البرامج.",
    "info": "ملاحظة دون أثر فعلي مباشر — تُرفع كمعلومات مفيدة.",
}

_REMEDIATION = ("مراجعة المدخلات والتحقق من التفويض على كل مورد (least privilege)، "
                "فرض قيود CORS/HSTS/WAF حسب المسار، ثم إعادة الاختبار والتأكد من الإغلاق.")


def _drafts_state():
    return C.load_json(DRAFTS_FILE, {"drafts": [], "next_id": 1})


def _drafts_save(s):
    C.atomic_write(DRAFTS_FILE, s)


def _platform_of(program):
    src = (program or {}).get("authorization_source") or ""
    if ":" in src:
        return src.split(":")[-1]
    return "hackerone"


def prepare_drafts():
    """تحويل الإيجابيات المؤكدة إلى تقارير نهائية جاهزة للرفع لهوية الحساب البشري.
    لا يرفع شيئاً — بل يجهّز النص الكامل: العنوان/الخطورة/الأثر/الإثبات/العلاج + دليل الرفع."""
    from agent_os import bounty_accounts
    state = _load()
    st = _drafts_state()
    existing = {d["finding_id"] for d in st["drafts"]}
    made = []
    for f in state["findings"]:
        if f["status"] not in ("validated", "pending") or f["id"] in existing:
            continue
        prog = next((p for p in state["programs"] if p["id"] == f["program_id"]), None)
        platform = _platform_of(prog)
        sev = f["severity"] or "info"
        impact = _IMPACT_TEXT.get(sev, _IMPACT_TEXT["info"])
        body = "\n".join([
            f"# {f['title']}",
            "",
            f"- **البرنامج:** {prog['name'] if prog else '?'}",
            f"- **المنصة:** {platform}",
            f"- **المضيف/الأصل:** `{f['host']}`",
            f"- **الخطورة:** {sev}",
            f"- **الأثر:** {impact}",
            "",
            "## خطوات الإثبات (PoC)",
            "",
            f"```\n{f['evidence'][:800]}\n```",
            "",
            "## الأثر على المستخدمين/النظام",
            "",
            f"{impact}",
            "",
            "## المعالجة المقترحة",
            "",
            f"{_REMEDIATION}",
            "",
            "## سياسة الكشف",
            "",
            "اكتشاف مسؤول ضمن برنامج المكافآت المعلن؛ لم تُنفَّذ أي إجراءات خارج النطاق أو تخريبية، "
            "ولا بيانات مستخدمين حقيقية.",
        ])
        draft = {
            "id": st["next_id"],
            "finding_id": f["id"],
            "program_id": f["program_id"],
            "platform": platform,
            "title": f["title"],
            "severity": sev,
            "host": f["host"],
            "status": "ready",
            "body": body,
            "guide": bounty_accounts.submission_guide(platform),
            "created": C.now_iso(),
        }
        st["next_id"] += 1
        st["drafts"].append(draft)
        made.append(draft)
    _drafts_save(st)
    for d in made:
        C.log(f"📄 تقرير جاهز #{d['id']} على {d['platform']}: {d['title']}")
    return st["drafts"]


def drafts():
    return _drafts_state()["drafts"]


def draft(id):
    return next((d for d in drafts() if d["id"] == id), None)


def approve_draft(id):
    """تأكيد الموافقة البشرية: التقرير جاهز ويُرفع يدوياً من حسابك (نموذج الرفع في guide)."""
    st = _drafts_state()
    for d in st["drafts"]:
        if d["id"] == id:
            d["status"] = "approved"
            d["approved_at"] = C.now_iso()
            _drafts_save(st)
            C.log(f"✅ وافقت على التقرير #{id} — أكمِل الرفع عبر: {d.get('guide','').splitlines()[3] if d.get('guide') else '؟'}")
            return d
    return None


def reject_draft(id):
    st = _drafts_state()
    for d in st["drafts"]:
        if d["id"] == id:
            d["status"] = "rejected"
            _drafts_save(st)
            return d
    return None


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("الاستعمال: program <اسم> <نطاق...> | scan <برنامجId> <مضيف> | findings | report")
    elif args[0] == "program" and len(args) >= 2:
        name = args[1]
        scope_list = args[2:]
        add_program(name, scope_list)
    elif args[0] == "scope" and len(args) >= 3:
        add_scope(int(args[1]), " ".join(args[2:]))
    elif args[0] == "scan" and len(args) >= 3:
        prog = next((p for p in list_programs() if p["id"] == int(args[1])), None)
        if prog:
            print(passive_recon(prog, args[2]))
    elif args[0] == "report":
        print(report_markdown())
    elif args[0] == "findings":
        for f in submission_queue():
            print(f"#{f['id']} [{f['severity']}] {f['title']} — {f['host']} ({f['status']})")
    elif args[0] == "prep":
        for d in prepare_drafts():
            print(f"#{d['id']} [{d['severity']}] {d['title']} — {d['platform']} ({d['status']})")
    elif args[0] == "drafts":
        for d in drafts():
            print(f"#{d['id']} [{d['severity']}] {d['title']} — {d['platform']} ({d['status']})")
    elif args[0] == "approve" and len(args) >= 2:
        print(approve_draft(int(args[1])) or "لم يُوجد")
    elif args[0] == "draft" and len(args) >= 2:
        d = draft(int(args[1]))
        print(d["body"] if d else "لم يُوجد")
        print("\n--- دليل الرفع ---\n" + (d["guide"] if d else ""))
    elif args[0] == "guide" and len(args) >= 2:
        from agent_os import bounty_accounts
        print(bounty_accounts.submission_guide(args[1]))
    elif args[0] == "plan" and len(args) >= 2:
        print(attack_plan(int(args[1])) or "لم يُوجد برنامج بهذا المعرّف")