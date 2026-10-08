"""
python -m trading demo [iterations]   يشغّل دورة تحسين كاملة (بيانات تجريبية إن لزم) ويطبع تقريراً
python -m trading status              لقطة حالة الأنابيب الحالية
python -m trading reset               يصفّي سجل الاستراتيجيات وقاعدة الحقائق
"""

import json
import sys


def cmd_demo(iterations):
    from trading import strategy_agent, point_in_time as pit

    print("=" * 60)
    print("  🤖 وكيل التداول ذاتي التحسين — دورة تجريبية")
    print("=" * 60)

    before = pit.fact_count()
    result = strategy_agent.run_self_improvement_cycle(iterations=iterations)
    if "error" in result:
        print(f"❌ {result['error']}")
        return

    if result["used_demo_data"]:
        print("⚠️  لا بيانات حقيقية بالمخزن — استُخدمت بيانات تجريبية اصطناعية "
              "(موسومة is_demo=True)، ليست بيانات سوق حقيقية.")
    print(f"📥 حقائق بالمخزن: {before} → {pit.fact_count()}")
    print()

    for entry in result["this_run"]:
        label = strategy_agent.FACTOR_LABELS.get(entry["spec"]["factor"], entry["spec"]["factor"])
        print(f"  تكرار #{entry['iteration']} — العامل: {label} (أعلى {entry['spec']['top_n']} شركات)")
        print(f"    شارپ صادق (آمن زمنياً)  : {entry['honest_sharpe']}")
        print(f"    شارپ متحيّز (لو غششنا)  : {entry['biased_sharpe']}")
        print(f"    مقدار الوهم (تضخّم الغش) : {entry['sharpe_inflation']}")
        if entry.get("note"):
            print(f"    💬 {entry['note']}")
        print()

    best = result["best"]
    best_label = strategy_agent.FACTOR_LABELS.get(best["spec"]["factor"], best["spec"]["factor"])
    print("-" * 60)
    print(f"🏆 أفضل عامل حتى الآن عبر {result['history_total']} تكرار إجمالي: {best_label}")
    print(f"   شارپ صادق: {best['honest_sharpe']} (هذا هو الرقم الوحيد الذي يستحق الثقة — "
          f"ليس {best['biased_sharpe']})")
    print("-" * 60)


def cmd_status():
    from trading import strategy_agent, kill_switch, alpaca_client
    snap = strategy_agent.pipeline_snapshot()
    print(json.dumps({
        "pipeline": snap,
        "kill_switch": kill_switch.status(),
        "alpaca": alpaca_client.status(),
    }, ensure_ascii=False, indent=2))


def cmd_reset():
    from trading import strategy_agent, point_in_time as pit, universe
    strategy_agent.reset_history()
    pit.clear_all()
    universe._save({"listings": []})
    print("✅ صُفِّي: سجل الاستراتيجيات + مخزن الحقائق + الكون الزمني.")


if __name__ == "__main__":
    args = sys.argv[1:]
    action = args[0] if args else "demo"
    if action == "demo":
        cmd_demo(int(args[1]) if len(args) > 1 else 5)
    elif action == "status":
        cmd_status()
    elif action == "reset":
        cmd_reset()
    else:
        print(__doc__)
