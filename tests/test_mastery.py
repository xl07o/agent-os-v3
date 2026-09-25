"""اختبارات mastery.py (محرك الإتقان وحارس AST).

تشغيل: python -m pytest tests/ -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_mastery_state_and_tracks():
    """حالة الإتقان تحتوي كل المسارات بمستويات صحيحة."""
    import mastery
    st = mastery._load_state()
    assert len(st["tracks"]) == len(mastery.TRACKS)
    for t in mastery.TRACKS:
        tr = st["tracks"][t["id"]]
        assert 1 <= tr["level"] <= 5
    assert "total_cycles" in st and "total_demos" in st


def test_mastery_presence_flag():
    """علامة الحضور توقف الإتقان — الأساس للعودة بسلامة."""
    import mastery
    mastery.mark_user_away()
    assert mastery.user_present() is False
    mastery.mark_user_active()
    assert mastery.user_present() is True
    mastery.mark_user_away()


def test_mastery_next_target():
    """اختيار المسار الأقل تقدماً دائماً."""
    import mastery
    track, tr = mastery.next_target()
    assert track is not None and tr is not None
    assert tr["level"] < 5


def test_mastery_sanitize_and_levels():
    """توليد أسماء آمنة ومستويات محدودة بـ 5."""
    import mastery
    assert mastery._sanitize("Pwn Security!! أمن") == "pwn_security"
    assert mastery._LEVEL_NAMES[5] == "خبير"


def test_mastery_stop_control():
    """stop/resume عبر ملف العلامة."""
    import mastery
    mastery.do_stop()
    assert mastery.stalled() is True
    mastery.do_resume()
    assert mastery.stalled() is False


def test_mastery_demos_inside_projects():
    """المكتبات المولدة ذاتياً لا تخرج خارج projects/mastery أبداً."""
    import mastery
    assert mastery.IMPROV_DIR.startswith(mastery.MASTERY_DIR)


def test_mastery_report_no_crash():
    """التقرير والحالة يعملان دون استثناءات."""
    import mastery
    status = mastery.status()
    assert "# محرك الإتقان" in status and "مكتبات مقبولة" in status
    report_path = mastery.report()
    assert os.path.exists(report_path)


def test_mastery_static_guard_rejects_evil():
    """حارس AST يرفض أي استيراد/استدعاء خطير قبل التنفيذ."""
    import mastery
    assert mastery._static_guard("import os\nos.remove('x')")[0] is False
    assert mastery._static_guard("import subprocess")[0] is False
    assert mastery._static_guard("from socket import socket")[0] is False
    assert mastery._static_guard("import urllib.request")[0] is False
    assert mastery._static_guard("import ctypes")[0] is False
    assert mastery._static_guard("importlib.import_module('os')")[0] is False
    assert mastery._static_guard("eval('1+1')")[0] is False
    assert mastery._static_guard("exec('print(1)')")[0] is False
    assert mastery._static_guard("obj.system('id')")[0] is False
    assert mastery._static_guard("shutil.rmtree('/x')")[0] is False
    assert mastery._static_guard("open('secrets.txt')")[0] is False
    assert mastery._static_guard("pathlib.Path('/etc/passwd')")[0] is False
    assert mastery._static_guard("import requests")[0] is False


def test_mastery_static_guard_rejects_size_and_syntax():
    """الحد الأقصى للأسطر والصياغة المعطوبة تُرفض."""
    import mastery
    assert mastery._static_guard("# a\n" * 500)[0] is False
    assert mastery._static_guard("def broken(:" )[0] is False


def test_mastery_static_guard_allows_safe_code():
    """مكتبات قياسية آمنة تبقى مسموحة — لا نكسر التوليد الذاتي."""
    import mastery
    safe = (
        "import math, re, json\n"
        "from collections import Counter\n"
        "def main():\n"
        "    return math.sqrt(4) + len(re.findall('a', 'abc'))\n"
    )
    ok, why = mastery._static_guard(safe)
    assert ok is True, why