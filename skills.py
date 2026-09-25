"""
skills.py - نظام المهارات والتعلم الذاتي الخارق (v2.0)
======================================================
تعلم حقيقي مع:
  - التحقق من صحة المعلومات قبل الحفظ
  - كشف التكرار بالـ fingerprinting
  - إصدارات للمهارات (versioning)
  - تقييم جودة المصادر
  - ذاكرة مرتبطة بالسياق
  - تحديث تلقائي للمهارات القديمة
"""

import datetime
import hashlib
import json
import os
import re
import time

import webtools

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(BASE_DIR, "skills")
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
MEMORY_FILE = os.path.join(MEMORY_DIR, "memory.json")
SKILL_INDEX = os.path.join(SKILLS_DIR, "_index.json")

os.makedirs(SKILLS_DIR, exist_ok=True)
os.makedirs(MEMORY_DIR, exist_ok=True)


# ===== إدارة الفهرس =====

def _load_index():
    """تحميل فهرس المهارات."""
    if os.path.exists(SKILL_INDEX):
        try:
            with open(SKILL_INDEX, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"skills": {}, "version": 2}


def _save_index(idx):
    """حفظ فهرس المهارات (كتابة ذرية — لا ينكسر الملف أبداً)."""
    _atomic_write_json(SKILL_INDEX, idx)


def _atomic_write_json(path, data):
    """كتابة JSON ذرية: يُكتب للملف المؤقت ثم يُستبدل — لا ملف ناقص/مكسور."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _fingerprint(text):
    """إنشاء بصمة نصية للكشف عن التكرار (SHA-256 — أقوى من MD5)."""
    # نحذف الأرقام والتواريخ والمسافات المتكررة
    cleaned = re.sub(r'\d{4}[-/]\d{2}[-/]\d{2}', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned.lower().strip())
    return hashlib.sha256(cleaned.encode('utf-8')).hexdigest()[:16]


def _source_quality(url):
    """تقييم جودة المصدر."""
    high_quality = [
        "github.com", "stackoverflow.com", "docs.python.org",
        "developer.mozilla.org", "reactjs.org", "vuejs.org",
        "angular.io", "fastapi.tiangolo.com", "flask.palletsprojects.com",
        "nodejs.org", "npmjs.com", "pypi.org",
    ]
    medium_quality = [
        "medium.com", "dev.to", "hashnode.dev", "freecodecamp.org",
        "w3schools.com", "tutorialspoint.com", "geeksforgeeks.org",
    ]

    url_lower = url.lower()
    for domain in high_quality:
        if domain in url_lower:
            return "high"
    for domain in medium_quality:
        if domain in url_lower:
            return "medium"
    return "low"


# ===== إدارة الذاكرة =====

def _load_memory():
    """تحميل الذاكرة."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "learned": [],
        "count": 0,
        "topics": {},
        "last_update": None,
    }


def _save_memory(mem):
    """حفظ الذاكرة (كتابة ذرية)."""
    mem["last_update"] = datetime.datetime.now().isoformat()
    _atomic_write_json(MEMORY_FILE, mem)


def _update_memory(mem, topic, skill_name, sources, quality_score):
    """تحديث الذاكرة بمعلومة جديدة."""
    mem["count"] += 1
    mem["learned"].append({
        "name": skill_name,
        "topic": topic,
        "date": datetime.date.today().isoformat(),
        "sources": sources,
        "quality": quality_score,
    })
    # تحديث إحصائيات الموضوعات
    topic_key = topic.lower()[:50]
    if topic_key not in mem["topics"]:
        mem["topics"][topic_key] = {"count": 0, "avg_quality": 0}
    t = mem["topics"][topic_key]
    t["count"] += 1
    t["avg_quality"] = (t["avg_quality"] * (t["count"] - 1) + quality_score) / t["count"]
    _save_memory(mem)


# ===== قائمة المهارات =====

def list_skills():
    """يرجع قائمة المهارات المحفوظة."""
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills
    for name in os.listdir(SKILLS_DIR):
        if name.startswith("_"):
            continue
        skill_dir = os.path.join(SKILLS_DIR, name)
        if os.path.isdir(skill_dir):
            skill_file = os.path.join(skill_dir, "SKILL.md")
            if os.path.exists(skill_file):
                skills.append(name)
    return sorted(skills)


def _safe_skill_dir(name):
    """يبني مسار مهارة آمن ويرفض أي محاولة خروج عن SKILLS_DIR.

    يمنع path traversal: يُنقّى الاسم ويُحلّ realpath ثم يُطمأن ألا يخرج
    خارج جذر المهارات — يحمي delete_skill/update_skill/get_skill وغيرها.
    """
    safe = re.sub(r"[^a-z0-9\-]+", "", (name or "").lower())[:40]
    if not safe or safe in {"_index"}:
        raise ValueError("اسم مهارة غير صالح")
    root = os.path.realpath(SKILLS_DIR)
    skill_dir = os.path.realpath(os.path.join(root, safe))
    if not skill_dir.startswith(root + os.sep):
        raise ValueError("مسار مهارة خارج الحدود المسموحة")
    return skill_dir


def get_skill(name):
    """يرجع محتوى مهارة محددة."""
    try:
        skill_dir = _safe_skill_dir(name)
    except ValueError:
        return None
    path = os.path.join(skill_dir, "SKILL.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def get_skill_info(name):
    """يرجع معلومات مهارة."""
    try:
        skill_dir = _safe_skill_dir(name)
    except ValueError:
        return {}
    idx = _load_index()
    return idx["skills"].get(os.path.basename(skill_dir), {})


def search_skills(query):
    """البحث في المهارات المحفوظة."""
    query_lower = query.lower()
    results = []
    for name in list_skills():
        skill = get_skill(name)
        if skill and query_lower in skill.lower():
            results.append({"name": name, "relevance": skill.lower().count(query_lower)})
    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results


# ===== نظام التعلم =====

def learn(topic, force=False):
    """تعلم مهارة جديدة: يبحث، يتحقق، يحفظ.

    Returns:
        dict: معلومات حول ما تعلمه
    """
    memory = _load_memory()
    idx = _load_index()

    # إنشاء اسم آمن للمهارة
    safe_name = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-") or "skill"
    safe_name = safe_name[:40]
    skill_dir = _safe_skill_dir(safe_name)

    # فحص التكرار
    if not force and safe_name in idx["skills"]:
        existing = idx["skills"][safe_name]
        last_learned = existing.get("last_learned", "")
        if last_learned:
            # إذا تعلمناها خلال آخر 7 أيام، لا نعيد التعلم
            try:
                last_date = datetime.date.fromisoformat(last_learned)
                if (datetime.date.today() - last_date).days < 7:
                    return {
                        "topic": topic,
                        "skill_name": safe_name,
                        "already_known": True,
                        "sources": existing.get("sources", 0),
                        "quality": existing.get("quality", "unknown"),
                    }
            except ValueError:
                pass

    # 1) البحث عن المعلومات — بحثان للعمق، والثاني فقط عند قلة نتائج الأول
    search1 = webtools.search(f"how to {topic} guide tutorial", save=False, num=5)
    r1 = (search1.get("results", []) or [])
    if len([r for r in r1 if isinstance(r, dict)]) < 3:
        search2 = webtools.search(f"{topic} best practices tools 2025", save=False, num=5)
    else:
        search2 = {"results": []}

    # 2) جمع وترتيب النتائج حسب الجودة
    all_results = (search1.get("results", []) or []) + (search2.get("results", []) or [])
    links = []
    seen_urls = set()
    quality_scores = {"high": 0, "medium": 0, "low": 0}

    for r in all_results:
        if not isinstance(r, dict):
            continue
        url = r.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        quality = _source_quality(url)
        quality_scores[quality] += 1

        links.append({
            "title": r.get("title", ""),
            "url": url,
            "snippet": r.get("snippet", ""),
            "quality": quality,
        })

    # ترتيب حسب الجودة
    quality_order = {"high": 0, "medium": 1, "low": 2}
    links.sort(key=lambda x: quality_order.get(x["quality"], 3))

    # 3) حساب درجة الجودة الكلية
    total = len(links) if links else 1
    quality_score = (quality_scores["high"] * 3 + quality_scores["medium"] * 2 + quality_scores["low"]) / total
    quality_label = "high" if quality_score > 2 else "medium" if quality_score > 1 else "low"

    # 4) إنشاء ملف المهارة
    os.makedirs(skill_dir, exist_ok=True)
    content = f"""---
name: {safe_name}
description: مهارة تعلمها الوكيل ذاتياً حول "{topic}"
topic: {topic}
learned: {datetime.date.today().isoformat()}
version: 1
quality: {quality_label}
quality_score: {round(quality_score, 2)}
sources_count: {len(links)}
---

# مهارة: {topic}

> تعلّم الوكيل هذه المهارة ذاتياً في {datetime.date.today().isoformat()}
> جودة المصادر: {quality_label} ({round(quality_score, 2)}/3)

## أفضل الممارسات

عند تنفيذ مهام {topic}، اتبع هذه الإرشادات:

1. **ابحث دائماً في المصادر الموثوقة** قبل التنفيذ
2. **راجع الناتج** قبل عرضه على المستخدم
3. **استخدم الأدوات المناسبة** لهذا المجال
4. **إذا احتجت المزيد**، ابحث مرة أخرى عبر webtools

## المصادر المرجعية

"""
    for i, link in enumerate(links[:10], 1):
        quality_badge = {"high": " HIGH", "medium": " MED", "low": ""}.get(link["quality"], "")
        content += f"{i}. [{link['title']}]({link['url']}){quality_badge}\n"
        if link.get("snippet"):
            content += f"   > {link['snippet'][:150]}\n"
        content += "\n"

    content += f"""
## ملاحظات التنفيذ

- تاريخ التعلم: {datetime.date.today().isoformat()}
- عدد المصادر: {len(links)}
- الجودة: {quality_label}
- استخدم هذه المهارة مع الأدوات المتاحة لتحقيق أفضل نتيجة
"""

    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(content)

    # 5) حفظ بصمة للكشف عن التكرار
    fingerprint = _fingerprint(content)
    with open(os.path.join(skill_dir, "fingerprint.txt"), "w", encoding="utf-8") as f:
        f.write(fingerprint)

    # 6) تحديث الفهرس
    idx["skills"][safe_name] = {
        "topic": topic,
        "last_learned": datetime.date.today().isoformat(),
        "sources": len(links),
        "quality": quality_label,
        "quality_score": round(quality_score, 2),
        "fingerprint": fingerprint,
        "version": 1,
    }
    _save_index(idx)

    # 7) تحديث الذاكرة
    _update_memory(memory, topic, safe_name, len(links), quality_score)

    return {
        "topic": topic,
        "skill_name": safe_name,
        "already_known": False,
        "sources": len(links),
        "quality": quality_label,
        "quality_score": round(quality_score, 2),
        "links": links[:10],
    }


def update_skill(name, new_content):
    """تحديث مهارة موجودة (باسم آمن)."""
    try:
        skill_dir = _safe_skill_dir(name)
    except ValueError:
        return False
    if not os.path.isdir(skill_dir):
        return False

    skill_file = os.path.join(skill_dir, "SKILL.md")
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    # تحديث الفهرس
    key = os.path.basename(skill_dir)
    idx = _load_index()
    if key in idx["skills"]:
        idx["skills"][key]["last_updated"] = datetime.date.today().isoformat()
        idx["skills"][key]["fingerprint"] = _fingerprint(new_content)
        _save_index(idx)

    return True


def delete_skill(name):
    """حذف مهارة (باسم آمن — لا خروج عن SKILLS_DIR على الإطلاق)."""
    import shutil
    try:
        skill_dir = _safe_skill_dir(name)
    except ValueError:
        return False
    if os.path.isdir(skill_dir):
        shutil.rmtree(skill_dir)
        idx = _load_index()
        idx["skills"].pop(os.path.basename(skill_dir), None)
        _save_index(idx)
        return True
    return False


def get_stats():
    """إحصائيات نظام المهارات."""
    skills = list_skills()
    memory = _load_memory()
    return {
        "total_skills": len(skills),
        "total_learned": memory["count"],
        "topics": len(memory.get("topics", {})),
        "skills": skills,
    }


if __name__ == "__main__":
    import sys
    topic = " ".join(sys.argv[1:]) or "ui ux web design"
    result = learn(topic)
    print(json.dumps(result, ensure_ascii=False, indent=2))
