"""
browser_agent.py - النظام 5: طبقة متصفح حقيقية (v3.0)
=======================================================
تجريد موحد فوق المتصفحات:

  navigate, click, type, select, scroll, wait, extract,
  download, upload, screenshot, inspect, back, new_tab, switch_tab

الخلفيات:
  auto   -> playwright (إن توفر) -> selenium (إن توفر) -> http (افتراضي بلا متصفح)
  http   -> عميل بلا رأس: جلسة، روابط، نماذج (يعمل دون أي تثبيت).

الأمان: قبل أي navigate يُمرَّر الرابط عبر webtools (SSRF + عناوين خصوصية).

الاستخدام:
  python agent_os/browser_agent.py url https://example.com
"""

import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C


HTML_STRIP = re.compile(r"<[^>]+>")

# ===== تحديد المعدل + احترام robots.txt (عيب 27) =====

RATE_MIN_INTERVAL = float(os.environ.get("BROWSER_RATE_INTERVAL", "1.0"))
RATE_MAX_PER_MIN = int(os.environ.get("BROWSER_MAX_PER_MIN", "60"))


class _RateLimiter:
    """كبول محترم: لا نضرب أي موقع أسرع من المتاح، ولا نزوره حالياً مراراً."""

    def __init__(self, min_interval=RATE_MIN_INTERVAL, max_per_min=RATE_MAX_PER_MIN):
        self.min_interval = min_interval
        self.max_per_min = max_per_min
        self._last = {}
        self._window = int(time.time() // 60)
        self._counts = {}

    def wait(self, domain):
        import time as _t
        window = int(_t.time() // 60)
        if window != self._window:
            self._window = window
            self._counts = {}
        if self._counts.get(domain, 0) >= self.max_per_min:
            raise RuntimeError(f"rate limit: تجاوز هذا الموقع الوتيرة المسموحة هذا الدقيقة")
        last = self._last.get(domain, 0.0)
        wait = self.min_interval - (_t.time() - last)
        if wait > 0:
            _t.sleep(wait)
        self._last[domain] = _t.time()
        self._counts[domain] = self._counts.get(domain, 0) + 1


def _robots_allows(url, fetch):
    """احترام robots.txt: إن قرأنا سياسة الموقع وتم منعُنا — لا نزوره (أفضل جُهد).
    أي فشل في قراءة السياسة = نسمح بسخاء (لا نمنع بسبب حالة مؤقتة)."""
    try:
        import urllib.robotparser as rp
        p = urllib.parse.urlparse(url)
        if not p.netloc:
            return True
        robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
        body = fetch(robots_url, timeout=8)
        if not isinstance(body, str):
            return True
        parser = rp.RobotFileParser()
        parser.parse(body.splitlines())
        if not parser.disallow_all and not parser.allow_all:
            return parser.can_fetch("*", url)
        return parser.can_fetch("*", url)
    except Exception:
        return True


class _HttpBackend:
    """متصفح بلا رأس — جلسة وروابط ونماذج على HTTP فقط."""

    def __init__(self, timeout=15):
        import webtools
        self._wt = webtools
        self.timeout = timeout
        self.url = None
        self.html = ""
        self.status = 0
        self.links = []
        self.forms = []
        self._limiter = _RateLimiter()

    def navigate(self, url):
        if not self._wt._is_safe_url(url):
            raise ValueError("رابط محظور أمنياً (SSRF/خاص)")
        if not _robots_allows(url, self._wt._fetch):
            raise ValueError("هذا الموقع يمنع الزحف (robots.txt)")
        self._limiter.wait(urllib.parse.urlparse(url).netloc)
        resp = self._wt._fetch(url, timeout=self.timeout)
        self.url = url
        self.html = resp if isinstance(resp, str) else str(resp)
        self._parse()
        self.status = 200
        return self.status

    def _parse(self):
        html = self.html
        self.title = (HTML_STRIP.sub(" ", html.partition("<title>")[2].partition("</title>")[0])).strip()
        self.text = HTML_STRIP.sub(" ", html)
        self.links = []
        for m in re.finditer(r'href=["\']([^"\']+)["\']', html):
            href = m.group(1)
            if not href.startswith(("javascript:", "data:", "#")):
                self.links.append(urllib.parse.urljoin(self.url, href))
        self.forms = []
        for fm in re.finditer(r"<form[^>]*>([\s\S]*?)</form>", html, re.I):
            block = fm.group(1)
            inputs = re.findall(r'name=["\']([^"\']+)["\']', block)
            action = re.search(r'action=["\']([^"\']+)["\']', fm.group(0))
            self.forms.append({
                "action": urllib.parse.urljoin(self.url, action.group(1)) if action else self.url,
                "method": "post" if re.search(r"method=['\"]post", fm.group(0), re.I) else "get",
                "inputs": inputs,
                "html": block[:1500],
            })

    def click(self, link_text):
        for i, href in enumerate(self.links):
            if link_text.lower() in href.lower():
                return self.navigate(href)
        return None

    def back(self):
        return self.url  # عميل بلا رأس بدون سجل تنقل حقيقي

    def extract(self):
        return {"url": self.url, "title": self.title, "text": self.text[:4000], "links": self.links}

    def status_bar(self):
        return f"HTTP {self.status} — {self.url}"


class _SeleniumBackend:
    """متصفح حقيقي عبر selenium — يُستورد عند توفر المكتبة فقط."""

    def __init__(self, timeout=15):
        from selenium import webdriver
        opt = webdriver.ChromeOptions()
        opt.add_argument("--headless=new")
        opt.add_argument("--no-sandbox")
        self._driver = webdriver.Chrome(options=opt)
        self._driver.set_page_load_timeout(timeout)
        self.url = None
        self._limiter = _RateLimiter()

    def navigate(self, url):
        import webtools
        if not webtools._is_safe_url(url):
            raise ValueError("رابط محظور (SSRF)")
        if not _robots_allows(url, webtools._fetch):
            raise ValueError("هذا الموقع يمنع الزحف (robots.txt)")
        self._limiter.wait(urllib.parse.urlparse(url).netloc)
        self._driver.get(url)
        self.url = self._driver.current_url
        if not webtools._is_safe_url(self.url):
            try: self._driver.back()
            except Exception: pass
            raise PermissionError("navigation redirected to a blocked/private URL")
        return 200

    def click(self, link_text):
        from selenium.webdriver.common.by import By
        self._driver.find_element(By.LINK_TEXT, link_text).click()
        return 200

    def type(self, selector, text):
        from selenium.webdriver.common.by import By
        el = self._driver.find_element(By.CSS_SELECTOR, selector)
        el.clear()
        el.send_keys(text)
        return True

    def select(self, selector, value):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select
        Select(self._driver.find_element(By.CSS_SELECTOR, selector)).select_by_value(value)
        return True

    def scroll(self):
        self._driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        return True

    def wait(self, seconds=1):
        import time
        time.sleep(seconds)
        return True

    def back(self):
        self._driver.back()
        return self._driver.current_url

    def download(self, url, dest):
        import webtools
        if not webtools._is_safe_url(url):
            raise ValueError("رابط محظور (SSRF)")
        content = webtools._fetch(url, timeout=30)
        with open(dest, "wb" if isinstance(content, bytes) else "w", encoding=None if isinstance(content, bytes) else "utf-8") as f:
            f.write(content)
        return dest

    def upload(self, filepath):
        self._driver.execute_script("arguments[0]? 'file' : ''", None)
        return filepath

    def screenshot(self, path):
        self._driver.save_screenshot(path)
        return path

    def inspect(self):
        from selenium.webdriver.common.by import By
        links = [a.get_attribute("href") for a in self._driver.find_elements(By.TAG_NAME, "a") if a.get_attribute("href")]
        return {"url": self._driver.current_url,
                "title": self._driver.title,
                "links": list(dict.fromkeys(links))[:150],
                "text": self._driver.find_element(By.TAG_NAME, "body").text[:4000]}

    def get_url(self):
        return self._driver.current_url

    def quit(self):
        try:
            self._driver.quit()
        except Exception:
            pass


class _PlaywrightBackend:
    """متصفح كامل عبر Playwright — يُحمَّل عند توفر المكتبة فقط (اختياري نقي)."""

    def __init__(self, timeout=15):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self.page = None
        self.url = None
        self.timeout = timeout * 1000
        self._limiter = _RateLimiter()

    def navigate(self, url):
        import webtools
        if not webtools._is_safe_url(url):
            raise ValueError("رابط محظور (SSRF)")
        if not _robots_allows(url, webtools._fetch):
            raise ValueError("هذا الموقع يمنع الزحف (robots.txt)")
        self._limiter.wait(urllib.parse.urlparse(url).netloc)
        self.page = self._browser.new_page()
        self.page.goto(url, timeout=self.timeout)
        self.url = self.page.url
        if not webtools._is_safe_url(self.url):
            try: self.page.go_back()
            except Exception: pass
            raise PermissionError("navigation redirected to a blocked/private URL")
        return 200

    def click(self, link_text):
        self.page.get_by_text(link_text, exact=False).first.click()
        self.url = self.page.url
        return 200

    def type(self, selector, text):
        self.page.fill(selector, text)
        return True

    def select(self, selector, value):
        self.page.select_option(selector, value)
        return True

    def scroll(self):
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        return True

    def wait(self, seconds=1):
        import time
        time.sleep(seconds)
        return True

    def back(self):
        self.page.go_back()
        self.url = self.page.url
        return self.url

    def screenshot(self, path):
        self.page.screenshot(path=path)
        return path

    def inspect(self):
        return {"url": self.page.url,
                "title": self.page.title(),
                "links": list(self.page.eval_on_selector_all("a", "els => els.map(e => e.href)"))[:150],
                "text": self.page.inner_text("body")[:4000]}

    def get_url(self):
        return self.url or (self.page.url if self.page else None)

    def quit(self):
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            self._pw.stop()
        except Exception:
            pass


class BrowserAgent:
    """واجهة موحدة — تختار الخلفية تلقائياً (playwright → selenium → http)."""

    def __init__(self, backend="auto"):
        self.backend_name = backend
        if backend == "http":
            self._b = _HttpBackend()
        elif backend == "playwright":
            self._b = _PlaywrightBackend()
            self.backend_name = "playwright"
        elif backend == "selenium":
            self._b = _SeleniumBackend()
            self.backend_name = "selenium"
        elif backend == "auto":
            try:
                __import__("playwright.sync_api")
                self._b = _PlaywrightBackend()
                self.backend_name = "playwright"
            except Exception:
                try:
                    __import__("selenium")
                    self._b = _SeleniumBackend()
                    self.backend_name = "selenium"
                except Exception:
                    self._b = _HttpBackend()
                    self.backend_name = "http"
        else:
            self._b = _HttpBackend()
            self.backend_name = "http"

    def navigate(self, url):
        return self._b.navigate(url)

    def click(self, link_text):
        return self._b.click(link_text)

    def back(self):
        return self._b.back()

    def extract(self):
        return self._b.extract()

    def type(self, *a, **k):
        raise NotImplementedError("type يتطلب متصفحاً مرئياً")

    def select(self, *a, **k):
        raise NotImplementedError("select يتطلب متصفحاً مرئياً")

    def scroll(self, *a, **k):
        return None

    def wait(self, *a, **k):
        return None

    def download(self, *a, **k):
        raise NotImplementedError("التحميل عبر webtools.search/download")

    def upload(self, *a, **k):
        raise NotImplementedError("upload يتطلب متصفحاً مرئياً")

    def screenshot(self, path=None):
        raise NotImplementedError("screenshot يتطلب متصفحاً مرئياً")

    def inspect(self):
        return self._b.extract()

    def new_tab(self, url):
        return self.navigate(url)

    def switch_tab(self, *a, **k):
        return None

    def get_url(self):
        return getattr(self._b, "url", None)

    def state(self):
        return {"backend": self.backend_name, "url": self.get_url()}


if __name__ == "__main__":
    args = sys.argv[1:]
    url = None
    if "--url" in args:
        url = args[args.index("--url") + 1]
    elif args and args[0] == "url" and len(args) > 1:
        url = args[1]
    if url:
        b = BrowserAgent()
        try:
            b.navigate(url)
            print(b.state())
            print("العنوان:", b._b.title if hasattr(b._b, "title") else "-")
            print("روابط:", len(b._b.links) if hasattr(b._b, "links") else 0)
            print("نماذج:", len(b._b.forms) if hasattr(b._b, "forms") else 0)
        except Exception as e:
            print("فشل:", e)
    else:
        print("الاستعمال: python agent_os/browser_agent.py url https://example.com")