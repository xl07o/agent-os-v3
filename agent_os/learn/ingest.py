"""
ingest.py - مُستوعِب المعرفة من أي مصدر عام (البند 1)
=====================================================
«يتعلم من كل مكان حرفياً»: نص خام، صفحة ويب، مستودع GitHub، أو نص فيديو
يوتيوب → يُقسَّم، يُخزَّن في الذاكرة طويلة الأمد بنَسَبه (المصدر + الثقة +
الصلاحية)، ويصبح تجربة قابلة للاستدعاء بالتشابه. لا مفاتيح مدفوعة.

النواة (ingest_text) تعمل وتُختبر بلا شبكة. الجالبات (url/github/youtube)
طبقة رقيقة فوقها تعيد استخدام حماية SSRF في webtools.fetch_text.

  ingest_text(source, text, kind, confidence) -> يخزّن ويرجع ملخّصاً
  ingest_url(url)                              -> يجلب صفحة ثم يستوعبها
  ingest_github(repo)                          -> يجلب README المستودع
  ingest_youtube(url_or_id)                    -> نص الفيديو إن توفّر
  learn_query(query, max_sources)              -> يبحث ويستوعب الأعلى
"""

import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_os import _common as C

MIN_USEFUL_CHARS = 40   # أقل من هذا = لا معرفة حقيقية، لا نخزّنه (البند 5)


def _clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _key(source, text):
    h = hashlib.md5((_clean(text)[:200]).encode("utf-8")).hexdigest()[:8]
    return f"ext:{re.sub(r'[^A-Za-z0-9_.:/-]', '_', str(source))[:60]}:{h}"


def ingest_text(source, text, kind="fact", confidence=0.6, topic=None):
    """النواة: يخزّن نصاً خارجياً في الذاكرة بنَسَبه. لا يخزّن الفارغ/الأخطاء."""
    text = _clean(text)
    if not text or text.startswith("(") or len(text) < MIN_USEFUL_CHARS:
        return {"ok": False, "reason": "نص فارغ أو قصير جداً أو رسالة خطأ", "chars": len(text)}

    key = _key(source, text)
    excerpt = text[:1500]

    # 1) نَسَب المعرفة — مصدر + ثقة + صلاحية زمنية.
    try:
        from agent_os.memory import provenance
        provenance.record(key, excerpt, source=str(source), confidence=confidence, kind=kind)
    except Exception:
        pass

    # 2) تجربة قابلة للاستدعاء بالتشابه لاحقاً.
    try:
        from agent_os.memory import contextual_memory as cm
        cm.save_experience(
            task=topic or f"معرفة من {source}",
            approach="ingest",
            tools=[str(source)],
            problem="",
            solution=excerpt,
            outcome="learned",
        )
    except Exception:
        pass

    C.log(f"📥 استوعب {len(text)} حرفاً من {source}")
    return {"ok": True, "chars": len(text), "key": key, "source": str(source)}


def ingest_url(url, kind="fact"):
    """يجلب نص صفحة (بحماية SSRF من webtools) ثم يستوعبه."""
    import webtools
    text = webtools.fetch_text(url, save=False, max_length=8000)
    return ingest_text(url, text, kind=kind, topic=url)


def ingest_github(repo, kind="skill"):
    """يستوعب README مستودع GitHub (owner/repo) من raw.githubusercontent."""
    import webtools
    repo = repo.strip().rstrip("/")
    m = re.search(r"github\.com/([^/]+/[^/]+)", repo)
    if m:
        repo = m.group(1)
    if repo.count("/") != 1:
        return {"ok": False, "reason": "صيغة المستودع يجب أن تكون owner/repo"}
    for branch in ("main", "master"):
        for name in ("README.md", "readme.md", "README.rst"):
            url = f"https://raw.githubusercontent.com/{repo}/{branch}/{name}"
            text = webtools.fetch_text(url, save=False, max_length=8000)
            if text and not text.startswith("(") and len(text) >= MIN_USEFUL_CHARS:
                return ingest_text(f"github:{repo}", text, kind=kind, topic=f"مستودع {repo}")
    return {"ok": False, "reason": f"تعذّر جلب README لـ {repo}"}


def ingest_youtube(url_or_id, kind="fact"):
    """يستوعب نص فيديو يوتيوب إن توفّرت المكتبة، وإلا يخبر بصراحة."""
    vid = url_or_id.strip()
    m = re.search(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})", vid)
    if m:
        vid = m.group(1)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception:
        return {"ok": False, "reason": "youtube_transcript_api غير مثبّتة — pip install youtube-transcript-api"}
    try:
        parts = YouTubeTranscriptApi.get_transcript(vid, languages=["ar", "en"])
        text = " ".join(p.get("text", "") for p in parts)
        return ingest_text(f"youtube:{vid}", text, kind=kind, topic=f"فيديو {vid}")
    except Exception as e:
        return {"ok": False, "reason": f"تعذّر جلب النص: {str(e)[:120]}"}


def learn_query(query, max_sources=3):
    """يبحث عن موضوع ويستوعب أعلى النتائج — «تعلّم شيئاً لا تعرفه»."""
    import webtools
    results = webtools.search(query, save=False, num=max_sources * 2)
    ingested, tried = [], 0
    for r in (results.get("results", []) if isinstance(results, dict) else []):
        url = r.get("url") if isinstance(r, dict) else None
        if not url:
            continue
        tried += 1
        res = ingest_url(url, kind="fact")
        if res.get("ok"):
            ingested.append(url)
        if len(ingested) >= max_sources:
            break
    return {"ok": bool(ingested), "query": query, "ingested": ingested, "tried": tried}


if __name__ == "__main__":
    import json
    if len(sys.argv) >= 3 and sys.argv[1] == "url":
        print(json.dumps(ingest_url(sys.argv[2]), ensure_ascii=False, indent=2))
    elif len(sys.argv) >= 3 and sys.argv[1] == "github":
        print(json.dumps(ingest_github(sys.argv[2]), ensure_ascii=False, indent=2))
    elif len(sys.argv) >= 3 and sys.argv[1] == "learn":
        print(json.dumps(learn_query(" ".join(sys.argv[2:])), ensure_ascii=False, indent=2))
    else:
        print("الاستعمال: python agent_os/learn/ingest.py [url <رابط> | github <owner/repo> | learn <موضوع>]")
