"""
capability_gap.py - محلل فجوات القدرات (Capability Gap Analyzer) — §13-14
=========================================================================
يجيب على سؤال المواصفة: "وش الأشياء اللي ما أقدر أسويها؟"

يفحص القدرات المطلوبة لمهمة مقابل ما هو مسجَّل فعلاً (أدوات/مهارات/مكتبات)،
ويعيد الفجوات مع مسار سدّها: بحث → تعلّم → تثبيت → اختبار → تسجيل.
"""

import os
import sys
import importlib.util

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

GAP_FILE = os.path.join(C.AGENT_OS_DIR, "capability_gaps.json")

# خريطة: قدرة → المكتبة/الأداة التي توفّرها (للفحص الفعلي)
CAPABILITY_REQUIREMENTS = {
    "browser_automation": ["selenium", "playwright"],
    "computer_control": ["pyautogui"],
    "web_scraping": ["bs4", "requests"],
    "data_analysis": ["pandas"],
    "image_processing": ["PIL"],
    "pdf_handling": ["pypdf", "fitz"],
    "system_monitoring": ["psutil"],
    "http_requests": ["requests"],
}


def _lib_available(name):
    """هل المكتبة مثبّتة فعلاً؟ (فحص حقيقي بلا استيراد كامل)."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def check_capability(capability):
    """هل القدرة متاحة؟ يعيد (متاح, الطريقة المتاحة أو None)."""
    reqs = CAPABILITY_REQUIREMENTS.get(capability)
    if reqs is None:
        return None, "قدرة غير معروفة — تحتاج تعريفاً"
    for lib in reqs:
        if _lib_available(lib):
            return True, lib
    return False, reqs[0]   # نقترح أول بديل لسدّ الفجوة


def analyze(required_capabilities):
    """يحلل قائمة قدرات مطلوبة ويعيد المتاح والمفقود مع خطة السدّ."""
    have, missing = [], []
    for cap in required_capabilities:
        ok, via = check_capability(cap)
        if ok:
            have.append({"capability": cap, "via": via})
        else:
            missing.append({
                "capability": cap,
                "suggested_lib": via,
                "acquisition_path": [
                    "ابحث عن الأداة/المكتبة",
                    "تحقق من الترخيص والأمان",
                    f"ثبّت {via} (بموافقة إن لزم)",
                    "اختبر في بيئة معزولة",
                    "سجّل القدرة في tool_registry",
                ],
            })
    if missing:
        _persist_gaps(missing)
    return {
        "have": have,
        "missing": missing,
        "coverage": round(len(have) / max(len(required_capabilities), 1), 3),
        "ready": len(missing) == 0,
    }


def _persist_gaps(missing):
    """يسجّل الفجوات المكتشفة لتتبّعها عبر الجلسات (لا حذف — §26)."""
    try:
        state = C.load_json(GAP_FILE, {"gaps": []})
        known = {g["capability"] for g in state["gaps"]}
        for m in missing:
            if m["capability"] not in known:
                state["gaps"].append({"capability": m["capability"],
                                      "suggested_lib": m["suggested_lib"],
                                      "detected_at": C.now_iso(),
                                      "status": "open"})
        C.atomic_write(GAP_FILE, state)
    except Exception as e:
        C.log(f"⚠️ فجوات لم تُحفظ: {e}")


def open_gaps():
    """يعيد الفجوات المفتوحة (لم تُسدّ بعد) — للوحة والتقرير الصباحي."""
    state = C.load_json(GAP_FILE, {"gaps": []})
    return [g for g in state["gaps"] if g.get("status") == "open"]


if __name__ == "__main__":
    result = analyze(["web_scraping", "browser_automation", "quantum_teleport"])
    print(f"التغطية: {result['coverage']} | جاهز: {result['ready']}")
    for m in result["missing"]:
        print(f"  فجوة: {m['capability']} → جرّب {m['suggested_lib']}")
