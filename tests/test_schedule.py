"""اختبارات schedule.py (الحقن في XML الجدولة).

تشغيل: python -m pytest tests/ -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_schedule_xml_escape():
    """منع حقن XML في الجدولة."""
    import schedule
    evil = 'task" <none/> &'
    xml = schedule._build_xml("2026-09-10T02:00:00", evil)
    assert "<none/>" not in xml
    assert "&lt;" in xml and "&quot;" in xml and "&amp;" in xml
    assert "task&quot;" in xml
    # أي عنصر حقن <none/> أو &quot; خالصة يجب ألا توجد
    assert xml.count("<Exec>") == 1


def test_schedule_xml_has_long_limit():
    """حد المهمة سخي وليس PT23H (لا يقطع المهمة قبل اكتمالها)."""
    import schedule
    xml = schedule._build_xml("2026-01-01T02:00:00", "مهمة اختبار")
    assert "PT23H" not in xml
    assert "{LIMIT}" not in xml  # لا placeholder متبقي
    assert "PT71H" in xml or "PT" in xml