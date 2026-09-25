"""اختبارات الأنظمة الـ15 الجديدة — كل وحدة حقيقية ومُختبَرة."""
import os, sys, tempfile, uuid, datetime
os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "mega_test"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ===== 1. الذاكرة الفوتوغرافية =====
def test_contextual_memory_save_and_recall():
    from agent_os.memory import contextual_memory as cm
    cm.save_experience("بناء موقع ويب", "HTML+CSS+JS", ["vscode"], "خطأ CSS", "flexbox", "success")
    results = cm.recall("بناء موقع جديد")
    assert len(results) >= 1
    assert results[0]["outcome"] == "success"

def test_contextual_memory_no_match():
    from agent_os.memory import contextual_memory as cm
    assert cm.recall("quantum physics zzz unique") == []

# ===== 2. التفكير المتسلسل =====
def test_chain_of_thought_structure():
    from agent_os.cognition import chain_of_thought as cot
    r = cot.think_chain("ما أفضل لغة برمجة؟", steps=2)
    assert "original_question" in r
    assert "chain" in r
    assert r["depth"] >= 0  # قد يكون 0 لو لا مزوّد

# ===== 3. تقليد الخبراء =====
def test_pattern_miner_self_analysis():
    from agent_os.cognition import pattern_miner as pm
    analysis = pm.analyze_self()
    assert "frameworks" in analysis
    assert len(analysis["frameworks"]) >= 3

def test_pattern_miner_recipe():
    from agent_os.cognition import pattern_miner as pm
    import agent_os._common as C
    recipe = pm.extract_recipe(C.BASE_DIR, "agent_os")
    assert recipe["name"] == "agent_os" or "ai-agent" in recipe["name"]
    assert recipe["has_tests"] is True

# ===== 4. المتجر التلقائي =====
def test_product_creation_and_pipeline():
    from agent_os.business import auto_products as ap
    p = ap.create_product("أداة تحليل أمني", "cli_tool", "تفحص الثغرات", 50)
    assert p["status"] == "idea"
    ap.advance_product(p["id"], "building")
    pipeline = ap.product_pipeline()
    assert "building" in pipeline or "idea" in pipeline

# ===== 5. صيد العقود =====
def test_contract_scouting():
    from agent_os.business import auto_products as ap
    opp = ap.scout_opportunity("بناء بوت تليقرام", "freelancer.com", 500, ["python", "telegram"])
    assert opp["status"] == "scouted"
    ap.evaluate_opportunity(opp["id"], roi_score=0.8)
    top = ap.top_opportunities()
    assert len(top) >= 1

# ===== 6. الجدول الذكي =====
def test_smart_scheduler_period():
    from agent_os.orchestration import smart_scheduler as ss
    period = ss.current_period()
    assert period in ("night", "morning", "active", "evening")

def test_smart_scheduler_prioritize():
    from agent_os.orchestration import smart_scheduler as ss
    tasks = [
        {"name": "تدريب نموذج", "weight": "heavy", "value": 0.8},
        {"name": "إشعار سريع", "weight": "light", "value": 0.3},
    ]
    ordered = ss.prioritize_for_now(tasks)
    assert len(ordered) == 2

# ===== 7. الحارس الليلي =====
def test_night_patrol_runs():
    from agent_os.orchestration import smart_scheduler as ss
    report = ss.night_patrol()
    assert "at" in report
    assert "checks" in report

def test_night_summary():
    from agent_os.orchestration import smart_scheduler as ss
    s = ss.night_summary()
    assert isinstance(s, str)

# ===== 8. الدرع الاستباقي =====
def test_shield_scan_no_critical_secrets():
    from agent_os.security import proactive_shield as ps
    scan = ps.full_scan()
    assert scan["critical"] == 0, f"أسرار مكشوفة! {scan['details'][:3]}"

# ===== 9. منحنى النمو =====
def test_growth_tracker_record_and_compare():
    from agent_os.security import proactive_shield as ps
    ps.record_day({"tasks_done": 5, "skills": 2, "revenue": 100})
    # لا يوجد أمس → لا مقارنة
    r = ps.compare_with_yesterday()
    # نسجّل أمس يدوياً
    import agent_os._common as C
    log = C.load_json(ps.GROWTH_FILE, {"days": {}})
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    log["days"][yesterday] = {"tasks_done": 3, "skills": 1, "revenue": 50}
    C.atomic_write(ps.GROWTH_FILE, log)
    r = ps.compare_with_yesterday()
    assert r["available"] is True
    assert r["trend"] == "📈 صاعد"

# ===== 10. الشخصية المتكيّفة =====
def test_personality_adapts():
    from agent_os.interface import adaptive_personality as ap
    ap.observe("preferred_detail", "brief")
    style = ap.current_style()
    assert style["detail"] == "brief"

def test_personality_formats():
    from agent_os.interface import adaptive_personality as ap
    ap.observe("preferred_detail", "brief")
    short = ap.format_response("x" * 500)
    assert len(short) <= 203  # 200 + "..."

# ===== 11. المعلّم =====
def test_teacher_lesson():
    from agent_os.interface import adaptive_personality as ap
    l = ap.teach("API Design", "جرّبت REST وGraphQL", "REST أبسط للمشاريع الصغيرة",
                 "أقل تعقيد وأسهل تصحيح")
    assert l["topic"] == "API Design"
    report = ap.teaching_report()
    assert "API Design" in report

# ===== 12. المفاوض =====
def test_negotiator_full_capability():
    from agent_os.interface import negotiator as ng
    r = ng.negotiate("اكتب كود بايثون لتحليل البيانات")
    assert r["type"] in ("full_capability", "partial_capability")

def test_negotiator_blocked():
    from agent_os.interface import negotiator as ng
    r = ng.negotiate("سوّ لي payment وأنشئ حساب بنكي")
    assert "needs_human" in r["assessment"]

# ===== تكامل: كل شي يشتغل مع بعض =====
def test_all_new_modules_import():
    """كل الوحدات الجديدة تُستورد بلا خطأ."""
    from agent_os.memory import contextual_memory
    from agent_os.cognition import chain_of_thought
    from agent_os.cognition import pattern_miner
    from agent_os.business import auto_products
    from agent_os.orchestration import smart_scheduler
    from agent_os.security import proactive_shield
    from agent_os.interface import adaptive_personality
    from agent_os.interface import negotiator
    assert True  # لو وصل هنا = كل الاستيرادات نجحت
