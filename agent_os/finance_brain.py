"""
finance_brain.py - الفكر المالي: تحليل جدوى الفرص (البند 7)
==========================================================
«يشوف فرصة، يحسبها، يقرّر». يحوّل فكرة/فرصة إلى أرقام قرار: عائد على
الاستثمار، فترة الاسترداد، صافي شهري متوقّع، ثم حكم go/no-go بسبب صريح.
حتمي وقابل للاختبار بلا شبكة؛ يسجّل كل تقييم في الذاكرة كمرجع.

  evaluate(idea, cost_usd, monthly_revenue_usd, effort_days, confidence)
  rank(opportunities)          -> مرتّبة بالأفضلية (score)
  fund_plan(budget_usd, opps)  -> ما الذي يُموَّل ضمن الميزانية
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

# عتبات القرار (شفّافة وقابلة للضبط).
MIN_ROI = 1.0          # عائد سنوي ≥ 100% من التكلفة ليُنصح به
MAX_PAYBACK_DAYS = 180  # استرداد خلال ≤ 6 أشهر
DAILY_EFFORT_COST = 20.0  # تكلفة ضمنية لليوم من جهد الوكيل (للمقارنة العادلة)


def _num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def evaluate(idea, cost_usd=0, monthly_revenue_usd=0, effort_days=1, confidence=0.6):
    """يقيّم فرصة واحدة ويعيد أرقام القرار + حكماً بسبب صريح."""
    cost = max(0.0, _num(cost_usd))
    rev_m = max(0.0, _num(monthly_revenue_usd))
    effort = max(0.0, _num(effort_days, 1))
    conf = min(1.0, max(0.0, _num(confidence, 0.6)))

    total_cost = cost + effort * DAILY_EFFORT_COST
    annual_rev = rev_m * 12 * conf              # إيراد سنوي معدّل بالثقة
    roi = ((annual_rev - total_cost) / total_cost) if total_cost > 0 else (float("inf") if annual_rev > 0 else 0.0)
    payback_days = (total_cost / (rev_m / 30.0)) if rev_m > 0 else float("inf")

    reasons = []
    go = True
    if rev_m <= 0:
        go = False
        reasons.append("لا إيراد متوقّع")
    if roi < MIN_ROI:
        go = False
        reasons.append(f"العائد {roi:.2f} أقل من العتبة {MIN_ROI}")
    if payback_days > MAX_PAYBACK_DAYS:
        go = False
        reasons.append(f"الاسترداد {payback_days:.0f} يوماً يتجاوز {MAX_PAYBACK_DAYS}")
    if conf < 0.4:
        reasons.append("ثقة منخفضة — تحقّق أكثر قبل الالتزام")
    if go and not reasons:
        reasons.append("عائد جيد واسترداد سريع ضمن العتبات")

    # score للترتيب: عائد موزون بالثقة ومخصوم بطول الاسترداد.
    score = round(roi * conf - (payback_days / 365.0 if payback_days != float("inf") else 5), 3)

    result = {
        "idea": str(idea)[:120],
        "total_cost_usd": round(total_cost, 2),
        "annual_revenue_adj_usd": round(annual_rev, 2),
        "roi": round(roi, 3) if roi != float("inf") else "∞",
        "payback_days": round(payback_days, 1) if payback_days != float("inf") else None,
        "confidence": conf,
        "verdict": "go" if go else "no-go",
        "reasons": reasons,
        "score": score,
    }
    _remember(result)
    return result


def rank(opportunities):
    """يقيّم قائمة فرص ويرتّبها بالأفضلية. كل عنصر dict فيه مفاتيح evaluate."""
    evaluated = [evaluate(**o) if isinstance(o, dict) else evaluate(o) for o in opportunities]
    return sorted(evaluated, key=lambda e: e["score"], reverse=True)


def fund_plan(budget_usd, opportunities):
    """يختار الفرص المُوصى بها (go) الأعلى أفضليةً ضمن الميزانية."""
    budget = max(0.0, _num(budget_usd))
    chosen, spent = [], 0.0
    for e in rank(opportunities):
        if e["verdict"] != "go":
            continue
        if spent + e["total_cost_usd"] <= budget:
            chosen.append(e)
            spent += e["total_cost_usd"]
    return {"budget_usd": budget, "spent_usd": round(spent, 2),
            "funded": chosen, "count": len(chosen)}


def _remember(result):
    try:
        st = C.load_json(os.path.join(C.AGENT_OS_DIR, "finance_evaluations.json"), {"evals": []})
        st["evals"].append({"time": C.now_iso(), **result})
        st["evals"] = st["evals"][-300:]
        C.atomic_write(os.path.join(C.AGENT_OS_DIR, "finance_evaluations.json"), st)
    except Exception:
        pass


if __name__ == "__main__":
    import json
    print(json.dumps(evaluate("أداة CLI مدفوعة", cost_usd=0, monthly_revenue_usd=200,
                              effort_days=3, confidence=0.7), ensure_ascii=False, indent=2))
