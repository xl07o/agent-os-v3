"""
jarvis.py — JARVIS: مساعد الذكاء الاصطناعي الكامل
=====================================================
نقطة الدخول الرئيسية لنظام JARVIS.
يشغّل API server + يفتح الواجهة في المتصفح.

التشغيل:
  python jarvis.py          # شغّل كل شيء
  python jarvis.py --cli    # وضع terminal فقط
  python jarvis.py --status # حالة النظام
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from dotenv import load_dotenv
load_dotenv(_HERE / ".env")

import brain
import memory_bank
import domain_learner as _dl

PORT = int(os.getenv("SELFRUNNER_PORT", "8082"))
UI_FILE = _HERE / "jarvis_ui" / "index.html"

# ===== حالة عامة مشتركة =====
_state = {
    "tasks": [],
    "chat_history": [],
    "domains": {
        "trading": 0,
        "coding": 80,
        "research": 45,
        "data": 20,
    },
}
_state_lock = threading.Lock()
_brain_session = None


def _get_brain():
    global _brain_session
    if _brain_session is None:
        _brain_session = brain.Brain(
            "أنت JARVIS — مساعد ذكاء اصطناعي متكامل. "
            "أجب باختصار ووضوح بالعربية. "
            "كن ذكياً وعملياً كجارفيس من Iron Man."
        )
    return _brain_session


def _get_status() -> dict:
    """يجمع كل بيانات الحالة لواجهة JARVIS."""
    status = {}

    # العقول
    engines_raw = brain.available_engines()
    all_engines = [
        {"id": e["id"], "name": e["name"], "available": True}
        for e in engines_raw
    ]
    for e in brain.ENGINES_ALL:
        if not any(x["id"] == e["id"] for x in all_engines):
            all_engines.append({"id": e["id"], "name": e["name"], "available": False})
    status["engines"] = all_engines
    status["model"] = os.getenv("SELFRUNNER_MODEL", "llama3.1")

    # الذاكرة
    try:
        mem_stats = memory_bank.stats()
        status["memory"] = mem_stats
    except Exception:
        status["memory"] = {}

    # ملفات Obsidian vault
    try:
        vault_dir = _HERE / "obsidian_vault"
        vault_count = sum(1 for _ in vault_dir.rglob("*.md")) if vault_dir.exists() else 0
        status["vault_files"] = vault_count
    except Exception:
        status["vault_files"] = 0

    # مجالات التعلم
    with _state_lock:
        status["domains"] = dict(_state["domains"])

    # إتقان
    try:
        mastery_state = _HERE / "mastery_state.json"
        if mastery_state.exists():
            ms = json.loads(mastery_state.read_text(encoding="utf-8"))
            xp = ms.get("total_xp", 0)
            pct = min(100, int(xp / 10))
            status["mastery_pct"] = pct
        else:
            status["mastery_pct"] = 0
    except Exception:
        status["mastery_pct"] = 0

    # تداول
    try:
        from trading import strategy_agent, alpaca_client
        snap = strategy_agent.pipeline_snapshot()
        if snap.get("has_run"):
            status["trading"] = {
                "mode": alpaca_client.mode(),
                "factor": snap.get("current_factor_label", "—"),
                "sharpe": snap.get("honest_sharpe", "—"),
                "pnl": "—",
                "iters": snap.get("iterations_total", 0),
            }
        else:
            status["trading"] = {"mode": "لم يبدأ", "factor": "—", "sharpe": "—", "pnl": "—", "iters": 0}
    except Exception:
        status["trading"] = {"mode": "غير متاح", "factor": "—", "sharpe": "—", "pnl": "—", "iters": 0}

    # مالية
    try:
        from agent_os import finance_intel
        r = finance_intel.daily_report()
        status["finance"] = {
            "income_today_usd": r.get("income_today_usd", 0),
            "spent_today_usd": r.get("spent_today_usd", 0),
            "net_usd": round(r.get("income_today_usd", 0) - r.get("spent_today_usd", 0), 4),
            "free_savings_usd": r.get("free_savings_usd", 0),
            "budget_remaining_today": r.get("budget_remaining_today", 2.0),
        }
    except Exception:
        status["finance"] = {}

    # مهام أخيرة
    with _state_lock:
        status["tasks"] = list(_state["tasks"][-8:])

    return status


def _process_chat(message: str) -> str:
    """يعالج رسالة المستخدم ويرد."""

    # أوامر خاصة
    msg_low = message.strip().lower()

    if msg_low in {"status", "حالة", "وضع"}:
        s = _get_status()
        engines_on = sum(1 for e in s.get("engines", []) if e["available"])
        return (
            f"النظام يعمل ✅\n"
            f"العقول: {engines_on} متاح\n"
            f"الذاكرة: {s.get('memory', {}).get('total_items', 0)} معلومة\n"
            f"Obsidian: {s.get('vault_files', 0)} ملف\n"
            f"التداول: {s.get('trading', {}).get('mode', '—')}"
        )

    if msg_low.startswith("تعلم") or msg_low.startswith("learn"):
        parts = message.split(maxsplit=1)
        domain_name = parts[1] if len(parts) > 1 else "البرمجة"
        _add_task(f"تعلم: {domain_name}", running=True)
        thread = threading.Thread(
            target=_run_learning, args=(domain_name,), daemon=True
        )
        thread.start()
        return f"بدأت التعلم العميق في مجال '{domain_name}' 📚 — سأحدّث لوحة التحكم تلقائياً"

    if msg_low.startswith("//بناء") or msg_low.startswith("بناء لوحة"):
        req = message.replace("//بناء", "").replace("بناء لوحة", "").strip()
        try:
            import chat_cli as _cc
            result = _cc._build_dashboard(req or message)
            _add_task(f"بناء لوحة: {req[:40]}", done=True)
            return result
        except Exception as e:
            return f"خطأ في البناء: {e}"

    if msg_low.startswith("//تداول") or msg_low.startswith("تداول"):
        try:
            import chat_cli as _cc
            sub = message.replace("//تداول", "").replace("تداول", "").strip()
            return _cc._trading(sub)
        except Exception as e:
            return f"خطأ التداول: {e}"

    if msg_low.startswith("تذكر"):
        content = message[3:].strip()
        if content:
            memory_bank.remember(content[:80], content, importance=0.8, tags=["user_fact"])
            return f"حفظتُ: {content[:60]}... ✅"

    # رد عادي من العقل
    b = _get_brain()
    try:
        # استرجاع الذاكرة ذات الصلة
        mem_ctx = memory_bank.recall_as_context(message)
        prompt = message
        if mem_ctx:
            prompt = f"[ذاكرة ذات صلة]\n{mem_ctx}\n\nسؤال: {message}"

        out, engine = b.ask(prompt)
        if engine in (None, "none"):
            return "⚠️ لا يوجد عقل متاح حالياً — تأكد أن Ollama شغّال"

        # حفظ في الذاكرة
        if len(str(out)) > 20:
            memory_bank.remember(
                message[:80], str(out)[:400],
                importance=0.5, tags=["jarvis_chat"]
            )
        return str(out).strip()
    except Exception as e:
        return f"خطأ: {e}"


def _add_task(title: str, done=False, running=False):
    with _state_lock:
        _state["tasks"].append({
            "title": title[:60],
            "done": done,
            "running": running,
            "ts": time.strftime("%H:%M"),
        })
        if len(_state["tasks"]) > 20:
            _state["tasks"] = _state["tasks"][-20:]


def _run_learning(domain_name: str):
    """يشغّل التعلم العميق في الخلفية ويحدّث الحالة."""
    domain_key = {
        "تداول": "trading", "تداول الأسهم": "trading",
        "كريبتو": "trading", "بيتكوين": "trading",
        "برمجة": "coding", "python": "coding", "كود": "coding",
        "بحث": "research", "تحليل": "data", "بيانات": "data",
    }.get(domain_name.strip().lower(), "research")

    learner = _dl.get_domain_learner(domain_name)
    result = learner.learn_until_ready(
        f"تنفيذ مهمة متقدمة في {domain_name}",
        max_cycles=5
    )
    with _state_lock:
        _state["domains"][domain_key] = result["final_level"]

    _add_task(f"تعلم {domain_name}: {result['final_level']}%", done=True)


# ===== HTTP Server =====
class JarvisHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # suppress access logs

    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, mime: str):
        try:
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(404, str(e))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ("/", "/index.html", "/jarvis"):
            self._send_file(UI_FILE, "text/html; charset=utf-8")

        elif path == "/status":
            self._send_json(_get_status())

        elif path.startswith("/jarvis_ui/"):
            rel = path[len("/jarvis_ui/"):]
            f = _HERE / "jarvis_ui" / rel
            if f.exists() and f.is_file():
                mime = "text/css" if f.suffix == ".css" else "application/javascript"
                self._send_file(f, mime)
            else:
                self.send_error(404)

        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        if path == "/chat":
            try:
                data = json.loads(body.decode("utf-8"))
                message = str(data.get("message", "")).strip()
                if not message:
                    self._send_json({"error": "رسالة فارغة"}, 400)
                    return
                reply = _process_chat(message)
                self._send_json({"reply": reply, "ok": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif path == "/learn":
            try:
                data = json.loads(body.decode("utf-8"))
                domain = str(data.get("domain", "البرمجة")).strip()
                _add_task(f"تعلم: {domain}", running=True)
                t = threading.Thread(target=_run_learning, args=(domain,), daemon=True)
                t.start()
                self._send_json({"ok": True, "message": f"بدأ التعلم في '{domain}'"})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        else:
            self.send_error(404)


def run_server(open_browser: bool = True):
    """يشغّل خادم JARVIS."""
    server = HTTPServer(("localhost", PORT), JarvisHandler)
    url = f"http://localhost:{PORT}"
    print(f"\n{'='*52}")
    print(f"   🤖 JARVIS — موظف الليل")
    print(f"   {'='*46}")
    print(f"   الواجهة:   {url}")
    print(f"   API:       {url}/status")
    print(f"   العقول:    {', '.join(e['id'] for e in brain.available_engines()) or 'لا يوجد'}")
    print(f"{'='*52}\n")

    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nJARVIS أُوقف.")


def cli_mode():
    """وضع terminal تفاعلي."""
    print("\n🤖 JARVIS — وضع CLI")
    print("   اكتب طلبك أو 'exit' للخروج\n")
    while True:
        try:
            raw = input("أنت > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nوداعاً!")
            break
        if raw.lower() in {"exit", "quit", "خروج"}:
            print("وداعاً!")
            break
        if raw:
            reply = _process_chat(raw)
            print(f"JARVIS > {reply}\n")


def print_status():
    s = _get_status()
    engines_on = sum(1 for e in s.get("engines", []) if e["available"])
    print(f"\n🤖 JARVIS — حالة النظام")
    print(f"   العقول المتاحة: {engines_on}/{len(s.get('engines', []))}")
    for e in s.get("engines", []):
        icon = "✅" if e["available"] else "⛔"
        print(f"     {icon} {e['name']}")
    print(f"   الذاكرة: {s.get('memory', {}).get('total_items', 0)} معلومة")
    print(f"   Obsidian vault: {s.get('vault_files', 0)} ملف")
    print(f"   نموذج: {s.get('model', '—')}")
    print(f"   إتقان: {s.get('mastery_pct', 0)}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS — موظف الليل")
    parser.add_argument("--cli", action="store_true", help="وضع CLI فقط")
    parser.add_argument("--status", action="store_true", help="عرض الحالة وخروج")
    parser.add_argument("--no-browser", action="store_true", help="لا تفتح المتصفح")
    args = parser.parse_args()

    if args.status:
        print_status()
    elif args.cli:
        cli_mode()
    else:
        run_server(open_browser=not args.no_browser)
