"""
لقطة حالة os4 الحقيقية — للعرض الخارجي فقط (مثلاً web_bridge.py)، بلا أي
تنفيذ أو أثر جانبي. لا تكشف قيم المفاتيح، فقط هل هي موجودة أو لا.
"""

import os

from . import env  # noqa: F401  (يضمن تحميل .env قبل قراءة os.environ)
from . import approval, memory


def snapshot() -> dict:
    return {
        "pending_approvals": len(approval.pending()),
        "memory_entries": memory.count(),
        "claude_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "daytona_configured": bool(os.environ.get("DAYTONA_API_KEY")),
    }
