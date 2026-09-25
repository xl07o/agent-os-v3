"""
memory_bank.py - نظام الذاكرة الخارق (v2.0)
============================================
ذاكرة متجهة (RAG-like) تسمح للوكيل:
  - تخزين المفاهيم والمعلومات المهمة
  - البحث فيها بأسلوب semantic (بدون embeddings معقدة)
  - استرجاع السياق المناسب للمهمة
  - إدارة فعالة للذاكرة (تنظيف، ضغط، أولويات)
"""

import datetime
import hashlib
import json
import os
import re
import time

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
MEMORY_FILE = os.path.join(MEMORY_DIR, "memory_bank.json")
INDEX_FILE = os.path.join(MEMORY_DIR, "memory_index.json")

os.makedirs(MEMORY_DIR, exist_ok=True)

MAX_MEMORY_ITEMS = 500
MAX_CONTEXT_RESULTS = 5
DEFAULT_TTL = 30  # أيام


# ===== تخزين أساسي =====

def _load_bank():
    """تحميل بنك الذاكرة."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"items": [], "version": 2}


def _atomic_write_json(path, data):
    """كتابة JSON ذرية: يُكتب للملف المؤقت ثم يُستبدل — لا ملف مكسور عند انقطاع."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _save_bank(bank):
    """حفظ بنك الذاكرة (كتابة ذرية)."""
    _atomic_write_json(MEMORY_FILE, bank)


def _load_index():
    """تحميل فهرس البحث."""
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_index(idx):
    """حفظ فهرس البحث (كتابة ذرية)."""
    _atomic_write_json(INDEX_FILE, idx)


# ===== أدوات البحث البسيطة (keyword + weighted) =====

def _tokenize(text):
    """تقسيم النص إلى كلمات مع إزالة الكلمات الشائعة."""
    arabic = re.findall(r'[\u0600-\u06FF]{2,}', text.lower())
    english = re.findall(r'[a-z]{2,}', text.lower())
    return arabic + english


_STOP_WORDS_AR = {
    "في", "على", "من", "إلى", "الذي", "التي", "هذا", "هذه", "ذلك", "هناك",
    "مع", "عن", "كان", "كانت", "ما", "لا", "نعم", "أنت", "أنا", "هو", "هي",
    "هل", "لماذا", "كيف", "ماذا", "أين", "متى", "ثم", "عند", "حتى", "كل",
    "بعض", "يوم", "عام", "وقت", "شأن", "غاية",
}

_STOP_WORDS_EN = {
    "the", "and", "or", "for", "with", "from", "this", "that", "these",
    "those", "was", "were", "are", "is", "be", "been", "have", "has",
    "had", "will", "would", "can", "could", "should", "may", "might",
    "about", "what", "which", "who", "whom", "when", "where", "why",
    "how", "not", "but", "are", "has", "have", "one", "two", "very",
}


def _clean_tokens(tokens):
    """إزالة الكلمات الشائعة."""
    return [t for t in tokens if t not in _STOP_WORDS_AR and t not in _STOP_WORDS_EN]


def _compute_tf(text):
    """حساب term frequency."""
    tokens = _clean_tokens(_tokenize(text))
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    total = max(len(tokens), 1)
    return {k: v / total for k, v in tf.items()}


def _similarity(text_a, text_b):
    """تشابه بسيط (cosine similarity على TF vectors)."""
    tf_a = _compute_tf(text_a)
    tf_b = _compute_tf(text_b)

    common = set(tf_a.keys()) & set(tf_b.keys())
    if not common:
        return 0.0

    dot = sum(tf_a[k] * tf_b[k] for k in common)
    norm_a = sum(v ** 2 for v in tf_a.values()) ** 0.5
    norm_b = sum(v ** 2 for v in tf_b.values()) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ===== واجهة الذاكرة =====

def remember(key, content, importance=1.0, tags=None):
    """تخزين معلومة في الذاكرة.

    Args:
        key: مفتاح المعلومة
        content: المحتوى الكامل
        importance: أهمية (0-1)
        tags: وسوم للتصنيف
    """
    bank = _load_bank()
    now = datetime.datetime.now().isoformat()

    # فحص إذا كانت المعلومة موجودة مسبقاً
    for item in bank["items"]:
        if item["key"].lower() == key.lower():
            # تحديث الموجود
            item["content"] = content
            item["importance"] = max(item.get("importance", 0), importance)
            item["updated_at"] = now
            if tags:
                item["tags"] = list(set(item.get("tags", []) + tags))
            _save_bank(bank)
            return {"status": "updated", "key": key}

    # إضافة جديدة
    item = {
        "id": hashlib.md5(key.encode()).hexdigest()[:10],
        "key": key,
        "content": content,
        "importance": importance,
        "tags": tags or [],
        "created_at": now,
        "updated_at": now,
        "access_count": 0,
    }
    bank["items"].append(item)

    # تقليم إذا تجاوزنا الحد
    if len(bank["items"]) > MAX_MEMORY_ITEMS:
        # احذف الأقل أهمية والأقدم
        bank["items"].sort(key=lambda x: (x.get("importance", 0), x.get("access_count", 0)))
        bank["items"] = bank["items"][-MAX_MEMORY_ITEMS:]

    _save_bank(bank)
    return {"status": "stored", "id": item["id"], "key": key}


def recall(query, max_results=MAX_CONTEXT_RESULTS, min_score=0.05):
    """البحث في الذاكرة واسترجاع الأكثر صلة.

    Args:
        query: نص البحث
        max_results: عدد النتائج
        min_score: الحد الأدنى للتشابه
    """
    bank = _load_bank()
    results = []

    for item in bank["items"]:
        # تشابه مع المفتاح والمحتوى
        score_key = _similarity(query, item["key"]) * 2.0
        score_content = _similarity(query, item["content"])
        score = max(score_key, score_content)

        # مكافأة للوسوم المطابقة
        if item.get("tags"):
            tag_score = max(_similarity(query, tag) for tag in item["tags"])
            score = max(score, tag_score)

        # عامل الأهمية
        score *= (0.5 + item.get("importance", 1.0) * 0.5)

        results.append({
            "key": item["key"],
            "content": item["content"],
            "score": round(score, 4),
            "importance": item.get("importance", 1.0),
            "tags": item.get("tags", []),
            "created": item.get("created_at", ""),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    top = [r for r in results if r["score"] >= min_score][:max_results]

    # تحديث access count
    if top:
        bank = _load_bank()
        top_ids = {r["key"] for r in top}
        for item in bank["items"]:
            if item["key"] in top_ids:
                item["access_count"] = item.get("access_count", 0) + 1
        _save_bank(bank)

    return top


def recall_as_context(query):
    """استرجاع الذاكرة كسياق جاهز للـ LLM."""
    results = recall(query)
    if not results:
        return ""

    lines = ["## الذاكرة ذات الصلة", ""]
    for r in results[:3]:
        lines.append(f"---\n**{r['key']}** ({r['score']})")
        lines.append(r["content"][:500])
        lines.append("")
    return "\n".join(lines)


def forget(key=None, all_items=False):
    """حذف معلومة من الذاكرة."""
    bank = _load_bank()
    if all_items:
        bank["items"] = []
        _save_bank(bank)
        return {"deleted": "all", "count": 0}

    if key:
        before = len(bank["items"])
        bank["items"] = [i for i in bank["items"] if i["key"] != key]
        _save_bank(bank)
        return {"deleted": key, "count": before - len(bank["items"])}

    return {"deleted": None, "count": 0}


def stats():
    """إحصائيات الذاكرة."""
    bank = _load_bank()
    total = len(bank["items"])
    total_chars = sum(len(i["content"]) for i in bank["items"])
    avg_importance = sum(i.get("importance", 0) for i in bank["items"]) / max(total, 1)
    avg_access = sum(i.get("access_count", 0) for i in bank["items"]) / max(total, 1)

    return {
        "total_items": total,
        "total_chars": total_chars,
        "avg_importance": round(avg_importance, 2),
        "avg_access": round(avg_access, 2),
        "unique_tags": len(set(t for i in bank["items"] for t in i.get("tags", []))),
    }


def prune_old(days=30):
    """تنظيف الذاكرة من العناصر القديمة وغير المهمة."""
    bank = _load_bank()
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    cutoff_ts = cutoff.isoformat()

    before = len(bank["items"])
    old_items = [
        i for i in bank["items"]
        if i.get("importance", 0) < 0.3
        and i.get("updated_at", "") < cutoff_ts
        and i.get("access_count", 0) < 2
    ]
    # مطابقة بالمعرّف (id) وليس بالمحتوى الكامل — حتى لا يُحذف عنصر متطابق بالصدفة
    old_ids = {i.get("id") or i.get("key") for i in old_items}
    bank["items"] = [i for i in bank["items"] if (i.get("id") or i.get("key")) not in old_ids]
    _save_bank(bank)
    return {"removed": before - len(bank["items"]), "before": before, "after": len(bank["items"])}


if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if action == "stats":
        print(json.dumps(stats(), ensure_ascii=False, indent=2))
    elif action == "prune":
        print(json.dumps(prune_old(), ensure_ascii=False, indent=2))
    elif action == "clear":
        print(json.dumps(forget(all_items=True), ensure_ascii=False, indent=2))
    elif action == "search" and len(sys.argv) > 2:
        results = recall(" ".join(sys.argv[2:]))
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print("استخدام: stats | prune | clear | search <query>")