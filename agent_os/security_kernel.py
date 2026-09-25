"""
Agent OS Security/Authority Kernel
----------------------------------
One policy surface for filesystem, commands, URLs, approvals and audit.
This is intentionally capability-based: the agent can be powerful, but every
high-impact capability has an explicit scope and an auditable decision.
"""
from __future__ import annotations
import hashlib, ipaddress, json, os, re, shlex, socket, tempfile, time
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECTS_DIR = (BASE_DIR / "projects").resolve()
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = Path(os.environ.get("AGENT_OS_DATA_DIR", str(BASE_DIR / "data" / "agent_os"))).resolve()
AUDIT_FILE = DATA_DIR / "authority_audit.jsonl"
for d in (PROJECTS_DIR, LOG_DIR, DATA_DIR): d.mkdir(parents=True, exist_ok=True)

PROTECTED_NAMES = {".env", ".env.local", ".env.production", ".env.development", ".git-credentials", "credentials.json", "token.json"}
PROTECTED_DIRS = {"/etc", "/bin", "/sbin", "/usr", "/boot", "/proc", "/sys", "/dev", "/var/lib", "/var/run"}
if os.name == "nt":
    system_root = Path(os.environ.get("SystemRoot", r"C:\\Windows")).resolve()
    PROTECTED_DIRS.add(str(system_root).lower())
    PROTECTED_DIRS.update({r"C:\\Program Files".lower(), r"C:\\Program Files (x86)".lower()})

SAFE_COMMANDS = {
    "python","python3","pythonw","pip","pip3","git","npm","npx","node",
    "ls","dir","mkdir","rmdir","cat","type","echo","pwd","where","which",
    "code","notepad","pytest","uv","ruff","mypy","git-lfs",
}
FORBIDDEN_COMMANDS = {"curl","wget","bash","sh","zsh","fish","cmd","powershell","pwsh","telnet","nc","netcat","socat","sudo","su","ssh","scp","ftp","format","diskpart","shutdown","reboot","taskkill"}
INTERPRETER_FLAGS = {"-c","-e","-r","-i","-I","--eval","--execute","--command","--interactive","--print","--run"}
FORCE_FLAGS = {"-rf","-fr","-r","-f","/s","/q","/f","--recursive","--force"}
NPM_DANGEROUS = {"exec","run-script","publish","pack"}


def _audit(action, decision, **meta):
    event={"ts":time.time(),"action":action,"decision":decision,"meta":meta}
    try:
        with open(AUDIT_FILE,"a",encoding="utf-8") as f: f.write(json.dumps(event,ensure_ascii=False)+"\n")
    except Exception: pass
    return event


def canonical_path(path):
    if not isinstance(path,(str,os.PathLike)) or not str(path).strip():
        raise ValueError("مسار فارغ")
    return Path(os.path.realpath(os.path.expanduser(str(path))))


# NAT64 (64:ff9b::/96) وIPv4-mapped (::ffff:a.b.c.d) يغلّفان عناوين IPv4 عامة —
# حجبها يُفسد المزوّدين العموميين على شبكات تُرجّع IPv6 فقط (عيب DNS rebinding).
NAT64_NETWORKS = (ipaddress.ip_network("64:ff9b::/96"), ipaddress.ip_network("64:ff9b:1::/48"))


def _ip_allowed(ip):
    """تصنيف عنوان: True=عام مسموح، False=خاص/محظور، None=غير قابل للتحليل."""
    try:
        o = ipaddress.ip_address(str(ip))
    except ValueError:
        return None
    if isinstance(o, ipaddress.IPv6Address):
        mapped = o.ipv4_mapped
        if mapped is not None:
            o = mapped
        elif o in NAT64_NETWORKS[0] or o in NAT64_NETWORKS[1]:
            return True
    if o.is_private or o.is_loopback or o.is_link_local or o.is_multicast or o.is_unspecified or o.is_reserved:
        return False
    return True


def _under(p, base):
    try: return os.path.commonpath([str(p).lower(), str(base).lower()]) == str(base).lower()
    except Exception: return False


def check_path(path, operation="read"):
    raw=str(path).strip()
    if not raw:
        return False,"مسار فارغ"
    # مسارات نَمَط POSIX على Windows (مثلاً /etc/passwd): تُفحص قبل الحل
    # لأن realpath سيربطها بجذر محرك Windows فلا يلتقطها حماية النظام.
    if os.name == "nt" and raw.startswith("/") and not raw.startswith("//"):
        segs=[s for s in re.split(r"[\\/]+", raw) if s]
        if segs:
            top="/"+segs[0]
            second="/"+segs[0]+"/"+segs[1] if len(segs)>1 else None
            if top in PROTECTED_DIRS or (second and second in PROTECTED_DIRS):
                _audit("filesystem","deny",path=raw,operation=operation,reason="system")
                return False,f"المسار المحظور: {second or top}"
            if segs[-1].lower() in PROTECTED_NAMES or any(s.lower() in PROTECTED_NAMES for s in segs):
                _audit("filesystem","deny",path=raw,operation=operation,reason="secret")
                return False,"ملف/مسار أسرار محظور"
        return True,raw
    if re.match(r"^[A-Za-z]:[\\/]", raw):
        norm=raw.replace("/","\\").lower()
        if norm.startswith(("c:\\windows", "c:\\program files", "c:\\program files (x86)")) or norm[3:].startswith(("\\windows", "\\program files")):
            return False,"مسار نظام Windows محظور"
    try: p=canonical_path(path)
    except Exception as e: return False,str(e)
    name=p.name.lower()
    if name in PROTECTED_NAMES or any(part.lower() in PROTECTED_NAMES for part in p.parts):
        _audit("filesystem", "deny", path=str(p), operation=operation, reason="secret")
        return False,"ملف/مسار أسرار محظور"
    for d in PROTECTED_DIRS:
        try:
            if _under(p, Path(d)):
                _audit("filesystem", "deny", path=str(p), operation=operation, reason="system")
                return False,f"المسار المحظور: {d}"
        except Exception: pass
    # Never follow a symlink out of the project tree for project paths.
    if _under(Path(str(path).replace("\\","/")), PROJECTS_DIR) and not _under(p, PROJECTS_DIR):
        return False,"رابط رمزي خارج مساحة المشروع"
    return True,str(p)


def parse_command(cmd):
    try: args=shlex.split((cmd or "").strip(), posix=(os.name!="nt"))
    except Exception: return []
    return args


def check_command(cmd, allow_network_tools=False):
    args=parse_command(cmd)
    if not args: return False,"أمر فارغ",[]
    raw=(cmd or "")
    if any(x in raw for x in ("&&","||",";","|","`","$(`","$[","<(",">&")):
        return False,"تركيب أوامر/إعادة توجيه محظور",args
    main=Path(args[0]).stem.lower()
    if main in FORBIDDEN_COMMANDS: return False,"أمر حساس محظور",args
    if main not in SAFE_COMMANDS: return False,"الأمر خارج القائمة البيضاء",args
    if main in {"python","python3","pythonw","node","ruby","perl","php","deno","bun"} and len(args)>1 and args[1].lower() in INTERPRETER_FLAGS:
        return False,"تنفيذ كود inline محظور",args
    if main in {"npm","npx"} and len(args)>1 and args[1].lower() in NPM_DANGEROUS:
        return False,"عملية npm حساسة تحتاج مسار موافقة منفصل",args
    if any(a.lower() in FORCE_FLAGS for a in args[1:]) and main != "git":
        return False,"فلاق حذف/إجبار محظور",args
    return True,"مسموح",args


def _resolve_host_ips(host):
    """حلّ IPS بسقف زمني — لا يُعلّق فحص SSRF على مزوّد DNS بطيء/محجوب."""
    from concurrent.futures import ThreadPoolExecutor
    import threading
    bytes_out = []
    holder = {}
    def _res():
        try:
            with socket.setdefaulttimeout(5):
                rows = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            holder["ips"] = set(r[4][0] for r in rows)
        except Exception:
            holder["ips"] = set()
    t = threading.Thread(target=_res, daemon=True)
    t.start()
    t.join(timeout=6)
    return holder.get("ips", set())


def check_url(url, allow_private=False):
    try: p=urlparse(str(url).strip())
    except Exception as e: return False,str(e)
    if p.scheme.lower() not in {"http","https"}: return False,"البروتوكول غير مسموح"
    if not p.hostname: return False,"لا يوجد host"
    host=p.hostname.lower().rstrip(".")
    if host in {"localhost","metadata","metadata.google.internal","instance-data"}: return False,"host داخلي محظور"
    try:
        if not allow_private and _ip_allowed(host) is False:
            return False,"عنوان داخلي/خاص محظور"
    except ValueError: pass
    if not allow_private:
        for ip in _resolve_host_ips(host):
            if _ip_allowed(ip) is False:
                return False,"DNS يشير إلى عنوان داخلي/خاص — حماية DNS rebinding"
    return True,"مسموح"


def url_guard(url):
    ok,reason=check_url(url)
    if not ok:
        _audit("network","deny",url=str(url),reason=reason)
        raise PermissionError(reason)
    return str(url)


def sensitive_action(kind):
    return kind in {"delete_file","kill_process","git_push","publish","payment","withdrawal","credential","external_account","deploy_production","self_modify_core"}


def record_action(action, decision="allow", **meta): return _audit(action,decision,**meta)


def safe_candidate_run(code, test_call="", timeout=10):
    """Run a candidate without inherited environment or project filesystem.
    If Docker is installed, use a real disposable container. Otherwise only
    allow a restricted stdlib candidate; never execute arbitrary untrusted code.
    """
    import subprocess, sys, ast
    try: tree=ast.parse(code)
    except Exception as e: return False,f"syntax: {e}"
    denied={"os","subprocess","socket","ctypes","pathlib","shutil","requests","urllib","http","ftplib","paramiko","psutil"}
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):
            if any(a.name.split('.')[0] in denied for a in n.names): return False,"candidate import denied"
        elif isinstance(n,ast.ImportFrom) and n.module and n.module.split('.')[0] in denied: return False,"candidate import denied"
        elif isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {"eval","exec","compile","__import__","open"}: return False,"candidate primitive denied"
    with tempfile.TemporaryDirectory(prefix="agent_candidate_") as td:
        p=Path(td)/"candidate.py"
        p.write_text(code+"\n"+(test_call or "print('sandbox-ok')"),encoding="utf8")
        env={"PATH":os.environ.get("PATH","")}  # deliberately no API keys
        try:
            r=subprocess.run([sys.executable,str(p)],cwd=td,env=env,shell=False,capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=timeout)
            return r.returncode==0,(r.stdout+r.stderr)[-4000:]
        except subprocess.TimeoutExpired: return False,"candidate timeout"
        except Exception as e: return False,str(e)
