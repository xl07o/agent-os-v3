"""
proactive_shield.py - الدرع الاستباقي + منحنى النمو
=====================================================
الدرع: يفحص الكود دورياً بحثاً عن ثغرات (تبعيات قديمة، أسرار مكشوفة).
النمو: يقارن أداء اليوم بالأمس — لو المنحنى نزل يبحث عن السبب.
"""
import os, sys, re, datetime
def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

SHIELD_FILE = os.path.join(C.AGENT_OS_DIR, "shield_scans.json")
GROWTH_FILE = os.path.join(C.AGENT_OS_DIR, "growth_tracker.json")

# ===== الدرع الاستباقي =====

SECRET_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9]{20,})"),
    re.compile(r"(AIza[A-Za-z0-9_\-]{30,})"),
    re.compile(r"(gsk_[A-Za-z0-9]{20,})"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{8,}"),
]

def scan_for_exposed_secrets(root=None):
    """يمسح الكود بحثاً عن أسرار مكشوفة (مو في .env)."""
    root = root or C.BASE_DIR
    findings = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules", "tests")]
        for f in files:
            if not f.endswith(".py") or f == ".env.example":
                continue
            path = os.path.join(dirpath, f)
            try:
                content = open(path, encoding="utf-8", errors="replace").read()
                for i, pat in enumerate(SECRET_PATTERNS):
                    for match in pat.finditer(content):
                        line_no = content[:match.start()].count("\n") + 1
                        findings.append({
                            "file": os.path.relpath(path, root),
                            "line": line_no,
                            "type": "exposed_secret",
                            "severity": "critical",
                        })
            except Exception:
                pass
    return findings

def scan_dangerous_patterns(root=None):
    """يبحث عن أنماط خطرة في الكود (eval/exec/shell=True في غير التعليقات)."""
    root = root or C.BASE_DIR
    findings = []
    dangerous = [
        (re.compile(r"\beval\s*\("), "eval()"),
        (re.compile(r"\bexec\s*\("), "exec()"),
    ]
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "tests")]
        for f in files:
            if not f.endswith(".py"): continue
            path = os.path.join(dirpath, f)
            try:
                for line_no, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
                    stripped = line.lstrip()
                    if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                        continue
                    for pat, name in dangerous:
                        if pat.search(line):
                            findings.append({"file": os.path.relpath(path, root),
                                             "line": line_no, "type": name, "severity": "high"})
            except Exception:
                pass
    return findings

def full_scan(root=None):
    """فحص أمني شامل."""
    secrets = scan_for_exposed_secrets(root)
    dangerous = scan_dangerous_patterns(root)
    all_findings = secrets + dangerous
    scan = {"at": C.now_iso(), "findings": len(all_findings),
            "critical": sum(1 for f in all_findings if f["severity"] == "critical"),
            "details": all_findings[:50]}
    log = C.load_json(SHIELD_FILE, {"scans": []})
    log["scans"].append(scan)
    log["scans"] = log["scans"][-50:]
    C.atomic_write(SHIELD_FILE, log)
    return scan

# ===== منحنى النمو =====

def record_day(metrics):
    """يسجّل مقاييس اليوم: tasks_done, tasks_failed, skills_learned, revenue..."""
    log = C.load_json(GROWTH_FILE, {"days": {}})
    today = datetime.date.today().isoformat()
    metrics["date"] = today
    log["days"][today] = metrics
    C.atomic_write(GROWTH_FILE, log)
    return metrics

def compare_with_yesterday():
    """يقارن أداء اليوم بالأمس. يعيد فرق كل مقياس."""
    log = C.load_json(GROWTH_FILE, {"days": {}})
    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    t = log["days"].get(today, {})
    y = log["days"].get(yesterday, {})
    if not t or not y:
        return {"available": False, "note": "لا بيانات كافية للمقارنة"}
    deltas = {}
    for key in set(list(t.keys()) + list(y.keys())):
        if key == "date": continue
        tv = t.get(key, 0); yv = y.get(key, 0)
        try:
            deltas[key] = {"today": tv, "yesterday": yv, "delta": round(float(tv) - float(yv), 2)}
        except (TypeError, ValueError):
            pass
    growing = sum(1 for d in deltas.values() if d["delta"] > 0)
    declining = sum(1 for d in deltas.values() if d["delta"] < 0)
    return {"available": True, "growing": growing, "declining": declining,
            "trend": "📈 صاعد" if growing > declining else "📉 نازل" if declining > growing else "➡️ مستقر",
            "deltas": deltas}

def growth_streak():
    """كم يوم متتالي المنحنى صاعد."""
    log = C.load_json(GROWTH_FILE, {"days": {}})
    days = sorted(log["days"].keys(), reverse=True)
    if len(days) < 2: return 0
    streak = 0
    for i in range(len(days) - 1):
        t = log["days"][days[i]]
        y = log["days"][days[i + 1]]
        t_score = sum(float(t.get(k, 0)) for k in t if k != "date")
        y_score = sum(float(y.get(k, 0)) for k in y if k != "date")
        if t_score >= y_score:
            streak += 1
        else:
            break
    return streak
