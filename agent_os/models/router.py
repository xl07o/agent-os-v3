"""
router.py - موجّه النماذج (Model Router) — §8, §51
==================================================
يقرر أي نموذج لأي مهمة: مجاني أولاً، ثم رخيص، ثم مدفوع — إلا إذا كانت
جودة المهمة تستحق الترقية. منطق خالص يُغذّى بسجل مزوّدين قابل للتحديث.

المبادئ (من المواصفة §9):
  FREE → CHEAP → PREMIUM
  المجاني لا يُحتسب في التكلفة المالية.
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

# سجل مزوّدين افتراضي — يعكس ما هو مدعوم فعلاً في brain.py
# (free=مجاني، cost=تكلفة نسبية 0..1، quality/latency/reliability 0..1)
DEFAULT_PROVIDERS = [
    {"id": "ollama",     "free": True,  "cost": 0.0,  "quality": 0.55, "latency": 0.4, "reliability": 0.7},
    {"id": "gemini",     "free": True,  "cost": 0.0,  "quality": 0.8,  "latency": 0.8, "reliability": 0.85},
    {"id": "groq",       "free": True,  "cost": 0.0,  "quality": 0.75, "latency": 0.95, "reliability": 0.8},
    {"id": "mistral",    "free": True,  "cost": 0.0,  "quality": 0.7,  "latency": 0.75, "reliability": 0.75},
    {"id": "deepseek",   "free": False, "cost": 0.1,  "quality": 0.85, "latency": 0.7, "reliability": 0.85},
    {"id": "openrouter", "free": True,  "cost": 0.05, "quality": 0.78, "latency": 0.7, "reliability": 0.7},
    {"id": "anthropic",  "free": False, "cost": 0.9,  "quality": 0.97, "latency": 0.75, "reliability": 0.95},
    {"id": "openai",     "free": False, "cost": 0.7,  "quality": 0.92, "latency": 0.8, "reliability": 0.92},
]

# ملامح المهام: أي بُعد يهم أكثر (المواصفة §8 quality/cost/latency/reliability router)
TASK_PROFILES = {
    "cheap":    {"cost": -1.0, "quality": 0.2, "latency": 0.3, "reliability": 0.3},
    "quality":  {"cost": -0.2, "quality": 1.0, "latency": 0.1, "reliability": 0.5},
    "fast":     {"cost": -0.3, "quality": 0.3, "latency": 1.0, "reliability": 0.4},
    "reliable": {"cost": -0.3, "quality": 0.4, "latency": 0.2, "reliability": 1.0},
    "balanced": {"cost": -0.5, "quality": 0.6, "latency": 0.4, "reliability": 0.6},
}


def _available(providers):
    """المزوّدون المتاحون فعلاً: مجاني دائماً، مدفوع فقط لو المفتاح موجود."""
    out = []
    for p in providers:
        if p["free"]:
            out.append(p)
        else:
            env = f"{p['id'].upper()}_API_KEY"
            if os.getenv(env):
                out.append(p)
    return out


def _score(provider, profile):
    weights = TASK_PROFILES.get(profile, TASK_PROFILES["balanced"])
    s = 0.0
    for dim, w in weights.items():
        val = provider.get(dim, 0.0)
        s += val * w
    return round(s, 4)


def route(profile="balanced", providers=None, prefer_free=True, only_available=True):
    """يختار المزوّد الأنسب لملمح مهمة.

    prefer_free: عند تقارب الجودة يفضّل المجاني (المواصفة §9).
    only_available: يقصر على المتاح فعلاً (مفتاح موجود للمدفوع).
    """
    pool = list(DEFAULT_PROVIDERS if providers is None else providers)
    if only_available:
        pool = _available(pool)
    if not pool:
        return {"provider": None, "reason": "لا مزوّد متاح"}

    ranked = sorted(pool, key=lambda p: _score(p, profile), reverse=True)

    if prefer_free and len(ranked) > 1:
        top = ranked[0]
        # لو الأفضل مدفوع وهناك مجاني قريب منه (فارق جودة < 0.15) نفضّل المجاني
        if not top["free"]:
            for p in ranked:
                if p["free"] and (top["quality"] - p["quality"]) < 0.15:
                    return {"provider": p["id"], "profile": profile,
                            "reason": "مجاني قريب من الأفضل — توفير التكلفة",
                            "paid_alternative": top["id"]}

    best = ranked[0]
    return {
        "provider": best["id"],
        "profile": profile,
        "free": best["free"],
        "reason": f"أعلى درجة لملمح '{profile}'",
        "ranking": [p["id"] for p in ranked[:4]],
    }


def fallback_chain(profile="balanced", providers=None):
    """سلسلة بدائل مرتّبة — للتحويل عند فشل مزوّد (المواصفة §52)."""
    pool = _available(list(DEFAULT_PROVIDERS if providers is None else providers))
    ranked = sorted(pool, key=lambda p: _score(p, profile), reverse=True)
    return [p["id"] for p in ranked]


if __name__ == "__main__":
    for prof in ("cheap", "quality", "fast"):
        r = route(prof)
        print(f"{prof:9} → {r['provider']} ({r['reason']})")
    print("سلسلة البدائل (balanced):", fallback_chain())
