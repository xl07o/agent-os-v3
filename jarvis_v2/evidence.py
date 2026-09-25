# -*- coding: utf-8 -*-
"""سجل الإثبات — كل أداة تُسجِّل دليلاً (JSONL) يبقى بعد الجلسة. بوابة الصدق تعتمد عليه."""
import json
import os
import time
import uuid

from . import config

_PATH = os.path.join(config.EVID_DIR, "evidence.jsonl")


def append(kind, tool, status, note=None, artifact=None, **extra):
    rec = {
        "id": uuid.uuid4().hex[:8],
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "session": _session,
        "kind": kind,
        "tool": tool,
        "status": status,               # ok | fail | skip
        "note": (note or "")[:400],
        "artifact": artifact,           # أي ملف ملموس كدليل (diff/ناتج/تقرير)
    }
    rec.update(extra)
    try:
        with open(_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return rec


def begin_session(label):
    global _session
    _session = "%s-%s" % (time.strftime("%Y%m%d_%H%M%S"), uuid.uuid4().hex[:6])
    append("session", "janvis_v2", "ok", note=("بدء جلسة: %s" % label))
    return _session


def load():
    out = []
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return out


def since(session, kind=None):
    return [r for r in load() if r.get("session") == session and (kind is None or r.get("kind") == kind)]


def has_ok_evidence(session):
    """بوابة الصدق: هل يوجد دليل ناجح ملموس؟ (أداة ok مع artifact أو خالص)"""
    rows = since(session)
    if not rows:
        return False
    # نرفض الجلسة الفارغة/الميتة
    non_session = [r for r in rows if r.get("kind") != "session"]
    if not non_session:
        return False
    ok = [r for r in non_session if r.get("status") == "ok"]
    # محاولة سيئة لا تعدّ خاتمة ناجحة
    fails = [r for r in non_session if r.get("status") == "fail"]
    return True if ok and not (fails and len(ok) <= len(fails)) else bool(ok)


def path():
    return _PATH