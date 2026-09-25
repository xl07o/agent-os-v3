"""
adaptive_personality.py - الشخصية المتكيّفة + المعلّم
=====================================================
يلاحظ أسلوب المالك (إيجاز/تفصيل، يسأل أولاً/يبدأ مباشرة) ويتكيّف.
ويسوّي تقارير تعليمية: "سويت كذا وتعلّمت إن كذا أحسن من كذا عشان..."
"""
import os, sys
def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

PERSONALITY_FILE = os.path.join(C.AGENT_OS_DIR, "adaptive_personality.json")
TEACHINGS_FILE = os.path.join(C.AGENT_OS_DIR, "teachings.json")

DEFAULT_PREFS = {
    "detail_level": "balanced",    # brief / balanced / detailed
    "ask_before_start": False,     # يسأل قبل ما يبدأ ولا يبدأ مباشرة
    "language": "arabic",
    "notification_level": "important",  # all / important / critical
    "interaction_count": 0,
    "observed_preferences": [],
}

def _load():
    return C.load_json(PERSONALITY_FILE, dict(DEFAULT_PREFS))

def _save(p):
    C.atomic_write(PERSONALITY_FILE, p)

def observe(signal, value):
    """يسجّل ملاحظة عن تفضيل المالك."""
    p = _load()
    p["observed_preferences"].append({
        "signal": signal, "value": value, "at": C.now_iso()
    })
    p["observed_preferences"] = p["observed_preferences"][-100:]
    p["interaction_count"] = p.get("interaction_count", 0) + 1

    # تكيّف تلقائي بناءً على الملاحظات المتراكمة
    if signal == "preferred_detail":
        p["detail_level"] = value
    elif signal == "prefers_asking":
        p["ask_before_start"] = bool(value)
    elif signal == "notification_pref":
        p["notification_level"] = value
    _save(p)
    return p

def current_style():
    """أسلوب التواصل الحالي."""
    p = _load()
    return {
        "detail": p["detail_level"],
        "ask_first": p["ask_before_start"],
        "notifications": p["notification_level"],
        "interactions": p["interaction_count"],
    }

def should_ask():
    """هل يسأل المالك قبل البدء بمهمة؟"""
    return _load().get("ask_before_start", False)

def format_response(text, max_brief=200, max_detailed=2000):
    """يختصر/يطوّل الرد حسب تفضيل المالك."""
    level = _load()["detail_level"]
    if level == "brief":
        return text[:max_brief] + ("..." if len(text) > max_brief else "")
    if level == "detailed":
        return text[:max_detailed]
    return text[:800]

# ===== المعلّم =====

def teach(topic, what_happened, what_learned, why_better=""):
    """يسجّل درساً تعليمياً للمالك."""
    log = C.load_json(TEACHINGS_FILE, {"lessons": []})
    lesson = {
        "topic": topic[:100],
        "what_happened": what_happened[:300],
        "what_learned": what_learned[:300],
        "why_better": why_better[:200],
        "at": C.now_iso(),
    }
    log["lessons"].append(lesson)
    log["lessons"] = log["lessons"][-200:]
    C.atomic_write(TEACHINGS_FILE, log)
    return lesson

def recent_teachings(n=5):
    log = C.load_json(TEACHINGS_FILE, {"lessons": []})
    return log["lessons"][-n:]

def teaching_report():
    """تقرير تعليمي للمالك: آخر 3 دروس بأسلوب سهل."""
    lessons = recent_teachings(3)
    if not lessons:
        return "لا دروس جديدة."
    lines = ["📖 دروس اليوم:"]
    for l in lessons:
        lines.append(f"• {l['topic']}: {l['what_learned']}")
        if l.get("why_better"):
            lines.append(f"  ↳ السبب: {l['why_better']}")
    return "\n".join(lines)
