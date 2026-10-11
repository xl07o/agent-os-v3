"""
تطوير ذاتي: اقتراح تعديل لملف داخل agent_os4 نفسه. لا يُطبَّق على القرص
الحقيقي إلا بعد شرطين، بلا استثناء لأي ملف — حتى safety.py وapproval.py
نفسهما (بوابة الأمان والموافقة) يمرّان بنفس الطريق بالضبط، بلا باب خلفي:

  1) الكود الجديد يُختبر فعلياً داخل Daytona sandbox معزول تماماً عن
     جهازك: يُترجم، يُستورد، ثم selftest.py يتأكد أن الحواجز (الموافقة،
     منع أدوات الجهاز، سقف الصرف، CSRF) لسا شغالة فعلاً. فشل الاختبار — أو حتى مجرد تعذّر الوصول لـDaytona نفسه —
     يوقف كل شي هنا؛ لا يصل أبداً لمرحلة طلب الموافقة. فشل الساندبوكس
     = فشل الاقتراح، ليس تجاوزاً.
  2) موافقتك الصريحة على الفرق (diff) الكامل والحقيقي بين القديم
     والجديد، لا وصف عام — نفس بوابة approval.py المستخدمة لكل شيء آخر.

عند apply(): نسخة احتياطية من الملف القديم تُحفظ أولاً دائماً بـ
data/self_improve_backups، كي لو صار خطأ حتى بعد كل هذا يقدر صاحب
الجهاز يرجّعها يدوياً بثانية.
"""

import difflib
import json
import os
import time

from . import approval, decision, sandbox

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_PKG_DIR, "data")
_PROPOSALS_FILE = os.path.join(_DATA_DIR, "self_improve_proposals.json")
_BACKUP_DIR = os.path.join(_DATA_DIR, "self_improve_backups")

# كل ملفات الحزمة التي يُتحقَّق من استيرادها بنجاح داخل الساندبوكس قبل
# أي موافقة — قائمة صريحة بدل اكتشاف تلقائي، كي لا يفوتنا ملف بصمت.
_SUBMODULES = [
    "env", "safety", "approval", "memory", "brain", "sandbox",
    "obsidian", "tools", "status", "housekeeping", "self_improve",
    "roles", "decision", "bots", "chatroom", "skills", "evidence",
    "router", "metrics", "web_chat", "deploy", "kernel", "cli",
    "rooms", "spend", "web", "learning", "ceo", "market", "widgets", "selftest",
    "agent_memory", "agent_skills", "reflect", "textnorm", "sessions", "scheduler",
]


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


def _real_path(relative_filename: str) -> str:
    """relative_filename مثل 'kernel.py' — ملف .py مباشر داخل agent_os4
    فقط، لا مجلدات فرعية ولا هروب خارجها (نفس صرامة safety.validate_path)."""
    path = os.path.normpath(os.path.join(_PKG_DIR, relative_filename))
    if os.path.dirname(path) != _PKG_DIR or not relative_filename.endswith(".py"):
        raise ValueError(f"مسار غير مسموح للتطوير الذاتي: {relative_filename}")
    return path


def sandbox_script(relative_filename: str, new_content: str) -> str:
    """نفس السكربت اللي يشتغل داخل Daytona — منفصل عشان ينختبر محلياً."""
    tar_b64 = sandbox.build_package_tarball_b64({relative_filename: new_content})
    imports = ", ".join(f"agent_os4.{m}" for m in _SUBMODULES)
    return (
        "set -e\n"
        "rm -rf /tmp/os4test && mkdir -p /tmp/os4test && cd /tmp/os4test\n"
        f"echo '{tar_b64}' | base64 -d | tar xz\n"
        "pip install -q python-dotenv requests >/tmp/pip.log 2>&1 || true\n"
        "python3 -m py_compile agent_os4/*.py\n"
        f"python3 -c \"import sys; sys.path.insert(0, '.'); import {imports}; print('IMPORT_OK')\"\n"
        # اختبار سلوكي: الحواجز (موافقة/أدوات الجهاز/سقف الصرف/CSRF) لسا شغالة فعلاً
        "python3 -m agent_os4.selftest\n"
    )


def _test_in_sandbox(relative_filename: str, new_content: str) -> dict:
    script = sandbox_script(relative_filename, new_content)
    sb_id = None
    try:
        sb_id = sandbox.create(label="self-improve-test")
        result = sandbox.run_bash(sb_id, script, timeout=120)
        output = str(result["output"])
        passed = result["exit_code"] == 0 and "IMPORT_OK" in output and "SELFTEST_OK" in output
        return {"ok": passed, "output": str(result["output"])[:3000]}
    except Exception as e:  # noqa: BLE001 — أي فشل بالوصول لـDaytona نفسه = فشل اختبار، لا تجاوز صامت
        return {"ok": False, "output": f"{type(e).__name__}: {e}"}
    finally:
        if sb_id:
            try:
                sandbox.destroy(sb_id)
            except Exception:
                pass


def propose(relative_filename: str, new_content: str, why: str, proposed_by: str = "owner") -> dict:
    """يختبر التعديل بساندبوكس معزول أولاً — فشل هنا يوقف كل شي، صفر
    طلبات موافقة على كود لم يُثبَت أنه يعمل. لو نجح، يفتح طلباً عبر
    decision.py (لا approval.py مباشرة) — فيلمس ملفاً حساساً زي safety.py
    يحصل تلقائياً على مراجعة مستقلة إضافية قبل موافقتك، ويُسجَّل باللدجر."""
    real_path = _real_path(relative_filename)
    old_content = ""
    if os.path.exists(real_path):
        with open(real_path, "r", encoding="utf-8") as f:
            old_content = f.read()

    diff = "".join(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{relative_filename}", tofile=f"b/{relative_filename}",
    ))
    if not diff:
        return {"ok": False, "stage": "diff", "error": "لا فرق فعلي عن النسخة الحالية"}

    test = _test_in_sandbox(relative_filename, new_content)
    if not test["ok"]:
        return {"ok": False, "stage": "sandbox_test", "error": test["output"], "diff": diff}

    result = decision.propose(
        what=f"تطوير ذاتي: {relative_filename}",
        why=f"{why}\n\n--- الفرق الكامل ---\n{diff}",
        proposed_by=proposed_by,
    )
    req_id = result["request_id"]
    proposals = _load_proposals()
    proposals[req_id] = {
        "relative_filename": relative_filename,
        "new_content": new_content,
        "diff": diff,
        "proposed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_proposals(proposals)
    return {
        "ok": True, "stage": "pending_approval", "request_id": req_id,
        "diff": diff, "independent_review": result.get("independent_review"),
    }


def apply(request_id: str) -> dict:
    """لا يُطبَّق أبداً إلا لو الطلب موافَق عليه صراحةً. يأخذ نسخة
    احتياطية من الملف القديم قبل أي كتابة."""
    record = approval.get(request_id)
    if not record:
        return {"ok": False, "error": "طلب غير موجود"}
    if record["status"] != "approved":
        return {"ok": False, "error": f"الطلب ليس موافَقاً عليه (الحالة: {record['status']})"}

    proposals = _load_proposals()
    proposal = proposals.get(request_id)
    if not proposal:
        return {"ok": False, "error": "لا يوجد اقتراح محفوظ لهذا الطلب"}

    real_path = _real_path(proposal["relative_filename"])
    os.makedirs(_BACKUP_DIR, exist_ok=True)
    backup_path = None
    if os.path.exists(real_path):
        backup_path = os.path.join(
            _BACKUP_DIR, f"{proposal['relative_filename']}.{time.strftime('%Y%m%d-%H%M%S')}.bak"
        )
        with open(real_path, "r", encoding="utf-8") as f:
            old = f.read()
        with open(backup_path, "w", encoding="utf-8") as b:
            b.write(old)

    with open(real_path, "w", encoding="utf-8") as f:
        f.write(proposal["new_content"])

    del proposals[request_id]
    _save_proposals(proposals)
    return {"ok": True, "applied_to": real_path, "backup": backup_path}


def list_proposals() -> list[dict]:
    proposals = _load_proposals()
    out = []
    for req_id, p in proposals.items():
        record = approval.get(req_id) or {}
        out.append({"request_id": req_id, "status": record.get("status", "?"), **p})
    return out


def list_backups(relative_filename: str) -> list[str]:
    if not os.path.isdir(_BACKUP_DIR):
        return []
    prefix = relative_filename + "."
    return sorted(p for p in os.listdir(_BACKUP_DIR) if p.startswith(prefix))


def restore(relative_filename: str, backup_path: str | None = None, proposed_by: str = "owner") -> dict:
    """Rollback & Recovery Authority: يرجّع ملفاً لنسخة احتياطية سابقة.
    نفس الطريق بالضبط مثل أي تعديل ذاتي آخر — عبر decision.py وموافقة
    صريحة — لا اختصار "آمن" لأنه رجوع، نفس القاعدة بلا استثناء. يُعاد
    استخدام apply() الموجودة فعلياً للتطبيق، لا كتابة مسار تنفيذ ثانٍ."""
    real_path = _real_path(relative_filename)

    if backup_path is None:
        candidates = list_backups(relative_filename)
        if not candidates:
            return {"ok": False, "error": "لا نسخة احتياطية موجودة لهذا الملف"}
        backup_path = os.path.join(_BACKUP_DIR, candidates[-1])
    if not os.path.isfile(backup_path):
        return {"ok": False, "error": f"نسخة احتياطية غير موجودة: {backup_path}"}

    with open(backup_path, "r", encoding="utf-8") as f:
        old_content = f.read()
    current_content = ""
    if os.path.exists(real_path):
        with open(real_path, "r", encoding="utf-8") as f:
            current_content = f.read()

    diff = "".join(difflib.unified_diff(
        current_content.splitlines(keepends=True),
        old_content.splitlines(keepends=True),
        fromfile=f"a/{relative_filename} (حالي)", tofile=f"b/{relative_filename} (نسخة احتياطية)",
    ))
    if not diff:
        return {"ok": False, "error": "الملف الحالي مطابق للنسخة الاحتياطية أصلاً — لا داعي للاسترجاع"}

    result = decision.propose(
        what=f"استرجاع: {relative_filename}",
        why=f"استرجاع لنسخة احتياطية: {backup_path}\n\n--- الفرق ---\n{diff}",
        proposed_by=proposed_by,
    )
    req_id = result["request_id"]
    proposals = _load_proposals()
    proposals[req_id] = {
        "relative_filename": relative_filename,
        "new_content": old_content,
        "diff": diff,
        "proposed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_proposals(proposals)
    return {"ok": True, "request_id": req_id, "diff": diff}
