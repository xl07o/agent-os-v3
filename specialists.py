"""
specialists.py - مكتبة شخصيات خبراء جاهزة (v1.0)
=====================================================
282 شخصية subagent من مشروع The Agency (MIT، انظر specialists/README.md)
تحت specialists/*.md. يفهرسها هذا الملف ويتيح استعارة نص أي شخصية كـ
system prompt مؤقت لسؤال محدد — عبر brain.py (نفس راوتر المزودين
المستخدم بكل مكان آخر بالمشروع، بما فيه الفشل التلقائي بين المزودين).

لا تُحمَّل كل الشخصيات بالذاكرة دفعة وحدة؛ الفهرس فقط (اسم + وصف) يُبنى
مرة وحدة ويُخزَّن مؤقتاً، وجسم الشخصية الكامل يُقرأ من القرص فقط عند
الاستخدام الفعلي.
"""

import os

from memory_bank import _similarity

SPECIALISTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "specialists")

_index_cache = None


def _parse_frontmatter(path):
    """يقرأ كتلة frontmatter البسيطة (key: value) بدون الحاجة لمكتبة yaml."""
    meta = {}
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines or lines[0].strip() != "---":
        return meta, "".join(lines)

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return meta, "".join(lines)

    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"').strip("'")

    body = "".join(lines[end + 1:]).strip()
    return meta, body


def _build_index():
    index = []
    if not os.path.isdir(SPECIALISTS_DIR):
        return index
    for fname in sorted(os.listdir(SPECIALISTS_DIR)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(SPECIALISTS_DIR, fname)
        meta, _ = _parse_frontmatter(path)
        if not meta.get("name"):
            continue
        index.append({
            "id": fname[:-3],
            "file": path,
            "name": meta.get("name", fname[:-3]),
            "description": meta.get("description", ""),
            "emoji": meta.get("emoji", ""),
        })
    return index


def list_specialists() -> list:
    """فهرس خفيف (اسم + وصف فقط، بدون محتوى الشخصية) لكل الخبراء المتاحين."""
    global _index_cache
    if _index_cache is None:
        _index_cache = _build_index()
    return _index_cache


def find(query: str, limit: int = 5) -> list:
    """أقرب الشخصيات تطابقاً للاستعلام (بالاسم أو الوصف)، الأعلى تشابهاً أولاً."""
    query = (query or "").strip()
    if not query:
        return []
    scored = []
    for item in list_specialists():
        score = max(
            _similarity(query, item["name"]),
            _similarity(query, item["description"]) * 0.8,
        )
        if query.lower() in item["name"].lower():
            score = max(score, 0.9)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


def get_persona_prompt(specialist_id_or_name: str):
    """يرجع (meta, system_prompt) لأقرب شخصية مطابقة، أو None إن ما لقى شي."""
    matches = find(specialist_id_or_name, limit=1)
    if not matches:
        for item in list_specialists():
            if item["id"] == specialist_id_or_name:
                matches = [item]
                break
    if not matches:
        return None
    meta = matches[0]
    _, body = _parse_frontmatter(meta["file"])
    return meta, body


def ask(specialist_id_or_name: str, question: str) -> dict:
    """يسأل شخصية خبير محدّدة سؤالاً، مستعيراً نصها كـ system prompt مؤقت
    لجلسة brain.Brain واحدة (نفس راوتر المزودين متعدد المصادر المستخدم
    بكل المشروع). لا يحتفظ بالشخصية بعد انتهاء السؤال."""
    found = get_persona_prompt(specialist_id_or_name)
    if not found:
        suggestions = find(specialist_id_or_name, limit=5)
        return {
            "ok": False,
            "error": f"ما لقيت شخصية مطابقة لـ '{specialist_id_or_name}'",
            "suggestions": [s["name"] for s in suggestions],
        }

    meta, persona_prompt = found
    import brain
    session = brain.Brain(persona_prompt)
    answer, engine = session.ask(question)
    return {"ok": True, "specialist": meta["name"], "engine": engine, "answer": answer}


if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        print(json.dumps([{"id": i["id"], "name": i["name"]} for i in list_specialists()],
                         ensure_ascii=False, indent=2))
    elif len(sys.argv) > 2 and sys.argv[1] == "find":
        print(json.dumps(find(" ".join(sys.argv[2:])), ensure_ascii=False, indent=2))
    elif len(sys.argv) > 3 and sys.argv[1] == "ask":
        print(json.dumps(ask(sys.argv[2], " ".join(sys.argv[3:])), ensure_ascii=False, indent=2))
    else:
        print("الاستخدام: python specialists.py list | find <كلمة> | ask <اسم> <سؤال>")
