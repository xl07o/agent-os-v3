"""اختبارات dashboard.py.

تشغيل: python -m pytest tests/ -v
"""

import os
import sys
import re as _re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_dashboard_build():
    """التحقق من بناء لوحة العرض."""
    import dashboard
    path = dashboard.build_html()
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "لوحة موظف الليل" in content


def test_dashboard_links_are_relative():
    """لوحة المعلومات لا تكشف مسار القرص الكامل (لا file:/// ولا C:/Users)."""
    import dashboard
    path = dashboard.build_html()
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    assert "file:///" not in html
    assert "C:/Users" not in html
    hrefs = _re.findall(r'href="([^"]+)"', html)
    assert all(
        h and not h.startswith(("file:", "C:", "D:", "/")) for h in hrefs
    )