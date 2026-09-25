"""
tool_registry.py - النظام 4: السجل العام للأدوات (v3.0)
=======================================================
قدرة دائمة: اكتشاف أداة -> مراجعة أمنية -> تثبيت -> اختبار -> تسجيل -> صحة -> إصدار.

قواعد صارمة:
  - لا يكشف الوكيل أسراراً تلقائياً: أي credential يحتاج موافقة بشرية.
  - فحص أمني باستخدام قواعد mastery (منع os/subprocess/socket/eval/exec...)
  - التثبيت عبر pip --user بأسماء مُصفّاة من الرموز الخطرة فقط.

الاستخدام:
  python agent_os/tool_registry.py discover <اسم>
  python agent_os/tool_registry.py list
  python agent_os/tool_registry.py health
"""

import os
import re
import sys
import hashlib
import subprocess
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C
from agent_os import security_kernel as _auth


REGISTRY_FILE = os.path.join(C.AGENT_OS_DIR, "tool_registry.json")

# أنماط الحزم الخطرة — لا نسمح بتثبيتها/تسجيلها قياساً على حارس الحزم
DANGEROUS_KEYWORDS = ["os", "sock", "cryptomin", "rat ", "spyware", "keylog"]

# أنماط ممنوعة قطعياً بغض النظر عن السياق
FORBIDDEN_PATTERNS = [
    r"\bos\.system\s*\(",
    r"subprocess\.(Popen|call|run)\([^)]*shell\s*=\s*True",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"\bctypes\b",
    r"bypass",
    r"cloudflare",
    r"captcha.*solver",
    r"\.env\b",
    r"credential.*json",
    r"private_?key",
]

# ===== قائمة بيضاء للاستيرادات الداخلية (عيب 8) =====
# نوى النظام محمية قطعياً؛ استيراد داخلي خارج القائمة يخفض الأمان.
PROTECTED_CORE_MODULES = {"selfrunner", "webtools", "mastery", "skills", "memory_bank", "brain", "builders"}
ALLOWED_INTERNAL_IMPORTS = {
    "agent_os", "_common", "notifier", "kernel", "self_improve_engine",
    "finance_intel", "goal_manager", "world_model", "approval_center",
    "chief_staff", "browser_agent", "tool_registry", "product_factory",
    "devops_agent", "bounty_engine", "business_autopilot", "benchmark",
    "swarm", "skill_memory", "api_hunter", "evaluator_agent", "dashboard",
    "github_hunter", "opportunity_brain", "revenue_engine",
    "computer_agent", "tool_acquisition",
}


def _load():
    return C.load_json(REGISTRY_FILE, {"tools": [], "next_id": 1})


def _save(s):
    C.atomic_write(REGISTRY_FILE, s)


def security_review(name, description="", code=""):
    """مراجعة أمنية: حكم 0-100 + سبب. يرفض أي كود خطير."""
    reasons = []
    score = 60
    low = name.lower()
    for k in DANGEROUS_KEYWORDS:
        if k.lower() in low or k.lower() in (description or "").lower():
            score -= 30
            reasons.append(f"كلمة خطرة: {k}")
    for pat, note in [
        (r"\bos\b", "استيراد os"),
        (r"subprocess", "استيراد subprocess"),
        (r"socket", "استيراد socket"),
        (r"\beval\s*\(", "استدعاء eval"),
        (r"\bexec\s*\(", "استدعاء exec"),
        (r"__import__", "__import__"),
        (r"shutil\.rmtree", "حذف عشوائي"),
    ]:
        if re.search(pat, code or ""):
            score -= 25
            reasons.append(note)
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, (code or "").lower()):
            score -= 30
            reasons.append(f"نمط ممنوع قطعياً: {pat}")
    # قائمة بيضاء للاستيرادات الداخلية (عيب 8): لا يلمس كود ملتقط نوى النظام
    code_lower = (code or "").lower()
    for m in re.finditer(r"(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))", code_lower):
        path = ((m.group(1) or m.group(2)) or "").strip().split()[0]
        parts = path.split(".")
        if parts and parts[0] in PROTECTED_CORE_MODULES:
            score -= 35
            reasons.append(f"استيراد نواة محمية: {parts[0]}")
            continue
        if parts and parts[0] == "agent_os":
            sub = parts[1] if len(parts) > 1 else ""
            if sub and sub not in ALLOWED_INTERNAL_IMPORTS:
                score -= 30
                reasons.append(f"استيراد داخلي خارج القائمة: {sub}")
    return {"safe": score >= 50, "score": max(0, min(100, score)), "reasons": reasons}


def discover_tool(name, description="", code="", requires_api_key=False):
    """اكتشاف + مراجعة أمنية + اختبار معزول + تسجيل معلّق."""
    name = name.strip()
    if not name:
        return None
    review = security_review(name, description, code)
    state = _load()
    tool = {
        "id": state["next_id"],
        "name": name,
        "description": description[:300],
        "security": review,
        "code_hash": hashlib.sha256((code or "").encode("utf-8")).hexdigest()[:16],
        "source_url": "",
        "requires_api_key": bool(requires_api_key),
        "sandbox_result": None,
        "status": "approved" if review["safe"] else "blocked",
        "installed": False,
        "version": "",
        "tested": False,
        "health": "unknown",
        "secrets_needed": [],
        "needs_approval": True,
        "created": C.now_iso(),
    }
    # إن كان هناك كود — نختبره فعلياً داخل عزلة قبل أي تسجيل نشط
    if code and review["safe"]:
        ok, out = sandbox_test(code)
        tool["sandbox_result"] = out[:300]
        tool["status"] = "pending_key" if ok and requires_api_key else ("active" if ok else "rejected")
        if ok and requires_api_key:
            _open_credential_request(tool)
    state["next_id"] += 1
    state["tools"].append(tool)
    _save(state)
    C.log(f"🧰 أداة #{tool['id']} «{name}» → {tool['status']} (أمان {review['score']}%)")
    return tool


def _open_credential_request(tool):
    """أداة تحتاج مفتاح API → طلب اعتماد بشري صريح."""
    try:
        from agent_os import approval_center
        approval_center.create_request(
            f"تفعيل أداة تحتاج مفتاح API: {tool['name']}",
            tool["description"],
            ["احصل على المفتاح من المصدر الرسمي", "ضعه في .env بالاسم المناسب", "وافق على هذا الطلب"],
            kind="credential", risk="medium",
        )
    except Exception:
        pass


def sandbox_test(code_str, test_call="", timeout_sec=10):
    """تشغيل candidate عبر policy مركزي؛ بلا أسرار موروثة وبعزل disposable."""
    rev = security_review("candidate", "", code_str)
    if not rev["safe"]:
        return False, rev
    return _auth.safe_candidate_run(code_str, test_call=test_call, timeout=timeout_sec)


def register(name, description, code_str, source_url="", requires_api_key=False):
    """سجل أداة بعد مراجعة أمنية + اختبار معزول، مع حفظ metadata فعلياً."""
    entry = discover_tool(name, description, code_str, requires_api_key)
    if entry:
        state = _load()
        for tool in state["tools"]:
            if tool.get("id") == entry.get("id"):
                tool["source_url"] = (source_url or "")[:200]
                break
        _save(state)
        entry["source_url"] = (source_url or "")[:200]
    return entry


def list_active_tools():
    """الأدوات الجاهزة للاستدعاء فعلياً."""
    return [t for t in _load()["tools"] if t["status"] in {"active", "installed"} and (not t.get("tested") or t.get("health") == "healthy")]


def install_tool(tool_id, package_name=None):
    """تثبيت الأداة داخل virtualenv مستقل؛ لا نلوث Python الرئيسي."""
    import venv
    state = _load()
    tool = next((t for t in state["tools"] if t["id"] == tool_id), None)
    if not tool:
        return {"ok": False, "reason": "لا أداة"}
    if tool["status"] in {"blocked", "rejected"}:
        return {"ok": False, "reason": "مرفوض أمنياً"}
    pkg = package_name or tool["name"]
    if not re.match(r"^[A-Za-z0-9_.\-]+==[A-Za-z0-9_.+\-]+$", pkg):
        return {"ok": False, "reason": "يجب تثبيت نسخة محددة: package==version"}
    tool_dir = os.path.join(C.AGENT_OS_DIR, "tools", str(tool_id))
    venv_dir = os.path.join(tool_dir, "venv")
    try:
        os.makedirs(tool_dir, exist_ok=True)
        if not os.path.exists(venv_dir):
            venv.EnvBuilder(with_pip=True, clear=False).create(venv_dir)
        py = os.path.join(venv_dir, "Scripts", "python.exe") if os.name == "nt" else os.path.join(venv_dir, "bin", "python")
        r = subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", pkg], cwd=tool_dir, shell=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        out=(r.stdout+"\n"+r.stderr)[-3000:]
        tool["installed"] = r.returncode == 0
        tool["version"] = pkg.split("==",1)[1]
        tool["venv"] = venv_dir
        tool["status"] = "installed" if tool["installed"] else tool["status"]
        _save(state)
        return {"ok": tool["installed"], "output": out}
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "انتهت مهلة تثبيت الأداة"}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:300]}


def test_tool(tool_id, test_command="--version"):
    """اختبار تشغيلي داخل بيئة الأداة إن كانت مثبتة فيها."""
    state = _load()
    tool = next((t for t in state["tools"] if t["id"] == tool_id), None)
    if not tool:
        return {"ok": False}
    try:
        exe = tool.get("name", "")
        if tool.get("venv"):
            exe = os.path.join(tool["venv"], "Scripts" if os.name == "nt" else "bin", tool["name"])
        if not os.path.exists(exe) and tool.get("venv"):
            exe = os.path.join(tool["venv"], "Scripts" if os.name == "nt" else "bin", "python")
            args=[exe, "-m", tool["name"].split("==")[0], *([test_command] if test_command else [])]
        else:
            args=[exe, *([test_command] if test_command else [])]
        r=subprocess.run(args, cwd=tool.get("venv") or C.BASE_DIR, shell=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        output=(r.stdout+"\n"+r.stderr).strip()
        tool["tested"] = True
        tool["health"] = "healthy" if r.returncode == 0 else "unhealthy"
        _save(state)
        return {"ok": r.returncode == 0, "output": output[:1000]}
    except Exception as e:
        tool["tested"] = True; tool["health"] = "unhealthy"; _save(state)
        return {"ok": False, "output": str(e)[:500]}


def register_secret(tool_id, secret_name):
    """تسجيل اسم سر يحتاجه الوكيل — لا قيمة السر (تبقى بيد المستخدم/الموافقة)."""
    state = _load()
    tool = next((t for t in state["tools"] if t["id"] == tool_id), None)
    if not tool:
        return False
    if secret_name not in tool["secrets_needed"]:
        tool["secrets_needed"].append(secret_name)
        tool["needs_approval"] = True
        _save(state)
    return True


def health_check_all():
    """فحص صحة كل الأدوات المثبتة."""
    state = _load()
    for t in state["tools"]:
        if t["installed"]:
            test_tool(t["id"])
    return [(t["name"], t["status"], t["health"], t["secrets_needed"]) for t in state["tools"]]


def list_tools():
    return _load()["tools"]


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("الاستعمال: discover <name> | list | health | install <id> [pkg]")
    elif args[0] == "discover":
        discover_tool(" ".join(args[1:]) or "unnamed")
    elif args[0] == "list":
        for t in list_tools():
            print(f"#{t['id']} {t['name']} [{t['status']}] أمان {t['security']['score']}% إصدار {t['version'] or '-'}")
    elif args[0] == "health":
        for row in health_check_all():
            print(row)
    elif args[0] == "install" and len(args) > 1:
        pkg = args[2] if len(args) > 2 else None
        print(install_tool(int(args[1]), pkg))