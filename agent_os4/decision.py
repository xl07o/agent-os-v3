"""
منظومة الفصل في القرارات (ADJUDICATION & DECISION SYSTEM) — طبقة تسمية
وتوثيق فوق approval.py الموجودة، لا نظام تخزين جديد ولا بوابة موافقة
ثانية. كل الأسماء بهيكلك (Decision Engine, Approval Authority, Rejection
Authority, Decision Evidence Ledger, Appeals & Reconsideration Board,
Independent Review) تصف نفس العملية الواحدة: طلب ← (مراجعة مستقلة
تلقائية لو الطلب يلمس ملفاً حساساً) ← موافقة صاحب النظام الصريحة ← تنفيذ.

لا سلطة هنا تنفّذ شيئاً بدون موافقة صاحب النظام (Owner Authority). هذا
قرار تصميم ثابت، لا استثناء له — نفس مبدأ approval.py تماماً، بأسماء
توثّق "من اقترح" و"من قرر" لكل طلب.
"""

import json
import os
import time

from . import approval, memory, obsidian, roles

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_LEDGER_FILE = os.path.join(_DATA_DIR, "decision_ledger.json")

# ملفات حساسة تستاهل تحذيراً إضافياً صريح بنص المراجعة (مو شرط تفعيلها
# — المراجعة الآن تصير لكل طلب بلا استثناء، راجع propose()).
HIGH_RISK_MARKERS = ("safety.py", "approval.py", "decision.py", "roles.py", "selftest.py", "self_improve.py", "spend.py")


def _load_ledger() -> list[dict]:
    if not os.path.exists(_LEDGER_FILE):
        return []
    with open(_LEDGER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _append_ledger(entry: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    entries = _load_ledger()
    entries.append(entry)
    tmp = _LEDGER_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _LEDGER_FILE)


def _review_context(what: str, why: str) -> str:
    """يجمع سياقاً حقيقياً قبل المراجعة — ملاحظات Obsidian + ذكريات
    مطابقة فعلياً لنص الطلب، لا رأياً مجرّداً بلا خبرة متراكمة. هذا
    بالضبط ما يخلي المراجع "يعرف الصح عن الغلط" باستناد لتاريخ حقيقي،
    لا تخميناً من صفر بكل مرة."""
    query = f"{what} {why}"
    parts = []
    notes = obsidian.search(query, limit=4)
    if notes:
        parts.append("ملاحظات سابقة ذات صلة من Obsidian:\n" + "\n".join(
            f"- [{n['folder']}/{n['file']}] {n['excerpt'][:220].strip()}" for n in notes
        ))
    mems = memory.recall(query, limit=4)
    if mems:
        parts.append("ذكريات سابقة ذات صلة:\n" + "\n".join(f"- {m[:220]}" for m in mems))
    if any(marker in what for marker in HIGH_RISK_MARKERS):
        parts.append("تنبيه: هذا الطلب يلمس ملفاً حساساً بالنظام نفسه (أمان/موافقة/أدوار) — راجعه بعناية أكبر من المعتاد.")
    return "\n\n".join(parts)


def propose(what: str, why: str, proposed_by: str = "owner", level: str = approval.NEEDS_APPROVAL) -> dict:
    """Decision Engine: يفتح طلباً عبر approval.py، ويرفق مراجعة مستقلة
    حقيقية **لكل طلب بلا استثناء** (Independent Reviewer، مغذّاة بسياق
    فعلي من Obsidian/الذاكرة — راجع _review_context)، ويسجّل كل شيء
    بسجل الأدلة (Decision Evidence Ledger).

    المراجعة رأي إضافي يُعرَض لك دائماً، لا قرار بديل عنك — أنت من
    يوافق أو يرفض دائماً عبر approve()/reject(). هذا ثابت لا استثناء له."""
    context = _review_context(what, why)
    try:
        question = (f"{context}\n\n" if context else "") + f"الطلب: {what}\n\nالسبب: {why}"
        review = roles.consult("independent_reviewer", question)
    except Exception as e:  # noqa: BLE001 — فشل المراجعة لا يوقف الطلب، فقط يُسجَّل بصدق أنها لم تتم
        review = f"(تعذّرت المراجعة المستقلة: {type(e).__name__}: {e})"

    full_why = why + f"\n\n--- رأي المراجع المستقل ---\n{review}"
    _, req_id = approval.request(what=what, why=full_why, level=level, proposed_by=proposed_by)
    _append_ledger({
        "request_id": req_id, "what": what, "proposed_by": proposed_by,
        "independent_review": review, "stage": "proposed",
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    return {"request_id": req_id, "independent_review": review}


def record_owner_action(what: str, why: str, decided_by: str = "owner") -> str:
    """إجراء نفّذه صاحب النظام بنفسه (مثل تبديل وصول الجهاز أو تعديل سقف
    الصرف من اللوحة) — يُسجَّل بنفس السجل للشفافية، بلا مراجعة مستقلة:
    ما فيه شي يُراجَع، القرار صار فعلاً من صاحبه. وبلا استدعاء Claude
    مدفوع على لا شيء."""
    _, req_id = approval.request(what=what, why=why, level=approval.NEEDS_APPROVAL, proposed_by="owner")
    approval.resolve(req_id, approved=True, decided_by=decided_by)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    _append_ledger({
        "request_id": req_id, "what": what, "proposed_by": "owner",
        "independent_review": None, "stage": "proposed", "at": now,
    })
    _append_ledger({
        "request_id": req_id, "stage": "approved", "decided_by": decided_by,
        "reason": "إجراء مباشر من صاحب النظام", "at": now,
    })
    return req_id


def approve(request_id: str, decided_by: str = "owner", reason: str = "") -> bool:
    """Approval Authority."""
    ok = approval.resolve(request_id, approved=True, decided_by=decided_by)
    if ok:
        _append_ledger({
            "request_id": request_id, "stage": "approved",
            "decided_by": decided_by, "reason": reason,
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return ok


def reject(request_id: str, decided_by: str = "owner", reason: str = "") -> bool:
    """Rejection Authority — الرفض يجب يكون مسبباً، لا بصمت."""
    ok = approval.resolve(request_id, approved=False, decided_by=decided_by)
    if ok:
        _append_ledger({
            "request_id": request_id, "stage": "rejected",
            "decided_by": decided_by, "reason": reason,
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return ok


def appeal(request_id: str, new_evidence: str, proposed_by: str = "owner") -> dict:
    """Appeals & Reconsideration Board: يفتح طلباً جديداً مرتبطاً بالقديم
    — لكن فقط لو فيه دليل جديد فعلي، لا إعادة نفس سبب الرفض بلا تغيير."""
    record = approval.get(request_id)
    if not record:
        return {"ok": False, "error": "طلب غير موجود"}
    if record["status"] != "rejected":
        return {"ok": False, "error": f"الطلب ليس مرفوضاً (الحالة الحالية: {record['status']})"}
    if not new_evidence.strip():
        return {"ok": False, "error": "الاستئناف يحتاج دليلاً جديداً فعلياً"}

    last_rejection_reason = ""
    for entry in reversed(_load_ledger()):
        if entry.get("request_id") == request_id and entry.get("stage") == "rejected":
            last_rejection_reason = (entry.get("reason") or "").strip()
            break
    if last_rejection_reason and new_evidence.strip() == last_rejection_reason:
        return {"ok": False, "error": "الاستئناف يحتاج دليلاً جديداً فعلياً، لا تكراراً لنفس سبب الرفض"}

    result = propose(record["what"], f"استئناف لـ[{request_id}]: {new_evidence}", proposed_by=proposed_by)
    return {"ok": True, **result}


def ledger(limit: int = 50) -> list[dict]:
    """Decision Evidence Ledger + Decision Review & Audit: كل القرارات
    بترتيب زمني — من اقترح، من قرر، ورأي المراجعة المستقلة لو وُجد."""
    return _load_ledger()[-limit:]
