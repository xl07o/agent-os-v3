# -*- coding: utf-8 -*-
"""بوابة الصدق — لا تصدق النص أبداً؛ صدِّق الأدلة فقط."""
import os

from . import evidence

def final_verdict(results, label):
    """results: قائمة نتائج الخطوات. الحكم الصادق:
       تمام = لا فشل وكل خطوة نجحت بدليل    |    جزئي = بعضها فشل   |    لم يتم = صفر دليل."""
    if not results:
        return "لم يتم (لا دليل تنفيذ على الإطلاق — مهمة منتهية بلا عمل)"
    fails = [r for r in results if not r.get("ok")]
    if not fails:
        return "تمام — كل الخطوات نُفِّذت ودُوِّنت أدلتها"
    return "جزئي — %d/%d خطوات نجحت و%d فشلت (المشكلة مفصح عنها بالأسفل)" % (
        len(results) - len(fails), len(results), len(fails))


def claim_is_supported(session, claim):
    """هل يدعم السجل هذا الادعاء؟ (بوابة: لا 'نجح' بلا أثر في ledger)"""
    rows = [r for r in evidence.since(session) if r.get("status") == "ok"]
    artifacts = [r.get("artifact") for r in rows if r.get("artifact")]
    checkable = any(
        a and os.path.exists(a) for a in artifacts
    ) if artifacts else None
    return {
        "ok_actions": len(rows),
        "artifacts_real": artifacts,
        "artifacts_exist": checkable,
        "claim": claim,
    }