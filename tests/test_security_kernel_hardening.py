import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import security_kernel as sk

def test_dns_aware_ssrf():
    assert sk.check_url("http://127.0.0.1/")[0] is False
    assert sk.check_url("file:///etc/passwd")[0] is False

def test_path_secrets_and_system():
    assert sk.check_path(os.path.join(str(sk.BASE_DIR), ".env"))[0] is False
    assert sk.check_path("/etc/passwd")[0] is False
    assert sk.check_path(str(sk.PROJECTS_DIR / "ok.txt"))[0] is True

def test_command_policy():
    assert sk.check_command("python --version")[0] is True
    assert sk.check_command("python -c print(1)")[0] is False
    assert sk.check_command("bash script.sh")[0] is False
    assert sk.check_command("git status")[0] is True

def test_candidate_blocks_filesystem_and_network():
    ok,_=sk.safe_candidate_run("open('x','w').write('x')")
    assert ok is False
    ok,_=sk.safe_candidate_run("import socket")
    assert ok is False
    ok,out=sk.safe_candidate_run("def main():\n return 7\nmain()")
    assert ok is True
