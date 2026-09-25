"""
scanner.py - فاحص الثغرات الذكي (v1.0)
==========================================
يفحص الثغرات الشائعة بشكل آمن وقانوني
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from agent_os import security_kernel as _auth

SCAN_DIR = os.path.join(BASE_DIR, "data", "scans")
os.makedirs(SCAN_DIR, exist_ok=True)

# حمولات XSS آمنة للفحص
XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "\"'><img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "<svg onload=alert(1)>",
    "';alert(1)//",
]

# حمولات SQL Injection آمنة
SQLI_PAYLOADS = [
    "'",
    "'--",
    "' OR '1'='1",
    "1; SELECT 1--",
    "' UNION SELECT NULL--",
]

# أنماط الأخطاء الدالة على ثغرات
SQL_ERROR_PATTERNS = [
    r"sql syntax", r"mysql_fetch", r"ORA-\d+",
    r"PostgreSQL.*ERROR", r"Warning.*mysql",
    r"Unclosed quotation", r"SQLite.*error",
    r"Microsoft.*ODBC", r"syntax error",
]


def _safe_get(url, timeout=8):
    try:
        _auth.url_guard(url)
        import webtools
        body=webtools._fetch(url,timeout=timeout)
        return body if isinstance(body,str) else str(body)
    except Exception as e:
        return f"error:{e}"


def check_xss(url, param):
    """فحص XSS في بارامتر محدد."""
    findings = []
    parsed = urllib.parse.urlparse(url)
    params = dict(urllib.parse.parse_qsl(parsed.query))
    for payload in XSS_PAYLOADS[:3]:  # نختبر 3 فقط لتجنب الضجيج
        test_params = {**params, param: payload}
        test_url = parsed._replace(
            query=urllib.parse.urlencode(test_params)
        ).geturl()
        body, status = _safe_get(test_url)
        if payload in body and not body.startswith("error:"):
            findings.append({
                "type": "XSS",
                "param": param,
                "payload": payload,
                "url": test_url,
                "severity": "medium",
                "cvss": 6.1,
            })
            break
        time.sleep(0.5)
    return findings


def check_sqli(url, param):
    """فحص SQL Injection."""
    findings = []
    parsed = urllib.parse.urlparse(url)
    params = dict(urllib.parse.parse_qsl(parsed.query))
    for payload in SQLI_PAYLOADS[:3]:
        test_params = {**params, param: payload}
        test_url = parsed._replace(
            query=urllib.parse.urlencode(test_params)
        ).geturl()
        body, status = _safe_get(test_url)
        if body.startswith("error:"):
            continue
        for pattern in SQL_ERROR_PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                findings.append({
                    "type": "SQL Injection",
                    "param": param,
                    "payload": payload,
                    "url": test_url,
                    "severity": "critical",
                    "cvss": 9.8,
                    "evidence": pattern,
                })
                break
        time.sleep(0.5)
    return findings


def check_open_redirect(url, param):
    """فحص Open Redirect."""
    findings = []
    parsed = urllib.parse.urlparse(url)
    params = dict(urllib.parse.parse_qsl(parsed.query))
    payloads = ["https://evil.com", "//evil.com", "/\\evil.com"]
    for payload in payloads:
        test_params = {**params, param: payload}
        test_url = parsed._replace(
            query=urllib.parse.urlencode(test_params)
        ).geturl()
        body, status = _safe_get(test_url)
        if status in [301, 302] and "evil.com" in body:
            findings.append({
                "type": "Open Redirect",
                "param": param,
                "payload": payload,
                "url": test_url,
                "severity": "medium",
                "cvss": 6.1,
            })
            break
        time.sleep(0.3)
    return findings


def check_sensitive_exposure(domain, paths):
    """فحص كشف معلومات حساسة."""
    findings = []
    sensitive_patterns = {
        ".git/HEAD": ("Git Repository Exposed", "high", 7.5),
        ".env": ("Environment File Exposed", "critical", 9.1),
        "phpinfo": ("PHP Info Exposed", "medium", 5.3),
        "swagger": ("API Documentation Exposed", "low", 3.1),
        "graphql": ("GraphQL Endpoint Exposed", "medium", 5.3),
        "backup": ("Backup File Found", "high", 7.5),
        "db.sql": ("Database Dump Exposed", "critical", 9.8),
    }
    for path_info in paths:
        path = path_info.get("path", "")
        status = path_info.get("status", 0)
        if status == 200:
            for keyword, (name, severity, cvss) in sensitive_patterns.items():
                if keyword in path.lower():
                    findings.append({
                        "type": name,
                        "path": path,
                        "url": f"https://{domain}{path}",
                        "severity": severity,
                        "cvss": cvss,
                    })
    return findings


def check_missing_headers(security_headers):
    """تحويل الهيدرز المفقودة إلى ثغرات."""
    findings = []
    severity_map = {
        "Strict-Transport-Security": ("Missing HSTS", "medium", 6.1),
        "Content-Security-Policy": ("Missing CSP", "medium", 6.1),
        "X-Frame-Options": ("Clickjacking Possible", "medium", 6.1),
        "X-Content-Type-Options": ("MIME Sniffing Possible", "low", 4.3),
    }
    for header in security_headers.get("missing", []):
        if header in severity_map:
            name, severity, cvss = severity_map[header]
            findings.append({
                "type": name,
                "missing_header": header,
                "severity": severity,
                "cvss": cvss,
            })
    return findings


def full_scan(domain, recon_data=None):
    """فحص شامل للهدف."""
    print(f"\n🔎 فحص {domain}...")
    findings = []

    if recon_data:
        # فحص الهيدرز
        if "security_headers" in recon_data:
            h_findings = check_missing_headers(recon_data["security_headers"])
            findings.extend(h_findings)
            print(f"  ✓ هيدرز: {len(h_findings)} مشكلة")
        # فحص المسارات الحساسة
        if "paths" in recon_data:
            p_findings = check_sensitive_exposure(domain, recon_data["paths"])
            findings.extend(p_findings)
            print(f"  ✓ مسارات: {len(p_findings)} مشكلة")

    # فحص SSL
    if recon_data and recon_data.get("ssl", {}).get("valid") is False:
        findings.append({
            "type": "Invalid SSL Certificate",
            "severity": "high",
            "cvss": 7.5,
        })

    result = {
        "domain": domain,
        "date": datetime.datetime.now().isoformat(),
        "findings": findings,
        "total": len(findings),
        "critical": len([f for f in findings if f.get("severity") == "critical"]),
        "high": len([f for f in findings if f.get("severity") == "high"]),
        "medium": len([f for f in findings if f.get("severity") == "medium"]),
        "low": len([f for f in findings if f.get("severity") == "low"]),
    }

    out = os.path.join(SCAN_DIR, f"{domain.replace('.','_')}_scan.json")
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    os.replace(tmp, out)
    print(f"  ✓ محفوظ: {out}")
    return result


if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else "example.com"
    result = full_scan(domain)
    print(f"\nالنتائج: {result['total']} ثغرة")
    for f in result["findings"]:
        print(f"  [{f['severity'].upper()}] {f['type']}")
