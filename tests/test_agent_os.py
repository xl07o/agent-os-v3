"""
اختبارات Agent OS — كلها تعمل دون شبكة ودون دماغ.
تشغيل: python -m pytest tests/test_agent_os.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agent_os import goal_manager, benchmark, self_improve_engine
from agent_os import tool_registry, browser_agent, product_factory, devops_agent, bounty_engine
from agent_os import business_autopilot, finance_intel, approval_center, world_model, chief_staff
from agent_os import agent_os as nucleus


def test_goal_manager_add_and_priority():
    g = goal_manager.add_goal("هدف اختبار", "التحقق")
    assert g["status"] == "active"
    assert goal_manager.priority_next()


def test_benchmark_offline():
    s = benchmark.run_benchmark(use_brain=False)
    assert s["overall"] >= 0


def test_tool_registry_security_gate():
    t = tool_registry.discover_tool("os_rm", "محذوف نظامي", "import os; os.remove('/') import subprocess")
    assert t["status"] == "blocked"
    ok = tool_registry.discover_tool("مفكرة", "أداة آمنة")
    assert ok["status"] == "approved"


def test_browser_http_backend():
    b = browser_agent.BrowserAgent("http")
    assert b.state()["backend"] == "http"


def test_product_factory_web():
    dest = os.path.join(ROOT, "data", "agent_os", "test_products")
    r = product_factory.build_product("web", "تجريبي", dest)
    assert os.path.exists(os.path.join(r["path"], "index.html"))


def test_devops_health():
    h = devops_agent.health_check(ROOT)
    assert "dir" in h["checks"]


def test_bounty_scope_hard_gate():
    prog = bounty_engine.add_program("تجربة", ["example.com"], None)
    ok, _ = bounty_engine.in_scope(prog, "example.com")
    assert ok
    block = bounty_engine.in_scope(prog, "evil.org")
    assert not block or not block[0]
    f = bounty_engine.add_finding(prog["id"], "outside.net", "ثغرة", "high")
    assert f["blocked"]


def test_finance_report():
    finance_intel.add_transaction("freelance", 100, "مشروع")
    r = finance_intel.report()
    assert r["income"] >= 100


def test_approval_center_flow():
    req = approval_center.create_request("أنشئ حساباً", "لانه ضروري", ["خطوة"], "استكمل التنفيذ")
    assert req["id"]
    approval_center.approve(req["id"])
    assert [r for r in approval_center.list_requests() if r["id"] == req["id"]][0]["status"] == "done"


def test_world_model_build():
    w = world_model.build()
    assert w["day"]


def test_chief_staff_wake_and_brief():
    b = chief_staff.wake()
    assert b["day"]
    assert chief_staff.brief()


def test_nucleus_full_chain_offline():
    res = nucleus.run_task("أبحث عن أفكار مشاريع", use_brain=False)
    assert res["intent"] in ("research", "unknown")
    assert res["result"]["status"] in ("verified", "revised", "needs_human")


def test_business_opportunity_shape():
    ideas = business_autopilot.discover_opportunities()
    assert isinstance(ideas, list)


def test_self_improve_protected_set():
    for f in self_improve_engine.PROTECTED:
        assert f


def test_goal_breakdown_fallback():
    g = goal_manager.add_goal("هدف بديل", auto=False)
    b = goal_manager.breakdown(g["id"])
    assert b["tasks"]
    assert b["status"] == "working"


def test_advance_all_no_pending():
    g = goal_manager.add_goal("هدف فارغ حتمي", "", "high", auto=False)
    res = goal_manager.advance_all(max_runs=1)
    assert res and res[0]["status"] == "no_pending"


def test_benchmark_weak_hints():
    benchmark.run_benchmark(use_brain=False)
    h = benchmark.weakest_hints(3)
    assert isinstance(h, dict)


def test_self_improve_lock():
    import os
    os.makedirs(os.path.dirname(self_improve_engine.LOCK_FILE), exist_ok=True)
    first = self_improve_engine._acquire_lock()
    second = self_improve_engine._acquire_lock()
    self_improve_engine._release_lock()
    third = self_improve_engine._acquire_lock()
    self_improve_engine._release_lock()
    assert first and not second and third


def test_devops_ci():
    from agent_os import devops_agent
    path = devops_agent.generate_ci(ROOT, "test/repo")
    assert os.path.exists(path)
    content = open(path, encoding="utf-8").read()
    assert "actions/checkout" in content
    assert "python -m pytest" in content


def test_devops_monitor():
    m = devops_agent.monitor()
    assert m["tracked"] >= 0


def test_bounty_wildcard():
    import time
    prog = bounty_engine.add_program("wild", ["*.example.com", "https://sub.example.com", "evil.org"], None)
    assert bounty_engine.in_scope(prog, "app.example.com")[0]
    f = bounty_engine.add_finding(prog["id"], "app.example.com", f"ثقرة wildcard {time.time()}", "high", "test evidence")
    assert f["status"] == "validated"


def test_bounty_scope_extension_requires_authorization():
    prog = bounty_engine.add_program("ext", ["a.com"], None)
    blocked = bounty_engine.add_scope(prog["id"], "*.new.com")
    assert blocked.get("blocked") is True
    updated = next(p for p in bounty_engine.list_programs() if p["id"] == prog["id"])
    assert not bounty_engine.in_scope(updated, "deep.new.com")[0]

def test_bounty_report_markdown():
    prog = bounty_engine.add_program("rpt", ["report.com"], None)
    bounty_engine.add_finding(prog["id"], "report.com", "test f", "low", "evidence")
    md = bounty_engine.report_markdown()
    assert "test f" in md


def test_approval_resume_no_hint():
    req = approval_center.create_request("Hess", "لأنه", [], None)
    approval_center.approve(req["id"])
    res = approval_center.resume(req["id"])
    assert not res["ok"]
    assert res["reason"]


def test_approval_resume_with_hint():
    from agent_os import approval_center
    import agent_os.agent_os as ns

    original = ns.run_task
    ns.run_task = lambda *a, **k: {"result": {"status": "verified"}}
    req = approval_center.create_request("Hess2", "لأنه", [], "أكمل")
    approval_center.approve(req["id"])
    res = approval_center.resume(req["id"])
    assert res["ok"]
    ns.run_task = original  # استعادة


def test_world_model_kpi():
    world_model.build()
    k = world_model.kpi()
    assert "day" in k and "products" in k


def test_browser_auto_fallback():
    b = browser_agent.BrowserAgent("auto")
    # سلسلة auto (ذهان #5): playwright → selenium → http
    assert b.state()["backend"] in ("playwright", "selenium", "http")


def test_nucleus_report_file():
    import glob
    import os
    before = set(glob.glob(os.path.join(ROOT, "output", "agent_os", "run_*.md")))
    nucleus.run_task("اختبار كتابة تقرير", use_brain=False)
    after = set(glob.glob(os.path.join(ROOT, "output", "agent_os", "run_*.md")))
    assert after - before


# ===== الفجوات من كود كلاودي الحرفي =====

def test_approval_kind_risk_and_pending_count():
    req = approval_center.create_request("تفعيل حساب", "لأنه مطلوب", [],
                                         kind="account_creation", risk="high")
    assert req["kind"] == "account_creation" and req["risk"] == "high"
    assert approval_center.pending_count() >= 1
    assert approval_center.check_resolution(req["id"]) is None  # ما زال معلقاً


def test_approval_check_resolution_after_approve():
    req = approval_center.create_request("اعتماد مؤقت", "اختبار", [], kind="code_change", risk="medium")
    approval_center.approve(req["id"])
    res = approval_center.check_resolution(req["id"])
    assert res is not None and res["status"] == "done"


def test_goal_category_and_next_actionable():
    g = goal_manager.add_goal("هدف مالي", "اختبار الفئة", category="finance")
    assert g["category"] == "finance"
    goal_manager.breakdown(g["id"])
    goal, task = goal_manager.next_actionable_task()
    assert goal is not None and task is not None and task["id"]


def test_goal_waiting_approval_is_skipped():
    g = goal_manager.add_goal("هدف ينتظر موافقة", "اختبار", priority="high")
    goal_manager.breakdown(g["id"])
    goal, task = goal_manager.next_actionable_task()
    flag = goal_manager.link_approval(task["id"], "external_action", "لأنه خارج", [])
    assert flag["kind"] == "external_action"
    # المهمة المعلّقة على موافقة تُتخطى
    goal2, task2 = goal_manager.next_actionable_task()
    assert task2 is None or task2["id"] != task["id"]


def test_goal_mark_failed_blocks_after_3():
    g = goal_manager.add_goal("هدف بعقبة", "اختبار")
    goal_manager.breakdown(g["id"])
    goal, task = goal_manager.next_actionable_task()
    for _ in range(3):
        goal_manager.mark_failed(task["id"], "محاولة فاشلة")
    state = goal_manager._load()
    found = None
    for gg in state["goals"]:
        for t in gg["tasks"]:
            if t.get("id") == task["id"]:
                found = t
    assert found["status"] == "blocked" and found["attempts"] == 3


def test_benchmark_feedback_and_scores():
    benchmark.record_result("coding", 42, "مهمة تجريبية")
    benchmark.record_result("coding", 58, "ثانية")
    s = benchmark.current_scores()
    assert "coding" in s and s["coding"] == 50.0
    w = benchmark.weakest_categories(2)
    assert w  # غير معروفين أولاً
    alloc = benchmark.learning_time_allocation()
    assert abs(sum(alloc.values()) - 1.0) < 0.01


def test_tool_registry_forbidden_and_sandbox():
    t = tool_registry.discover_tool("captcha_solver", "يتجاوز حماية", "import os; os.system('..')")
    assert t["status"] == "blocked"
    ok, out = tool_registry.sandbox_test("def main():\n    return 7\nmain()")
    assert ok
    ok2, _ = tool_registry.sandbox_test("import os; os.system('x')")
    assert not ok2
    assert tool_registry.list_active_tools() == []  # لا شيء نشط في الاختبار


def test_tool_requires_api_key_opens_approval():
    from agent_os import approval_center as ac
    before = ac.pending_count()
    tool_registry.discover_tool("llm_client", "مفتاح مطلوب", "def f(): pass\nf()", requires_api_key=True)
    assert ac.pending_count() > before


def test_finance_can_spend_gate():
    import agent_os.finance_intel as fi
    s0 = fi._load()
    s0["self_earned_usd"] = 0.0
    s0["spent_today_usd"] = 0.0
    s0["last_reset"] = ""
    s0.setdefault("ledger", [])
    fi._save(s0)  # صفر للحالة كي يكون الاختبار قابلاً للتكرار
    finance_intel.record_income("bounty", 5.0)
    assert finance_intel.can_spend(1.0) is True          # من رصيد مكتسب
    assert finance_intel.can_spend(999.0) is False        # يتجاوز الرصيد
    assert finance_intel.can_spend(99.0, is_free_provider=True) is True  # مجاني لا يُحتسب
    r = finance_intel.record_expense("تحسين", 1.0)
    assert r is True
    rep = finance_intel.daily_report()
    assert rep["self_earned_usd"] == 4.0 and rep["spent_today_usd"] == 1.0


def test_self_improve_critical_gate_and_apply():
    req = approval_center.create_request("تعديل حرج", "اختبار البوابة", [],
                                         kind="code_change", risk="high",
                                         payload={"target": "benchmark.py", "old": "zzz_not_exist", "new": "yyy"})
    approval_center.approve(req["id"])

    class Fake:
        @staticmethod
        def check_resolution(rid):
            for r in approval_center.list_requests():
                if r["id"] == rid and r["status"] != "pending":
                    return r
            return None
    from agent_os import self_improve_engine as sie
    apply_patch_orig = sie.apply_patch
    sie.apply_patch = lambda p, o, n: (p.endswith("benchmark.py"), "فقط للاختبار")
    try:
        res = sie.apply_critical_patch(req["id"])
        assert res["status"] in ("committed", "apply_failed", "bad_payload")
    finally:
        sie.apply_patch = apply_patch_orig


def test_self_improve_critical_declared():
    assert "approval_center.py" in self_improve_engine.CRITICAL_FILES
    assert "tool_registry.py" in self_improve_engine.CRITICAL_FILES


def test_kernel_cycle_runs_integration():
    from agent_os.kernel import AgentOS
    agent = AgentOS(use_brain=False)
    done = agent.run_cycle(max_steps=1)
    assert done and any(k in ("finance", "pending_approvals") for k, _ in done)


def test_kernel_import_via_package():
    from agent_os import AgentOS as A
    a = A(use_brain=False)
    assert hasattr(a, "run_cycle")
    assert hasattr(a, "ensure_goals")


# ===== (11) أرشفة برد بلا حذف =====

def test_finance_archive_preserves_data_and_readback():
    import agent_os.finance_intel as fi
    s = fi._load()
    s["txns"].append({"date": "2025-01-15T00:00:00", "amount": 3.0,
                      "kind": "bounty", "desc": "قديمة قبل الأرشيف"})
    fi._save(s)
    r = fi.archive_old_records(cutoff_days=30)
    assert r["moved"] >= 1
    assert "2025-01" in r["months"]
    assert any(t.get("desc") == "قديمة قبل الأرشيف" for t in fi.read_archive("2025-01"))


def test_goals_archive_preserves_data_and_readback():
    from agent_os import goal_manager as g
    s = g._load()
    s["goals"].append({"id": 999001, "title": "هدف قديم", "status": "achieved",
                       "created": "2025-02-10T00:00:00", "updated": "2025-02-10T00:00:00",
                       "priority": "low", "tasks": [], "attempts": 0})
    g._save(s)
    r = g.archive_achieved_goals(cutoff_days=30)
    assert r["moved"] >= 1
    assert any(x["id"] == 999001 for x in g.read_goal_archive("2025-02"))


# ===== (17) دوران ذكي بلا توقف =====

def test_no_hard_pause_on_single_hot_weakness():
    import agent_os.self_improve_engine as sie
    sie._note_cycle_outcome("أضعف منطقة", ok=False)
    sie._note_cycle_outcome("أضعف منطقة", ok=False)
    sie._note_cycle_outcome("أضعف منطقة", ok=False)
    try:
        assert sie.consecutive_failures("أضعف منطقة") >= 3     # فشل متتابع سُجّل
        assert sie._next_weakness(["أضعف منطقة"]) == "أضعف منطقة"  # لا توقف أبداً رغم السخونة
    finally:
        sie._note_cycle_outcome("أضعف منطقة", ok=True)          # تنظيف للتكرار


def test_rotation_skips_hot_when_alternative_resets_on_success():
    import agent_os.self_improve_engine as sie
    w = "ضA"
    for _ in range(3):
        sie._note_cycle_outcome(w, ok=False)
    try:
        assert sie.consecutive_failures(w) == 3
        assert sie._next_weakness(["ضB", w]) == "ضB"   # بديل بارد موجود → نمسك به
        assert sie._next_weakness([w]) == w            # لا بديل → نواصل الساخن
        sie._note_cycle_outcome(w, ok=True)            # نجاح يصفّر العدّاد
        assert sie.consecutive_failures(w) == 0
        assert sie._next_weakness([w, "ضB"]) == w
    finally:
        sie._note_cycle_outcome(w, ok=True)
        sie._note_cycle_outcome("ضB", ok=True)