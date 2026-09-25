"""اختبارات الكتابة الذرية لملفات JSON (skills/mastery).

تشغيل: python -m pytest tests/ -v
"""

import os
import sys
import json as _json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_atomic_json_writes():
    """كتابة JSON ذرية: الملف صالح دائماً ولا بقايا .tmp."""
    import skills
    import mastery
    # فهرس المهارات
    skills._save_index({"skills": {}, "version": 2})
    with open(skills.SKILL_INDEX, "r", encoding="utf-8") as f:
        assert _json.load(f)["version"] == 2
    assert not os.path.exists(skills.SKILL_INDEX + ".tmp")
    # الذاكرة
    skills._save_memory({"learned": [], "count": 0, "topics": {}, "last_update": None})
    with open(skills.MEMORY_FILE, "r", encoding="utf-8") as f:
        assert "count" in _json.load(f)
    assert not os.path.exists(skills.MEMORY_FILE + ".tmp")
    # حالة الإتقان
    mastery._save_state(mastery._load_state())
    with open(mastery.STATE_FILE, "r", encoding="utf-8") as f:
        assert _json.load(f)["version"] == 3
    assert not os.path.exists(mastery.STATE_FILE + ".tmp")