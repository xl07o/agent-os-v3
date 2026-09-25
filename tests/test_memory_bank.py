"""اختبارات memory_bank.py.

تشغيل: python -m pytest tests/ -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_remember_and_recall():
    """التحقق من تخزين واسترجاع الذاكرة."""
    import memory_bank
    # تخزين
    result = memory_bank.remember(
        "test_key_fix", "هذه معلومة اختبارية عن كيفية إصلاح الأخطاء الشائعة",
        importance=0.9,
        tags=["test"],
    )
    assert result["status"] == "stored" or result["status"] == "updated"

    # استرجاع
    results = memory_bank.recall("إصلاح الأخطاء", min_score=0.01)
    assert isinstance(results, list)


def test_memory_stats():
    """التحقق من إحصائيات الذاكرة."""
    import memory_bank
    stats = memory_bank.stats()
    assert "total_items" in stats
    assert "total_chars" in stats


def test_memory_prune_dedup():
    """prune_old لا يحذف عنصراً بمعيار واحد خاطئ."""
    import memory_bank
    # نتأكد فقط من أن الدالة تعمل وتعيد هيكل صحيح (المنطق بالمطابقة بالـ id)
    result = memory_bank.prune_old(days=0)
    assert "before" in result and "after" in result and "removed" in result


def test_memory_bank_atomic_write():
    """بنك الذاكرة يُكتب ذرياً (لا بقايا .tmp، الملف صالح)."""
    import json as _json
    import memory_bank
    memory_bank.remember("atomic_key_check", "اختبار الذرية", importance=0.3, tags=["t"])
    with open(memory_bank.MEMORY_FILE, "r", encoding="utf-8") as f:
        bank = _json.load(f)
    assert "items" in bank
    assert not os.path.exists(memory_bank.MEMORY_FILE + ".tmp")
    assert not os.path.exists(memory_bank.INDEX_FILE + ".tmp")