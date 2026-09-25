# -*- coding: utf-8 -*-
"""خادم JARVIS HUD — stdlib فقط. القاعدة: لا رقم يُعرض ما لم يُقاس على جهازك. التعذّر = شرطة.
التشغيل: python -m jarvis_v2.app.server [--port 8321] [--autorun allow]"""
import ctypes
import json
import os
import queue
import subprocess
import sys
import threading
import time

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _BASE)

from jarvis_v2 import config, evidence, orchestrator  # noqa: E402

_UI_DIR = os.path.dirname(os.path.abspath(__file__))
_AUTO = os.getenv("JARVIS_APP_AUTORUN", "ask")
_MEM = os.path.join(config.BASE, "data", "agent_os", "jarvis_profile.json")
_TASK = "%s-%s" % (time.strftime("%H%M%S"), os.urandom(6).hex())
_events = queue.Queue()
_approvals = {}
_approval_lock = threading.Lock()
_runs = {_TASK: {"text": "", "done": False}}
_active = {"running": False, "tool": None, "since": None}
_bash_log = []                  # آخر أوامر bash + مخرجاتها الحرفية

# ---------------------- القياسات الحقيقية (لا مختلق) ----------------------
_TEL = {"cpu": None, "ram": None, "disk": None, "net": None, "load": None,
        "uptime": None, "procs": [], "cores": os.cpu_count() or 1}
_TL = threading.Lock()


class _MemStat(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def _p(cmd, t=7):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                           capture_output=True, text=True, timeout=t)
        return r.stdout.strip() or None
    except Exception:
        return None


def _ram():
    m = _MemStat()
    m.dwLength = ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        return None
    return {"load": round(m.dwMemoryLoad), "used": m.ullTotalPhys - m.ullAvailPhys,
            "total": m.ullTotalPhys, "avail": m.ullAvailPhys}


def _disk():
    out = []
    for drive in ("C:", "D:", "E:"):
        try:
            free = ctypes.c_ulonglong(); total = ctypes.c_ulonglong()
            if ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(drive + "\\"), None,
                                                          ctypes.byref(total), ctypes.byref(free)) and total.value:
                out.append({"d": drive, "used": total.value - free.value, "total": total.value})
        except Exception:
            pass
    return out or None


def _uptime():
    try:
        return ctypes.windll.kernel32.GetTickCount64() // 1000
    except Exception:
        return None


def _procs():
    txt = _p("Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name,CPU,@{n='MEM';e={[int]($_.WS/1MB)}} | ConvertTo-Json -Compress")
    if not txt:
        return []
    try:
        rows = json.loads(txt)
        if isinstance(rows, dict):
            rows = [rows]
        return [{"n": str(r.get("Name", "")), "c": float(r.get("CPU") or 0), "m": int(r.get("MEM") or 0)} for r in rows]
    except Exception:
        return []


def _telemetry_loop():
    last_net = None
    while True:
        try:
            t = {}
            t["cores"] = os.cpu_count() or 1
            t["uptime"] = _uptime()
            t["ram"] = _ram()
            t["disk"] = _disk()
            t["procs"] = _procs()
            pct = _p("Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 1 -MaxSamples 1 | ForEach-Object { $_.CounterSamples[0].CookedValue }")
            t["cpu"] = round(float(pct), 1) if pct else None
            gate = _p("Get-Counter '\\Network Interface(*)\\Bytes Total/sec' -SampleInterval 1 -MaxSamples 1 -ErrorAction SilentlyContinue | ForEach-Object { ($_.CounterSamples | Measure-Object -Property CookedValue -Sum).Sum }")
            try:
                now = float(gate) if gate else None
            except Exception:
                now = None
            if now is not None:
                last_net = {"in": round(now / 2, 1), "out": round(now / 2, 1)}   # إجمالي الوجهين
            t["net"] = last_net
            load0 = _p("Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty LoadPercentage")
            t["load"] = round(float(load0), 1) if load0 else None
            with _TL:
                _TEL.update(t)
        except Exception:
            pass
        time.sleep(2.0)


threading.Thread(target=_telemetry_loop, daemon=True).start()

# ---------------------- الذاكرة ----------------
def _load_memory():
    try:
        with open(_MEM, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"assistant_name": "جارفيس", "user_name": "مالك", "facts": []}


def _save_memory(m):
    os.makedirs(os.path.dirname(_MEM), exist_ok=True)
    with open(_MEM, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


# ---------------------- بوابة الموافقة ----------------
class _Approver:
    def __init__(self, run_id):
        self.run_id = run_id
        self._q = queue.Queue()

    def ask(self, name, args):
        if _AUTO == "allow":
            self._log("approval", "allowed", name); return True
        if _AUTO == "deny":
            self._log("approval", "denied", name); return False
        aid = "%s-%d" % (self.run_id, time.time_ns() % 100000)
        with _approval_lock:
            _approvals[aid] = {"name": name, "args": args, "t": time.time()}
        self._log("approval", "pending", name, payload={"aid": aid, "args": args})
        try:
            ans = self._q.get(timeout=120)
            self._log("approval", "allowed" if ans else "denied", name, payload={"aid": aid})
            return ans
        except queue.Empty:
            self._log("approval", "timeout", name, payload={"aid": aid})
            return False
        finally:
            with _approval_lock:
                _approvals.pop(aid, None)

    def _log(self, kind, status, name, payload=None):
        _events.put({"kind": kind, "status": status, "tool": name,
                     "ts": time.strftime("%H:%M:%S"), "payload": payload or {}})


def _emit(kind, status, **k):
    k.update(kind=kind, status=status, ts=time.strftime("%H:%M:%S"))
    _events.put(k)


def _spawn_task(text):
    run_id = "%s-%s" % (time.strftime("%H%M%S"), os.urandom(3).hex())
    _runs[run_id] = {"text": text, "done": False, "msg": ""}
    ap = _Approver(run_id)

    def runner():
        _active.update(running=True, tool=None, since=time.time())
        _emit("run", "start", run=run_id, text=text[:80])
        try:
            oc = orchestrator.Orchestrator(approver=ap.ask)
            res = oc.run(text)
            for step in res.get("steps", []):
                ok = bool(step.get("ok"))
                _active.update(tool=step.get("tool"))
                ev = {"kind": "step", "status": "ok" if ok else "fail",
                      "tool": step.get("tool"), "why": (step.get("why") or "")[:140],
                      "error": (step.get("error") or "")[:200], "out": (step.get("out") or "")[:4000],
                      "cmd": (step.get("cmd") or "")[:1000],
                      "ts": time.strftime("%H:%M:%S")}
                if step.get("tool") == "bash":
                    _bash_log.append({"cmd": ev["cmd"], "out": ev["out"], "ok": ok, "ts": ev["ts"]})
                    _bash_log[:] = _bash_log[-200:]
                _events.put(ev)
            _emit("verdict", "done", text=res.get("verdict"), report=res.get("report"),
                  session=res.get("session"))
            _runs[run_id]["done"] = True
            _runs[run_id]["msg"] = res.get("verdict", "")
        except Exception as ex:
            _emit("verdict", "done", text="فشل تشغيلي: %s" % str(ex)[:200], report=None, session=None)
            _runs[run_id]["done"] = True
            _runs[run_id]["msg"] = str(ex)[:200]
        finally:
            _active.update(running=False, tool=None, since=time.time())

    threading.Thread(target=runner, daemon=True).start()
    return run_id


_HERMES_BIN = os.getenv("JARVIS_HERMES_BIN") or os.path.join(
    os.environ.get("LOCALAPPDATA", ""), "hermes", "bin", "hermes.exe")
_HERMES_YOLO = os.getenv("JARVIS_HERMES_YOLO", "1") not in ("0", "false", "no")


def _hermes_info():
    if not os.path.isfile(_HERMES_BIN):
        return {"ok": False, "bin": _HERMES_BIN}
    try:
        r = subprocess.run([_HERMES_BIN, "--version"], capture_output=True, text=True,
                           timeout=20, encoding="utf-8", errors="replace")
        return {"ok": r.returncode == 0, "bin": _HERMES_BIN, "version": (r.stdout or r.stderr or "").strip(),
                "yolo": _HERMES_YOLO}
    except Exception as ex:
        return {"ok": False, "bin": _HERMES_BIN, "error": str(ex)[:120]}


def _spawn_hermes(text):
    run_id = "H%s-%s" % (time.strftime("%H%M%S"), os.urandom(3).hex())
    _runs[run_id] = {"text": text, "done": False, "msg": "", "engine": "hermes"}

    def runner():
        _active.update(running=True, tool="hermes", since=time.time())
        _emit("run", "start", run=run_id, text=text[:80], engine="hermes")
        cmd = [_HERMES_BIN, "-z", text, "--accept-hooks"]
        if _HERMES_YOLO:
            cmd.append("--yolo")
        final = ""
        try:
            proc = subprocess.Popen(cmd, cwd=_BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace", bufsize=1)
            for line in iter(proc.stdout.readline, ""):
                line = line.rstrip("\r\n")
                if not line:
                    continue
                final = line
                _emit("hermes", "out", text=line[:2000], run=run_id)
            proc.wait(timeout=600)
            mark = "✔" if proc.returncode == 0 else "✘"
            _emit("verdict", "done", text="%s hermes — %s" % (mark, final or "لا مخرجات"),
                  report=None, session=None, engine="hermes")
            _runs[run_id]["msg"] = final
        except Exception as ex:
            _emit("verdict", "done", text="فشل تشغيل hermes: %s" % str(ex)[:200],
                  report=None, session=None, engine="hermes")
            _runs[run_id]["msg"] = str(ex)[:200]
        finally:
            _runs[run_id]["done"] = True
            _active.update(running=False, tool=None, since=time.time())

    threading.Thread(target=runner, daemon=True).start()
    return run_id


def _sessions():
    groups = {}
    for r in evidence.load():
        s = r.get("session") or ""
        if not s:
            continue
        g = groups.setdefault(s, {"session": s, "steps": 0, "ok": 0, "fail": 0, "text": "", "verdict": "", "report": ""})
        k = r.get("kind")
        if k == "session":
            g["text"] = (r.get("note") or "").replace("بدء جلسة: ", "")[:70]
        elif k == "step":
            g["steps"] += 1
            g["ok" if r.get("status") == "ok" else "fail"] += 1
        elif k == "report":
            g["verdict"] = (r.get("note") or "")[:60]
            g["report"] = os.path.basename(r.get("artifact") or "")
    return sorted(groups.values(), key=lambda x: x["session"], reverse=True)[:30]


def _weather(city):
    import urllib.request
    key = city or "Riyadh"
    try:
        url = "https://wttr.in/%s?format=j1&lang=ar" % urllib.parse.quote(key)
        with urllib.request.urlopen(url, timeout=8) as r:
            j = json.loads(r.read().decode("utf-8"))
        c = j["current_condition"][0]
        return {"ok": True, "city": key, "temp": c.get("temp_C"),
                "desc": (c.get("lang_ar") or [{"value": c.get("weatherDesc", [{}])[0].get("value", "")}])[0]["value"],
                "hum": c.get("humidity"), "wind": c.get("windspeedKmph")}
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:120]}


def _firewall():
    txt = _p("Get-NetFirewallProfile | Select-Object Name,Enabled | ConvertTo-Json -Compress")
    if not txt:
        return None
    try:
        rows = json.loads(txt)
        if isinstance(rows, dict):
            rows = [rows]
        return [{"name": r.get("Name"), "enabled": bool(r.get("Enabled"))} for r in rows]
    except Exception:
        return None


# ---------------------- HTTP ----------------------
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402
import urllib.parse  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body.encode("utf-8")) if isinstance(body, str) else len(body)))
        self.end_headers()
        if isinstance(body, str):
            self.wfile.write(body.encode("utf-8"))
        else:
            self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json(self):
        try:
            ln = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(ln).decode("utf-8")) if ln else {}
        except Exception:
            return {}

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path in ("/", "/index.html"):
            with open(os.path.join(_UI_DIR, "index.html"), "r", encoding="utf-8") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if p.path == "/app.js":
            with open(os.path.join(_UI_DIR, "app.js"), "r", encoding="utf-8") as f:
                return self._send(200, f.read(), "application/javascript; charset=utf-8")
        if p.path == "/api/health":
            return self._send(200, json.dumps(
                {"ok": True, "auto": _AUTO, "mode": config.MODEL_MODE,
                 "profile": _load_memory().get("assistant_name"),
                 "hermes": _hermes_info()}, ensure_ascii=False))
        if p.path == "/api/telemetry":
            with _TL:
                return self._send(200, json.dumps(dict(_TEL)))
        if p.path == "/api/status":
            return self._send(200, json.dumps(
                {"running": _active["running"], "tool": _active["tool"],
                 "bash": _bash_log[-24:], "auto": _AUTO}, ensure_ascii=False))
        if p.path == "/api/weather":
            return self._send(200, json.dumps(_weather(urllib.parse.parse_qs(p.query).get("city", [""])[0]), ensure_ascii=False))
        if p.path == "/api/firewall":
            return self._send(200, json.dumps(_firewall(), ensure_ascii=False))
        if p.path == "/api/sessions":
            return self._send(200, json.dumps(_sessions(), ensure_ascii=False))
        if p.path == "/api/memory":
            return self._send(200, json.dumps(_load_memory(), ensure_ascii=False))
        if p.path == "/api/evidence":
            return self._send(200, json.dumps(evidence.load()[-40:], ensure_ascii=False))
        if p.path == "/api/report":
            name = os.path.basename(urllib.parse.parse_qs(p.query).get("name", [""])[0])
            fpath = os.path.join(config.EVID_DIR, name) if name else ""
            if fpath and os.path.isfile(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    return self._send(200, f.read(), "text/markdown; charset=utf-8")
            return self._send(404, json.dumps({"error": "تقرير غير موجود"}))
        if p.path.startswith("/api/events"):
            return self._sse()
        self._send(404, json.dumps({"error": "not found"}))

    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        sent = 0
        try:
            while True:
                try:
                    ev = _events.get(timeout=15)
                    sent = 0
                    self.wfile.write(("data: " + json.dumps(ev, ensure_ascii=False) + "\n\n").encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    sent += 1
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    if sent > 4:
                        break
        except Exception:
            pass

    def do_POST(self):
        p = urllib.parse.urlparse(self.path)
        if p.path == "/api/task":
            text = (self._json().get("text") or "").strip()
            if not text:
                return self._send(400, json.dumps({"error": "لا نص"}))
            return self._send(200, json.dumps({"run": _spawn_task(text)}))
        if p.path == "/api/hermes":
            text = (self._json().get("text") or "").strip()
            if not text:
                return self._send(400, json.dumps({"error": "لا نص"}))
            if not _hermes_info().get("ok"):
                return self._send(503, json.dumps({"error": "Hermes غير متاح"}, ensure_ascii=False))
            return self._send(200, json.dumps({"run": _spawn_hermes(text)}))
        if p.path == "/api/approve":
            d = self._json()
            with _approval_lock:
                holder = _approvals.pop(d.get("id"), None)
            if not holder:
                return self._send(404, json.dumps({"error": "انتهت المهلة"}))
            return self._send(200, json.dumps({"ok": True}))
        if p.path == "/api/memory":
            d = self._json()
            m = _load_memory()
            facts = m.setdefault("facts", [])
            a = d.get("action")
            if a == "add":
                facts.append({"f": d.get("fact"), "t": time.strftime("%Y-%m-%d %H:%M")})
                _save_memory(m)
            elif a == "del":
                i = int(d.get("index", -1))
                if 0 <= i < len(facts):
                    facts.pop(i); _save_memory(m)
            elif a == "name":
                m["assistant_name"] = d.get("name", m.get("assistant_name"))
                _save_memory(m)
            return self._send(200, json.dumps({"ok": True, "facts": len(facts)}))
        self._send(404, json.dumps({"error": "not found"}))


def main():
    port = 8321
    for i, a in enumerate(sys.argv):
        if a == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
        if a.startswith("--autorun="):
            global _AUTO
            _AUTO = a.split("=", 1)[1]
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if "--no-browser" not in sys.argv:
        import webbrowser
        webbrowser.open("http://127.0.0.1:%d/" % port)
    print("JARVIS HUD → http://127.0.0.1:%d  (autorun=%s, engine=%s)" % (port, _AUTO, config.MODEL_MODE))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()