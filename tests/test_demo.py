"""اختبار العرض الحيّ — يجب أن يمرّ المسار الكامل بلا عقل ولا شبكة."""
import os, sys, tempfile, uuid
os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "demo_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import demo

def test_demo_runs_end_to_end():
    r = demo.run()
    assert r["ok"] is True
    assert r["priorities"]
    assert r["finance"]["verdict"] in ("go", "no-go")
