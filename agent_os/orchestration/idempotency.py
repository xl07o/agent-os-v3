"""
idempotency.py - طبقة عدم التكرار (Idempotency Layer) — §55
============================================================
لا يكرّر العمليات الخطرة (دفع، نشر، هجرة قاعدة، إنشاء حساب) لمجرد إعادة
التشغيل. كل عملية حسّاسة لها مفتاح فريد؛ إن نُفّذت مسبقاً لا تُعاد.
"""

import os
import sys
import hashlib
import json

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

LEDGER_FILE = os.path.join(C.AGENT_OS_DIR, "idempotency_ledger.json")

# العمليات التي يجب ألا تتكرر أبداً بلا مفتاح صريح
DANGEROUS_OPS = {"payment", "deployment", "db_migration", "account_creation",
                 "publishing", "email_send", "purchase", "api_provision"}


def make_key(operation, *parts):
    """يبني مفتاحاً حتمياً من نوع العملية ومعاملاتها المميّزة."""
    raw = operation + "::" + "::".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _load():
    return C.load_json(LEDGER_FILE, {"done": {}})


def already_done(key):
    """هل نُفّذت هذه العملية من قبل؟ يعيد السجل أو None."""
    return _load()["done"].get(key)


def mark_done(key, operation, result=None):
    """يسجّل عملية كمنتهية (كتابة ذرّية)."""
    state = _load()
    state["done"][key] = {
        "operation": operation,
        "at": C.now_iso(),
        "result": str(result)[:300] if result is not None else None,
    }
    C.atomic_write(LEDGER_FILE, state)
    return state["done"][key]


def run_once(operation, key_parts, action, force=False):
    """ينفّذ action مرة واحدة فقط لهذا المفتاح.

    operation: نوع العملية (يُفضّل من DANGEROUS_OPS).
    key_parts: قائمة معاملات مميّزة (مثل معرّف الطلب، المبلغ، المستلم).
    action: دالة بلا وسائط تُنفّذ العملية وتعيد نتيجة.
    force: تجاوز الحماية (للاختبار/الحالات الخاصة).

    يعيد dict: {executed, skipped, result, key}.
    """
    key = make_key(operation, *key_parts)
    prior = already_done(key)
    if prior and not force:
        C.log(f"⏭️ عملية مكرّرة مُتخطّاة [{operation}] key={key}")
        return {"executed": False, "skipped": True,
                "result": prior.get("result"), "key": key,
                "reason": "نُفّذت مسبقاً — منع التكرار"}
    try:
        result = action()
    except Exception as e:
        # فشل التنفيذ لا يُسجَّل كمنتهٍ — يمكن إعادة المحاولة بأمان
        C.log(f"⚠️ فشل عملية [{operation}]: {e}")
        return {"executed": False, "skipped": False,
                "result": None, "key": key, "error": str(e)[:150]}
    mark_done(key, operation, result)
    return {"executed": True, "skipped": False, "result": result, "key": key}


def is_dangerous(operation):
    return operation in DANGEROUS_OPS


if __name__ == "__main__":
    calls = {"n": 0}

    def pay():
        calls["n"] += 1
        return f"دُفع (استدعاء {calls['n']})"

    r1 = run_once("payment", ["invoice-123", "500SAR"], pay)
    r2 = run_once("payment", ["invoice-123", "500SAR"], pay)   # نفس المفتاح
    print("الأولى:", r1["executed"], "|", r1["result"])
    print("الثانية:", r2["executed"], "(تُخطّيت) |", r2["result"])
    print("عدد التنفيذ الفعلي:", calls["n"], "(يجب أن يكون 1)")
