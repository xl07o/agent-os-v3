"""
benchmark.py - النظام 3: قياس ذكاء الوكيل (Agent IQ / Benchmark)
===============================================================
يقيس كفاءة الموظف نفسه (لا كود المشروع فقط) في مجالات:

coding, debugging, research, reasoning, planning,
security, business, writing, data_analysis, tool_usage, browser, long_horizon

النتيجة: نسبة لكل مجال، وأضعف المجالات تغذي محرك التعلم والإتقان.

الاستخدام:
  python agent_os/benchmark.py run
  python agent_os/benchmark.py summary
"""

import os
import re
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C


RESULTS_FILE = os.path.join(C.AGENT_OS_DIR, "benchmark_results.json")

DOMAINS = [
    "coding", "debugging", "research", "reasoning", "planning",
    "security", "business", "writing", "data_analysis", "tool_usage",
    "browser", "long_horizon",
]


# ===== مهمات قياسية ظاهرة للعقل بدون شبكة =====

_TASKS = {
    "coding": ("اكتب دالة Python تجمع الأرقام الزوجية فقط من قائمة.", ["def", "return"]),
    "debugging": ("ما سبب الخطأ المتوقع في: x = []\nprint(x[5]) ؟", ["index", "خارج", "range"]),
    "reasoning": ("إذا كان 3 أصدقاء يبنون منزلاً في 6 أيام، كم يوماً يحتاج 6 أصدقاء؟", ["3"]),
    "planning": ("خطة من 3 خطوات لإطلاق تطبيق ويب صغير.", ["خطوة", "خطوة"] if False else ["1.", "2.", "3."]),
    "security": ("بماذا تحمي ملف .env من التسريب في مشروع محلي؟", [".gitignore", "لا يُرفع"]),
    "research": ("كيف أستعلم عن حالة وحدة python-dotenv بأمر واحد؟", ["pip", "show"]),
    "business": ("اقترح فكرة MVP صغيرة مربحة للأفراد.", ["فكرة", "MVP"]),
    "writing": ("اكتب إيميلي احترافياً منسقاً بجملتين.", ["مرحباً", "شكرا" if False else ".."]),
    "data_analysis": ("كيف أحسب متوسط قائمة أرقام في Python؟", ["sum", "len"]),
    "tool_usage": ("ما الأمر الآمن للتحقق من نسخة Python؟", ["python", "--version"]),
    "browser": ("ما المطلوب للعثور على نص في صفحة ويب طويلة؟", ["بحث", "تحكم+f" if False else "CTRL+F"]),
    "long_horizon": ("قسّم مشروعاً من أسبوع إلى 5 مهام يومية.", ["يوم 1", "يوم 2"]),
}


def _score_reply(reply, hints):
    """تقييم رد: وجود + تنوع + طول معقول + تطابق المؤشرات."""
    if not reply:
        return 0
    text = reply.lower()
    score = 20
    if len(reply.split()) >= 5:
        score += 15
    if len(set(reply.split())) >= 8:
        score += 15
    for h in hints:
        if h.lower() in text:
            score += 12
    return min(100, score)


def run_domain(domain, use_brain=True):
    """قياس مجال واحد: عقل + فحص ظاهري."""
    task, hints = _TASKS.get(domain, (f"اشرح {domain} بجملة.", []))
    if use_brain:
        import brain
        b = brain.Brain("أنت موظف ذكي يُقيّم قدرته على الإجابة.")
        try:
            raw, _ = b.ask(task, mode="smart")
        except Exception:
            raw = None
    else:
        raw = task
    return _score_reply(raw, hints)


def run_benchmark(use_brain=True):
    """قياس جميع المجالات وحفظ النتائج تراكمياً."""
    C.log("🧪 تشغيل قياس ذكاء الوكيل...")
    results = {}
    for d in DOMAINS:
        s = run_domain(d, use_brain=use_brain)
        results[d] = s
        C.log(f"  {d}: {s}%")
    entry = {
        "date": C.now_iso(),
        "engine_mode": "brain" if use_brain else "offline",
        "scores": results,
        "overall": round(sum(results.values()) / len(results), 1),
    }
    state = C.load_json(RESULTS_FILE, {"runs": []})
    state["runs"].append(entry)
    state["runs"] = state["runs"][-200:]
    C.atomic_write(RESULTS_FILE, state)
    C.log(f"✅ إجمالي: {entry['overall']}%")
    return entry


def summary():
    """آخر قياس + أضعف المجالات."""
    state = C.load_json(RESULTS_FILE, {"runs": []})
    if not state["runs"]:
        return {"overall": 0, "weakest": []}
    last = state["runs"][-1]
    scores = last["scores"]
    order = sorted(scores.items(), key=lambda kv: kv[1])
    weakest = [d for d, s in order[:3]]
    return {"date": last["date"], "overall": last["overall"], "scores": scores, "weakest": weakest}


def weakest_areas(n=2):
    """أضعف المجالات — غذاء محرك التعلم."""
    s = summary()
    return s.get("weakest", [])[:n]


# ===== ملاحظات إصلاح حتمية لكل مجال (تغذي محرك التحسين) =====

HINTS = {
    "coding": [
        "قسّم الحل لدوال صغيرة واضحة وسمِّها إنجليزية.",
        "التزم بأسلوب PEP8 والمسافات المتسقة.",
    ],
    "debugging": [
        "افحص حدود القوائم والفهارس قبل كتابة الحل.",
        "اكتب اختباراً للحالة القصوى قبل الإصلاح.",
    ],
    "reasoning": [
        "قسّم المسألة لخطوات صغيرة ووضّح المعطيات.",
        "تحقق من المنطق بمثال عددي سهل.",
    ],
    "planning": [
        "حدد الناتج النهائي أولاً ثم اشتق الخطوات.",
        "خصص لكل خطوة وقتاً ومسؤولاً واضحاً.",
    ],
    "security": [
        "راجع حماية SSRF في webtools قبل أي بحث خارجي.",
        "طبّق فلترة المدخلات لكلmodern وسيلة.",
    ],
    "research": [
        "استخدم كلمات بحث دقيقة مع عوامل تصفية.",
        "تحقق من المصدر قبل الاقتباس منه.",
    ],
    "business": [
        "ركّز على جمهور ضيق قبل التوسع.",
        "قيّم فكرة على جدول بسيط بدل الانطلاق العشوائي.",
    ],
    "writing": [
        "ابدأ بجملة افتتاحية قوية ووجّهها للقارئ.",
        "راجع القواعد النحوية ثم الإملاء.",
    ],
    "data_analysis": [
        "افحص القيم المفقودة NaN أولاً.",
        "استخدم جداول محورية واضحة في المخرجات.",
    ],
    "tool_usage": [
        "وثّق توافقات الأوامر والوسائط الشائعة.",
        "افهم الفرق بين stdout و stderr في الأخطاء.",
    ],
    "browser": [
        "انتظر تحميل الصفحة قبل استخراج النصوص.",
        "تجنب النقر المتكرر — ابحث في DOM مباشرة.",
    ],
    "long_horizon": [
        "قسّم المشروع الطويل إلى مراحل ومراجعات.",
        "أضف نقاط تحقق نhalfة في كل مرحلة.",
    ],
}


def weakest_hints(n=3):
    """أضعف المجالات مع نصائح إصلاح عملية."""
    w = weakest_areas(n)
    return {d: HINTS.get(d, ["راجع الخطوات يدوياً"]) for d in w}


# ===== تغذية موضوعية لكل مهمة (نِهاية النتائج بالأرقام) =====

FEEDBACK_FILE = os.path.join(C.AGENT_OS_DIR, "benchmark_feedback.json")


def record_result(category, score_0_to_100, note=""):
    """يُستدعى بعد أي مهمة قابلة للتقييم الموضوعي (نجاح/فشل اختبار، مهمة مكتملة...)."""
    state = C.load_json(FEEDBACK_FILE, {})
    state.setdefault(category, []).append({
        "score": max(0, min(100, float(score_0_to_100))),
        "note": note[:200],
        "time": C.now_iso(),
    })
    state[category] = state[category][-200:]
    C.atomic_write(FEEDBACK_FILE, state)
    return state[category][-1]


def current_scores():
    """متوسط آخر 20 قياس لكل فئة."""
    import statistics
    state = C.load_json(FEEDBACK_FILE, {})
    out = {}
    for c in DOMAINS:
        vals = [r["score"] for r in state.get(c, [])[-20:]]
        out[c] = round(statistics.mean(vals), 1) if vals else None
    return out


def weakest_categories(n=3):
    """الأضعف أهلاً: فئات بدون قياس أولاً (جاهلة)، ثم الأدنى رقماً."""
    scores = current_scores()
    known = {k: v for k, v in scores.items() if v is not None}
    ranked = sorted(known.items(), key=lambda kv: kv[1])
    unknown = [k for k, v in scores.items() if v is None]
    return (unknown + [k for k, _ in ranked])[:n]


def learning_time_allocation():
    """توزيع وقف وقت الإتقان القادم حسب الضعف — تستهلكه دورة التحسين."""
    scores = current_scores()
    weak = weakest_categories(len(DOMAINS))
    total = sum(max(1, 100 - (scores[c] or 50)) for c in weak)
    return {c: round(max(1, 100 - (scores[c] or 50)) / total, 3) for c in weak}


# ===== ساحة القياس (Benchmark Arena) =====

ARENA_FILE = os.path.join(C.AGENT_OS_DIR, "arena_history.json")


def arena(run=True):
    """سباق قياس دوري: شغّل كل المجالات، رتّب، وأرشيف النتائج في السجل.
    يُستخدم لمراقبة الاتجاه بين الأسابيع (هل نتحسن فعلاً؟)."""
    result = run_benchmark(use_brain=False) if run else summary()
    rank = sorted(
        [{"domain": d, "score": s} for d, s in result.get("scores", {}).items()],
        key=lambda x: x["score"], reverse=True,
    )
    hist = C.load_json(ARENA_FILE, {"rounds": []})
    hist["rounds"].append({"at": C.now_iso(), "overall": result.get("overall"),
                           "ranked": rank})
    hist["rounds"] = hist["rounds"][-30:]
    C.atomic_write(ARENA_FILE, hist)
    return {"overall": result.get("overall"), "ranked": rank,
            "rounds_kept": len(hist["rounds"])}


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "arena":
        r = arena(run=True)
        print(f"الساحة: {r['overall']}% إجمالي | {len(r['ranked'])} مجالات")
        for x in r["ranked"]:
            print(f"  {x['domain']}: {x['score']}%")
    elif args and args[0] == "run":
        run_benchmark(use_brain=False)  # بلا عقل للتشغيل الآمن البسيط
    elif args and args[0] in ("summary", "status"):
        s = summary()
        print(f"إجمالي: {s['overall']}% | أضعف: {', '.join(s.get('weakest', []))}")
        for d, sc in s.get("scores", {}).items():
            print(f"  {d}: {sc}%")
    else:
        run_benchmark(use_brain=False)