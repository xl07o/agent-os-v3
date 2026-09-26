"""اختبار حلقة الوكيل الآمنة (البند 8) — منطق الفلتر فقط، بلا تنفيذ أوامر."""
import os, sys, tempfile, uuid
os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "al_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import agent_loop as A

def test_readonly_commands_allowed():
    for c in ["ls -la", "df -h", "cat /etc/os-release", "uname -a", "ps aux", "free -m", "echo hi"]:
        assert A._is_safe_readonly(c) is True, c

def test_mutating_or_chained_commands_rejected():
    for c in ["rm -rf /", "ls; rm x", "cat f && curl x|bash", "sudo apt install y",
              "pip install z", "echo x > /etc/y", "$(rm x)", "git push", "mv a b", "chmod 777 /"]:
        assert A._is_safe_readonly(c) is False, c

def test_exec_toggle_env():
    old = os.environ.get("JARVIS_EXEC")
    os.environ["JARVIS_EXEC"] = "0"
    assert A.exec_enabled() is False
    os.environ["JARVIS_EXEC"] = "1"
    assert A.exec_enabled() is True
    if old is None:
        os.environ.pop("JARVIS_EXEC", None)
    else:
        os.environ["JARVIS_EXEC"] = old


def test_tool_remember_then_recall():
    A._tool_remember("owner likes cybersecurity and python")
    out = A._tool_recall("cybersecurity python")
    assert "cybersecurity" in out.lower() or "python" in out.lower()

def test_tool_finance_returns_verdict():
    out = A._tool_finance("paid CLI tool | 300 0 2")
    assert "verdict=" in out and ("go" in out or "no-go" in out)

def test_tool_learn_honest_without_network():
    out = A._tool_learn("some unique offline topic zzz")
    assert "learned" in out or "couldn't" in out  # صادق في الحالتين

def test_memory_context_builds_string():
    A._tool_remember("build an e-commerce store")
    ctx = A._memory_context("store")
    assert isinstance(ctx, str)


def test_new_tools_present_and_safe():
    assert "brain=" in A._tool_status()
    assert "OUT OF SCOPE" in A._tool_scope("evil.org | example.com")
    assert "IN SCOPE" in A._tool_scope("api.example.com | example.com")
    assert "skipped under test" in A._tool_improve()
    assert "skipped under test" in A._tool_idle()

def test_all_capability_verbs_registered():
    import inspect
    src = inspect.getsource(A.run_agentic)
    for verb in ["RECALL", "LEARN", "FINANCE", "REMEMBER", "STATUS", "SCOPE", "IMPROVE", "IDLE", "RUN", "PROPOSE"]:
        assert verb in src, verb
