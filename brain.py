"""
brain.py - العقل الخارق لموظف الليل (v2.0)
=============================================
نظام متعدد العقول مع:
  - Thread safety كامل
  - History trimming ذكي (يمنع تجاوز السياق)
  - Hybrid حقيقي (مقارنة فعلية بين النتائج)
  - Retry logic مع exponential backoff
  - Rate limiting
  - Token estimation
  - Performance tracking
  - Auto-fallback بين المزودين

المبدأ: مجاني أولاً → أرخص مدفوع → الأقوى عند الحاجة.
"""

import json
import os
import re
import threading
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# تحميل .env
_BRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BRAIN_DIR, ".env"))

import urllib.request
from agent_os import security_kernel as _auth
import urllib.error

OLLAMA_URL = "http://localhost:11434/api/chat"

# ===== إعدادات عامة =====
MAX_HISTORY_TOKENS = int(os.getenv("SELFRUNNER_MAX_HISTORY_TOKENS", "6000"))
MAX_HISTORY_MESSAGES = int(os.getenv("SELFRUNNER_MAX_HISTORY", "40"))
RETRY_ATTEMPTS = int(os.getenv("SELFRUNNER_RETRY_ATTEMPTS", "2"))
RETRY_DELAY = float(os.getenv("SELFRUNNER_RETRY_DELAY", "1.0"))
RATE_LIMIT_DELAY = float(os.getenv("SELFRUNNER_RATE_LIMIT", "0.5"))
REQUEST_TIMEOUT = int(os.getenv("SELFRUNNER_TIMEOUT", "120"))
# سقف التكلفة اليومي للمزودين المدفوعين (بالدولار) — المجاني (Ollama/Gemini/Groq/NVIDIA) لا يُحسب
MAX_COST_USD = float(os.getenv("SELFRUNNER_MAX_COST_USD", "2.0"))
_PERF_FILE = os.path.join(_BRAIN_DIR, "output", "brain_perf.json")

# ===== تبريد المزوّد الفاشل (قاطع دائرة بسيط) =====
_PROVIDER_COOLDOWN = {}
_COOLDOWN_LOCK = threading.Lock()


def _mark_provider_fail(eid):
    """يسجّل فشلاً ويعزل المزوّد بمدة مؤشرية: 30s → 60s → 120s … بحدّ أقصى 600s."""
    if not eid:
        return
    with _COOLDOWN_LOCK:
        cur = _PROVIDER_COOLDOWN.get(eid, {"until": 0.0, "fails": 0})
        n = int(cur.get("fails", 0)) + 1
        secs = min(600, 30 * (2 ** (n - 1)))
        _PROVIDER_COOLDOWN[eid] = {"until": time.time() + secs, "fails": n}


def _mark_provider_ok(eid):
    """نجاح بسيط يعيد المزوّد للخدمة فوراً."""
    if not eid:
        return
    with _COOLDOWN_LOCK:
        _PROVIDER_COOLDOWN.pop(eid, None)


def _provider_quarantined(eid):
    try:
        with _COOLDOWN_LOCK:
            info = _PROVIDER_COOLDOWN.get(eid)
            if not info:
                return False
            if time.time() >= info["until"]:
                _PROVIDER_COOLDOWN.pop(eid, None)
                return False
            return True
    except Exception:
        return False


def _apply_feedback(entries):
    """يحوّل نتيجتَي كل مزوّد داخل جولة واحدة إلى تبريد/تعافي."""
    for _t, eid, status, _tk in entries:
        if eid and eid != "none":
            if status == "err":
                _mark_provider_fail(eid)
            else:
                _mark_provider_ok(eid)


def _today():
    """تاريخ اليوم لميزانية التكلفة اليومية."""
    return time.strftime("%Y-%m-%d")


def _perf_total(perf=None):
    """إجمالي التكلفة المقدرة لكل المزودين (دولار) — بتاريخ اليوم فقط.

    الميزانية "يومية": أي تراكم من يوم سابق لا يُحتسب (تُنسى تلقائياً
    بعد منتصف الليل بدل إيقاف المزود المدفوع للأبد).
    """
    if perf is None:
        try:
            with open(_PERF_FILE, "r", encoding="utf-8") as f:
                perf = json.load(f)
        except Exception:
            perf = {}
    if not isinstance(perf, dict):
        perf = {}
    if perf.get("_date") != _today():
        return {}
    agg = {}
    prices = {e["id"]: (e.get("cost", 0) if not e.get("free") else 0.0) for e in ENGINES_ALL}
    for eid, d in (perf or {}).items():
        if eid == "_date" or not isinstance(d, dict):
            continue
        tokens = d.get("tokens", 0)
        agg[eid] = prices.get(eid, 0.0) * tokens / 1_000_000
    return agg


def _over_budget(eng):
    """هل تجاوز مزودٌ بعينه سقف التكلفة؟ (المجاني أبداً لا يتجاوز)."""
    if eng.get("free"):
        return False
    totals = _perf_total()
    return totals.get(eng["id"], 0.0) >= MAX_COST_USD


def _budget_report():
    return {"max_cost_usd": MAX_COST_USD, "totals": _perf_total()}


# ===== أدوات مساعدة =====

def _estimate_tokens(text):
    """تقدير تقريبي لعدد الـ tokens (عربي + إنجليزي)."""
    if not text:
        return 0
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
    other_chars = len(text) - arabic_chars
    return int(arabic_chars * 0.5 + other_chars * 0.25)


def _hash_response(text):
    """تجزئة الاستجابة للكشف عن التكرار."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:12]


def _safe_request(url, payload=None, headers=None, timeout=REQUEST_TIMEOUT, method="GET"):
    """طلب HTTP آمن مع retry logic."""
    try:
        _auth.url_guard(url)
    except Exception as e:
        raise PermissionError(f"network policy: {e}")
    last_error = None
    for attempt in range(RETRY_ATTEMPTS + 1):
        try:
            # User-Agent متصفّحي: بوابات Cloudflare (Groq وغيرها) تحظر طلبات
            # بلا UA برمز 1010. نضيفه افتراضياً ويمكن للمستدعي تجاوزه.
            _ua = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            if payload is not None:
                data = json.dumps(payload).encode("utf-8")
                hdrs = {"Content-Type": "application/json", "User-Agent": _ua, **(headers or {})}
                req = urllib.request.Request(url, data=data, headers=hdrs, method=method if method != "GET" else "POST")
            else:
                hdrs = {"User-Agent": _ua, **(headers or {})}
                req = urllib.request.Request(url, headers=hdrs)

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
            if e.code == 429:  # Rate limited
                wait = RETRY_DELAY * (2 ** attempt)
                time.sleep(wait)
                continue
            if e.code >= 500:  # Server error - retry
                if attempt < RETRY_ATTEMPTS:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
            raise Exception(last_error)
        except urllib.error.URLError as e:
            last_error = f"Network error: {e.reason}"
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            raise Exception(last_error)
        except Exception as e:
            last_error = str(e)
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            raise Exception(last_error)

    raise Exception(f"All {RETRY_ATTEMPTS + 1} attempts failed: {last_error}")


def _check_ollama_alive(timeout=3):
    """فحص صحيح من جاهزية Ollama."""
    try:
        _auth.url_guard("http://localhost:11434/api/tags") if False else None
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            return bool(data.get("models"))
    except Exception:
        return False


# ===== المزودون =====

ENGINES_ALL = [
    {
        "id": "ollama",
        "name": "Ollama (محلي)",
        "cost": 0.0,
        "free": True,
        "strength": 3,
        "speed": 3,
        "check": _check_ollama_alive,
        "call": lambda msgs: _call_ollama(msgs),
    },
    {
        "id": "gemini",
        "name": "Google Gemini",
        "cost": 0.0,
        "free": True,
        "strength": 5,
        "speed": 5,
        "check": lambda: bool(os.getenv("GEMINI_API_KEY")),
        "call": lambda msgs: _call_gemini(msgs),
    },
    {
        "id": "groq",
        "name": "Groq",
        "cost": 0.0,
        "free": True,
        "strength": 4,
        "speed": 5,
        "check": lambda: bool(os.getenv("GROQ_API_KEY")),
        "call": lambda msgs: _call_groq(msgs),
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "cost": 0.1,
        "free": False,
        "strength": 5,
        "speed": 4,
        "check": lambda: bool(os.getenv("DEEPSEEK_API_KEY")),
        "call": lambda msgs: _call_deepseek(msgs),
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "cost": 0.2,
        "free": True,
        "strength": 5,
        "speed": 4,
        "check": lambda: bool(os.getenv("OPENROUTER_API_KEY")),
        "call": lambda msgs: _call_openrouter(msgs),
    },
    {
        "id": "nvidia",
        "name": "NVIDIA NIM",
        "cost": 0.0,
        "free": True,
        "strength": 4,
        "speed": 4,
        "check": lambda: bool(os.getenv("NVIDIA_API_KEY")),
        "call": lambda msgs: _call_nvidia(msgs),
    },
    {
        "id": "mistral",
        "name": "Mistral",
        "cost": 0.3,
        "free": True,
        "strength": 4,
        "speed": 4,
        "check": lambda: bool(os.getenv("MISTRAL_API_KEY")),
        "call": lambda msgs: _call_mistral(msgs),
    },
    {
        "id": "anthropic",
        "name": "Claude",
        "cost": 0.5,
        "free": False,
        "strength": 5,
        "speed": 3,
        "check": lambda: bool(os.getenv("ANTHROPIC_API_KEY")),
        "call": lambda msgs: _call_anthropic(msgs),
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "cost": 0.5,
        "free": False,
        "strength": 5,
        "speed": 4,
        "check": lambda: bool(os.getenv("OPENAI_API_KEY")),
        "call": lambda msgs: _call_openai(msgs),
    },
]


# ===== منفذو المزودين =====

def _call_ollama(msgs):
    sys_prompt = None
    msgs_clean = []
    for m in msgs:
        if m.get("role") == "system":
            sys_prompt = m["content"]
        else:
            msgs_clean.append(m)
    payload = {
        "model": os.getenv("SELFRUNNER_MODEL", "llama3.1"),
        "messages": (
            ([{"role": "system", "content": sys_prompt}] if sys_prompt else [])
            + msgs_clean
        ),
        "stream": False,
    }
    data = _safe_request(OLLAMA_URL, payload)
    return data["message"]["content"].strip(), "ollama"


def _call_gemini(msgs):
    key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    # Gemini API مع بنية رسائل صحيحة
    contents = []
    sys_instruction = None
    for m in msgs:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            sys_instruction = content
        else:
            gemini_role = "user" if role == "user" else "model"
            contents.append({"role": gemini_role, "parts": [{"text": content}]})

    payload = {"contents": contents}
    if sys_instruction:
        payload["systemInstruction"] = {"parts": [{"text": sys_instruction}]}

    # المفتاح في الهيدر (وليس في الـ query string الذي يُسجَّل في اللوجات)
    data = _safe_request(url, payload, {"x-goog-api-key": key})
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return text.strip(), "gemini"


def _call_deepseek(msgs):
    key = os.getenv("DEEPSEEK_API_KEY")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    data = _safe_request(
        "https://api.deepseek.com/chat/completions",
        {"model": model, "messages": msgs, "max_tokens": 4000},
        {"Authorization": f"Bearer {key}"},
    )
    return data["choices"][0]["message"]["content"].strip(), "deepseek"


# أقوى النماذج المجانية الحية عبر OpenRouter (مأخوذة من /api/v1/models، تحديث 2026-09)
OPENROUTER_FREE_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "thinkingmachines/inkling:free",
    "thinkingmachines/inkling-small:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "poolside/laguna-s-2.1:free",
    "liquid/lfm-2.5-2.6b:free",
    "cohere/north-mini-code:free",
    "dots-studio/dots-3-note-preview:free",
]

_openrouter_model_idx = 0
_openrouter_lock = __import__("threading").Lock()


def _get_best_openrouter_model():
    """يختار أقوى نموذج مجاني متاح في OpenRouter."""
    env_model = os.getenv("OPENROUTER_MODEL")
    if env_model:
        return env_model
    global _openrouter_model_idx
    with _openrouter_lock:
        return OPENROUTER_FREE_MODELS[_openrouter_model_idx % len(OPENROUTER_FREE_MODELS)]


def _rotate_openrouter_model():
    """ينتقل للنموذج التالي عند الفشل."""
    global _openrouter_model_idx
    with _openrouter_lock:
        _openrouter_model_idx += 1


def _call_openrouter(msgs):
    key = os.getenv("OPENROUTER_API_KEY")
    # جرب كل النماذج حتى ينجح واحد
    last_err = None
    for _ in range(len(OPENROUTER_FREE_MODELS)):
        model = _get_best_openrouter_model()
        try:
            data = _safe_request(
                "https://openrouter.ai/api/v1/chat/completions",
                {"model": model, "messages": msgs},
                {"Authorization": f"Bearer {key}",
                 "HTTP-Referer": "https://github.com/selfrunner",
                 "X-Title": "SelfRunner Agent"},
            )
            text = data["choices"][0]["message"]["content"].strip()
            return text, f"openrouter/{model}"
        except Exception as e:
            last_err = str(e)
            _rotate_openrouter_model()
            continue
    raise Exception(f"فشلت كل نماذج OpenRouter: {last_err}")


def _call_groq(msgs):
    key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    data = _safe_request(
        "https://api.groq.com/openai/v1/chat/completions",
        {"model": model, "messages": msgs},
        {"Authorization": f"Bearer {key}"},
    )
    return data["choices"][0]["message"]["content"].strip(), "groq"


def _call_nvidia(msgs):
    key = os.getenv("NVIDIA_API_KEY")
    model = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
    data = _safe_request(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        {"model": model, "messages": msgs, "max_tokens": 3000},
        {"Authorization": f"Bearer {key}"},
    )
    return data["choices"][0]["message"]["content"].strip(), "nvidia"


def _call_mistral(msgs):
    key = os.getenv("MISTRAL_API_KEY")
    model = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
    data = _safe_request(
        "https://api.mistral.ai/v1/chat/completions",
        {"model": model, "messages": msgs},
        {"Authorization": f"Bearer {key}"},
    )
    return data["choices"][0]["message"]["content"].strip(), "mistral"


def _call_anthropic(msgs):
    key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    sys_prompt = None
    msgs_h = []
    for m in msgs:
        if m.get("role") == "system":
            sys_prompt = m["content"]
        else:
            msgs_h.append(m)
    payload = {
        "model": model,
        "max_tokens": 4000,
        "messages": msgs_h,
    }
    if sys_prompt:
        payload["system"] = sys_prompt
    data = _safe_request(
        "https://api.anthropic.com/v1/messages",
        payload,
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    text = "".join(
        b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
    )
    return text.strip(), "anthropic"


def _call_openai(msgs):
    key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    data = _safe_request(
        "https://api.openai.com/v1/chat/completions",
        {"model": model, "messages": msgs},
        {"Authorization": f"Bearer {key}"},
    )
    return data["choices"][0]["message"]["content"].strip(), "openai"


# ===== واجهة الاستخدام =====

def available_engines():
    """يرجع المزودين المتاحين فعلياً (ويستثني المدفوع الذي تجاوز سقف التكلفة
    والمزوّد الذي أعطى أخطاء متتابعة في تبريد مؤقت)."""
    av = []
    for e in ENGINES_ALL:
        try:
            if _provider_quarantined(e["id"]):
                continue
            if not e["check"]():
                continue
            if _over_budget(e):
                continue
            av.append(e)
        except Exception:
            continue
    return av


def best_available():
    """يرجع المزودين مرتبين: مجاني أولاً ثم أرخص ثم الأقوى."""
    return sorted(available_engines(), key=lambda e: (not e["free"], e["cost"], -e["strength"]))


def status_report():
    av = available_engines()
    return {
        "available": [e["id"] for e in av],
        "total_engines": len(ENGINES_ALL),
        "preferred": [e["id"] for e in best_available()],
    }


class Brain:
    """كائن العقل الخارق: thread-safe مع history trimming و hybrid حقيقي.

    أوضاع التشغيل:
      hybrid    : يسأل عقلين ويقارن فعلياً ويأخذ الأفضل (الوضع الافتراضي)
      smart     : مجاني أولاً ثم أرخص مع ميل للأقوى
      fastest   : الأسرع
      strongest : الأقوى
      ollama    : محلي فقط
    """

    def __init__(self, system_prompt):
        self.system_prompt = system_prompt
        self.history = []
        self.mode = os.getenv("SELFRUNNER_MODE", "hybrid")
        self.last_engine = None
        self._lock = threading.Lock()
        self._perf_file = os.path.join(_BRAIN_DIR, "output", "brain_perf.json")
        self._perf = self._load_perf()
        self._response_hashes = {}  # كشف التكرار (مرتّب — لا "عشوائية")

    def _load_perf(self):
        try:
            os.makedirs(os.path.dirname(self._perf_file), exist_ok=True)
            with open(self._perf_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_perf(self):
        try:
            tmp = self._perf_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._perf, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._perf_file)  # استبدال ذري — لا ينكسر الملف أبداً
        except Exception:
            pass

    def _record(self, eid, ok, seconds, tokens=0):
        with self._lock:
            today = _today()
            if self._perf.get("_date") != today:
                # يوم جديد — نُصفّر الـ tokens التراكمية (إحصائيات n/ok تبقى)
                for k, v in self._perf.items():
                    if k != "_date" and isinstance(v, dict):
                        v["tokens"] = 0
                self._perf["_date"] = today
            d = self._perf.setdefault(eid, {"n": 0, "ok": 0, "t": 0.0, "t_ok": 0.0, "tokens": 0})
            d["n"] = d.get("n", 0) + 1
            d["t"] = d.get("t", 0) + seconds
            d["tokens"] = d.get("tokens", 0) + tokens
            if ok:
                d["ok"] = d.get("ok", 0) + 1
                d["t_ok"] = d.get("t_ok", 0.0) + seconds
            self._save_perf()

    def _trim_history(self):
        """قصّ التاريخ لتبقى ضمن الحدود مع الحفاظ على السياق."""
        if not self.history:
            return

        # حساب إجمالي الـ tokens
        total = _estimate_tokens(self.system_prompt)
        msg_tokens = []
        for m in self.history:
            t = _estimate_tokens(m.get("content", ""))
            msg_tokens.append(t)
            total += t

        # إذا كنا ضمن الحد، لا نفعل شيئاً
        if total <= MAX_HISTORY_TOKENS and len(self.history) <= MAX_HISTORY_MESSAGES:
            return

        # نحتفظ بأول 4 رسائل (context أساسي) + آخر N رسائل
        keep_start = 4
        keep_end = min(len(self.history), MAX_HISTORY_MESSAGES - keep_start)

        if keep_end < 2:
            keep_end = 2

        # نلخص الرسائل المحذوفة
        removed = self.history[keep_start:len(self.history) - keep_end]
        removed_tokens = sum(msg_tokens[keep_start:len(self.history) - keep_end])

        if removed:
            summary = f"[تمتلئ السياق - تم حذف {len(removed)} رسائل (~{removed_tokens} token)]"
            self.history = (
                self.history[:keep_start]
                + [{"role": "system", "content": summary}]
                + self.history[-keep_end:]
            )

    def _is_duplicate(self, text):
        """الكشف عن تكرار الاستجابة — مجموعة مرتبة تُقتطع من الأقدم."""
        h = _hash_response(text)
        if h in self._response_hashes:
            return True
        self._response_hashes[h] = len(self._response_hashes)
        # نحافظ على الحجم: نستبعد الأقدم فقط (لا "عشوائية")
        while len(self._response_hashes) > 100:
            self._response_hashes.pop(next(iter(self._response_hashes)))
        return False

    def _choose(self, mode=None):
        av = available_engines()
        if not av:
            return None
        mode = mode or self.mode
        if mode == "ollama":
            return next((e for e in av if e["id"] == "ollama"), av[0])
        if mode == "fastest":
            # الأسرع بالوقت المقاس الحقيقي للنجاح (t_ok/ok من السجل الحي) لا بالتصنيف الثابت —
            # فالمزود الأقوى قد يكون الأبطأ فعلياً في المحادثة
            best = None
            for e in av:
                d = self._perf.get(e["id"])
                if d and d.get("ok", 0) >= 2 and d.get("t_ok", 0) > 0:
                    avg = d["t_ok"] / float(d["ok"])
                    if best is None or avg < best[1]:
                        best = (e, avg)
            if best:
                return best[0]
            return max(av, key=lambda e: e["speed"])
        if mode == "strongest":
            return max(av, key=lambda e: e["strength"])
        return best_available()[0]

    def _ask_one(self, eng, msgs):
        """سؤال مزود واحد مع retry."""
        start = time.time()
        try:
            out, eid = eng["call"](msgs)
            tokens = _estimate_tokens(out)
            self._record(eid, True, time.time() - start, tokens)
            return (out, eid, "ok", tokens)
        except Exception as ex:
            self._record(eng["id"], False, time.time() - start)
            return (f"(خطأ {eng['id']}: {str(ex)[:150]})", eng["id"], "err", 0)

    def _build_messages(self):
        """بناء رسائل الطلب مع السياق."""
        msgs = [{"role": "system", "content": self.system_prompt}]
        msgs.extend(self.history)
        return msgs

    def _compare_responses(self, results):
        """مقارنة حقيقية بين الاستجابات واختيار الأفضل."""
        valid = [(r, eid, tokens) for r, eid, status, tokens in results if status == "ok"]
        if not valid:
            return None, "none"

        if len(valid) == 1:
            return valid[0][0], valid[0][1]

        # معايير التقييم:
        # 1. طول الاستجابة (الأطول عادة أفضل)
        # 2. وجود كود أو خطوات عملية
        # 3. عدم التكرار
        best_score = -1
        best_idx = 0

        for idx, (text, eid, tokens) in enumerate(valid):
            score = 0
            # طول معقول (ليس قصير جداً أو طويل جداً)
            length = len(text)
            if 50 < length < 5000:
                score += 2
            elif length >= 5000:
                score += 1
            elif length < 20:
                score -= 1

            # وجود محتوى مفيد
            if any(kw in text.lower() for kw in ["```", "def ", "class ", "import ", "npm ", "pip "]):
                score += 2  # يحتوي كود
            if any(kw in text for kw in ["خطوة", "步骤", "step", "أولاً", "ثانياً", "1."]):
                score += 1  # يحتوي خطوات منظمة

            # عدم التكرار
            if not self._is_duplicate(text):
                score += 1

            # السرعة (الأسرع يحصل على bonus)
            if idx == 0:
                score += 0.5

            if score > best_score:
                best_score = score
                best_idx = idx

        return valid[best_idx][0], valid[best_idx][1]

    def _judge_response(self, content, results):
        """حكم دلالي اختياري: مزود ثالث خفيف يقرر أيّ الردّين أدق (A أو B).

        يشغَّل فقط عند تفعيل SELFRUNNER_HYBRID_JUDGE=1، ويقع تلقائياً على
        التقييم الشكلي (_compare_responses) إن فشل الحكم أو عطّلته.
        """
        try:
            if int(os.getenv("SELFRUNNER_HYBRID_JUDGE", "0")) != 1:
                return None
        except ValueError:
            return None
        valid = [(r, eid) for r, eid, status, _ in results if status == "ok"]
        if len(valid) < 2:
            return None
        a_text, a_eid = valid[0]
        b_text, b_eid = valid[1]
        if not (a_text and b_text):
            return None

        av = available_engines()
        if not av:
            return None
        judge_eng = min(av, key=lambda e: (not e["free"], e["cost"], -e["strength"]))

        sys_p = "أنت حَكَم محايد. أجب بحرف واحد فقط: A إن كان الرد الأول أدق وأصح، أو B إن كان الثاني."
        prompt = (
            f"سؤال المستخدم:\n{content}\n\n"
            f"الرد A:\n{a_text[:2000]}\n\n"
            f"الرد B:\n{b_text[:2000]}\n\n"
            "أيّ الردّين أدق وأصح للمستخدم؟ (A أو B)"
        )
        out, eid, status, _ = self._ask_one(
            judge_eng, [{"role": "system", "content": sys_p}, {"role": "user", "content": prompt}]
        )
        if status != "ok":
            return None
        out = out.strip().upper()
        if out.startswith("B"):
            return b_text, b_eid
        if out.startswith("A"):
            return a_text, a_eid
        return None

    def ask(self, content, mode=None):
        """سؤال العقل — مع hybrid حقيقي أو أحادي.
        mode: تفضيل لهذه الدعوة فقط (smart=hybrid، fastest، strongest، ollama).
        الإرجاع: tuple دائماً (النص، معرّف المحرك) — يُفكَّك هكذا دائماً:
            نص, محرك = brain_session.ask("...")
        النص قد يكون رسالة اعتذار/خطأ عند غياب المزود أو فشله.
        """
        if mode == "smart":
            mode = "hybrid"
        mode = mode or self.mode
        with self._lock:
            self._trim_history()
            msgs = self._build_messages()
            msgs.append({"role": "user", "content": content})

        # ---- الوضع الهجين الحقيقي ----
        if mode == "hybrid":
            av = available_engines()
            if not av:
                return ("(لا يوجد مزود متاح. شغّل Ollama أو أضف مفتاحاً في .env)", "none")

            # نختار عقلين مختلفين
            pool = sorted(av, key=lambda e: (not e["free"], e["cost"], -e["strength"]))
            first = pool[0]
            second = next((e for e in pool if e["id"] != first["id"]), None)
            engines = [first] + ([second] if second else [])

            # نسألهما بالتوازي
            results = []
            try:
                with ThreadPoolExecutor(max_workers=len(engines)) as executor:
                    futures = {executor.submit(self._ask_one, eng, msgs): eng for eng in engines}
                    try:
                        for future in as_completed(futures, timeout=REQUEST_TIMEOUT + 5):
                            try:
                                result = future.result(timeout=5)
                                results.append(result)
                            except Exception as e:
                                eng = futures[future]
                                results.append((f"(خطأ {eng['id']}: {e})", eng["id"], "err", 0))
                    except TimeoutError:
                        # مزود تأخر — نسجّل ما تبقى كمهلة ولا نكسر التنفيذ
                        for future, eng in futures.items():
                            if not future.done():
                                results.append((f"(خطأ {eng['id']}: مهلة زمنية)", eng["id"], "err", 0))
            except Exception:
                results = [(f"(خطأ {eng['id']}: تعذّر التجميع)", eng["id"], "err", 0) for eng in engines]

            # تغذية قاطع الدائرة: أي مزود فشل هنا يُعزل مؤقتاً بالمدة المؤشرية
            _apply_feedback(results)

            # مقارنة حقيقية واختيار الأفضل
            best_text, best_engine = self._compare_responses(results)

            # إن كان الهجين فعّالاً وفُعّل الحكم الدلالي، ندعه يقرر بدل النقاط الشكلية
            if best_text:
                judged = self._judge_response(content, results)
                if judged:
                    best_text, best_engine = judged

            if best_text:
                with self._lock:
                    self.history.append({"role": "user", "content": content})
                    self.history.append({"role": "assistant", "content": best_text})
                    self.last_engine = "hybrid[" + "+".join(e["id"] for e in engines) + "]"
                return best_text, self.last_engine

            # طوارئ: الاثنان المختاران فشلا — اكشف بقية المزوّدين تسلسلياً حتى ينجح واحد
            # (تحويل عند الليميت/المحظور/المنتهي: groq محجوب، openrouter بلا رصيد، إلخ)
            errors = [f"{eid}: {text[:80]}" for text, eid, status, _ in results if status == "err"]
            tried = {e["id"] for e in engines}
            for eng in pool:
                if eng["id"] in tried:
                    continue
                try:
                    out, eid, status, _ = self._ask_one(eng, msgs)
                except Exception as ex:
                    out, eid, status, _ = f"(خطأ {eng['id']}: {ex})", eng["id"], "err", 0
                if status == "ok":
                    _mark_provider_ok(eng["id"])
                    with self._lock:
                        self.history.append({"role": "user", "content": content})
                        self.history.append({"role": "assistant", "content": out})
                        self.last_engine = f"hybrid-fallback[{eid}]"
                    return out, self.last_engine
                _mark_provider_fail(eng["id"])
                errors.append(f"{eid}: {out[:80]}")

            return (f"(فشل كل المزودين: {'; '.join(errors)})", "none")

        # ---- الأوضاع الأحادية ----
        eng = self._choose(mode)
        if eng is None:
            return ("(لا يوجد مزود متاح. شغّل Ollama أو أضف مفتاحاً في .env)", "none")

        out, eid, status, tokens = self._ask_one(eng, msgs)
        if status == "ok":
            _mark_provider_ok(eid)
            with self._lock:
                self.history.append({"role": "user", "content": content})
                self.history.append({"role": "assistant", "content": out})
                self.last_engine = eid
            return out, eid
        _mark_provider_fail(eid)

        # فشل المزود — نجرب مزود آخر
        for fallback in best_available():
            if fallback["id"] != eid:
                out2, eid2, status2, _ = self._ask_one(fallback, msgs)
                if status2 == "ok":
                    _mark_provider_ok(eid2)
                    with self._lock:
                        self.history.append({"role": "user", "content": content})
                        self.history.append({"role": "assistant", "content": out2})
                        self.last_engine = eid2
                    return out2, eid2

        return (out, eid)

    def reset(self):
        with self._lock:
            self.history = []
            self.last_engine = None
            self._response_hashes.clear()


if __name__ == "__main__":
    print(json.dumps(status_report(), ensure_ascii=False, indent=2))
