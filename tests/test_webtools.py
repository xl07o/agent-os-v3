"""اختبارات webtools.py (بحث، SSRF، DNS rebinding، cache).

تشغيل: python -m pytest tests/ -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_search_cache():
    """التحقق من الـ cache."""
    import webtools
    obj = {"query": "test", "results": [{"title": "t", "url": "u"}]}
    webtools._set_cache("query_test", "auto", obj)
    cached = webtools._get_cached("query_test", "auto")
    assert cached == obj


def test_webtools_search():
    """التحقق من البحث — فعّال صراحةً بـ SELFRUNNER_NETWORK_TESTS=1 فقط."""
    if os.getenv("SELFRUNNER_NETWORK_TESTS") != "1":
        import pytest
        pytest.skip("فعّل الاختبارات الشبكية: SELFRUNNER_NETWORK_TESTS=1")
    import webtools
    result = webtools.search("test query", save=False, num=3)
    assert isinstance(result, dict)
    assert "results" in result


def test_ssrf_and_local_file_blocks():
    """منع قراءة الملفات المحلية وSSRF."""
    import webtools
    assert webtools._is_safe_url("file:///etc/passwd") is False
    assert webtools._is_safe_url("file:///C:/Users/me/.env") is False
    assert webtools._is_safe_url("http://169.254.169.254/latest/meta-data/") is False
    assert webtools._is_safe_url("http://127.0.0.1:8000/admin") is False
    assert webtools._is_safe_url("http://192.168.1.1/config") is False
    assert webtools._is_safe_url("http://10.0.0.5/") is False
    assert webtools._is_safe_url("http://localhost:11434/api/tags") is False
    assert webtools._is_safe_url("http://[::1]/") is False
    assert webtools._is_safe_url("ftp://ftp.example.com/file") is False


def test_webtools_resolve_blocks_private_and_local():
    """_resolve_safe_ip يرفض العناوين الخاصة/المحلية مباشرةً بلا شبكة."""
    import webtools
    assert webtools._resolve_safe_ip("file:///etc/passwd")[0] is False
    assert webtools._resolve_safe_ip("ftp://x.com/f")[0] is False
    assert webtools._resolve_safe_ip("http://127.0.0.1:8000/a")[0] is False
    assert webtools._resolve_safe_ip("http://[::1]/")[0] is False
    assert webtools._resolve_safe_ip("http://169.254.169.254/meta")[0] is False
    assert webtools._resolve_safe_ip("http://192.168.1.1/x")[0] is False
    assert webtools._resolve_safe_ip("http://10.0.0.5/")[0] is False
    assert webtools._resolve_safe_ip("http://172.16.0.1/")[0] is False
    assert webtools._resolve_safe_ip("http://localhost:11434/api")[0] is False
    assert webtools._resolve_safe_ip("http://something.local/")[0] is False
    assert webtools._is_safe_url("http://127.0.0.1/") is False


def test_fetch_rejects_private_without_network():
    """_fetch يرفض الرابط المحلي برسالة فحص قبل أي اتصال شبكة."""
    import webtools
    msg = webtools._fetch("http://127.0.0.1:9999/x", timeout=2)
    assert "محظور" in msg


class _FakeResp:
    def __init__(self, status, headers, body=b""):
        self.status = status
        self._hdrs = headers
        self._body = body

    def getheader(self, key):
        return self._hdrs.get(key)

    def read(self, size=-1):
        if size < 0 or size >= len(self._body):
            out = self._body
            self._body = b""
            return out
        out = self._body[:size]
        self._body = self._body[size:]
        return out


class _FakeConn:
    """استبدال الاتصال الحقيقي — لا يلمس الشبكة أبداً."""

    def __init__(self, *args, **kwargs):
        pass

    def request(self, method, path, headers=None):
        pass

    def getresponse(self):
        return _FakeResp(302, {"Location": "http://127.0.0.1/steal"})

    def close(self):
        pass


def test_redirect_to_private_is_blocked(monkeypatch):
    """DNS rebinding لا يصل حتى للوجهة التحويلية الداخلية —
    الوجهة الجديدة تُفحص وتُثبَّت من نفسها وتحل مرة واحدة فقط."""
    import webtools
    calls = {"n": 0}

    def fake_resolve(url):
        calls["n"] += 1
        if calls["n"] == 1:
            return True, "8.8.8.8"          # الرابط الأولي "آمن"
        return False, "IP غير عام"          # وجهة التحويل مرفوضة

    monkeypatch.setattr(webtools, "_resolve_safe_ip", fake_resolve)
    monkeypatch.setattr(webtools, "_PinnedHTTPConnection", _FakeConn)
    res = webtools._fetch("http://example.com/start", timeout=2)
    assert "محظور" in res and "IP غير عام" in res
    assert calls["n"] == 2  # حلّان: واحد للرابط وواحد للوجهة — لا يُعاد حلّ لاتصال