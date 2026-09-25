"""اختبارات skills.py.

تشغيل: python -m pytest tests/ -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_list_skills():
    """التحقق من أن list_skills يعمل."""
    import skills
    result = skills.list_skills()
    assert isinstance(result, list)


def test_memory_load():
    """التحقق من تحميل الذاكرة."""
    import skills
    mem = skills._load_memory()
    assert "learned" in mem
    assert "count" in mem


def test_skill_traversal_neutralized():
    """أسماء المهارات الممررة لا تخرج عن SKILLS_DIR أبداً (لا rmtree خارج النطاق)."""
    import skills
    root = os.path.realpath(skills.SKILLS_DIR)
    project_dir = os.path.dirname(os.path.abspath(skills.__file__))
    for evil in ["..", "../..", "../../projects", "../../README", "a/../../x", "..\\..\\../x"]:
        try:
            d = skills._safe_skill_dir(evil)
            assert os.path.realpath(d).startswith(root + os.sep)
        except ValueError:
            pass  # الاسم مرفوض تماماً وهو السلوك المطلوب
    # حذف/تحديث/قراءة بروابط عابرة: لا تعدّل ملفاً خارجاً ولا تحذف مجلداً
    assert skills.delete_skill("..") is False
    assert skills.update_skill("../README", "محتوى ضار") is False
    assert skills.get_skill("../../requirements.txt") is None
    assert skills.get_skill_info("../../projects") == {}
    assert os.path.exists(os.path.join(project_dir, "README.md"))