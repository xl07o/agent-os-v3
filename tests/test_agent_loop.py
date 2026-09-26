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
