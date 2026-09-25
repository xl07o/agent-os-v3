"""اختبارات ollama_manager.py.

تشغيل: python -m pytest tests/ -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ollama_manager():
    """التحقق من مدير Ollama."""
    import ollama_manager
    report = ollama_manager.status_report()
    assert "running" in report
    assert "models" in report


def test_ollama_model_name_sanitized():
    """اسم نموذج Ollama يُرفض إن لم يكن أحرفاً آمنة."""
    import ollama_manager
    assert ollama_manager._safe_model_name("llama3.1:latest") == "llama3.1:latest"
    try:
        ollama_manager._safe_model_name("../rm -rf /")
        assert False, "يجب رفض الاسم الضار"
    except ValueError:
        pass
    ok, _ = ollama_manager.delete_model("../../evil")
    assert ok is False