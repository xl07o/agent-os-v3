"""
approval_center.py - النظام 11: مركز الطلبات والموافقات البشرية (v3.0)
======================================================================
بدل توقف المهمة «أحتاج تسوي X»:

  REQUEST #N
    المطلوب / لماذا / الخطوات / الحالة
    [تنفيذي أولاً] -> [تم] -> الوكيل يستكمل من حيث توقف

لا يقرأ الوكيل أسراراً أو يفعل أعمالاً خارج حدود الموافقة إلا عبر هذا المركز.

الاستخدام:
  python agent_os/approval_center.py create "أنشئ حساباً" "سبب" "خطوات..."
  python agent_os/approval_center.py list
  python agent_os/approval_center.py done <id>
"""

import os
import sys
import datetime
import hashlib
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

REQUESTS_FILE = os.path.join(C.AGENT_OS_DIR, "requests.json")
STATE_FILE = REQUESTS_FILE  # مرجع ثانٍ للتوافق مع أي وحدة قرأت بالاسم القديم


def _load():
    return C.load_json(REQUESTS_FILE, {"requests": [], "next_id": 1})


def _save(s):
    C.atomic_write(REQUESTS_FILE, s)


def create_request(what, why="", steps=None, resume_hint="", kind="other", risk="medium", payload=None, blocking_task_id=None):
    """إنشاء طلب بشري.
    kind: financial | account_creation | credential | code_change | external_action | other
    risk: low | medium | high — يستخدمه الداشبورد للتلوين والتنبيه.
    """
    state = _load()
    rid = state["next_id"]
    state["next_id"] += 1
    req = {
        "id": rid,
        "what": what[:200],
        "why": why[:300],
        "steps": (steps or [])[:10],
        "status": "pending",          # pending / in_progress / done / cancelled
        "resume_hint": (resume_hint or "")[:200],
        "kind": kind if kind in ("financial", "account_creation", "credential", "code_change", "external_action", "other") else "other",
        "risk": risk if risk in ("low", "medium", "high") else "medium",
        "payload": payload or {},
        "payload_hash": hashlib.sha256(json.dumps(payload or {}, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        "blocking_task_id": blocking_task_id,
        "created": C.now_iso(),
        "resolved": None,
    }
    state["requests"].append(req)
    _save(state)
    C.log(f"🙋 طلب #{rid} [{req['risk']}] {what}")
    return req


def _apply_immediately(req):
    """إذا وافق الإنسان على تعديل حرج من محرك التحسين — طُبِّق الآن بلا انتظار
    دورة قادمة (عيب 1): الحلقة بين الإنسان والوكيل تُغلق لحظياً."""
    if not req or req.get("kind") != "code_change":
        return
    try:
        from agent_os import self_improve_engine as si
        res = si.apply_critical_patch(req["id"])
        if isinstance(res, dict) and res.get("status") == "applied":
            C.log(f"✅ طُبِّق فوراً بموافقتك: {req.get('payload', {}).get('target')}")
    except Exception as e:
        C.log(f"⚠️ تعذّر التطبيق الفوري: {str(e)[:120]}")


def approve(rid, by="user"):
    """تأكيد أن الطلب نفَّذه الإنسان."""
    state = _load()
    req = next((r for r in state["requests"] if r["id"] == rid), None)
    if req and req.get("status") == "pending":
        current_hash = hashlib.sha256(json.dumps(req.get("payload", {}), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        if current_hash != req.get("payload_hash"):
            req["status"] = "cancelled"
            req["resolved"] = C.now_iso()
            req["resolution_reason"] = "payload tampered before approval"
            _save(state)
            return req
        req["status"] = "done"
        req["resolved"] = C.now_iso()
        req["approved_by"] = by
        _save(state)
        _apply_immediately(req)
    return req


def resume(rid):
    """بعد موافقة الإنسان: استكمل عمل الوكيل من حيث توقف (معالجة تلقائية)."""
    state = _load()
    req = next((r for r in state["requests"] if r["id"] == rid), None)
    if not req:
        return {"ok": False, "reason": "لا طلب"}
    hint = (req.get("resume_hint") or "").strip()
    if req["status"] != "done":
        return {"ok": False, "reason": "الطلب لم يُقبل بعد"}
    if not hint:
        return {"ok": False, "reason": "لا تعليمات استكمال"}
    try:
        from agent_os import agent_os as nucleus
        result = nucleus.run_task(hint)
        req["resumed"] = C.now_iso()
        req["resume_result"] = result.get("result", {}).get("status", "؟")
        _save(state)
        C.log(f"⏯️ استئناف #{rid}: {hint}")
        return {"ok": True, "result": req["resume_result"]}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120]}


def mark_in_progress(rid):
    state = _load()
    req = next((r for r in state["requests"] if r["id"] == rid), None)
    if req:
        req["status"] = "in_progress"
        _save(state)
    return req


def cancel(rid):
    state = _load()
    req = next((r for r in state["requests"] if r["id"] == rid), None)
    if req:
        req["status"] = "cancelled"
        req["resolved"] = C.now_iso()
        _save(state)
    return req


def list_requests(status=None):
    reqs = _load()["requests"]
    if status:
        reqs = [r for r in reqs if r["status"] == status]
    return reqs


def pending_summary():
    pending = list_requests("pending")
    if not pending:
        return None
    most = pending[0]
    return f"REQUEST #{most['id']}: {most['what']} — لماذا: {most['why']}"


def pending_count():
    """عدد الطلبات المعلّقة — يُعرض في رأس حلقة التشغيل."""
    return len(list_requests("pending"))


def check_resolution(rid):
    """يستعلمها الموظف: هل طلبه اتحلّ؟ يعيد الطلب بحاله، أو None إن ما زال معلقاً."""
    for r in list_requests():
        if r["id"] == rid and r["status"] != "pending":
            return r
    return None


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("الاستعمال: create <ماذا> [لماذا] [خطوات] | list | done <id> | resume <id> | pending")
    elif args[0] == "create" and len(args) >= 2:
        create_request(args[1], " ".join(args[2:3]), args[3:])
    elif args[0] == "list":
        for r in list_requests():
            print(f"#{r['id']} [{r['status']}] {r['what']} — {r['why'][:60]}")
    elif args[0] == "done" and len(args) > 1:
        approve(int(args[1]))
    elif args[0] == "resume" and len(args) > 1:
        print(resume(int(args[1])))
    elif args[0] == "pending":
        print(pending_summary() or "لا طلبات معلّقة")