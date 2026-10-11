"""
تزامن التوثيق — مستوحى من مهارة "neat-freak" (khazix-skills، MIT)، لكن
مبسّط لحجم agent_os4: لا أحاول نسخ آلتها الكاملة (6 ملفات مرجعية،
مساران خفيف/كامل، نظام أدلة متعدد الطبقات) — فقط الجزء المفيد فعلياً
هنا: هل التوثيق لسا يطابق الكود الحقيقي، ورصد مخلّفات جلسات سابقة
(PLAN.md، نسخ _old/_backup) كمرشحات مراجعة فقط.

قاعدة واحدة بلا استثناء، نفس باقي النظام: audit() قراءة فقط، بلا أي
تعديل أو حذف. أي تعديل توثيق مقترَح يمر عبر decision.py نفسها بموافقة
صريحة — ومرشحات المخلّفات تُعرَض فقط، لا تُحذف أبداً من هنا.
"""

import difflib
import json
import os
import re
import time

from . import approval, decision

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_PROPOSALS_FILE = os.path.join(_DATA_DIR, "docs_sync_proposals.json")

_RESIDUE_PATTERNS = (
    re.compile(r"^(PLAN|TODO|NOTES?)\.md$", re.I),
    re.compile(r".*_old\.\w+$", re.I),
    re.compile(r".*_backup\.\w+$", re.I),
    re.compile(r".*_v\d+\.\w+$", re.I),
    re.compile(r"^debug_.*\.py$", re.I),
)


def _load_proposals() -> dict:
    if not os.path.exists(_PROPOSALS_FILE):
        return {}
    with open(_PROPOSALS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_proposals(data: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _PROPOSALS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _PROPOSALS_FILE)


def _safe_doc_path(project_root: str, doc_filename: str) -> str:
    """doc_filename مباشر داخل project_root فقط — لا هروب خارجه
    (نفس صرامة safety.validate_path/self_improve._real_path)."""
    project_root = os.path.abspath(project_root)
    path = os.path.normpath(os.path.join(project_root, doc_filename))
    if os.path.dirname(path) != project_root:
        raise ValueError(f"اسم ملف غير مسموح (يخرج عن مجلد المشروع): {doc_filename}")
    return path


def _list_py_files(project_root: str) -> set[str]:
    return {
        name for name in os.listdir(project_root)
        if name.endswith(".py") and os.path.isfile(os.path.join(project_root, name))
    }


def _find_documented_files(doc_text: str) -> set[str]:
    """يلتقط أسماء ملفات .py مذكورة بين backticks بالتوثيق، مثل `kernel.py`."""
    return set(re.findall(r"`([a-zA-Z_][\w]*\.py)`", doc_text))


def _find_residue(project_root: str) -> list[str]:
    return sorted(
        name for name in os.listdir(project_root)
        if os.path.isfile(os.path.join(project_root, name)) and any(p.match(name) for p in _RESIDUE_PATTERNS)
    )


def audit(project_root: str, doc_filename: str = "README.md") -> dict:
    """تقرير فحص فقط — بلا أي تعديل أو حذف. استخدم propose_doc_fix()
    لاقتراح تعديل فعلي (يحتاج موافقة)."""
    doc_path = _safe_doc_path(project_root, doc_filename)
    doc_text = ""
    if os.path.isfile(doc_path):
        with open(doc_path, "r", encoding="utf-8", errors="replace") as f:
            doc_text = f.read()

    actual_files = _list_py_files(project_root)
    documented_files = _find_documented_files(doc_text)

    undocumented = sorted(actual_files - documented_files)
    stale_references = sorted(documented_files - actual_files)
    residue_candidates = _find_residue(project_root)

    return {
        "doc_file": doc_filename,
        "doc_exists": os.path.isfile(doc_path),
        "undocumented_files": undocumented,
        "stale_doc_references": stale_references,
        "residue_candidates": residue_candidates,
        "in_sync": not undocumented and not stale_references and not residue_candidates,
    }


def propose_doc_fix(project_root: str, doc_filename: str, new_content: str, why: str, proposed_by: str = "owner") -> dict:
    """يقترح تعديل ملف توثيق — عبر decision.py نفسها بموافقة صريحة
    دائماً. لا يكتب الملف مباشرة أبداً."""
    doc_path = _safe_doc_path(project_root, doc_filename)
    old_content = ""
    if os.path.isfile(doc_path):
        with open(doc_path, "r", encoding="utf-8", errors="replace") as f:
            old_content = f.read()
    if old_content == new_content:
        return {"ok": False, "error": "لا فرق فعلي عن النسخة الحالية"}

    diff = "".join(difflib.unified_diff(
        old_content.splitlines(keepends=True), new_content.splitlines(keepends=True),
        fromfile=f"a/{doc_filename}", tofile=f"b/{doc_filename}",
    ))
    result = decision.propose(
        what=f"تعديل توثيق: {doc_filename}",
        why=f"{why}\n\n--- الفرق ---\n{diff}",
        proposed_by=proposed_by,
    )
    req_id = result["request_id"]
    proposals = _load_proposals()
    proposals[req_id] = {
        "doc_path": doc_path, "new_content": new_content, "diff": diff,
        "proposed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_proposals(proposals)
    return {"ok": True, "request_id": req_id, "diff": diff}


def apply_doc_fix(request_id: str) -> dict:
    """لا يُطبَّق أبداً إلا لو موافَق عليه صراحةً — نفس قاعدة
    self_improve.apply() بالضبط."""
    record = approval.get(request_id)
    if not record:
        return {"ok": False, "error": "طلب غير موجود"}
    if record["status"] != "approved":
        return {"ok": False, "error": f"الطلب ليس موافَقاً عليه (الحالة: {record['status']})"}

    proposals = _load_proposals()
    proposal = proposals.get(request_id)
    if not proposal:
        return {"ok": False, "error": "لا يوجد اقتراح محفوظ لهذا الطلب"}

    with open(proposal["doc_path"], "w", encoding="utf-8") as f:
        f.write(proposal["new_content"])

    del proposals[request_id]
    _save_proposals(proposals)
    return {"ok": True, "applied_to": proposal["doc_path"]}
