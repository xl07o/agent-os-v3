"""اختبارات الدفعة 9: idempotency, network_policy, owner_model, تكاملات."""

import os
import sys
import tempfile

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "batch9_data"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os.orchestration import idempotency as idem
from agent_os.security import network_policy as net
from agent_os.strategy import owner_model as om
from agent_os.models import consensus as cons


# ===== Idempotency =====

def test_dangerous_op_runs_once():
    calls = {"n": 0}
    def act():
        calls["n"] += 1
        return "ok"
    import uuid
    inv = uuid.uuid4().hex[:8]
    r1 = idem.run_once("payment", [inv, "500"], act)
    r2 = idem.run_once("payment", [inv, "500"], act)
    assert r1["executed"] is True
    assert r2["skipped"] is True
    assert calls["n"] == 1   # نُفّذ مرة واحدة فقط


def test_different_keys_both_run():
    calls = {"n": 0}
    def act():
        calls["n"] += 1
        return "ok"
    import uuid
    idem.run_once("deployment", [uuid.uuid4().hex], act)
    idem.run_once("deployment", [uuid.uuid4().hex], act)
    assert calls["n"] == 2


def test_failed_op_not_marked_done():
    def boom():
        raise ValueError("فشل")
    import uuid
    key_parts = [uuid.uuid4().hex]
    r = idem.run_once("publishing", key_parts, boom)
    assert r["executed"] is False
    assert "error" in r
    # يمكن إعادة المحاولة لأنها لم تُسجَّل كمنتهية
    assert idem.already_done(r["key"]) is None


# ===== Network Policy (SSRF) =====

def test_blocks_localhost():
    ok, _ = net.check_url("http://localhost:8080/admin")
    assert ok is False


def test_blocks_metadata_endpoint():
    ok, _ = net.check_url("http://169.254.169.254/latest/meta-data")
    assert ok is False


def test_blocks_private_ip():
    ok, _ = net.check_url("http://10.0.0.5/")
    assert ok is False


def test_blocks_file_scheme():
    ok, _ = net.check_url("file:///etc/passwd")
    assert ok is False


def test_allows_public_https():
    ok, _ = net.check_url("https://api.github.com/repos")
    assert ok is True


def test_guard_raises():
    import pytest
    with pytest.raises(PermissionError):
        net.guard("http://localhost/")


# ===== Owner Model =====

def test_owner_ranks_preferred_higher():
    om.add_preference("coding", preferred=True)
    om.add_preference("manual_entry", preferred=False)
    ranked = om.rank_tasks([
        {"type": "coding", "value": 0.5},
        {"type": "manual_entry", "value": 0.5},
    ])
    assert ranked[0]["type"] == "coding"


def test_owner_learns_from_rejection():
    om.learn_from_decision("spam_task", approved=False)
    m = om._load()
    assert "spam_task" in m["avoided_work"]


def test_owner_score_reflects_goals():
    om.set_goals(current=["بناء coding منتج"])
    s = om.score_task("coding")
    assert s > 0.5


# ===== Consensus live (بلا مزوّد → لا يكسر) =====

def test_live_consensus_no_provider_graceful():
    # في بيئة الاختبار لا مزوّد، يجب أن يعيد نتيجة فارغة لا استثناء
    r = cons.live_consensus("2+2=?", n=2)
    assert "winner" in r
