"""
hypothesis_lab.py - مختبر الفرضيات (Hypothesis Sandbox)
========================================================
فكرة المالك: "يسوي واجهة وهمية زي الفرضية يختبرها ويدرسها ويحللها
                ويوم تنجح يطبقها بجهازي"
التوسيع: كل فكرة/تغيير/مشروع يمر بمسار علمي:
  فرضية → تصميم تجربة → sandbox → قياس → قرار (طبّق / عدّل / ألغِ)
  لا يُطبَّق شيء على الحقيقي إلا بعد نجاح في المختبر.
"""

import os
import sys
import uuid
import tempfile
import shutil

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

LAB_FILE = os.path.join(C.AGENT_OS_DIR, "hypothesis_lab.json")


def create(hypothesis, success_criteria, experiment_fn=None):
    """ينشئ فرضية جديدة.

    hypothesis: وصف الفكرة.
    success_criteria: كيف نعرف إنها نجحت؟ (نص أو dict).
    experiment_fn: دالة تنفّذ التجربة في sandbox وتعيد {"success": bool, ...}.
    """
    exp_id = f"HYP-{uuid.uuid4().hex[:8]}"
    record = {
        "id": exp_id,
        "hypothesis": str(hypothesis)[:500],
        "success_criteria": str(success_criteria)[:300],
        "status": "created",
        "created_at": C.now_iso(),
        "sandbox_result": None,
        "production_result": None,
        "lessons": [],
    }

    if experiment_fn:
        record = _run_in_sandbox(record, experiment_fn)

    _save(record)
    return record


def _run_in_sandbox(record, experiment_fn):
    """يشغّل التجربة في بيئة معزولة (مجلد مؤقت)."""
    sandbox = tempfile.mkdtemp(prefix="hypothesis_")
    record["status"] = "testing"
    try:
        result = experiment_fn(sandbox)
        record["sandbox_result"] = {
            "success": bool(result.get("success")),
            "metrics": result.get("metrics", {}),
            "output": str(result.get("output", ""))[:500],
        }
        record["status"] = "passed" if result.get("success") else "failed"
    except Exception as e:
        record["sandbox_result"] = {"success": False, "error": str(e)[:200]}
        record["status"] = "error"
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    record["tested_at"] = C.now_iso()
    return record


def promote(exp_id, production_result=None):
    """ينقل فرضية ناجحة من المختبر إلى الإنتاج."""
    lab = _load()
    if exp_id not in lab["experiments"]:
        return {"error": "فرضية غير موجودة"}
    exp = lab["experiments"][exp_id]
    if exp["status"] != "passed":
        return {"error": "لا يمكن ترقية فرضية لم تنجح في المختبر"}
    exp["status"] = "promoted"
    exp["promoted_at"] = C.now_iso()
    exp["production_result"] = production_result
    C.atomic_write(LAB_FILE, lab)
    C.log(f"🧪→🚀 فرضية {exp_id} رُقّيت للإنتاج")
    return exp


def reject(exp_id, reason=""):
    """يرفض فرضية فاشلة ويسجّل الدرس."""
    lab = _load()
    if exp_id not in lab["experiments"]:
        return {"error": "فرضية غير موجودة"}
    exp = lab["experiments"][exp_id]
    exp["status"] = "rejected"
    exp["rejected_at"] = C.now_iso()
    if reason:
        exp["lessons"].append(reason)
    C.atomic_write(LAB_FILE, lab)
    return exp


def active():
    """الفرضيات النشطة (بلا حسم بعد)."""
    lab = _load()
    return [e for e in lab["experiments"].values()
            if e["status"] in ("created", "testing", "passed")]


def stats():
    """إحصائيات المختبر للتقرير."""
    lab = _load()
    exps = lab["experiments"].values()
    return {
        "total": len(lab["experiments"]),
        "passed": sum(1 for e in exps if e["status"] == "passed"),
        "promoted": sum(1 for e in exps if e["status"] == "promoted"),
        "rejected": sum(1 for e in exps if e["status"] in ("rejected", "failed", "error")),
    }


def _load():
    return C.load_json(LAB_FILE, {"experiments": {}})


def _save(record):
    lab = _load()
    lab["experiments"][record["id"]] = record
    C.atomic_write(LAB_FILE, lab)


if __name__ == "__main__":
    def demo_experiment(sandbox_dir):
        test_file = os.path.join(sandbox_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("تجربة")
        return {"success": os.path.exists(test_file), "metrics": {"files": 1}}

    r = create("كتابة ملفات في بيئة معزولة تعمل بأمان",
               "الملف يُنشأ في sandbox ولا يؤثر على النظام الحقيقي",
               demo_experiment)
    print(f"النتيجة: {r['status']} | المختبر: {r['sandbox_result']}")
