"""
webtools.py - أدوات البحث والإبحار الخارقة (v2.0)
==================================================
بحث حقيقي عبر DuckDuckGo API + جلب صفحات مع retry + rate limiting.

الميزات:
  - بحث عبر DuckDuckGo API (وليس HTML scraping)
  - Retry logic مع exponential backoff
  - Rate limiting ذكي
  - Cache بسيط لتقليل الطلبات المتكررة
  - جلب نصوص الصفحات مع تنظيف ذكي
  - حفظ تلقائي للنتائج
"""

import datetime
import hashlib
import html
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import threading
import time
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEARCH_DIR = os.path.join(BASE_DIR, "output", "searches")
os.makedirs(SEARCH_DIR, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ===== Rate Limiting (قفل — آمن للخيوط المتوازية) =====
_last_request_time = 0
_MIN_REQUEST_INTERVAL = 1.0  # ثانية واحدة على الأقل بين الطلبات
_rate_lock = threading.Lock()

# ===== Cache (قفل — لا سباق قراءة/كتابة من خيوط متعددة) =====
_cache = {}
_cache_lock = threading.Lock()
_CACHE_MAX = 100
_CACHE_TTL = 3600  # ساعة واحدة


def _rate_limit():
    """التحكم في سرعة الطلبات — بشكل متسلسل آمن بين الخيوط."""
    global _last_request_time
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        _last_request_time = time.time()


def _read_limited(resp, max_bytes=5 * 1024 * 1024):
    """قراءة الاستجابة بمقاطع محدودة — يمنع إهلاك الذاكرة بصفحات عملاقة."""
    chunks = []
    total = 0
    while True:
        chunk = resp.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            chunks.append(b"")
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _cache_key(query, engine):
    """مفتاح الـ cache."""
    return hashlib.md5(f"{query}:{engine}".encode()).hexdigest()


def _get_cached(query, engine):
    """الحصول من الـ cache (ضمن قفل)."""
    with _cache_lock:
        key = _cache_key(query, engine)
        if key in _cache:
            entry = _cache[key]
            if time.time() - entry["time"] < _CACHE_TTL:
                return entry["data"]
            del _cache[key]
    return None


def _set_cache(query, engine, data):
    """حفظ في الـ cache (ضمن قفل)."""
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX:
            # نحذف الأقدم
            oldest_key = min(_cache.keys(), key=lambda k: _cache[k]["time"])
            del _cache[oldest_key]
        _cache[_cache_key(query, engine)] = {"data": data, "time": time.time()}


def _resolve_safe_ip(url):
    """يحل DNS مرة واحدة ويتحقق أنه IP عام — يرجع (ok, ip_or_reason).

    مفتاح الدفاع ضد DNS rebinding: التحقق والاتصال يستخدمان نفس نتيجة الحل،
    ولا يعاد حل DNS مرة ثانية عند فتح الاتصال.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False, "رابط غير صالح"

    if parsed.scheme not in ("http", "https"):
        return False, "بروتوكول غير مسموح"

    host = (parsed.hostname or "").lower()
    if not host:
        return False, "لا يوجد host"

    # أسماء محلية مباشرة
    if host in {"localhost", "localhost.localdomain", "metadata.google.internal", "kubernetes.docker.internal"}:
        return False, "host محظور"
    if host.endswith(".local"):
        return False, "نطاق محلي محظور"

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # حلّ DNS بسقف زمني وعبر مصدّر الأمان (المصنَّف: IPv4 عام أو NAT64 لعام).
        try:
            from agent_os import security_kernel as _sk
            host_check = host.rstrip(".")
            ips = _sk._resolve_host_ips(host_check)
            if not ips:
                return False, "تعذر حل DNS"
            # IPv4 أولاً، ثم أي عنوان صنّفه الأمان عاماً (لا يكسر مزوّدي NAT64)
            for candidate in sorted(ips, key=lambda x: (":" in x)):
                if _sk._ip_allowed(candidate) is True:
                    return True, str(candidate)
            return False, "IP غير عام"
        except Exception:
            return False, "تعذر حل DNS"
    except Exception:
        return False, "عناوين غير صالحة"

    if not ip.is_global:
        return False, "IP غير عام"

    return True, str(ip)


def _is_safe_url(url):
    """منع SSRF: http/https عام فقط (نفس نتيجة الحل تُستخدم للاتصال كمان)."""
    ok, _ = _resolve_safe_ip(url)
    return ok


# ===== اتصالات مثبَّتة على IP محلول مسبقاً (لمنع DNS rebinding) =====

class _PinnedHTTPConnection(http.client.HTTPConnection):
    """اتصال http يتصل فعلياً بالـ IP المثبَّت مع إبقاء Host الأصلي."""

    def __init__(self, host, port, pin_ip, **kwargs):
        self._pin_ip = pin_ip
        super().__init__(host, port, **kwargs)

    def connect(self):
        self.sock = socket.create_connection(
            (self._pin_ip, self.port), self.timeout, self.source_address)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """اتصال https: يتصل بالـ IP المثبَّت لكن SNI/الشهادة تبقى على الاسم الأصلي."""

    def __init__(self, host, port, pin_ip, **kwargs):
        self._pin_ip = pin_ip
        super().__init__(host, port, **kwargs)

    def connect(self):
        # نفس سلوك HTTPConnection.connect لكن على الـ IP المثبَّت (لا إعادة حل DNS)
        self.sock = socket.create_connection(
            (self._pin_ip, self.port), self.timeout, self.source_address)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        server_hostname = getattr(self, "_tunnel_host", None) or self.host
        self.sock = self._context.wrap_socket(
            self.sock, server_hostname=server_hostname)


def _fetch(url, timeout=30, headers=None):
    """جلب URL مع retry و rate limiting — اتصالاً مثبَّتاً على IP محلول مرة واحدة.

    لا يعيد حل DNS عند الاتصال (يمنع DNS rebinding تماماً، http و https معاً).
    التحويلات (redirects) تُتبع حتى 3 بقفزات، وكل وجهة جديدة تُفحص وتُثبَّت من جديد.
    """
    ok, ip_or_reason = _resolve_safe_ip(url)
    if not ok:
        return f"(الرابط محظور لأسباب أمان — {ip_or_reason}): {url}"

    _rate_limit()
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    scheme = parsed.scheme
    conn_cls = _PinnedHTTPSConnection if scheme == "https" else _PinnedHTTPConnection

    redirects = 0
    attempts = 0
    last_error = None
    while True:
        conn = None
        try:
            conn = conn_cls(host, port, ip_or_reason, timeout=timeout)
            hdrs = dict(headers or {})
            hdrs.setdefault("User-Agent", USER_AGENT)
            hdrs.setdefault("Accept", "*/*")
            hdrs["Host"] = host if port in (80, 443) else f"{host}:{port}"
            conn.request("GET", path, headers=hdrs)
            resp = conn.getresponse()

            # التحقق من نوع المحتوى قبل تحميل الجسم — لا ننزل ملفات ثنائية/صور
            ctype = (resp.getheader("Content-Type") or "").lower()
            if ctype:
                allowed_ct = (
                    "text", "json", "xml", "javascript", "xhtml",
                    "rss", "atom", "csv", "markdown", "yaml",
                )
                if not any(t in ctype for t in allowed_ct):
                    return f"(النوع غير مدعوم للنص: {ctype}): {url}"
            # قراءة محدودة الحجم — صفحة لا تهلك الذاكرة بلا حدود
            body = _read_limited(resp)

            if resp.status in (301, 302, 303, 307, 308):
                location = resp.getheader("Location")
                if not location:
                    return body.decode("utf-8", errors="replace")
                redirects += 1
                if redirects > 3:
                    return f"(الرابط محظور لأسباب أمان — تحويلات أكثر من المسموح): {url}"
                next_url = urllib.parse.urljoin(url, location)
                nok, nip = _resolve_safe_ip(next_url)
                if not nok:
                    return f"(الرابط محظور لأسباب أمان — وجهة تحويل {nip}): {next_url}"
                url = next_url
                parsed = urllib.parse.urlparse(url)
                host = parsed.hostname
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                scheme = parsed.scheme
                conn_cls = _PinnedHTTPSConnection if scheme == "https" else _PinnedHTTPConnection
                ip_or_reason = nip
                attempts = 0
                continue

            if resp.status in (429,) or resp.status >= 500:
                attempts += 1
                if attempts < 3:
                    time.sleep(2 ** attempts)
                    continue
                return f"(فشل الجلب HTTP {resp.status} بعد المحاولات): {url}"
            if resp.status >= 400:
                return f"(فشل الجلب HTTP {resp.status}): {url}"

            return body.decode("utf-8", errors="replace")
        except (http.client.HTTPException, OSError, ssl.SSLError, ValueError) as e:
            last_error = str(e)
            attempts += 1
            if attempts < 3:
                time.sleep(1 * attempts)
                continue
            raise Exception(f"فشل الجلب ({last_error}): {url}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


def duckduckgo_search(query, num=8):
    """البحث عبر DuckDuckGo (التهجئة الجديدة ddgs أولاً ثم القديمة ثم HTML)."""
    # محاولة استخدام المكتبة (ddgs أولاً — الحزمة أُعيدت تسميتها)
    for maker in (_ddgs_results, _old_ddgs_results):
        try:
            results = maker(query, num)
            if results:
                return results
        except Exception:
            continue

    # Fallback: بحث HTML محسّن
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        content = _fetch(url)
        results = []
        blocks = re.findall(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            content,
            re.DOTALL,
        )
        for href, title, snippet in blocks[:num]:
            title = re.sub(r"<[^>]+>", "", title)
            title = html.unescape(title).strip()
            snippet = re.sub(r"<[^>]+>", "", snippet)
            snippet = html.unescape(snippet).strip()
            m = re.search(r"uddg=([^&]+)", href)
            real = urllib.parse.unquote(m.group(1)) if m else href
            results.append({"title": title, "url": real, "snippet": snippet})
        return results
    except Exception as e:
        return [{"error": str(e)}]


def _ddgs_results(query, num):
    """نتائج عبر الحزمة الجديدة ddgs."""
    from ddgs import DDGS
    results = []
    with DDGS() as d:
        for r in d.text(query, max_results=num):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            })
    return results


def _old_ddgs_results(query, num):
    """نتائج عبر الحزمة القديمة duckduckgo_search."""
    from duckduckgo_search import DDGS
    results = []
    with DDGS() as d:
        for r in d.text(query, max_results=num):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            })
    return results


def brave_search(query, num=8):
    """بحث عبر Brave Search API (مجاني مع مفتاح BRAVE_API_KEY)."""
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        return None
    try:
        url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count={num}"
        data = _fetch(
            url, timeout=15,
            headers={"x-api-key": api_key, "Accept": "application/json"},
        )
        if not isinstance(data, str):
            return None
        if data.startswith("("):  # رسالة حظر/خطأ
            return None
        j = json.loads(data)
        results = []
        for r in j.get("web", {}).get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", ""),
            })
        return results or None
    except Exception:
        return None


def search(query, engine="auto", save=True, num=8):
    """البحث وحفظ النتائج.
    engine: auto|duckduckgo|brave
    """
    # فحص الـ cache أولاً
    cached = _get_cached(query, engine)
    if cached:
        return cached

    results = []

    if engine in ("auto", "duckduckgo"):
        results = duckduckgo_search(query, num)

    if (not results or (len(results) == 1 and "error" in results[0])) and engine != "duckduckgo":
        brave = brave_search(query, num)
        if brave:
            results = brave

    if not results:
        results = [{"error": "No results found"}]

    obj = {
        "query": query,
        "engine": engine,
        "time": datetime.datetime.now().isoformat(),
        "count": len(results),
        "results": results,
    }

    _set_cache(query, engine, obj)

    if save:
        safe_name = re.sub(r'[^\w\-]', '_', query[:50]).strip('_')
        path = os.path.join(
            SEARCH_DIR,
            f"search_{safe_name}_{datetime.datetime.now():%Y%m%d_%H%M%S}.json",
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)

    return obj


# محلِّل HTML: lxml أدق في التحلل من html.parser — مع احتياط تلقائي عند غيابه
try:
    import lxml  # noqa: F401
    _HTML_PARSER = "lxml"
except Exception:
    _HTML_PARSER = "html.parser"


def _html_to_text(content):
    """تحويل HTML إلى نص نظيف — bs4 أولاً ثم regex كاحتياط."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, _HTML_PARSER)
        for tag in soup(["script", "style", "nav", "footer", "header", "iframe", "svg", "form", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        # احتياط قديم بـ regex
        text = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        return re.sub(r'\s+', ' ', text).strip()


def fetch_text(url, save=True, max_length=8000):
    """جلب نص صفحة مع تنظيف ذكي (مع منع قراءة الملفات المحلية)."""
    if not _is_safe_url(url):
        return f"(الرابط محظور لأسباب أمان): {url}"
    try:
        content = _fetch(url)
        if content.startswith("(") and "محظور" in content:
            return content
        text = _html_to_text(content)
        # إزالة الأسطر الطويلة المكررة
        lines = text.split('\n')
        seen = set()
        unique_lines = []
        for line in lines:
            line = line.strip()
            if line and line not in seen and len(line) > 10:
                seen.add(line)
                unique_lines.append(line)
        text = ' '.join(unique_lines)

        if save:
            safe_name = re.sub(r'[^\w\-]', '_', url[:50]).strip('_')
            path = os.path.join(
                SEARCH_DIR,
                f"page_{safe_name}_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt",
            )
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

        return text[:max_length]
    except Exception as e:
        return f"(تعذر جلب الصفحة: {e})"


def search_and_summarize(query, num=5):
    """بحث + ملخص تلقائي للنتائج."""
    results = search(query, save=False, num=num)
    summary_lines = [f"## نتائج البحث: {query}", ""]

    for i, r in enumerate(results.get("results", [])[:num], 1):
        if isinstance(r, dict) and "error" not in r:
            title = r.get("title", "بدون عنوان")
            url = r.get("url", "")
            snippet = r.get("snippet", "")
            summary_lines.append(f"### {i}. {title}")
            if snippet:
                summary_lines.append(f"{snippet}")
            if url:
                summary_lines.append(f"[رابط]({url})")
            summary_lines.append("")

    return "\n".join(summary_lines)


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "best AI tools 2025"
    res = search(q, num=5)
    print(json.dumps(res["results"], ensure_ascii=False, indent=2))
