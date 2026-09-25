"""
provenance.py - نسب المعرفة (Knowledge DNA)
============================================
كل معلومة يخزّنها الوكيل تحمل: القيمة + المصدر + درجة الثقة + نوعها +
لحظة آخر تحقق. ولكل نوع صلاحية زمنية (TTL): السعر يتقادم بيوم، الحقيقة
العامة بشهر. هكذا يعرف الوكيل ما الذي يحتاج إعادة تحقق قبل أن يبني عليه.

  record(key, value, source, confidence, kind) -> يخزّن/يحدّث
  get(key)                                     -> العنصر أو None
  is_stale(key, now=None)                      -> هل تقادم؟
  mark_verified(key)                           -> تحديث لحظة التحقق
  stale_keys(now=None)                         -> كل المفاتيح المتقادمة
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import _common as C

# صلاحية كل نوع بالأيام — بعدها تُعتبر المعرفة متقادمة وتحتاج إعادة تحقق.
TTL_DAYS = {
    "price": 1, "rate": 1, "news": 1, "market": 1, "stock": 1,
    "fact": 30, "definition": 90, "skill": 90, "config": 365,
}
DEFAULT_TTL_DAYS = 7


def _file():
    return os.path.join(C.AGENT_OS_DIR, "provenance.json")


def _load():
    return C.load_json(_file(), {"items": {}})


def _save(st):
    C.atomic_write(_file(), st)


def _parse(ts):
    """تحويل نص ISO إلى datetime (يتحمّل الصيغ الجزئية)."""
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(ts)
    except ValueError:
        try:
            return datetime.datetime.fromisoformat(ts.split("T")[0])
        except ValueError:
            return None


def record(key, value, source="", confidence=0.7, kind="fact"):
    """يخزّن معلومة بنَسَبها الكامل. يحدّث القائمة إن وُجد المفتاح."""
    st = _load()
    now = C.now_iso()
    item = {
        "value": value,
        "source": source or "unknown",
        "confidence": round(float(confidence), 3),
        "kind": kind,
        "recorded": st.get("items", {}).get(key, {}).get("recorded", now),
        "last_verified": now,
    }
    st.setdefault("items", {})[key] = item
    _save(st)
    return item


def get(key):
    return _load().get("items", {}).get(key)


def _ttl_days(kind):
    return TTL_DAYS.get((kind or "").lower(), DEFAULT_TTL_DAYS)


def is_stale(key, now=None):
    """هل تجاوز العنصر صلاحيته منذ آخر تحقق؟ (مفتاح غير موجود = ليس متقادماً)."""
    item = get(key)
    if not item:
        return False
    verified = _parse(item.get("last_verified"))
    if verified is None:
        return True
    now = now or datetime.datetime.now()
    age = now - verified
    return age > datetime.timedelta(days=_ttl_days(item.get("kind")))


def mark_verified(key):
    """يجدّد لحظة التحقق (المعلومة أُعيد التأكد منها الآن)."""
    st = _load()
    item = st.get("items", {}).get(key)
    if not item:
        return False
    item["last_verified"] = C.now_iso()
    _save(st)
    return True


def stale_keys(now=None):
    """كل المفاتيح التي تقادمت وتحتاج إعادة تحقق."""
    st = _load()
    return [k for k in st.get("items", {}) if is_stale(k, now=now)]


if __name__ == "__main__":
    import json
    print(json.dumps({"items": len(_load().get("items", {})),
                      "stale": stale_keys()}, ensure_ascii=False, indent=2))
