"""
اختبار الحلقة الدائمة (البنود 2/16) — دورة خفيفة بلا التحسين الثقيل.
"""
import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "daemon_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import daemon


def test_tick_returns_summary_and_persists():
    s = daemon.tick(do_improve=False)
    assert "cycle" in s and "learning" in s
    st = daemon._load_state()
    assert st["cycles"] == s["cycle"]
    assert st.get("last")


def test_resume_increments_cycle():
    a = daemon.tick(do_improve=False)
    b = daemon.tick(do_improve=False)
    assert b["cycle"] == a["cycle"] + 1   # يستأنف لا يبدأ من الصفر


def test_run_bounded_cycles():
    r = daemon.run(max_cycles=2, interval=1, do_improve=False)
    assert r["ran_cycles"] == 2
