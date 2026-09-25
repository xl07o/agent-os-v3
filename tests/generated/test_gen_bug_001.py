"""اختبار انحدار مولّد تلقائياً — bug: BUG-001
now_iso يجب أن يعيد نصاً غير فارغ
لا تحذفه: يمنع عودة هذا الخطأ (المواصفة §60, §62).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_os._common import now_iso


def test_regression_bug_001_now_iso():
    result = now_iso()
    assert result, 'now_iso يجب أن يعيد نصاً غير فارغ'
