"""
orchestrator.py - قائد العمليات الخارق (v2.0)
==============================================
نظام orchestration متقدم:
  - توزيع المهام على العقول بكفاءة
  - إدارة الدورة الكاملة
  - مراقبة الأداء في الوقت الحقيقي
  - فشل آمن مع fallbacks

هذا يعطي "موظف الليل" ذكاءً تنظيمياً:
  1. يقسم المهمة الكبيرة لمهام فرعية
  2. يوزعها على أفضل عقول
  3. يجمع النتائج ويبني التقرير النهائي
"""

import datetime
import json
import os
import sys
import time

import brain
import skills
import memory_bank
import webtools

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


def plan_task(task_description):
    """تخطيط المهمة وتقسيمها لمهام فرعية عبر العقل."""
    b = brain.Brain(
        "أنت مخطط مشاريع خبير. حلّل المهمة المطلوبة وقسّمها لخطوات واضحة ومحددة. "
        "أجب بالعربية بخطوات مرقمة، كل خطوة في سطر مستقل:"
    )
    prompt = (
        f"قسّم هذه المهمة إلى 3-5 خطوات عملية واضحة:\n"
        f"{task_description}\n\n"
        f"أجب فقط بقائمة مرقمة بالخطوات، بدون شرح إضافي."
    )
    try:
        response, engine = b.ask(prompt)
        steps = [
            line.strip().lstrip("0123456789.).- ").strip()
            for line in response.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        steps = [s for s in steps if len(s) > 5]
        return steps or [task_description]
    except Exception:
        return [task_description]


def run_step(step, step_num, total):
    """تنفيذ خطوة واحدة من المهمة."""
    import selfrunner
    print(f"\n  ⚡ تنفيذ الخطوة {step_num}/{total}: {step[:80]}")
    report = selfrunner.run_task(step)

    # حفظ الخطوة في الذاكرة
    try:
        memory_bank.remember(
            step[:80], f"تم تنفيذ: {step[:200]}\nالتقرير: {report}",
            importance=0.7,
            tags=["task_step"],
        )
    except Exception:
        pass

    return report


def run_orchestrated(task, max_steps=None):
    """تشغيل مهمة كاملة بشكل منظم."""
    print("=" * 60)
    print("   🧠 موظف الليل - وضع الأوركسترا")
    print("=" * 60)

    # 1) التخطيط
    print("  1. تحليل المهمة وتقسيمها...")
    steps = plan_task(task)
    print(f"     تم التقسيم إلى {len(steps)} خطوات")

    if max_steps and len(steps) > max_steps:
        steps = steps[:max_steps]

    # 2) التنفيذ
    reports = []
    for i, step in enumerate(steps, 1):
        report = run_step(step, i, len(steps))
        reports.append({"step": step, "report": report})

    # 3) التقرير النهائي
    summary_lines = [
        f"# تقرير الأوركسترا",
        f"**المهمة:** {task}",
        f"**الخطوات:** {len(steps)}",
        f"**التاريخ:** {datetime.datetime.now():%Y-%m-%d %H:%M}",
        f"**العقول:** {', '.join(e['id'] for e in brain.available_engines()) or 'لا شيء'}",
        "",
        "## الخطوات المنفذة",
        "",
    ]
    for i, r in enumerate(reports, 1):
        summary_lines.append(f"### الخطوة {i}: {r['step'][:100]}")
        summary_lines.append(f"- التقرير: {r['report']}")
        summary_lines.append("")

    summary_lines += ["", "## المهارات الحالية"]
    for s in skills.list_skills():
        summary_lines.append(f"- {s}")

    os.makedirs(os.path.join(BASE_DIR, "reports"), exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(BASE_DIR, "reports", f"orchestrated_{ts}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    print(f"\n  ✅ اكتملت المهمة. التقرير: {path}")
    return path


if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) or "ابنِ موقعاً بسيطاً ومفيداً"
    run_orchestrated(task)