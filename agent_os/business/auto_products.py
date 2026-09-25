"""
auto_products.py - المتجر التلقائي + صيد العقود
=================================================
يبني منتجات رقمية (أدوات CLI، APIs، قوالب، أتمتة)، يقيّم الطلب عليها،
ويجهّزها للبيع. ويبحث عن فرص عمل حر مناسبة لقدراته.
"""
import os, sys, uuid
def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

PRODUCTS_FILE = os.path.join(C.AGENT_OS_DIR, "auto_products.json")
CONTRACTS_FILE = os.path.join(C.AGENT_OS_DIR, "contract_hunting.json")

# ===== المتجر التلقائي =====

PRODUCT_TYPES = ["cli_tool", "api_service", "template", "automation_script",
                 "web_app", "data_product", "saas"]

def create_product(name, product_type, description, estimated_value=0):
    """ينشئ منتج رقمي جديد في خط الإنتاج."""
    products = C.load_json(PRODUCTS_FILE, {"products": [], "revenue": 0})
    product = {
        "id": f"PROD-{uuid.uuid4().hex[:6]}",
        "name": name, "type": product_type,
        "description": description[:300],
        "estimated_value": estimated_value,
        "status": "idea",  # idea → building → testing → ready → published → earning
        "created_at": C.now_iso(), "revenue": 0,
    }
    products["products"].append(product)
    C.atomic_write(PRODUCTS_FILE, products)
    return product

def advance_product(product_id, new_status, notes=""):
    """ينقل المنتج للمرحلة التالية."""
    products = C.load_json(PRODUCTS_FILE, {"products": [], "revenue": 0})
    for p in products["products"]:
        if p["id"] == product_id:
            p["status"] = new_status
            p["last_updated"] = C.now_iso()
            if notes: p["notes"] = notes[:200]
            C.atomic_write(PRODUCTS_FILE, products)
            return p
    return {"error": "منتج غير موجود"}

def product_pipeline():
    """خط الإنتاج: كم منتج في كل مرحلة."""
    products = C.load_json(PRODUCTS_FILE, {"products": []})
    pipeline = {}
    for p in products.get("products", []):
        s = p.get("status", "idea")
        pipeline[s] = pipeline.get(s, 0) + 1
    return pipeline

# ===== صيد العقود =====

def scout_opportunity(title, source, estimated_pay, skills_needed, difficulty="medium"):
    """يسجّل فرصة عمل حر مكتشفة."""
    contracts = C.load_json(CONTRACTS_FILE, {"opportunities": [], "won": 0})
    opp = {
        "id": f"OPP-{uuid.uuid4().hex[:6]}",
        "title": title[:200], "source": source, "pay": estimated_pay,
        "skills": skills_needed, "difficulty": difficulty,
        "status": "scouted",  # scouted → evaluated → proposed → won → delivered
        "scouted_at": C.now_iso(),
    }
    contracts["opportunities"].append(opp)
    contracts["opportunities"] = contracts["opportunities"][-200:]
    C.atomic_write(CONTRACTS_FILE, contracts)
    return opp

def evaluate_opportunity(opp_id, roi_score, risk="low"):
    """يقيّم فرصة بالـROI."""
    contracts = C.load_json(CONTRACTS_FILE, {"opportunities": []})
    for o in contracts.get("opportunities", []):
        if o["id"] == opp_id:
            o["roi"] = roi_score
            o["risk"] = risk
            o["status"] = "evaluated"
            C.atomic_write(CONTRACTS_FILE, contracts)
            return o
    return None

def top_opportunities(n=5):
    contracts = C.load_json(CONTRACTS_FILE, {"opportunities": []})
    evaluated = [o for o in contracts.get("opportunities", []) if "roi" in o]
    evaluated.sort(key=lambda o: o["roi"], reverse=True)
    return evaluated[:n]
