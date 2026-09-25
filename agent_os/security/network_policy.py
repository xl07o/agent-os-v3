"""
network_policy.py - سياسة الشبكة وحماية SSRF — §114
====================================================
كل طلب شبكة يمرّ عبر هذه السياسة. تمنع الوصول لعناوين داخلية/خاصة
(localhost, 127.x, 10.x, 169.254 metadata...) وبروتوكولات خطرة (file://).
"""

import os
import sys
import re
import ipaddress
from urllib.parse import urlparse

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C
from agent_os import security_kernel as _auth

# بروتوكولات مسموحة فقط
ALLOWED_SCHEMES = {"http", "https"}

# مضيفات محظورة صراحةً (metadata endpoints وأسماء داخلية)
BLOCKED_HOSTS = {
    "localhost", "metadata.google.internal", "169.254.169.254",
    "metadata", "instance-data",
}


def _is_private_ip(host):
    """هل المضيف عنوان IP خاص/داخلي؟"""
    try:
        ip = ipaddress.ip_address(host)
        return (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified)
    except ValueError:
        return False   # ليس IP — اسم نطاق


def check_url(url):
    """فحص URL مركزي، بما في ذلك DNS resolution لمنع DNS rebinding/SSRF."""
    return _auth.check_url(url)


def guard(url):
    """يرفع استثناءً إن كان الرابط محظوراً — للاستخدام قبل أي fetch."""
    ok, reason = check_url(url)
    if not ok:
        raise PermissionError(f"سياسة الشبكة رفضت الرابط: {reason}")
    return url


def safe_hosts_sample():
    """أمثلة روابط مسموحة/ممنوعة — للتوثيق والاختبار."""
    return {
        "allowed": ["https://api.github.com", "http://example.com/page"],
        "blocked": ["http://localhost:8080", "http://169.254.169.254/latest",
                    "file:///etc/passwd", "http://10.0.0.5/admin"],
    }


if __name__ == "__main__":
    for url in ["https://api.github.com", "http://localhost/admin",
                "http://169.254.169.254/meta", "file:///etc/passwd",
                "http://10.1.1.1/"]:
        ok, reason = check_url(url)
        print(f"{'✅' if ok else '🚫'} {url} — {reason}")
