"""
جسر رفيع لـ obsidian_vault.py الموجود بجذر المشروع — جرّبته حياً ويشتغل
صحيح، فلا داعي لإعادة كتابته. مجرد استيراد.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from obsidian_vault import write_note  # noqa: E402,F401
