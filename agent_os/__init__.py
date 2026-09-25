"""agent_os - نظام تشغيل الوكيل v3.

حزمة أنظمة: أهداف، تحسين ذاتي، قياس، أدوات، متصفح، أعمال، منتجات، نشر،
بجتي، مالية، موافقات، نموذج عالمي، ومدير رئيسي (Router/Planner/Executor/Critic/Verifier).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from . import _common  # noqa: E402,F401

__all__ = ["_common"]


def AgentOS(*args, **kw):
    """جسد الوكيل متكاسل الاستيراد — تجنب تحميل الأنظمة عند استيراد الحزمة فقط."""
    from agent_os.kernel import AgentOS as _A
    return _A(*args, **kw)