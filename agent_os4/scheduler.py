"""
مهام مجدولة بأسلوب Hermes Agent (cron) — "كل يوم الساعة 9 عطني تقرير
الأسهم" يشتغل لحاله بدون ما تكتب شي.

صيغ الجدولة (بتوقيت الجهاز اللي شغّال عليه السيرفر):
  30m / 2h / 1d            كل مدة (أقل شي 15 دقيقة — عشان الفلوس)
  daily 09:00              كل يوم
  weekly sun 09:00         كل أسبوع (sun mon tue wed thu fri sat، أو الأحد..السبت)
  once 2026-10-20 09:00    مرة وحدة

التشغيل غير تفاعلي: أي خطوة تحتاج موافقة تبقى معلّقة لين ترجع وتوافق —
المهمة المجدولة ما تتجاوز بوابة الموافقة. لو السيرفر كان طافي وفاتت
مواعيد: تشتغل مرة وحدة بس لما يرجع، ما تنفجر كلها ورا بعض.
"""

import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta

_FILE = os.path.join(os.path.dirname(__file__), "data", "schedule.json")
MAX_JOBS = 20
MIN_INTERVAL = 15 * 60
_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
         "الاثنين": 0, "الثلاثاء": 1, "الأربعاء": 2, "الاربعاء": 2, "الخميس": 3, "الجمعة": 4, "السبت": 5, "الأحد": 6, "الاحد": 6}
_lock = threading.Lock()


def _load() -> list[dict]:
    if not os.path.exists(_FILE):
        return []
    with open(_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save(jobs: list[dict]) -> None:
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    tmp = _FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _FILE)


def _hm(text: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return int(m.group(1)), int(m.group(2))


def parse(schedule: str) -> tuple[dict | None, str | None]:
    s = " ".join(str(schedule or "").strip().lower().split())
    m = re.fullmatch(r"(\d+)\s*(m|h|d)", s)
    if m:
        seconds = int(m.group(1)) * {"m": 60, "h": 3600, "d": 86400}[m.group(2)]
        if seconds < MIN_INTERVAL:
            return None, "أقل مدة 15 دقيقة (كل تشغيل يكلّف استدعاءات Claude)"
        return {"kind": "every", "seconds": seconds}, None
    parts = s.split(" ")
    if parts[0] == "daily" and len(parts) == 2 and _hm(parts[1]):
        return {"kind": "daily", "hm": list(_hm(parts[1]))}, None
    if parts[0] == "weekly" and len(parts) == 3 and parts[1] in _DAYS and _hm(parts[2]):
        return {"kind": "weekly", "day": _DAYS[parts[1]], "hm": list(_hm(parts[2]))}, None
    if parts[0] == "once" and len(parts) == 3:
        try:
            at = datetime.strptime(f"{parts[1]} {parts[2]}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None, "التاريخ لازم يكون بصيغة once 2026-10-20 09:00"
        return {"kind": "once", "at": at.timestamp()}, None
    return None, "صيغة غير مفهومة — أمثلة: 2h ، daily 09:00 ، weekly sun 09:00 ، once 2026-10-20 09:00"


def next_after(spec: dict, now: float) -> float | None:
    if spec["kind"] == "every":
        return now + spec["seconds"]
    if spec["kind"] == "once":
        return spec["at"] if spec["at"] > now else None
    base = datetime.fromtimestamp(now)
    h, m = spec["hm"]
    candidate = base.replace(hour=h, minute=m, second=0, microsecond=0)
    if spec["kind"] == "daily":
        if candidate.timestamp() <= now:
            candidate += timedelta(days=1)
        return candidate.timestamp()
    candidate += timedelta(days=(spec["day"] - candidate.weekday()) % 7)
    if candidate.timestamp() <= now:
        candidate += timedelta(days=7)
    return candidate.timestamp()


def validate(job: dict, valid_targets) -> tuple[dict | None, str | None]:
    if not isinstance(job, dict):
        return None, "المهمة لازم تكون كائن"
    spec, error = parse(job.get("schedule", ""))
    if error:
        return None, error
    prompt = str(job.get("prompt", "")).strip()
    target = str(job.get("target") or "ceo").strip()
    if not prompt or len(prompt) > 2000:
        return None, "نص المهمة فاضي أو طويل"
    if target not in valid_targets:
        return None, f"جهة تنفيذ غير معروفة: {target}"
    return {"schedule": " ".join(str(job["schedule"]).split()), "spec": spec, "prompt": prompt, "target": target,
            "title": str(job.get("title") or prompt[:40]).strip()[:60]}, None


def add(job: dict, valid_targets, created_by: str = "owner", now: float | None = None) -> dict:
    cleaned, error = validate(job, valid_targets)
    if error:
        raise ValueError(error)
    now = now or time.time()
    first = next_after(cleaned["spec"], now)
    if first is None:
        raise ValueError("الموعد فات")
    with _lock:
        jobs = _load()
        if len(jobs) >= MAX_JOBS:
            raise ValueError(f"الحد الأقصى {MAX_JOBS} مهمة مجدولة")
        record = {"id": uuid.uuid4().hex[:10], **cleaned, "enabled": True, "created_by": created_by,
                  "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "next_run": first,
                  "last_run": None, "last_result": None, "runs": 0}
        jobs.append(record)
        _save(jobs)
    return record


def remove(job_id: str) -> bool:
    with _lock:
        jobs = _load()
        kept = [j for j in jobs if j["id"] != job_id]
        if len(kept) == len(jobs):
            return False
        _save(kept)
    return True


def set_enabled(job_id: str, enabled: bool, now: float | None = None) -> bool:
    with _lock:
        jobs = _load()
        for j in jobs:
            if j["id"] == job_id:
                j["enabled"] = bool(enabled)
                if enabled and not j.get("next_run"):
                    j["next_run"] = next_after(j["spec"], now or time.time())
                _save(jobs)
                return True
    return False


def list_jobs() -> list[dict]:
    return _load()


def _claim_due(now: float, only_id: str | None = None) -> list[dict]:
    """يحجز المهام المستحقة ويحسب موعدها الجاي قبل التشغيل — نفس المهمة
    ما تشتغل مرتين لو جت دورة ثانية أثناء تشغيلها."""
    with _lock:
        jobs = _load()
        due = []
        for j in jobs:
            if only_id is not None:
                if j["id"] != only_id:
                    continue
            elif not j["enabled"] or not j.get("next_run") or j["next_run"] > now:
                continue
            due.append(dict(j))
            if only_id is None:
                j["next_run"] = next_after(j["spec"], now)
                if j["next_run"] is None:
                    j["enabled"] = False
        _save(jobs)
    return due


def _record(job_id: str, text: str, now: float) -> None:
    with _lock:
        jobs = _load()
        for j in jobs:
            if j["id"] == job_id:
                j["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
                j["last_result"] = text[:1500]
                j["runs"] = j.get("runs", 0) + 1
        _save(jobs)


def run_due(execute, notify=None, now: float | None = None, only_id: str | None = None) -> list[dict]:
    """execute(job) -> نص النتيجة. notify(job, text) اختياري (مثلاً تيليجرام)."""
    now = now or time.time()
    results = []
    for job in _claim_due(now, only_id):
        try:
            text = execute(job)
        except Exception as e:  # noqa: BLE001 — فشل مهمة ما يوقف الباقي، ينسجل بصدق
            text = f"فشل التشغيل: {type(e).__name__}: {e}"
        _record(job["id"], text, now)
        if notify:
            try:
                notify(job, text)
            except Exception:  # noqa: BLE001
                pass
        results.append({"id": job["id"], "title": job["title"], "result": text})
    return results


def start_background(execute, notify=None, interval: float = 30) -> threading.Thread:
    def loop():
        while True:
            try:
                run_due(execute, notify)
            except Exception as e:  # noqa: BLE001
                print(f"[scheduler] خطأ: {e}")
            time.sleep(interval)
    t = threading.Thread(target=loop, daemon=True, name="os4-scheduler")
    t.start()
    return t
