"""
backtest_engine.py - إعادة تشغيل يوم بيوم + مقارنة "مع غش" مقابل "بدونه" v1.0
=================================================================================
يمشي بالتاريخ يوماً بيوم (أو إعادة توازن كل N يوم)، يسأل الاستراتيجية
"مين تشتري الآن؟" بمعرفة محدودة بتاريخ معين فقط، ثم يقيس العائد الفعلي
اللاحق. النتيجة الأهم هنا ليست رقم واحد — هي المقارنة:

  lookahead_safe=True   الاستراتيجية ترى فقط ما known_on <= تاريخ القرار (صحيح)
  lookahead_safe=False  الاستراتيجية ترى كل البيانات حتى نهاية الفترة (غش متعمّد، للتعليم فقط)

نفس مقارنة الحلقات #1 (0.98 مقابل 3.18) و#2 (0.55 مقابل 1.33) و#3
(0.39 مقابل 1.77) — الفارق بين الاثنين هو مقدار الوهم اللي بياناتك
العادية كانت ستخفيه عنك لو ما بنيت المنصة صح.
"""

import os
import statistics
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)

FAR_FUTURE = "9999-12-31"


def _trading_dates(price_index, start_date, end_date):
    dates = sorted({d for series in price_index.values() for d in series if start_date <= d <= end_date})
    return dates


def _price_index():
    """يبني فهرس أسعار بالذاكرة مرة وحدة: {ticker: {date: close}}."""
    from trading import point_in_time as pit
    index = {}
    for f in pit.all_facts(metric="close"):
        index.setdefault(f["ticker"], {})[f["period"]] = f["value"]
    return index


def _price_on_or_before(series, date):
    best = None
    for d, close in series.items():
        if d <= date and (best is None or d > best[0]):
            best = (d, close)
    return best[1] if best else None


def sharpe_ratio(period_returns, periods_per_year):
    if len(period_returns) < 2:
        return 0.0
    mean = statistics.mean(period_returns)
    stdev = statistics.pstdev(period_returns)
    if stdev == 0:
        return 0.0
    return round((mean / stdev) * (periods_per_year ** 0.5), 3)


def cumulative_curve(period_returns, start_value=1.0):
    curve = [start_value]
    for r in period_returns:
        curve.append(round(curve[-1] * (1 + r), 6))
    return curve


def run_backtest(strategy_fn, start_date, end_date, rebalance_every=21, lookahead_safe=True, rebalance_label="21 يوم تداول"):
    """strategy_fn(as_of_date, universe_tickers) -> قائمة تذاكر بوزن متساوٍ.
    الموتور هو من يقرر as_of_date، لا الاستراتيجية — بالضبط الفكرة: منع
    الغش مسؤولية منصة البيانات، لا مسؤولية منطق الاستراتيجية."""
    from trading import universe

    price_index = _price_index()
    dates = _trading_dates(price_index, start_date, end_date)
    if len(dates) < 2:
        return {"error": "لا بيانات أسعار كافية بهذا المدى", "lookahead_safe": lookahead_safe}

    rebalance_dates = dates[::rebalance_every] or [dates[0]]
    if rebalance_dates[-1] != dates[-1]:
        rebalance_dates.append(dates[-1])

    picks_log = []
    period_returns = []

    for i in range(len(rebalance_dates) - 1):
        decision_date = rebalance_dates[i]
        hold_until = rebalance_dates[i + 1]
        eval_date = decision_date if lookahead_safe else end_date
        uni_date = decision_date if lookahead_safe else end_date
        uni = universe.universe_as_of(uni_date)

        picks = strategy_fn(eval_date, uni) or []
        rets = []
        for t in picks:
            series = price_index.get(t, {})
            p0 = _price_on_or_before(series, decision_date)
            p1 = _price_on_or_before(series, hold_until)
            if p0 and p1 and p0 > 0:
                rets.append((p1 - p0) / p0)
        period_return = sum(rets) / len(rets) if rets else 0.0
        period_returns.append(period_return)
        picks_log.append({
            "decision_date": decision_date, "held_until": hold_until,
            "picks": picks, "names_priced": len(rets), "return": round(period_return, 4),
        })

    periods_per_year = max(1, round(252 / rebalance_every))
    return {
        "lookahead_safe": lookahead_safe,
        "rebalance_label": rebalance_label,
        "start_date": start_date,
        "end_date": end_date,
        "sharpe": sharpe_ratio(period_returns, periods_per_year),
        "total_return_pct": round((cumulative_curve(period_returns)[-1] - 1) * 100, 2),
        "period_returns": period_returns,
        "cumulative_curve": cumulative_curve(period_returns),
        "picks_log": picks_log,
    }


def compare_biased_vs_honest(strategy_fn, start_date, end_date, rebalance_every=21, rebalance_label="21 يوم تداول"):
    """يشغّل نفس الاستراتيجية مرتين، بالضبط كالحلقات #1/#2/#3. يرجع
    'trust_this_one': النتيجة الصحيحة الوحيدة اللي تستحق الثقة."""
    honest = run_backtest(strategy_fn, start_date, end_date, rebalance_every, lookahead_safe=True, rebalance_label=rebalance_label)
    biased = run_backtest(strategy_fn, start_date, end_date, rebalance_every, lookahead_safe=False, rebalance_label=rebalance_label)
    return {
        "honest": honest,
        "biased": biased,
        "trust_this_one": "honest",
        "sharpe_inflation": round((biased.get("sharpe", 0) - honest.get("sharpe", 0)), 3),
    }


if __name__ == "__main__":
    print("استخدم strategy_agent.py لتشغيل دورة تحسين كاملة — هذا الملف مكتبة فقط.")
