"""
report_writer.py - كاتب التقارير الاحترافي (v1.0)
==============================================
يولد تقارير احترافية بالعربية والإنجليزية
"""
import datetime
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

REPORTS_DIR = os.path.join(BASE_DIR, "data", "security_reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

SEVERITY_AR = {
    "critical": "حرج",
    "high": "عالي",
    "medium": "متوسط",
    "low": "منخفض",
    "info": "معلوماتي",
}

SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
    "info": "⚪",
}

REMEDIATION = {
    "XSS": "تطبيق HTML encoding على جميع مدخلات المستخدم واستخدام Content Security Policy.",
    "SQL Injection": "استخدام Prepared Statements و Parameterized Queries بدل تجميع الاستعلامات مباشرة.",
    "Open Redirect": "التحقق من الروابط قبل إعادة التوجيه واستخدام قائمة بيضاء للنطاقات المسموح بها.",
    "Git Repository Exposed": "حذف مجلد .git من الوصول العام أو حظره عبر إعدادات الخادم.",
    "Environment File Exposed": "حذف ملف .env من الوصول العام فوراً.",
    "Missing HSTS": "إضافة هيدر Strict-Transport-Security مع max-age لا يقل عن سنة.",
    "Missing CSP": "تطبيق Content-Security-Policy لتحديد مصادر المحتوى المسموح بها.",
    "Clickjacking Possible": "إضافة X-Frame-Options: DENY أو SAMEORIGIN.",
    "MIME Sniffing Possible": "إضافة X-Content-Type-Options: nosniff.",
    "Invalid SSL Certificate": "تجديد شهادة SSL والتأكد من صحتها.",
    "PHP Info Exposed": "حذف ملف phpinfo.php من بيئة الإنتاج.",
    "API Documentation Exposed": "حماية وثائق API بمصادقة.",
    "Database Dump Exposed": "حذف ملفات قواعد البيانات من الخادم فوراً.",
    "Backup File Found": "حذف ملفات النسخ الاحتياطي من الوصول العام.",
    "GraphQL Endpoint Exposed": "تطبيق مصادقة على GraphQL وتعطيل introspection في الإنتاج.",
}


def estimate_bounty(findings):
    """تقدير المكافأة المتوقعة."""
    bounty_ranges = {
        "critical": (3000, 15000),
        "high": (1000, 5000),
        "medium": (200, 1000),
        "low": (50, 200),
    }
    total_min = 0
    total_max = 0
    for f in findings:
        sev = f.get("severity", "low")
        mn, mx = bounty_ranges.get(sev, (50, 200))
        total_min += mn
        total_max += mx
    return {"min": total_min, "max": total_max}


def write_report_arabic(domain, recon_data, scan_data):
    """تقرير عربي احترافي."""
    findings = scan_data.get("findings", [])
    bounty = estimate_bounty(findings)
    now = datetime.datetime.now()

    lines = [
        f"# تقرير فحص أمني - {domain}",
        f"**التاريخ:** {now:%Y-%m-%d %H:%M}",
        f"**إجمالي الثغرات:** {scan_data.get('total', 0)}",
        f"**المكافأة المتوقعة:** ${bounty['min']:,} - ${bounty['max']:,}",
        "",
        "## ملخص تنفيذي",
        f"- النطاقات الفرعية: {len(recon_data.get('subdomains', []))}",
        f"- المسارات المكتشفة: {len(recon_data.get('paths', []))}",
        f"- حرج: {scan_data.get('critical', 0)} | عالي: {scan_data.get('high', 0)} | متوسط: {scan_data.get('medium', 0)} | منخفض: {scan_data.get('low', 0)}",
        "",
        "## الثغرات المكتشفة",
        "",
    ]

    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "low")
        emoji = SEVERITY_EMOJI.get(sev, "⚪")
        sev_ar = SEVERITY_AR.get(sev, sev)
        lines += [
            f"### {emoji} ثغرة #{i}: {f.get('type', '-')}",
            f"**الخطورة:** {sev_ar} (CVSS: {f.get('cvss', '-')})",
        ]
        if f.get("url"):
            lines.append(f"**الرابط:** `{f['url']}`")
        if f.get("param"):
            lines.append(f"**البارامتر:** `{f['param']}`")
        if f.get("payload"):
            lines.append(f"**الحمولة:** `{f['payload']}`")
        remediation = REMEDIATION.get(f.get("type", ""), "راجع دليل OWASP.")
        lines.append(f"**الحل:** {remediation}")
        lines.append("")

    lines += [
        "## التوصيات",
        "",
        "1. إصلاح الثغرات الحرجة فوراً",
        "2. مراجعة إعدادات الخادم",
        "3. تفعيل هيدرز الأمان المفقودة",
        "4. مراجعة دورية للأمان",
        "",
        f"*تقرير مولّد تلقائياً - {now:%Y-%m-%d}*",
    ]

    path = os.path.join(REPORTS_DIR, f"{domain.replace('.','_')}_ar.md")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(tmp, path)
    return path


def write_report_english(domain, recon_data, scan_data):
    """تقرير إنجليزي لبرامج Bug Bounty."""
    findings = scan_data.get("findings", [])
    bounty = estimate_bounty(findings)
    now = datetime.datetime.now()

    lines = [
        f"# Security Assessment Report - {domain}",
        f"**Date:** {now:%Y-%m-%d}",
        f"**Findings:** {scan_data.get('total', 0)}",
        f"**Estimated Bounty:** ${bounty['min']:,} - ${bounty['max']:,}",
        "",
        "## Executive Summary",
        f"A security assessment was conducted on {domain}. "
        f"The assessment identified {scan_data.get('total', 0)} security issues "
        f"including {scan_data.get('critical', 0)} critical, "
        f"{scan_data.get('high', 0)} high, "
        f"{scan_data.get('medium', 0)} medium, and "
        f"{scan_data.get('low', 0)} low severity findings.",
        "",
        "## Findings",
        "",
    ]

    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "low").upper()
        lines += [
            f"### Finding #{i}: {f.get('type', '-')}",
            f"**Severity:** {sev} | **CVSS:** {f.get('cvss', '-')}",
            f"**Description:** {f.get('type', '')} vulnerability detected.",
        ]
        if f.get("url"):
            lines.append(f"**URL:** `{f['url']}`")
        if f.get("payload"):
            lines.append(f"**Proof of Concept:** `{f['payload']}`")
        remediation = REMEDIATION.get(f.get("type", ""), "Follow OWASP guidelines.")
        lines.append(f"**Remediation:** {remediation}")
        lines.append("**Steps to Reproduce:**")
        lines.append(f"1. Navigate to `{f.get('url', 'target URL')}`")
        lines.append(f"2. Inject payload: `{f.get('payload', 'see above')}`")
        lines.append("3. Observe the vulnerability")
        lines.append("")

    lines += [
        "## Recommendations",
        "1. Immediately patch critical findings",
        "2. Review server configurations",
        "3. Implement missing security headers",
        "4. Schedule regular security audits",
        "",
        f"*Report generated automatically - {now:%Y-%m-%d}*",
    ]

    path = os.path.join(REPORTS_DIR, f"{domain.replace('.','_')}_en.md")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(tmp, path)
    return path


if __name__ == "__main__":
    print("تقرير تجريبي")
    recon = {"subdomains": ["api.example.com"], "paths": [{"path": "/.git/HEAD", "status": 200}]}
    scan = {"total": 2, "critical": 1, "high": 0, "medium": 1, "low": 0,
            "findings": [
                {"type": "Git Repository Exposed", "severity": "high", "cvss": 7.5, "url": "https://example.com/.git/HEAD"},
                {"type": "Missing CSP", "severity": "medium", "cvss": 6.1},
            ]}
    ar = write_report_arabic("example.com", recon, scan)
    en = write_report_english("example.com", recon, scan)
    print(f"عربي: {ar}")
    print(f"إنجليزي: {en}")
