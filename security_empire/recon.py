"""
recon.py - الاستطلاع الذكي (v1.0)
=====================================
يجمع معلومات شاملة عن الهدف قبل الفحص
"""
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.parse
import urllib.request
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from agent_os import security_kernel as _auth
sys.path.insert(0, BASE_DIR)

RECON_DIR = os.path.join(BASE_DIR, "data", "recon")
os.makedirs(RECON_DIR, exist_ok=True)


def _safe_get(url, timeout=10):
    try:
        _auth.url_guard(url)
        import webtools
        body=webtools._fetch(url,timeout=timeout)
        return body if isinstance(body,str) else str(body)
    except Exception as e:
        return f"error:{e}"


def get_headers(domain):
    result={}
    for scheme in ("https", "http"):
        url=f"{scheme}://{domain}"
        try:
            _auth.url_guard(url)
            import webtools
            body=webtools._fetch(url,timeout=10)
            if body is not None:
                result["status"]=200; result["headers"]={}; result["url"]=url; result["scheme"]=scheme
                break
        except Exception as e:
            result[f"{scheme}_error"]=str(e)
    return result


def check_security_headers(headers):
    """فحص هيدرز الأمان المفقودة."""
    important = [
        "Strict-Transport-Security",
        "Content-Security-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "X-XSS-Protection",
    ]
    missing = []
    present = []
    for h in important:
        found = any(h.lower() == k.lower() for k in headers.keys())
        if found:
            present.append(h)
        else:
            missing.append(h)
    return {"missing": missing, "present": present, "score": len(present) / len(important)}


def dns_lookup(domain, timeout=6):
    """فحص DNS بسقف زمني — لا تعلق الحلقة على مزوّد DNS بطيء/محجوب."""
    result = {}
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout

    def _ip():
        try:
            result["ip"] = socket.gethostbyname(domain)
        except Exception as e:
            result["ip_error"] = str(e)

    def _v6():
        try:
            info = socket.getaddrinfo(domain, None)
            result["ipv6"] = any(i[0] == socket.AF_INET6 for i in info)
        except Exception:
            result["ipv6"] = False

    with ThreadPoolExecutor(max_workers=2) as ex:
        fa = ex.submit(_ip)
        fb = ex.submit(_v6)
        for fut, key in ((fa, "ip"), (fb, "ipv6")):
            try:
                fut.result(timeout=timeout)
            except _FutTimeout:
                if key == "ip":
                    result["ip_error"] = f"DNS timeout بعد {timeout}s"
                else:
                    result["ipv6"] = False
            except Exception:
                pass
    return result


def check_ssl(domain):
    """فحص شهادة SSL."""
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(10)
            s.connect((domain, 443))
            cert = s.getpeercert()
            expire = cert.get("notAfter", "")
            return {
                "valid": True,
                "expires": expire,
                "subject": dict(x[0] for x in cert.get("subject", [])),
                "issuer": dict(x[0] for x in cert.get("issuer", [])),
            }
    except ssl.SSLError as e:
        return {"valid": False, "error": str(e)}
    except Exception as e:
        return {"valid": None, "error": str(e)}


def find_subdomains(domain):
    """اكتشاف النطاقات الفرعية عبر مصادر مجانية."""
    subs = set()
    # crt.sh
    try:
        url = f"https://crt.sh/?q=%.{domain}&output=json"
        data = _safe_get(url, timeout=15)
        if not data.startswith("error:"):
            entries = json.loads(data)
            for e in entries:
                name = e.get("name_value", "")
                for s in name.splitlines():
                    s = s.strip().lstrip("*.").lower()
                    if s.endswith(domain) and s != domain:
                        subs.add(s)
    except Exception:
        pass
    # hackertarget
    try:
        url = f"https://api.hackertarget.com/hostsearch/?q={domain}"
        data = _safe_get(url, timeout=10)
        if not data.startswith("error:"):
            for line in data.splitlines():
                parts = line.split(",")
                if parts and parts[0].endswith(domain):
                    subs.add(parts[0].strip())
    except Exception:
        pass
    return list(subs)[:50]


def check_common_paths(domain):
    """فحص مسارات شائعة قد تكشف معلومات."""
    paths = [
        "/.git/HEAD", "/.env", "/robots.txt", "/sitemap.xml",
        "/admin", "/admin/login", "/wp-admin", "/api", "/api/v1",
        "/.well-known/security.txt", "/security.txt",
        "/phpinfo.php", "/info.php", "/test.php",
        "/backup", "/backup.zip", "/db.sql",
        "/swagger", "/swagger-ui", "/api-docs",
        "/graphql", "/graphiql",
        "/.DS_Store", "/web.config",
    ]
    found = []
    for path in paths:
        try:
            url = f"https://{domain}{path}"
            body = _safe_get(url, timeout=5)
            if not body.startswith("error:"):
                found.append({"path": path, "status": 200})
            time.sleep(0.3)
        except Exception:
            pass
    return found


def full_recon(domain):
    """استطلاع شامل."""
    print(f"\n🔍 استطلاع {domain}...")
    result = {
        "domain": domain,
        "date": datetime.datetime.now().isoformat(),
        "dns": dns_lookup(domain),
        "ssl": check_ssl(domain),
    }
    print("  ✓ DNS و SSL")
    headers_data = get_headers(domain)
    result["headers"] = headers_data
    if "headers" in headers_data:
        result["security_headers"] = check_security_headers(headers_data["headers"])
    print("  ✓ هيدرز")
    result["subdomains"] = find_subdomains(domain)
    print(f"  ✓ نطاقات فرعية: {len(result['subdomains'])}")
    result["paths"] = check_common_paths(domain)
    print(f"  ✓ مسارات: {len(result['paths'])}")
    # حفظ
    out = os.path.join(RECON_DIR, f"{domain.replace('.','_')}.json")
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    os.replace(tmp, out)
    print(f"  ✓ محفوظ: {out}")
    return result


if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else "example.com"
    r = full_recon(domain)
    print(json.dumps(r, ensure_ascii=False, indent=2))
