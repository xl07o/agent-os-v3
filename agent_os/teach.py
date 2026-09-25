# -*- coding: utf-8 -*-
"""
teach.py - المعلم المباشر («قل له تعلّم، فيتعلّم قدامك»)
========================================================
تعلم فوري عند طلب المستخدم عبر الخيوط الآتية:

  1) استدعاء ذاكرة المهارات المتعلقة بالموضوع.
  2) عصف مكثف بالعقل (أوضح محركات مجانية) لبناء درس منظم.
  3) حفظ الدرس في data/agent_os/knowledge/<slug>.md (أرشيف معرفة).
  4) تسجيله في ذاكرة المهارات skill_memory (يُسحب في مهام لاحقة عبر _skill_hint).
  5) بث كل خطوة إلى event_bus → تظهر حيّة في سجل النشاط باللوحة.

Security/cost:
  - لا ضربات شبكة خارجية جشعة؛ المصدر هو عقل الوكيل + ذاكرته الحالية.
  - جلسة عقل واحدة تُشيَّأ عند الحاجة وتُقاس بوقت مهلة آمن.
  - الأخطاء عزلية: أي فشل يكتب ملاحظة ولا يُوقف التعليم.
"""

import os
import re
import sys
import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
from agent_os import _common as C

KNOWLEDGE_DIR = os.path.join(C.AGENT_OS_DIR, "knowledge")
BRAIN_MODE = "fastest"


def _slug(text):
    s = re.sub(r"[^\w\s-]", "", str(text), flags=re.UNICODE).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    return (s or "topic")[:60]


def _step(step_no, label, status="running", extra=""):
    import json
    from agent_os import event_bus
    event_bus.publish("teach_step", {
        "step": step_no, "label": label[:80], "status": status, "extra": str(extra)[:200]
    }, source="teach")


def _lesson_prompt(topic, context):
    return (
        "علّمني درساً كاملاً عن الموضوع التالي كما لو كنت معلم خبير: \""
        + topic + "\".\n"
        + (("[مهم من ذاكرتي له علاقة: " + context[:800] + "]\n") if context else "")
        + "اكتب إجابتك بعلامة Markdown فقسم واحداً إلى الأقسام التالية بالضبط:\n"
        "## التعريف\nما هو بجملتين واضحتين بلغة المستخدم.\n"
        "## لماذا يهم\nأهميته عملياً في أعمالي.\n"
        "## كيف أطبّقه داخل نظام Agent OS\nخطوات تنفيذ محددة وقابلة للحقن في "
        "المهام اليومية (مهام، أدوات، نقاط تحقق).\n"
        "## مثال عملي خطوة بخطوة\nسيناريو مصغّر واقعي بأرقام.\n"
        "## التحقق من الفهم\nأسئلة سريعة بجوابها المختصر.\n"
        "قلّل الكلام الزخرفي؛ لا تختلق نتائج، وإن جهلت جانباً صرّح بذلك."
    )


def teach(topic, use_brain=True):
    """يدرّس موضوعاً أمام المستخدم ويعيد سجل الدرس كاملاً."""
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    topic = str(topic).strip()
    steps = []
    progress = {}

    def mark(status, label, extra=""):
        progress[status] = label
        steps.append({"status": status, "label": label[:120], "extra": str(extra)[:300]})

    _step(1, "روّضت الموضوع وسحبت ما عرفه عن له صلة في ذاكرتي")
    context = ""
    try:
        from agent_os import skill_memory
        hits = skill_memory.recall(topic, top=3)
        context = "\n".join(h[3] for h in hits) if hits else ""
    except Exception as e:
        context = ""
        mark("warn", "الذاكرة لم تستجب", e)
    mark("done", "ذهني جاهز وانضم الشيب له")

    # ---- عصف العقل: درس منظم ----
    _step(2, "أعقل يُلخّص ويرتّب الدرس… (أسرع محركات مجانية)")
    answer = None
    if use_brain:
        try:
            os.environ.setdefault("SELFRUNNER_MODE", BRAIN_MODE)
            import brain
            session = brain.Brain(
                "أنت معلم مباشر للوكيل — تعلّم بوضوح بعربي سليم، دقيق، بلا اختلاق."
            )
            answer, engine = session.ask(_lesson_prompt(topic, context))
            answer = str(answer).strip()
            if len(answer) < 80:
                raise ValueError("رد غير كافٍ من العقل")
            mark("done", f"الدرس صيغ بواسطة محرك {engine}")
        except Exception as e:
            mark("warn", "العقل لم يحضر — أعتمد الجمع اليدوي", e)
            answer = "\n".join([
                "## التعريف\n" + topic + " — موضوع تعلّمي جديد أضيفه لقاعدة معرفتي.",
                "",
                "## لماذا يهم\nليُستحضر عند المهام القادمة المتعلقة به.",
                "",
                "## كيف أطبّقه داخل نظام Agent OS\n- سجالة الجزء في ذاكرة المهارات;\n- استدعاؤه تلقائياً عبر skill_memory في المهام.",
                "",
                "## مثال عملي\nسجّل وانبعث خطوة في events.jsonl.",
            ])

    # ---- حفظ الدرس ----
    _step(3, "أقدّم الدرس في أرشيف المعرفة")
    slug = _slug(topic)
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    fname = slug + "-" + datetime.datetime.now().strftime("%Y%m%d") + ".md"
    path = os.path.join(KNOWLEDGE_DIR, fname)
    header = "# 🎓 درس: " + topic + "\n\n*وقت التعلّم: " + C.now_iso() + "*\n\n"
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(header + answer + "\n")
        mark("done", "الدرس محفوظ في أرشيف المعرفة")
    except Exception as e:
        mark("fail", "تعذّر حفظ الدرس", e)

    # ---- ذاكرة المهارات: يُتعلَّم للأبد ----
    _step(4, "أثبّته في ذاكرة المهارات الدائمة")
    try:
        from agent_os import skill_memory
        skill_memory.remember(topic, action=f"lesson:{slug}", ok=True,
                              notes=("درس " + fname))
        mark("done", "دخل ذاكرة المهارات — يتسلل لمهامك القادمة")
    except Exception as e:
        mark("warn", "لم يكتب الذاكرة", e)

    # ---- ملخص للسجل ----
    _step(5, "انتهيت — سجّلت السير كاملاً")
    try:
        from agent_os import event_bus
        event_bus.publish("lesson_created", {"topic": topic, "slug": slug, "path": path},
                          source="teach")
    except Exception:
        pass

    return {"ok": True, "topic": topic, "slug": slug, "path": path,
            "steps": steps, "engine": engine if use_brain else "offline"}


def list_lessons(limit=10):
    """أحدث الدروس في أرشيف المعرفة (لللوحة)."""
    out = []
    if not os.path.isdir(KNOWLEDGE_DIR):
        return out
    try:
        names = sorted(os.listdir(KNOWLEDGE_DIR), reverse=True)[:limit]
    except Exception:
        names = []
    for n in names:
        p = os.path.join(KNOWLEDGE_DIR, n)
        try:
            size = os.path.getsize(p)
        except Exception:
            size = 0
        out.append({"file": n, "size": size,
                    "modified": datetime.datetime.fromtimestamp(os.path.getmtime(p))
                    .isoformat(timespec="seconds") if size else None})
    return out


if __name__ == "__main__":
    import json
    args = sys.argv[1:]
    if args and args[0] == "lessons":
        print(json.dumps(list_lessons(), ensure_ascii=False, indent=1))
    elif args:
        print(json.dumps(teach(" ".join(args)), ensure_ascii=False, indent=1))
    else:
        print("الاستعمال: teach <موضوع> | teach lessons")