"""
counterfactual.py - محرك القرار المضاد (Counterfactual Engine) — المواصفة §6
=============================================================================
يسأل قبل القرار: ماذا لو فعلت A؟ ماذا لو فعلت B؟ ماذا لو لم أفعل شيئاً؟

منطق خالص بلا اعتماد خارجي — يقارن الخيارات على أبعاد قابلة للقياس
(قيمة متوقعة، مخاطرة، تكلفة، عكوسية) ويعيد الخيار الأفضل مع تبريره.
"""

import os
import sys

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C


def _score(option):
    """درجة مركّبة لخيار: القيمة المتوقعة مرجّحة ضد المخاطرة والتكلفة.

    option: dict فيه (كلها 0..1 عدا value قد تتجاوز):
        value       القيمة المتوقعة (منفعة)
        probability احتمال النجاح
        risk        الخطورة (يُطرح)
        cost        التكلفة النسبية (تُطرح)
        reversible  هل القرار قابل للتراجع؟ (مكافأة أمان)
    """
    value = float(option.get("value", 0.0))
    prob = float(option.get("probability", 0.5))
    risk = float(option.get("risk", 0.0))
    cost = float(option.get("cost", 0.0))
    reversible = 1.0 if option.get("reversible", True) else 0.0
    # القيمة المتوقعة = value*prob، ثم نخصم المخاطرة والتكلفة، ونكافئ العكوسية
    ev = value * prob
    score = ev - (risk * 0.6) - (cost * 0.4) + (reversible * 0.1)
    return round(score, 4)


def compare(options, include_noop=True):
    """يقارن خيارات ويعيد الترتيب + التوصية.

    options: قائمة dicts، كل واحد فيه على الأقل {"name", "value"}.
    include_noop: يضيف خيار "لا تفعل شيئاً" كخط أساس (المواصفة §6).
    """
    pool = list(options)
    if include_noop and not any(o.get("name") == "noop" for o in pool):
        pool.append({"name": "noop", "value": 0.0, "probability": 1.0,
                     "risk": 0.0, "cost": 0.0, "reversible": True,
                     "note": "الوضع الحالي — لا تغيير"})

    scored = []
    for o in pool:
        s = _score(o)
        scored.append({**o, "score": s})
    scored.sort(key=lambda x: x["score"], reverse=True)

    best = scored[0]
    runner = scored[1] if len(scored) > 1 else None
    margin = round(best["score"] - runner["score"], 4) if runner else best["score"]

    reason = f"الأعلى قيمة متوقعة بعد خصم المخاطرة والتكلفة (فارق {margin})"
    if best["name"] == "noop":
        reason = "لا خيار يتفوق على عدم الفعل — الأفضل الانتظار"

    return {
        "recommended": best["name"],
        "score": best["score"],
        "margin": margin,
        "confident": margin >= 0.15,   # فارق ضيق = قرار غير حاسم
        "reason": reason,
        "ranking": [{"name": o["name"], "score": o["score"]} for o in scored],
    }


def what_if(action, value, probability=0.5, risk=0.0, cost=0.0, reversible=True):
    """يقيّم سيناريو واحداً بمعزل — 'ماذا لو فعلت هذا؟'."""
    o = {"name": action, "value": value, "probability": probability,
         "risk": risk, "cost": cost, "reversible": reversible}
    return {"action": action, "expected_score": _score(o),
            "expected_value": round(value * probability, 4)}


if __name__ == "__main__":
    demo = [
        {"name": "ابنِ MVP الآن", "value": 0.9, "probability": 0.6, "risk": 0.3, "cost": 0.5, "reversible": True},
        {"name": "ابحث أكثر أولاً", "value": 0.5, "probability": 0.9, "risk": 0.1, "cost": 0.2, "reversible": True},
        {"name": "أطلق دون اختبار", "value": 0.95, "probability": 0.3, "risk": 0.8, "cost": 0.4, "reversible": False},
    ]
    result = compare(demo)
    print(f"التوصية: {result['recommended']} (score={result['score']}, حاسم={result['confident']})")
    for r in result["ranking"]:
        print(f"  {r['name']}: {r['score']}")
