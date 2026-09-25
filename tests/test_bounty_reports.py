"""اختبارات سجل الحسابات + تحضير تقارير الرفع (بلا شبكة)."""

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agent_os import bounty_accounts
from agent_os import bounty_engine


def test_accounts_never_request_password():
    assert bounty_accounts.selftest()["no_password_stored"]
    assert bounty_accounts.selftest()["all_manual"]
    acc = bounty_accounts.set_account("immunefi", "my_handle", token="tk_x")
    assert acc["mode"] == "manual"
    assert "_pwd" not in acc
    assert bounty_accounts.accounts()["immunefi"]["handle"] == "my_handle"
    bounty_accounts.remove_account("immunefi")


def test_submission_guide_gives_concrete_steps():
    guide = bounty_accounts.submission_guide("immunefi")
    assert "bugs.immunefi.com" in guide
    assert "KYC" in guide


def test_prepare_drafts_and_approve():
    prog = bounty_engine.add_program("DemoProg", ["app.example.com", "api.example.com"],
                                     authorization_source="public-policy:immunefi")
    f = bounty_engine.add_finding(prog["id"], "app.example.com",
                                  "IDOR: تعديل معرّف الحساب", "high",
                                  "GET /api/users/1001 -> 200 والاستجابة تكشف بيانات مستخدم آخر")
    assert isinstance(f, dict) and not f.get("blocked")
    assert f["severity"] == "high"
    drafts = bounty_engine.prepare_drafts()
    mine = [d for d in drafts if d["finding_id"] == f["id"]]
    assert mine, "التقرير لم يُحضَّر"
    d = mine[0]
    assert d["platform"] == "immunefi"
    assert d["status"] == "ready"
    assert "PoC" in d["body"] and "المعالجة المقترحة" in d["body"]
    ap = bounty_engine.approve_draft(d["id"])
    assert ap["status"] == "approved"
    bounty_engine.reject_draft(d["id"])


def test_attack_plan_is_method_not_guess():
    prog = bounty_engine.add_program("PlanProg", ["a.example.com", "b.example.com"],
                                     rules="قاعدة اختبار", authorization_source="public-policy:intigriti")
    plan = bounty_engine.attack_plan(prog["id"])
    assert "المراحل الخمس" in plan
    assert "a.example.com" in plan
    assert "IDOR/BOLA" in plan
    assert "prepare_drafts" in plan
    assert "ترفعه يدوياً" in plan