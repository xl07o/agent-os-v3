"""
human_requests.py - طابور الطلبات البشرية الذكي — §37 موسّع
============================================================
فكرة المالك: "اذا احتاج تدخل مني يكون له ملف بالطلبات اللي يبيها
              وانفذها له... مثل إنشاء حساب بنكي واحطها بملف المنفذة"
التوسيع: طابور ذكي:
  - يرتّب بالأولوية (عاجل/مهم/عادي)
  - يتتبع الحالة (معلّق → منفّذ → مكتمل)
  - لمّا المالك ينفّذ طلباً ويعلّمه "منفّذ"، الوكيل يكمل تلقائياً
  - لا يوقف كل شي عشان طلب واحد (يكمل مهام ثانية)
"""

import os
import sys
import uuid

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

REQUESTS_FILE = os.path.join(C.AGENT_OS_DIR, "human_requests.json")

PRIORITIES = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _load():
    return C.load_json(REQUESTS_FILE, {"pending": [], "completed": []})


def _save(data):
    C.atomic_write(REQUESTS_FILE, data)


def request(reason, instructions, priority="medium", context=""):
    """ينشئ طلباً جديداً للمالك."""
    data = _load()
    req = {
        "id": f"REQ-{uuid.uuid4().hex[:6]}",
        "reason": reason,
        "instructions": instructions if isinstance(instructions, list) else [instructions],
        "priority": priority,
        "priority_score": PRIORITIES.get(priority, 2),
        "context": context[:300],
        "status": "pending",
        "created_at": C.now_iso(),
        "completed_at": None,
        "owner_notes": "",
    }
    data["pending"].append(req)
    data["pending"].sort(key=lambda r: r["priority_score"], reverse=True)
    _save(data)
    C.log(f"📋 طلب جديد للمالك [{priority}]: {reason[:60]}")
    return req


def complete(request_id, notes=""):
    """المالك ينفّذ طلباً — الوكيل يعرف ويكمل العمل المعلّق."""
    data = _load()
    found = None
    for i, r in enumerate(data["pending"]):
        if r["id"] == request_id:
            found = data["pending"].pop(i)
            break
    if not found:
        return {"error": "طلب غير موجود"}
    found["status"] = "completed"
    found["completed_at"] = C.now_iso()
    found["owner_notes"] = notes[:300]
    data["completed"].append(found)
    data["completed"] = data["completed"][-200:]
    _save(data)
    C.log(f"✅ طلب {request_id} نُفّذ بواسطة المالك")
    return found


def pending():
    """الطلبات المعلّقة مرتّبة بالأولوية."""
    return _load()["pending"]


def pending_count():
    return len(_load()["pending"])


def summary():
    """ملخّص للتقرير الصباحي."""
    data = _load()
    p = data["pending"]
    critical = sum(1 for r in p if r["priority"] == "critical")
    return {
        "pending": len(p),
        "critical": critical,
        "completed_total": len(data["completed"]),
        "top_request": p[0]["reason"][:60] if p else None,
    }


if __name__ == "__main__":
    request("أنشئ حساب Stripe للدفع", ["ادخل stripe.com", "سجّل", "أرسل المفتاح"],
            priority="high", context="مطلوب لمشروع المتجر")
    request("فعّل 2FA على GitHub", ["ادخل إعدادات الأمان"], priority="medium")
    print(f"طلبات معلّقة: {pending_count()}")
    for r in pending():
        print(f"  [{r['priority']}] {r['reason']}")
