"""اختبارات نظام Bug Bounty — bounty_engine + security_empire."""

import os
import sys
import uuid
import tempfile

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "bounty_test"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===== bounty_engine (agent_os) =====

def test_add_program():
    from agent_os import bounty_engine as be
    name = f"TestProg-{uuid.uuid4().hex[:6]}"
    p = be.add_program(name, ["*.example.com", "api.example.com"],
                       rules="لا اختبار DDoS")
    assert p["name"] == name
    assert len(p["scope"]) == 2


def test_scope_gate_allows_in_scope():
    from agent_os import bounty_engine as be
    name = f"ScopeTest-{uuid.uuid4().hex[:6]}"
    p = be.add_program(name, ["*.safe-target.com"])
    # _scope_gate يعيد bool فقط (لا tuple)
    ok = be._scope_gate(p, "sub.safe-target.com")
    assert ok is True


def test_scope_gate_blocks_out_of_scope():
    from agent_os import bounty_engine as be
    name = f"ScopeBlock-{uuid.uuid4().hex[:6]}"
    p = be.add_program(name, ["*.allowed.com"])
    ok = be._scope_gate(p, "evil-outside.com")
    assert ok is False


def test_add_finding():
    from agent_os import bounty_engine as be
    name = f"FindProg-{uuid.uuid4().hex[:6]}"
    p = be.add_program(name, ["vuln-test.com"])  # تطابق تام، لا wildcard
    f = be.add_finding(p["id"], "vuln-test.com", "XSS في صفحة البحث",
                       severity="medium", evidence="<script>alert(1)</script>")
    assert f is not None
    assert f.get("severity") == "medium"


def test_list_programs():
    from agent_os import bounty_engine as be
    programs = be.list_programs()
    assert isinstance(programs, list)


def test_report_markdown():
    from agent_os import bounty_engine as be
    md = be.report_markdown()
    assert isinstance(md, str)


def test_passive_recon_returns_dict():
    from agent_os import bounty_engine as be
    name = f"ReconProg-{uuid.uuid4().hex[:6]}"
    p = be.add_program(name, ["*.recon-test.com"])
    r = be.passive_recon(p, "recon-test.com")
    assert isinstance(r, (dict, type(None)))


# ===== security_empire =====

def test_empire_bounty_tracker_stats():
    from security_empire import bounty_tracker as bt
    stats = bt.get_stats()
    assert "total" in stats or "total_submissions" in stats or isinstance(stats, dict)


def test_empire_report_writer_estimate():
    from security_empire import report_writer as rw
    findings = [
        {"severity": "high", "title": "XSS"},
        {"severity": "low", "title": "Info Disclosure"},
    ]
    est = rw.estimate_bounty(findings)
    # يعيد dict بـ min و max
    assert est["min"] > 0 and est["max"] > 0


def test_empire_scanner_header_check():
    from security_empire import scanner
    headers = {"X-Frame-Options": "DENY", "Content-Type": "text/html"}
    issues = scanner.check_missing_headers(headers)
    assert isinstance(issues, list)


def test_empire_recon_dns():
    from security_empire import recon
    # DNS lookup لنطاق معروف — قد يفشل بلا شبكة لكن لا يرمي استثناء
    result = recon.dns_lookup("example.com")
    assert isinstance(result, (dict, list, type(None)))


# ===== تكامل: bounty_engine مع الحلقة الذهبية =====

def test_bounty_scope_enforced_always():
    """بوابة النطاق يجب ألا تُلتف عليها أبداً (§45, §73)."""
    from agent_os import bounty_engine as be
    name = f"StrictScope-{uuid.uuid4().hex[:6]}"
    p = be.add_program(name, ["only.this-domain.com"])
    # محاولات التفاف شائعة
    for evasion in ["other.com", "only.this-domain.com.evil.com",
                    "127.0.0.1", "localhost"]:
        ok = be._scope_gate(p, evasion)
        assert ok is False, f"تسرّب خارج النطاق: {evasion}"
