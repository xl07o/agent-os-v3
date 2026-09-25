"""
code_reviewer.py - فاحص الكود الذكي (v1.0)
==========================================
يفحص الكود ويعطيك تقرير عيوب كامل
الاستخدام:
  python code_reviewer.py <ملف.py>
  python code_reviewer.py <مجلد/>
  python code_reviewer.py --project
"""

import ast
import os
import sys
import json
import re
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REVIEW_DIR = os.path.join(BASE_DIR, "data", "code_reviews")
os.makedirs(REVIEW_DIR, exist_ok=True)


def analyze_python_ast(code, filename=""):
    """تحليل عميق لكود بايثون."""
    issues = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [{"type": "SyntaxError", "severity": "critical",
                 "line": e.lineno, "msg": str(e), "fix": "أصلح خطأ الصياغة"}]

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec", "compile"}:
                    issues.append({
                        "type": "Dangerous Function",
                        "severity": "critical",
                        "line": node.lineno,
                        "msg": f"استخدام {node.func.id}() خطير جداً",
                        "fix": "استخدم بدائل آمنة"
                    })

        if isinstance(node, ast.ExceptHandler):
            if node.type is None or (isinstance(node.type, ast.Name) and node.type.id == "Exception"):
                body = node.body
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    issues.append({
                        "type": "Empty Exception Handler",
                        "severity": "high",
                        "line": node.lineno,
                        "msg": "استثناء فارغ - يخفي الأخطاء",
                        "fix": "أضف logging أو معالجة حقيقية"
                    })

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_lines = (node.end_lineno or node.lineno) - node.lineno
            if func_lines > 50:
                issues.append({
                    "type": "Long Function",
                    "severity": "medium",
                    "line": node.lineno,
                    "msg": f"دالة {node.name} طويلة ({func_lines} سطر)",
                    "fix": "قسّمها لدوال أصغر"
                })
            if not (node.body and isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant)):
                if func_lines > 10:
                    issues.append({
                        "type": "Missing Docstring",
                        "severity": "low",
                        "line": node.lineno,
                        "msg": f"دالة {node.name} بدون docstring",
                        "fix": "أضف docstring يشرح الدالة"
                    })

    return issues


def check_security_patterns(code, filename=""):
    """فحص أنماط أمان بالتعبيرات النظامية."""
    issues = []
    lines = code.splitlines()

    patterns = [
        (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded Password", "critical",
         "استخدم متغيرات بيئة .env"),
        (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API Key", "critical",
         "استخدم متغيرات بيئة .env"),
        (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded Secret", "critical",
         "استخدم متغيرات بيئة .env"),
        (r'shell\s*=\s*True', "Shell Injection Risk", "high",
         "استخدم shell=False ومرر الوسائط كقائمة"),
        (r'pickle\.loads?\(', "Pickle Deserialization", "high",
         "استخدم json بدل pickle"),
        (r'md5\(|hashlib\.md5', "Weak Hash MD5", "medium",
         "استخدم SHA-256 أو bcrypt"),
        (r'http://', "Insecure HTTP", "medium",
         "استخدم HTTPS"),
        (r'TODO|FIXME|HACK|XXX', "Technical Debt", "low",
         "عالج هذه النقاط"),
        (r'print\(.*password|print\(.*secret|print\(.*key', "Sensitive Data Logging", "high",
         "لا تطبع بيانات حساسة"),
    ]

    for i, line in enumerate(lines, 1):
        for pattern, issue_type, severity, fix in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                issues.append({
                    "type": issue_type,
                    "severity": severity,
                    "line": i,
                    "msg": f"اكتشف: {issue_type}",
                    "code": line.strip()[:100],
                    "fix": fix
                })

    return issues


def check_code_quality(code, filename=""):
    """فحص جودة الكود."""
    issues = []
    lines = code.splitlines()

    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            issues.append({
                "type": "Long Line",
                "severity": "low",
                "line": i,
                "msg": f"سطر طويل ({len(line)} حرف)",
                "fix": "قسّمه لأسطر أقصر"
            })

    if len(lines) > 500:
        issues.append({
            "type": "Large File",
            "severity": "medium",
            "line": 1,
            "msg": f"ملف كبير ({len(lines)} سطر)",
            "fix": "قسّمه لملفات أصغر"
        })

    return issues


def review_file(filepath):
    """فحص ملف واحد."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            code = f.read()
    except Exception as e:
        return {"error": str(e), "file": filepath}

    filename = os.path.basename(filepath)
    issues = []

    if filepath.endswith(".py"):
        issues.extend(analyze_python_ast(code, filename))

    issues.extend(check_security_patterns(code, filename))
    issues.extend(check_code_quality(code, filename))

    critical = [i for i in issues if i.get("severity") == "critical"]
    high = [i for i in issues if i.get("severity") == "high"]
    medium = [i for i in issues if i.get("severity") == "medium"]
    low = [i for i in issues if i.get("severity") == "low"]

    score = 100
    score -= len(critical) * 20
    score -= len(high) * 10
    score -= len(medium) * 5
    score -= len(low) * 2
    score = max(0, score)

    return {
        "file": filepath,
        "lines": len(code.splitlines()),
        "issues": issues,
        "total": len(issues),
        "critical": len(critical),
        "high": len(high),
        "medium": len(medium),
        "low": len(low),
        "score": score,
        "grade": "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F",
    }


def review_project(project_dir=None, use_ai=True):
    """فحص كل المشروع."""
    if not project_dir:
        project_dir = BASE_DIR

    results = []
    py_files = []

    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in {
            "__pycache__", ".git", "node_modules", ".venv", "venv", ".pytest_cache"
        }]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))

    print(f"\n🔍 فحص {len(py_files)} ملف بايثون...")

    for fp in py_files:
        rel = os.path.relpath(fp, project_dir)
        print(f"  ✓ {rel}")
        result = review_file(fp)
        result["file"] = rel
        results.append(result)

    total_issues = sum(r["total"] for r in results)
    total_critical = sum(r["critical"] for r in results)
    total_high = sum(r["high"] for r in results)
    avg_score = sum(r["score"] for r in results) / len(results) if results else 0

    report = {
        "date": datetime.datetime.now().isoformat(),
        "project": project_dir,
        "files_reviewed": len(results),
        "total_issues": total_issues,
        "critical": total_critical,
        "high": total_high,
        "avg_score": round(avg_score, 1),
        "overall_grade": "A" if avg_score >= 90 else "B" if avg_score >= 75 else "C" if avg_score >= 60 else "D",
        "files": results,
    }

    if use_ai and total_issues > 0:
        try:
            import brain
            worst = sorted(results, key=lambda x: x["critical"] * 10 + x["high"], reverse=True)[:3]
            summary = json.dumps([{"file": r["file"], "issues": r["issues"][:5]} for r in worst],
                                 ensure_ascii=False)
            b = brain.Brain("أنت خبير مراجعة كود متخصص.")
            ai_review, _ = b.ask(f"راجع هذه المشاكل وأعطني توصيات محددة:\n{summary}")
            report["ai_review"] = ai_review
        except Exception as e:
            report["ai_review"] = f"تعذر الفحص بالذكاء: {e}"

    out = os.path.join(REVIEW_DIR, f"review_{datetime.datetime.now():%Y%m%d_%H%M}.json")
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    os.replace(tmp, out)

    return report


def print_report(report):
    """طباعة التقرير."""
    print("\n" + "=" * 60)
    print("📊 تقرير فحص الكود")
    print("=" * 60)
    print(f"📁 الملفات: {report.get('files_reviewed', 1)}")
    print(f"🔴 حرج: {report.get('critical', 0)}")
    print(f"🟠 عالي: {report.get('high', 0)}")
    print(f"🟡 متوسط: {report.get('medium', 0)}")
    print(f"🔵 منخفض: {report.get('low', 0)}")
    print(f"⭐ الدرجة: {report.get('avg_score', report.get('score', 0))}/100 ({report.get('overall_grade', report.get('grade', '-'))})")

    files = report.get("files", [])
    if files:
        worst = sorted(files, key=lambda x: x.get("critical", 0) * 10 + x.get("high", 0), reverse=True)[:5]
        print("\n🚨 أسوأ الملفات:")
        for f in worst:
            if f.get("total", 0) > 0:
                print(f"  {f['file']}: درجة {f.get('score',0)}/100 | {f.get('critical',0)} حرج | {f.get('high',0)} عالي")

    all_issues = []
    for f in files:
        for issue in f.get("issues", []):
            issue["_file"] = f["file"]
            all_issues.append(issue)
    if "issues" in report:
        all_issues = report["issues"]

    critical_issues = [i for i in all_issues if i.get("severity") == "critical"]
    if critical_issues:
        print("\n🔴 مشاكل حرجة:")
        for issue in critical_issues[:10]:
            f_name = issue.get("_file", "")
            print(f"  [{f_name}:{issue.get('line',0)}] {issue['type']}: {issue['msg']}")
            print(f"    → الحل: {issue.get('fix', '-')}")

    if report.get("ai_review"):
        print("\n🧠 مراجعة الذكاء الاصطناعي:")
        print(report["ai_review"][:1000])

    print("\n" + "=" * 60)


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "--project":
        report = review_project(use_ai=True)
        print_report(report)
    elif os.path.isdir(args[0]):
        report = review_project(args[0], use_ai=True)
        print_report(report)
    elif os.path.isfile(args[0]):
        result = review_file(args[0])
        print_report(result)
    else:
        print("الاستخدام:")
        print("  python code_reviewer.py --project")
        print("  python code_reviewer.py brain.py")
        print("  python code_reviewer.py security_empire/")
