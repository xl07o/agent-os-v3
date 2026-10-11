"""
مهارات إجرائية بأسلوب Hermes Agent — "ذاكرة إجرائية": طريقة مجرّبة لنوع
مهمة يتكرر. كل مهارة ملف SKILL.md بصيغة Agent Skills المفتوحة (نفس صيغة
مهارات Claude وagentskills.io):

    data/agent_skills/<name>/SKILL.md
    ---
    name: stock-daily-report
    description: Use when ... (سطر يحدد متى تُستخدم)
    ---
    الخطوات والقواعد...

الوكيل يصنعها بنفسه بعد مهمة متعددة الخطوات نجحت، ويعدّلها (patch) لما
تطلع ناقصة أو قديمة — عبر reflect.py. أنت تشوفها وتحذفها من اللوحة.

بدل ما تدخل كل المهارات كاملة بكل طلب (فلوس)، يدخل نص أقرب مهارتين للمهمة
كاملاً + وصف سطر واحد لباقي المهارات — نفس فكرة "الكشف التدريجي" بـHermes.
"""

import os
import re
import shutil
import threading
import time

from . import agent_memory, textnorm

_DIR = os.path.join(os.path.dirname(__file__), "data", "agent_skills")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_DESC_MAX = 1024
_BODY_MAX = 20000
_lock = threading.Lock()


def _words(text: str) -> set[str]:
    return textnorm.words(text)


def _path(name: str) -> str:
    return os.path.join(_DIR, name, "SKILL.md")


def _render(name: str, description: str, body: str) -> str:
    desc = description.replace("\n", " ").strip()
    return f"---\nname: {name}\ndescription: {desc}\n---\n\n{body.strip()}\n"


def _parse(text: str) -> tuple[dict, str]:
    match = re.match(r"\A---\n(.*?)\n---\n?(.*)\Z", text, re.S)
    if not match:
        return {}, text
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, match.group(2).strip()


def _scan_text(text: str) -> str | None:
    if agent_memory._BLOCKED.search(text or ""):
        return "المهارة فيها نص يشبه أمراً لتجاوز القواعد أو سراً — مرفوضة"
    return None


def _validate(name: str, description: str, body: str) -> str | None:
    if not NAME_RE.match(name or ""):
        return f"اسم مهارة غير صالح: {name!r} (حروف إنجليزية صغيرة وأرقام و - فقط)"
    if not description or len(description) > _DESC_MAX:
        return "الوصف فاضي أو طويل"
    if not body or len(body) > _BODY_MAX:
        return "نص المهارة فاضي أو أطول من المسموح"
    return _scan_text(description + "\n" + body)


def get(name: str) -> dict | None:
    if not NAME_RE.match(name or "") or not os.path.exists(_path(name)):
        return None
    with open(_path(name), encoding="utf-8") as f:
        meta, body = _parse(f.read())
    return {"name": name, "description": meta.get("description", ""), "body": body,
            "updated_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(_path(name))))}


def list_skills() -> list[dict]:
    if not os.path.isdir(_DIR):
        return []
    out = []
    for name in sorted(os.listdir(_DIR)):
        skill = get(name)
        if skill:
            out.append({k: skill[k] for k in ("name", "description", "updated_at")})
    return out


def create(name: str, description: str, body: str) -> dict:
    error = _validate(name, description, body)
    if error:
        return {"ok": False, "error": error}
    with _lock:
        if os.path.exists(_path(name)):
            return {"ok": False, "error": f"المهارة {name} موجودة — استخدم patch"}
        os.makedirs(os.path.dirname(_path(name)), exist_ok=True)
        with open(_path(name), "w", encoding="utf-8") as f:
            f.write(_render(name, description, body))
    return {"ok": True, "name": name, "action": "create"}


def patch(name: str, old_text: str, new_text: str) -> dict:
    """استبدال محدد داخل المهارة — مو إعادة كتابة كاملة."""
    with _lock:
        skill = get(name)
        if not skill:
            return {"ok": False, "error": f"مهارة غير موجودة: {name}"}
        if not old_text or skill["body"].count(old_text) != 1:
            return {"ok": False, "error": "old_text لازم يطابق موضع واحد بالضبط بنص المهارة"}
        body = skill["body"].replace(old_text, new_text or "", 1)
        error = _validate(name, skill["description"], body)
        if error:
            return {"ok": False, "error": error}
        with open(_path(name), "w", encoding="utf-8") as f:
            f.write(_render(name, skill["description"], body))
    return {"ok": True, "name": name, "action": "patch"}


def delete(name: str) -> bool:
    if not NAME_RE.match(name or "") or not os.path.exists(_path(name)):
        return False
    with _lock:
        shutil.rmtree(os.path.dirname(_path(name)))
    return True


def relevant(task: str, limit: int = 2) -> list[dict]:
    words = _words(task)
    scored = []
    for meta in list_skills():
        skill = get(meta["name"])
        overlap = len(words & _words(f"{skill['name'].replace('-', ' ')} {skill['description']} {skill['body']}"))
        if overlap >= 2:
            scored.append((overlap, skill))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:limit]]


def prompt_block(task: str) -> str:
    chosen = relevant(task)
    others = [s for s in list_skills() if s["name"] not in {c["name"] for c in chosen}]
    if not chosen and not others:
        return ""
    parts = []
    if chosen:
        parts.append("مهارات مجرّبة تناسب هذي المهمة (اتبعها لو تنطبق):\n" + "\n\n".join(
            f"### {s['name']}\n{s['body'][:3000]}" for s in chosen))
    if others:
        listing = "\n".join(f"- {s['name']}: {s['description'][:150]}" for s in others[:20])
        parts.append("مهارات أخرى عندك:\n" + listing)
    return "\n\n".join(parts)
