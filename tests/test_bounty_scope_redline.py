"""
الخط الأحمر الدائم (البند 18): لا اختبار خارج النطاق المصرَّح أبداً،
والتوسيع لا يتم بلا تفويض صريح. اختبار يمنع أي انزلاق مستقبلي.
"""
import os
import sys
import tempfile
import uuid

os.environ.setdefault("AGENT_OS_DATA_DIR", os.path.join(tempfile.gettempdir(), "scope_" + uuid.uuid4().hex[:8]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_os import bounty_engine as be


def _prog():
    return {"scope": ["example.com", "*.test.com"]}


def test_out_of_scope_blocked():
    ok, _ = be.in_scope(_prog(), "evil.org")
    assert ok is False


def test_exact_and_subdomain_in_scope():
    assert be.in_scope(_prog(), "example.com")[0] is True
    assert be.in_scope(_prog(), "api.example.com")[0] is True
    assert be.in_scope(_prog(), "x.test.com")[0] is True


def test_wildcard_root_not_auto_allowed():
    # الجذر تحت wildcard يجب تحديده صراحةً — لا يُسمح ضمنياً.
    assert be.in_scope(_prog(), "test.com")[0] is False


def test_scope_expansion_requires_authorization():
    prog = be.add_program(f"prog_{uuid.uuid4().hex[:6]}", ["example.com"])
    blocked = be.add_scope(prog["id"], "new.com", authorization_source=None)
    assert blocked.get("blocked") is True


def test_empty_host_blocked():
    assert be.in_scope(_prog(), "")[0] is False
