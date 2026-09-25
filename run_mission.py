"""
run_mission.py - تشغيل مهمة الإتقان (v2.0)
==========================================
مهمة طويلة ذاتية مع:
  - حماية محسّنة (لا override للأمان)
  - عرض تقدم
  - إدارة المهلة
"""

import os
import sys
import time

# ضبط الجلسة الطويلة — مع الحفاظ على الحماية
os.environ["SELFRUNNER_STEPS"] = os.getenv("SELFRUNNER_STEPS", "200")
# لا نغير AUTORUN — نستخدم القيمة الأصلية (ask افتراضياً)
# os.environ["SELFRUNNER_AUTORUN"] = os.getenv("SELFRUNNER_AUTORUN", "allow")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    args = sys.argv[1:]
    hours = 3
    if "--hours" in args:
        i = args.index("--hours")
        try:
            hours = int(args[i + 1])
            del args[i:i + 2]
        except (ValueError, IndexError):
            pass

    mission = None
    for a in args:
        if a.endswith(".md"):
            mission = a
            break
    mission = mission or os.path.join(BASE_DIR, "mastery_mission.md")

    if not os.path.exists(mission):
        print(f"ملف المهمة غير موجود: {mission}")
        return

    with open(mission, "r", encoding="utf-8") as f:
        content = f.read()

    task = (
        f"نفّذ مهمة الإتقان التالية بجدية وكاملة. اقرأ محتواها واتبع كل خطوة.\n"
        f"الوقت المتاح: {hours} ساعات تقريباً. اعمل ذاتياً بدون توقف.\n"
        f"===== بداية المهمة =====\n{content}\n===== نهاية المهمة ====="
    )

    import selfrunner
    print(f"بدء مهمة الإتقان... الوقت المتاح: {hours} ساعة")
    print("لإيقاف التنفيذ اضغط Ctrl+C")

    start = time.time()
    try:
        rep = selfrunner.run_task(task)
        elapsed = time.time() - start
        if rep:
            print(f"\nتم تنفيذ المهمة في {elapsed/60:.1f} دقيقة. راجع التقرير: {rep}")
        else:
            print("\nلم يكتمل التنفيذ (تحقق أن Ollama يعمل، أو أضف مفتاحاً في .env).")
    except KeyboardInterrupt:
        print("\nتم إيقاف المهمة من قبلك.")
        print("ممكن تكمل لاحقاً — النتائج محفوظة تلقائياً!")


if __name__ == "__main__":
    main()