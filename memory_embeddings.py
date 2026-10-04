"""
memory_embeddings.py - طبقة تشابه دلالي اختيارية فوق memory_bank (v1.0)
==========================================================================
ترقية اختيارية لـ memory_bank: تشابه دلالي حقيقي عبر sentence-transformers
بدل مطابقة TF النصية البسيطة — لكن فقط عند توفر المكتبة فعلياً وبتفعيل
صريح من المستخدم (AGENT_MEMORY_EMBEDDINGS=1). ليست مفعّلة افتراضياً: تحميل
نموذج embeddings يحتاج اتصال إنترنت لتنزيله أول مرة، وتثبيت مكتبة إضافية
ثقيلة نسبياً، وهذا قرار يأخذه المستخدم بنفسه صراحة، لا افتراضاً خفياً.

التثبيت الفعلي (على جهاز المستخدم):
  pip install sentence-transformers
  export AGENT_MEMORY_EMBEDDINGS=1
"""

import os

_ENABLED = os.getenv("AGENT_MEMORY_EMBEDDINGS", "0") in ("1", "true", "yes")
_model = None


def available() -> bool:
    """متاحة فقط إن فعّلها المستخدم صراحة والمكتبة مثبّتة فعلاً."""
    if not _ENABLED:
        return False
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(os.getenv("AGENT_EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    return _model


def similarity(text_a: str, text_b: str):
    """يرجع تشابه دلالي بين 0 و1، أو None إن كانت الطبقة غير مفعّلة أو
    غير متاحة — عندها يرجع memory_bank تلقائياً لمطابقة TF كافتراضي آمن."""
    if not available():
        return None
    try:
        model = _get_model()
        import numpy as np
        emb = model.encode([text_a, text_b])
        a, b = emb[0], emb[1]
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)
    except Exception:
        return None


def status() -> dict:
    return {
        "enabled_by_user": _ENABLED,
        "library_installed": available(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(status(), ensure_ascii=False, indent=2))
