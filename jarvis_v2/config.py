# -*- coding: utf-8 -*-
"""إعدادات جارفيس v2 — مسارات، سياسة الإذن، المهل. لا أسرار هنا أبداً (كل شيء من .env الأصلي يُقرأ هناك)."""
import os
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

_STEM = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_STEM)                       # جذر المشروع
EVID_DIR = os.path.join(BASE, "output", "jarvis_v2")
os.makedirs(EVID_DIR, exist_ok=True)

# سياسة الإذن: allow = ينفذ فوراً | ask = يسأل قبل كل أمر/كتابة خارج الجذر (الافتراضي)
AUTORUN = os.getenv("JARVIS_AUTORUN", "ask")
MAX_STEPS = int(os.getenv("JARVIS_MAX_STEPS", "12"))
BASH_TIMEOUT = int(os.getenv("JARVIS_BASH_TIMEOUT", "60"))     # ثانية
FETCH_TIMEOUT = int(os.getenv("JARVIS_FETCH_TIMEOUT", "20"))
MAX_FILE_BYTES = int(os.getenv("JARVIS_MAX_FILE_BYTES", "200000"))
MODEL_MODE = os.getenv("SELFRUNNER_MODE", "hybrid")             # يُرى من env الأصلي


def is_inside(base, path):
    p = os.path.abspath(path)
    return p == os.path.abspath(base) or p.startswith(os.path.abspath(base) + os.sep)


def safe_resolve(rel):
    """حل مسار نسبي داخل الجذر فقط — رفض الهرولة خارج الحدود."""
    p = os.path.abspath(rel if os.path.isabs(rel) else os.path.join(BASE, rel))
    if not is_inside(BASE, p):
        raise PermissionError("المسار خارج جذر العمل: " + rel)
    return p


def short_args(args, limit=120):
    s = str(args)
    return s if len(s) <= limit else s[:limit] + "…"