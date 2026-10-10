"""
بوابة الموافقة الوحيدة. القاعدة: مستويان فقط، لا ثالث.

- AUTO: قراءة، بحث، محادثة — بلا أي أثر جانبي. ينفَّذ فوراً.
- NEEDS_APPROVAL: أي شيء له أثر جانبي حقيقي (أمر نظام، كتابة ملف، حذف،
  مال، تعديل كود الوكيل نفسه). يُحفظ كطلب معلّق ولا يُنفَّذ أبداً تلقائياً
  — لا موافقة ضمنية بالصمت، ولا مهلة زمنية تنتهي بتنفيذ تلقائي. هذا كان
  أكثر خطأ تكرر في كل التصاميم التي رُفضت: تصنيف "متوسط" ينفَّذ تلقائياً
  مع إشعار لاحق فقط. هنا لا يوجد "متوسط".

كل طلب يبقى pending حتى يرد المستخدم صراحة عبر resolve().
"""

import json
import os
import time
import uuid

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_FILE = os.path.join(_DATA_DIR, "approvals.json")

AUTO = "auto"
NEEDS_APPROVAL = "needs_approval"


def _load() -> list[dict]:
    if not os.path.exists(_FILE):
        return []
    with open(_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(requests: list[dict]) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(requests, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _FILE)


def request(what: str, why: str, level: str, proposed_by: str = "owner") -> tuple[bool, str | None]:
    """
    تُستدعى قبل أي فعل. ترجع (True, None) إذا نُفّذ فوراً (AUTO)،
    أو (False, request_id) إذا يحتاج موافقة — الفعل لا يُنفَّذ، المستدعي
    يتوقف عند هذه النقطة ويعرض للمستخدم أن هناك طلباً معلّقاً.

    proposed_by: من اقترح الطلب (اسم دور من roles.py، أو "owner" افتراضياً
    لما يكون المستخدم نفسه). توثيق فقط — لا يمنح أي صلاحية موافقة ذاتية.
    """
    if level == AUTO:
        return True, None
    req = {
        "id": uuid.uuid4().hex[:8],
        "what": what,
        "why": why,
        "proposed_by": proposed_by,
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    reqs = _load()
    reqs.append(req)
    _save(reqs)
    return False, req["id"]


def pending() -> list[dict]:
    return [r for r in _load() if r["status"] == "pending"]


def get(request_id: str) -> dict | None:
    for r in _load():
        if r["id"] == request_id:
            return r
    return None


def resolve(request_id: str, approved: bool, decided_by: str = "owner") -> bool:
    """يرجع True لو لُقي الطلب وحُدّث. decided_by توثيق فقط — الحسم
    الفعلي دائماً يتطلب استدعاء هذي الدالة صراحةً، لا تنفيذاً تلقائياً."""
    reqs = _load()
    for r in reqs:
        if r["id"] == request_id and r["status"] == "pending":
            r["status"] = "approved" if approved else "rejected"
            r["decided_by"] = decided_by
            r["resolved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _save(reqs)
            return True
    return False
