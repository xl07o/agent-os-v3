"""
strategy_agent.py - الحلقة ذاتية التحسين (Self-Improving Loop) v1.0
========================================================================
بالضبط حلقة كل حلقات @fidetolabs الخمس:

  الوكيل يقترح استراتيجية → منصة البيانات تبني جدول عامل آمن زمنياً →
  الـbacktest يسجّل درجة (صادقة ومتحيّزة) → الدرجة ترجع للوكيل → يعدّل

القرار التالي حتمي محلياً (لا يعتمد على توفر نموذج LLM) حتى تستمر
الحلقة دائماً؛ شرح نصي من brain.py اختياري وبأفضل-جهد فقط، تماماً كنمط
self_evolving.py.propose_improvement.

الاستخدام:
  from trading import strategy_agent
  result = strategy_agent.run_self_improvement_cycle(iterations=5)
  print(strategy_agent.pipeline_snapshot())
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)
from agent_os import _common as C

DATA_DIR = os.path.join(ROOT_DIR, "data", "trading")
os.makedirs(DATA_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(DATA_DIR, "strategy_history.json")

FACTORS = ["momentum", "price_value", "revenue_growth"]

FACTOR_LABELS = {
    "momentum": "زخم السعر (آخر 21 يوم)",
    "price_value": "الأرخص سعراً (قيمة)",
    "revenue_growth": "أسرع نمو إيرادات",
}


def _load_history():
    return C.load_json(HISTORY_FILE, {"entries": []})["entries"]


def _save_history(entries):
    C.atomic_write(HISTORY_FILE, {"entries": entries})


def reset_history():
    _save_history([])


# ===== حساب العوامل — كلها تمر إلزامياً عبر point_in_time (آمنة زمنياً) =====

def compute_factor(as_of_date, ticker, factor_name):
    from trading import point_in_time as pit

    if factor_name == "price_value":
        f = pit.latest_value_as_of(as_of_date, ticker, "close")
        return f["value"] if f else None

    if factor_name == "momentum":
        rows = pit.facts_as_of(as_of_date, ticker=ticker, metric="close")
        if len(rows) < 22:
            return None
        rows.sort(key=lambda r: r["period"])
        recent, past = rows[-1]["value"], rows[-22]["value"]
        return (recent - past) / past if past else None

    if factor_name == "revenue_growth":
        rows = pit.facts_as_of(as_of_date, ticker=ticker, metric="revenue")
        if len(rows) < 2:
            return None
        rows.sort(key=lambda r: (r["period"], r["known_on"]))
        by_period = {}
        for r in rows:
            by_period[r["period"]] = r["value"]  # آخر تسجيل معروف لكل فترة يفوز
        periods = sorted(by_period.keys())
        if len(periods) < 2:
            return None
        prev, cur = by_period[periods[-2]], by_period[periods[-1]]
        return (cur - prev) / prev if prev else None

    return None


def strategy_fn_from_spec(spec):
    """يبني دالة استراتيجية قابلة للتمرير لـbacktest_engine من مواصفة
    تصريحية بسيطة (لا كود يُنفَّذ — أأمن من sandbox تنفيذ كود حر لمجال
    مالي)."""
    factor = spec["factor"]
    direction = spec.get("direction", "desc")
    top_n = spec.get("top_n", 3)

    def fn(as_of_date, universe_tickers):
        scored = []
        for t in universe_tickers:
            v = compute_factor(as_of_date, t, factor)
            if v is not None:
                scored.append((t, v))
        scored.sort(key=lambda kv: kv[1], reverse=(direction == "desc"))
        return [t for t, _ in scored[:top_n]]

    return fn


# ===== حلقة الاقتراح والتعديل =====

def propose_initial_strategy():
    return {"factor": "momentum", "direction": "desc", "top_n": 3, "rebalance_every": 21}


def propose_revision(history):
    """يجرّب كل عامل مرة أولاً (استكشاف)، وبعدها يستغل أفضل عامل وجده
    ويضبط حجم السلة حوله (استغلال) — نفس روح 'الدرجة تخبره وش يجرّب بعده'."""
    tried_factors = {h["spec"]["factor"] for h in history}
    remaining = [f for f in FACTORS if f not in tried_factors]
    if remaining:
        return {"factor": remaining[0], "direction": "desc", "top_n": history[-1]["spec"]["top_n"],
                "rebalance_every": history[-1]["spec"]["rebalance_every"]}

    best = max(history, key=lambda h: h["honest_sharpe"])
    spec = dict(best["spec"])
    last_tn = history[-1]["spec"]["top_n"]
    spec["top_n"] = max(1, min(6, last_tn + (1 if last_tn < 5 else -2)))
    return spec


def _explain_with_brain(spec, cmp):
    """تفسير نصي اختياري — أفضل-جهد، لا يوقف الحلقة لو فشل (نفس نمط
    self_evolving.propose_improvement)."""
    try:
        import brain
        b = brain.Brain("أنت محلل كمّي مختصر جداً. جملة أو جملتين بالعربية، بلا مقدمات.")
        prompt = (
            f"عامل: {FACTOR_LABELS.get(spec['factor'], spec['factor'])}، أعلى {spec['top_n']} شركات. "
            f"شارپ صادق (آمن زمنياً) = {cmp['honest'].get('sharpe', 0)}. "
            f"شارپ متحيّز (لو غششنا) = {cmp['biased'].get('sharpe', 0)}. "
            f"فسّر بإيجاز هل هذا العامل مفيد فعلاً أم أن رقمه الجيد كان وهم تحيّز."
        )
        response, _engine = b.ask(prompt)
        return str(response)[:400]
    except Exception:
        return ""


def run_self_improvement_cycle(iterations=5, start_date=None, end_date=None, seed=None, explain=True):
    """الحلقة الكاملة. لو مخزن البيانات فاضي يحمّل بيانات تجريبية موسومة
    بوضوح أولاً — لا تدّعي أبداً أنها بيانات سوق حقيقية."""
    from trading import backtest_engine, point_in_time as pit

    loaded_demo = False
    if pit.fact_count() == 0:
        from trading import data_sources
        data_sources.load_demo_into_store(seed=seed or 42)
        loaded_demo = True

    if start_date is None or end_date is None:
        dates = sorted({f["period"] for f in pit.all_facts(metric="close")})
        if len(dates) < 2:
            return {"error": "لا بيانات أسعار كافية — شغّل data_sources.load_demo_into_store() أولاً"}
        start_date, end_date = dates[0], dates[-1]

    history = _load_history()
    spec = propose_initial_strategy() if not history else propose_revision(history)
    run_entries = []

    for _ in range(iterations):
        fn = strategy_fn_from_spec(spec)
        cmp = backtest_engine.compare_biased_vs_honest(
            fn, start_date, end_date, rebalance_every=spec.get("rebalance_every", 21),
        )
        entry = {
            "iteration": len(history) + 1,
            "spec": spec,
            "honest_sharpe": cmp["honest"].get("sharpe", 0),
            "biased_sharpe": cmp["biased"].get("sharpe", 0),
            "sharpe_inflation": cmp["sharpe_inflation"],
            "honest_total_return_pct": cmp["honest"].get("total_return_pct", 0),
            "honest_cumulative_curve": cmp["honest"].get("cumulative_curve", []),
            "at": C.now_iso(),
        }
        entry["note"] = _explain_with_brain(spec, cmp) if explain else ""
        history.append(entry)
        run_entries.append(entry)
        _save_history(history)
        spec = propose_revision(history)

    best = max(history, key=lambda h: h["honest_sharpe"])
    C.log(f"📈 [trading] دورة تحسين: {iterations} تكرار — أفضل عامل حتى الآن: "
          f"{FACTOR_LABELS.get(best['spec']['factor'], best['spec']['factor'])} (شارپ {best['honest_sharpe']})")
    return {
        "iterations_run": iterations,
        "used_demo_data": loaded_demo,
        "this_run": run_entries,
        "history_total": len(history),
        "best": best,
    }


def latest():
    history = _load_history()
    return history[-1] if history else None


def history():
    return _load_history()


# ===== لقطة حالة للموقع (web_bridge) — تطابق الرسم البياني بتصميم fidetolabs =====

def pipeline_snapshot():
    """حالة الأنابيب اللحظية لعرضها بلوحة التحكم: أي مرحلة آخر تشغيل وصل
    لها، عيّنة من جدول العوامل، ومقارنة الصادق/المتحيّز الأخيرة."""
    from trading import point_in_time as pit, kill_switch

    history = _load_history()
    last = history[-1] if history else None
    fact_total = pit.fact_count()

    sample_table = []
    if last:
        fn = strategy_fn_from_spec(last["spec"])
        dates = sorted({f["period"] for f in pit.all_facts(metric="close")})
        if dates:
            as_of = dates[-1]
            from trading import universe
            uni = universe.universe_as_of(as_of)
            picks = fn(as_of, uni)
            for t in picks:
                sample_table.append({
                    "ticker": t,
                    "factor_value": round(compute_factor(as_of, t, last["spec"]["factor"]) or 0, 4),
                })

    return {
        "has_run": last is not None,
        "facts_ingested": fact_total,
        "iterations_total": len(history),
        "current_spec": last["spec"] if last else None,
        "current_factor_label": FACTOR_LABELS.get(last["spec"]["factor"], "") if last else None,
        "honest_sharpe": last["honest_sharpe"] if last else None,
        "biased_sharpe": last["biased_sharpe"] if last else None,
        "sharpe_inflation": last["sharpe_inflation"] if last else None,
        "sample_picks": sample_table,
        "note": last.get("note", "") if last else "",
        "kill_switch_tripped": kill_switch.is_tripped(),
        "honest_cumulative_curve": last.get("honest_cumulative_curve", []) if last else [],
    }


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "run"
    if action == "run":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        import json
        print(json.dumps(run_self_improvement_cycle(iterations=n), ensure_ascii=False, indent=2)[:4000])
    elif action == "snapshot":
        import json
        print(json.dumps(pipeline_snapshot(), ensure_ascii=False, indent=2))
    elif action == "reset":
        reset_history()
        print("تمت تصفية سجل الاستراتيجيات.")
