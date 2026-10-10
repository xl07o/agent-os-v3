"""
سجل المهارات (Skill Registry & Version Control) + اختبار المهارات
(Skill Test & Benchmark Authority) + حماية من التراجع (Regression
Testing Authority) — مهارة = قالب برومبت معاد الاستخدام عبر أي بوت، مع
أمثلة اختبار محفوظة معها.

قاعدة واحدة بلا استثناء: نسخة جديدة من مهارة موجودة لازم تمر على كل
أمثلة النسخة القديمة بنجاح أولاً — فشل أي مثال قديم = رفض النسخة
الجديدة كاملة، لا اعتماد جزئي ولا "تحسّن بمتوسط" يُخفي تراجعاً حقيقياً.
هذا غلاف فوق brain.ask() — لا بنية تحتية جديدة.
"""

import json
import os
import time

from . import brain

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_FILE = os.path.join(_DATA_DIR, "skills.json")


def _load() -> dict:
    if not os.path.exists(_FILE):
        return {}
    with open(_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _FILE)


def _run_examples(prompt_template: str, examples: list[dict]) -> list[dict]:
    """ينجح المثال لو الكلمة المتوقعة (expect_contains) موجودة فعلاً
    بالرد الحقيقي من brain.ask() — لا تقييم لغوي ذاتي، تحقق نصي مباشر."""
    results = []
    for ex in examples:
        prompt = prompt_template.format(input=ex["input"])
        try:
            reply = brain.ask(prompt)
            passed = ex["expect_contains"].lower() in reply.lower()
            results.append({"input": ex["input"], "passed": passed, "reply": reply[:300]})
        except Exception as e:  # noqa: BLE001 — فشل استدعاء المخ = فشل المثال، لا استثناء يُبتلع
            results.append({"input": ex["input"], "passed": False, "reply": f"(فشل: {type(e).__name__}: {e})"})
    return results


def register(name: str, prompt_template: str, examples: list[dict]) -> dict:
    """يسجّل نسخة جديدة من مهارة. لو فيها نسخ سابقة، تُختبر كل الأمثلة
    المتراكمة من كل النسخ السابقة (لا آخر نسخة فقط — مثال من النسخة 1
    يبقى محمياً حتى بعد عشر نسخ لاحقة) على القالب الجديد (Regression
    Testing) — فشل أي واحد منها يرفض النسخة الجديدة كاملة قبل أي اعتماد."""
    skills = _load()
    history = skills.get(name, {"versions": []})

    if history["versions"]:
        seen_inputs: set[str] = set()
        all_prior_examples: list[dict] = []
        for v in history["versions"]:
            for ex in v["examples"]:
                if ex["input"] not in seen_inputs:
                    seen_inputs.add(ex["input"])
                    all_prior_examples.append(ex)

        regression = _run_examples(prompt_template, all_prior_examples)
        failed_old = [r for r in regression if not r["passed"]]
        if failed_old:
            return {
                "ok": False, "stage": "regression",
                "error": f"{len(failed_old)} من أمثلة النسخ السابقة (كلها، لا آخر نسخة فقط) فشلت بالنسخة الجديدة — رُفضت",
                "failed": failed_old,
            }

    new_results = _run_examples(prompt_template, examples)
    failed_new = [r for r in new_results if not r["passed"]]
    if failed_new:
        return {
            "ok": False, "stage": "new_examples",
            "error": f"{len(failed_new)} من الأمثلة الجديدة نفسها فشلت — لا تُعتمد مهارة لم تثبت",
            "failed": failed_new,
        }

    version = len(history["versions"]) + 1
    history["versions"].append({
        "version": version, "prompt_template": prompt_template, "examples": examples,
        "registered_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    skills[name] = history
    _save(skills)
    return {"ok": True, "version": version}


def use(name: str, input_text: str) -> str:
    """يستخدم آخر نسخة معتمدة من مهارة معيّنة."""
    skills = _load()
    history = skills.get(name)
    if not history or not history["versions"]:
        raise ValueError(f"مهارة غير موجودة: {name}")
    latest = history["versions"][-1]
    return brain.ask(latest["prompt_template"].format(input=input_text))


def list_skills() -> list[dict]:
    skills = _load()
    return [
        {"name": k, "latest_version": v["versions"][-1]["version"], "examples_count": len(v["versions"][-1]["examples"])}
        for k, v in skills.items()
    ]
