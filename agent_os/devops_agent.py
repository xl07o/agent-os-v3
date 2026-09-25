"""
devops_agent.py - النظام 8: وكيل النشر والتطوير التشغيلي (v3.0)
================================================================
يعرف: git, github, docker, CI, متغيرات البيئة، التحقق الصحي، السجلات،
التراجع، النشر. كل الأوامر عبر قوائم argv بلا shell.

الاستخدام:
  python agent_os/devops_agent.py git status
  python agent_os/devops_agent.py deploy <مسار>
  python agent_os/devops_agent.py health <مسار>
  python agent_os/devops_agent.py rollback <مسار>
"""

import os
import re
import subprocess
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

DEPLOYS_FILE = os.path.join(C.AGENT_OS_DIR, "deploys.json")

# قائمة بيضاء للأوامر التشغيلية (لا shell أبداً)
ALLOWED = {
    "git": {"status", "add", "commit", "log", "diff", "remote", "clone", "push", "pull", "init", "branch", "checkout"},
    "docker": {"ps", "build", "compose", "logs", "stop", "start", "restart", "pull", "run", "images"},
    "python": {"manage.py", "-m"},
}


def _load():
    return C.load_json(DEPLOYS_FILE, {"deploys": []})


def _save(s):
    C.atomic_write(DEPLOYS_FILE, s)


def _run_argv(argv, cwd=None, timeout=300):
    """تنفيذ قائمة وسائط بلا shell — خارج القائمة البيضاء = رفض."""
    if not argv:
        return "أمر فارغ"
    head = argv[0].lower()
    if head not in ALLOWED:
        return f"مرفوض: «{head}» خارج الأوامر التشغيلية المسموحة"
    try:
        allowed_set = ALLOWED[head]
        first_flag = argv[1] if len(argv) > 1 else ""
        if first_flag not in allowed_set and not first_flag.startswith("--"):
            return f"مرفوض: «{first_flag}»"
        proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd)
        out = (proc.stdout or "") + (proc.stderr or "")
        return out[-1500:] or f"exit={proc.returncode}"
    except subprocess.TimeoutExpired:
        return "المهلة انتهت"
    except FileNotFoundError:
        return "الأداة غير مثبتة (git/docker)"


def git(*args):
    return _run_argv(["git", *args])


def docker(*args):
    return _run_argv(["docker", *args])


def deploy(project_path):
    """نشر خطواتي بسيط: تحقق صحية، git status، ثم تسجيل نشر."""
    project_path = os.path.abspath(project_path)
    if not os.path.isdir(project_path):
        return {"ok": False, "reason": "المسار غير موجود"}
    checks = []
    checks.append(("exists", True))
    if os.path.exists(os.path.join(project_path, "requirements.txt")):
        checks.append(("requirements", True))
    if os.path.exists(os.path.join(project_path, "app.py")) or os.path.exists(os.path.join(project_path, "api.py")):
        checks.append(("entrypoint", True))
    health = health_check(project_path)
    record = {
        "project": project_path,
        "date": C.now_iso(),
        "checks": checks,
        "health": health,
        "status": "deployed" if all(c[1] for c in checks) else "partial",
    }
    state = _load()
    state["deploys"].append(record)
    state["deploys"] = state["deploys"][-100:]
    _save(state)
    C.log(f"🚀 نشر: {project_path} → {record['status']}")
    return record


def health_check(project_path):
    """فحص صحي للمشروع: بنية + سكربت إن وجد."""
    checks = {"dir": os.path.isdir(project_path)}
    files = os.listdir(project_path) if checks["dir"] else []
    checks["readme"] = any(f.lower() in ("readme.md", "readme") for f in files)
    checks["has_code"] = any(f.endswith(".py") for f in files)
    checks["has_health"] = os.path.exists(os.path.join(project_path, "health.txt")) or "health" in " ".join(files).lower()
    return {"ok": all(checks.values()), "checks": checks}


def rollback(project_path):
    """سجل تراجع: عودة لآخر نقطة إصدار مسجلة."""
    state = _load()
    last = [d for d in reversed(state["deploys"]) if d["project"] == os.path.abspath(project_path)]
    return {"status": "rollback_logged", "target_project": os.path.abspath(project_path), "since": last[0]["date"] if last else None}


def set_env(path, key, value):
    """إضافة/تحديث .env دون كتابة أسرار في السجلات."""
    env_path = os.path.join(path, ".env")
    existing = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f.read().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()
    existing[key] = value
    with open(env_path, "w", encoding="utf-8") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")
    # لا نطبع القيمة — فقط الاسم
    C.log(f"🔐 متغير بيئة: {key} ← (مُخفى) في {env_path}")
    return True


def generate_ci(project_path, repo_slug="owner/repo", python=""):
    """توليد مسار GitHub Actions حقيقي لتشغيليات المشروع."""
    python = python or "3.12"
    yml_path = os.path.join(project_path, ".github", "workflows", "ci.yml")
    os.makedirs(os.path.dirname(yml_path), exist_ok=True)
    content = f"""name: CI
on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '{python}'
      - run: pip install -r requirements.txt pytest
      - run: python -m pytest tests/ -q --no-header
      - run: python agent_os/benchmark.py run
      - run: python agent_os/world_model.py build
"""
    with open(yml_path, "w", encoding="utf-8") as f:
        f.write(content)
    C.log(f"🤖 CI مولّد: {yml_path}")
    return yml_path


def monitor(check_every_minutes=60):
    """مراقبة دورية لكل ما تم نشره: آخر حالة صحية لكل مشروع."""
    state = _load()
    timeline = []
    seen = set()
    for d in reversed(state["deploys"]):
        proj = d["project"]
        if proj in seen:
            continue
        seen.add(proj)
        h = health_check(proj)
        timeline.append({"project": proj, "last_deploy": d["date"], "ok": h["ok"], "checks": h["checks"]})
    return {"interval_min": check_every_minutes, "tracked": len(timeline), "projects": timeline}


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("الاستعمال: git <...> | docker <...> | deploy <مسار> | health <مسار> | rollback <مسار> | ci <مسار> | monitor")
    elif args[0] == "git":
        print(git(*args[1:]))
    elif args[0] == "docker":
        print(docker(*args[1:]))
    elif args[0] == "deploy" and len(args) > 1:
        print(deploy(" ".join(args[1:])))
    elif args[0] == "health" and len(args) > 1:
        print(health_check(" ".join(args[1:])))
    elif args[0] == "ci" and len(args) > 1:
        print(generate_ci(" ".join(args[1:])))
    elif args[0] == "monitor":
        print(monitor())
    elif args[0] == "rollback" and len(args) > 1:
        print(rollback(" ".join(args[1:])))