# -*- coding: utf-8 -*-
# ============================================================================
#  Agent OS · خادم الجسر (Bridge)
#  يربط لوحة التحكم (agent-os-control.html) ببيانات وكيلك الحقيقية.
#
#  • يعمل محلياً فقط على 127.0.0.1 — لا يفتح أي منفذ للإنترنت الخارجي.
#  • يقرأ ملفات JSON الحقيقية من مجلد بيانات الوكيل ويعرضها للّوحة.
#  • يستقبل إجراءاتك (موافقة/إيقاف هدف/مهمة) ويكتبها بأمان.
#  • لا يخزّن ولا يطلب أي كلمة مرور. يخفي قيم مفاتيح API دائماً.
#  • لا يرفع أي تقرير أمني تلقائياً — الرفع يدوي منك دائماً.
#
#  التشغيل:  شغّل ملف  run_site.bat  (أو:  python agent_bridge.py)
#  ثم افتح المتصفح على:  http://127.0.0.1:8787
# ============================================================================

import json, os, sys, io, time, datetime, http.server, socketserver, urllib.parse, threading, re

# ----------------------------------------------------------------------------
#  الإعدادات — عدّل هنا فقط إن لزم
# ----------------------------------------------------------------------------
PORT      = 8787
HOST      = "127.0.0.1"

# مجلد بيانات وكيلك الحقيقي (فيه world_state.json و goals.json ... إلخ)
DATA_DIR  = r"C:\Users\hhdjj\ai-agent\ai-agent-main\data\agent_os"

# ملف اللوحة (نفس مجلد هذا الملف افتراضياً)
HERE      = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(HERE, "agent-os-control.html")

# (اختياري) أمر تشغيل الوكيل عند إرسال مهمة من المحادثة.
# اتركه None ليُحفظ الطلب في صندوق الوارد فقط (الأكثر أماناً).
# مثال لو حبيت تفعّله لاحقاً:
#   AGENT_CMD = ["python", os.path.join(DATA_DIR, "..", "..", "selfrunner.py"), "--task", "{text}"]
AGENT_CMD = None

# آخر كم حدث يُعرض في السجل
EVENTS_TAIL = 60

# ============================================================================
#  محادثة ذكية حقيقية (مثل GPT) — عقل Agent OS الفعلي من جذر المشروع
# ============================================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(DATA_DIR))

CHAT_PERSONA = (
    "أنت Agent OS — عقل اصطناعي خبير وشامل في مساعد آلي متقدم."
    " رد بالعربية ما لم يطلَب غير ذلك، وكن موجزاً لكن دقيقاً."
    " حلّل طلبات المستخدم حقيقياً واذكر ما فهمته ونقاط القوة والملاحظات، ولا تختلق نتائج."
    " قدراتك الفعلية: محرك مكافآت على 6 منصات، إنشاء منتجات، ذاكرة دائمة، أدوات بحث وتقارير."
    " لا تفصح أبداً عن مفاتيح أو أسرار، ولا ترفع أي تقرير أمني تلقائياً (الرفع يدوي من المستخدم)."
)

_CHAT_SESSION = None
_CHAT_MEMORY = None
_CHAT_LOCK = threading.Lock()


def _ensure_chat():
    """يحضّر جلسة العقل مرة واحدة — تبقى حيّة عبر المحادثة كلها (ذكرى متصلة)."""
    global _CHAT_SESSION, _CHAT_MEMORY
    if _CHAT_SESSION is not None:
        return _CHAT_SESSION
    with _CHAT_LOCK:
        if _CHAT_SESSION is not None:
            return _CHAT_SESSION
        os.environ.setdefault("SELFRUNNER_MODE", "fastest")
        sys.path.insert(0, PROJECT_ROOT)
        try:
            import brain
            import memory_bank
        except Exception as e:
            raise RuntimeError("تعذّر تحميل عقل الوكيل: %s" % e)
        _CHAT_SESSION = brain.Brain(CHAT_PERSONA)
        _CHAT_MEMORY = memory_bank
        return _CHAT_SESSION


def _learn_topic(text):
    """يكشف طلب «علّمني/تعلّم X» ويعيد الموضوع، أو None إن لم يكن طلب تعلم."""
    if not text:
        return None
    m = re.match(r"^\s*(تعل[ّ]?م|علمني|علّمني|خله يتعلم|على الوكيل يتعلم)\s*[،,:؛]?\s*(.+)$", text, re.S)
    if m:
        return m.group(2).strip()
    if re.search(r"(تعل[ّ]?م|علّمني|علمني)\s+(أي|شيء|شيئًا|موضوع)[\s،]*(عن)?[\s]*", text):
        return text
    return None


def _ask_chat(text):
    s = _ensure_chat()
    content = text
    try:
        ctx = _CHAT_MEMORY.recall_as_context(text)
        if ctx:
            content = (
                "[خلفية من الذاكرة - قد لا تكون ذات صلة بكل سؤال]\n"
                + ctx
                + "\n\nسؤال المستخدم:\n"
                + text
            )
    except Exception:
        pass
    reply, engine = _brain_ask_capped(s, content)
    reply = str(reply).strip()
    try:
        if len(reply) > 20:
            _CHAT_MEMORY.remember(
                text[:100], reply, importance=0.6, tags=["chat", text.lower()[:50]]
            )
    except Exception:
        pass
    return reply, engine


CHAT_CEILING_SEC = float(os.environ.get("AGENT_OS_CHAT_CEILING", "18"))


def _brain_ask_capped(s, content):
    """محادثة سريعة بسقف زمني صارم: مزود واحد أسرع + مهلة مضمونة.
    لا سلسلة تباطؤ ولا انتظار مفتوح — يرد عوضاً عن الصمت بأسرع جملة.
    (لا ننضم إلى مؤشر الخيط عند المهلة حتى يتحرر الرد فوراً؛ يختتم الخيط وحده)."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _ThreadTimeout
    try:
        ex = ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(s.ask, content, mode="fastest")
        try:
            return fut.result(timeout=CHAT_CEILING_SEC)
        except _ThreadTimeout:
            return (f"(تجاوز الرد {CHAT_CEILING_SEC:.0f} ثانية — أعد صياغة السؤال باختصار)", "timeout")
    except Exception as e:
        return (f"(تعطّل عقل المحادثة: {str(e)[:90]})", "error")

# ============================================================================
#  أدوات مساعدة للقراءة الآمنة
# ============================================================================
def _read_json(name, default):
    """يقرأ ملف JSON من مجلد البيانات، ويرجّع default إن لم يوجد أو تعطّل."""
    path = os.path.join(DATA_DIR, name)
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _read_jsonl_tail(name, n):
    """يقرأ آخر n سطر من ملف JSONL."""
    path = os.path.join(DATA_DIR, name)
    out = []
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-n:]
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    except Exception:
        pass
    out.reverse()  # الأحدث أولاً
    return out

def _full_access_module():
    """استحضار كسول لوحدة الولوج الكامل (جذر المشروع)."""
    sys.path.insert(0, PROJECT_ROOT)
    import agent_os.full_access as fa
    return fa

def _write_json(name, obj):
    """يكتب ملف JSON بأمان (يكتب نسخة مؤقتة ثم يستبدل)."""
    path = os.path.join(DATA_DIR, name)
    tmp  = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")

def _audit(kind, payload):
    """سجل تدقيق لكل إجراء (append-only) — لا يُحذف أبداً."""
    line = json.dumps({"time": _now(), "type": kind, "payload": payload}, ensure_ascii=False)
    try:
        with io.open(os.path.join(DATA_DIR, "ui_actions.jsonl"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def _inbox(kind, payload):
    """صندوق وارد للإجراءات التي يلتقطها الوكيل (append-only، غير متلف)."""
    line = json.dumps({"time": _now(), "type": kind, **payload}, ensure_ascii=False)
    with io.open(os.path.join(DATA_DIR, "ui_inbox.jsonl"), "a", encoding="utf-8") as f:
        f.write(line + "\n")

def _hide_tokens(accounts):
    """يخفي أي token/secret/password في حسابات المكافآت قبل إرسالها للّوحة."""
    if not isinstance(accounts, dict):
        return accounts
    safe = {}
    for platform, acc in accounts.items():
        if isinstance(acc, dict):
            a = dict(acc)
            for k in list(a.keys()):
                if k.lower() in ("token", "secret", "password", "api_key", "key", "cookie"):
                    a[k] = "\u25cf\u25cf\u25cf\u25cf\u25cf\u25cf"   # ●●●●●●
            safe[platform] = a
        else:
            safe[platform] = acc
    return safe

def _full_access_status():
    try:
        return _full_access_module().status()
    except Exception:
        return {"enabled": False, "at": None, "reason": ""}


def _knowledge_summary():
    """أرشيف الدروس المعلَّمة حديثاً + إحصاء ذاكرة المهارات."""
    out = {"lessons": [], "skills": {}}
    try:
        sys.path.insert(0, PROJECT_ROOT)
        from agent_os import teach, skill_memory
        out["lessons"] = teach.list_lessons(8)
        out["skills"] = skill_memory.summarize()
    except Exception:
        pass
    return out


def read_worker_status():
    """حالة منفّذ الخلفية الحي — تُظهر اللوحة «يعمل الآن: ...» لحظياً."""
    try:
        with io.open(os.path.join(DATA_DIR, "worker.json"), "r", encoding="utf-8") as f:
            st = json.load(f)
        alive = (time.time() - float(st.get("ts", 0))) <= 90
        return {
            "alive": alive,
            "pid": st.get("pid"),
            "ts": st.get("ts"),
            "mode": (st.get("extra") or {}).get("mode"),
            "current": (st.get("extra") or {}).get("current"),
        }
    except Exception as e:
        return {"alive": False, "error": str(e)[:100]}


def read_inbox_results(limit=10):
    """نتائج تنفيذ مهام الصندوق الوارد (الأحدث أولاً) — تراقبها اللوحة لتعرض الرد."""
    rows = _read_jsonl_tail("ui_inbox_results.jsonl", limit)
    total = 0
    path = os.path.join(DATA_DIR, "ui_inbox_results.jsonl")
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            total = sum(1 for _ in f)
    except Exception:
        pass
    items = []
    for r in rows:
        items.append({
            "time": r.get("time"),
            "text": str(r.get("text", ""))[:120],
            "kind": r.get("kind"),
            "ok": r.get("ok"),
            "detail": str(r.get("detail", ""))[:500],
        })
    return {"total": total, "items": items}


# ============================================================================
#  تجميع كل البيانات للّوحة  → GET /api/all
# ============================================================================
def build_all():
    world = _read_json("world_state.json", {})
    # قيم افتراضية للحقول التجميلية إن غابت (كي لا تنكسر اللوحة)
    world.setdefault("modules", 92)
    world.setdefault("uptime_cycles", world.get("day", ""))
    world.setdefault("last_heartbeat", "الآن")

    finance = _read_json("finance.json", {})
    finance.setdefault("txns", [])
    finance.setdefault("self_earned_usd", 0.0)

    goals_f    = _read_json("goals.json", {})
    requests_f = _read_json("requests.json", {})
    progs_f    = _read_json("bounty_programs.json", {})
    drafts_f   = _read_json("bounty_drafts.json", {})
    accts_f    = _read_json("bounty_accounts.json", {})
    products_f = _read_json("products.json", {})
    notif_f    = _read_json("notifications.json", {})

    # برامج المكافآت: أضف حقولاً تجميلية إن غابت
    programs = progs_f.get("programs", []) if isinstance(progs_f, dict) else []
    for p in programs:
        p.setdefault("adopted", True)
        p.setdefault("max_payout", 0)
        if "platform" not in p:
            src = str(p.get("authorization_source", ""))
            p["platform"] = src.split(":")[-1] if ":" in src else "غير محدد"
    findings = progs_f.get("findings", []) if isinstance(progs_f, dict) else []

    out = {
        "world":         world,
        "finance":       finance,
        "goals":         goals_f.get("goals", []) if isinstance(goals_f, dict) else [],
        "requests":      requests_f.get("requests", []) if isinstance(requests_f, dict) else [],
        "bountyPrograms":programs,
        "bountyFindings":findings,
        "bountyDrafts":  drafts_f.get("drafts", []) if isinstance(drafts_f, dict) else [],
        "bountyAccounts":_hide_tokens(accts_f.get("accounts", accts_f) if isinstance(accts_f, dict) else {}),
        "products":      products_f.get("products", []) if isinstance(products_f, dict) else [],
        "notifications": notif_f.get("items", []) if isinstance(notif_f, dict) else [],
        "events":        _read_jsonl_tail("events.jsonl", EVENTS_TAIL),
        "fullAccess":    _full_access_status(),
        "knowledge":     _knowledge_summary(),
    }
    # ملفات اختيارية — تُعرض إن وُجدت، وإلا تبقى قيم اللوحة التجريبية
    settings = _read_json("ui_settings.json", None)
    if settings is not None:
        out["settings"] = settings
    pc = _read_json("platform_counts.json", None)
    if pc is not None:
        out["platformCounts"] = pc
    return out

# ============================================================================
#  تنفيذ الإجراءات  → POST /api/action   { "type": "...", "payload": {...} }
# ============================================================================
def do_action(kind, payload):
    _audit(kind, payload)

    # ---- موافقة/رفض طلب (عقد معروف: requests.json) ----
    if kind == "approve":
        rid = payload.get("id"); decision = payload.get("decision")
        if decision not in ("approved", "denied"):
            return {"ok": False, "message": "قرار غير صالح"}
        f = _read_json("requests.json", {"requests": []})
        hit = False
        for r in f.get("requests", []):
            if r.get("id") == rid:
                r["status"] = decision; r["decided_at"] = _now(); hit = True
        if hit: _write_json("requests.json", f)
        return {"ok": hit, "message": "تم" if hit else "لم يُعثر على الطلب"}

    # ---- إيقاف/تشغيل هدف (عقد معروف: goals.json) ----
    if kind == "goal_toggle":
        gid = payload.get("id"); status = payload.get("status")
        if status not in ("active", "paused"):
            return {"ok": False, "message": "حالة غير صالحة"}
        f = _read_json("goals.json", {"goals": []})
        hit = False
        for g in f.get("goals", []):
            if g.get("id") == gid:
                g["status"] = status; g["updated"] = _now(); hit = True
        if hit: _write_json("goals.json", f)
        return {"ok": hit, "message": "تم" if hit else "لم يُعثر على الهدف"}

    # ---- إضافة هدف جديد (عقد معروف: goals.json) ----
    if kind == "goal_add":
        f = _read_json("goals.json", {"goals": [], "next_id": 1})
        nid = f.get("next_id", (max([g.get("id", 0) for g in f.get("goals", [])] + [0]) + 1))
        g = {
            "id": nid,
            "title": payload.get("title", "هدف جديد"),
            "priority": payload.get("priority", "medium"),
            "category": payload.get("category", "general"),
            "auto": False, "status": "active",
            "strategy": "بانتظار توليد الاستراتيجية من goal_manager",
            "created": _now(), "updated": _now(),
        }
        f.setdefault("goals", []).insert(0, g)
        f["next_id"] = nid + 1
        _write_json("goals.json", f)
        return {"ok": True, "id": nid, "message": "أُنشئ الهدف"}

    # ---- محادثة ذكية حقيقية (GPT-like) ----
    if kind == "chat":
        text = payload.get("text", "").strip()
        if not text:
            return {"ok": False, "message": "نص فارغ"}
        lesson_topic = _learn_topic(text)
        if lesson_topic:
            # طلب تعلم → ينفَّذ أمامه في الخلفية (سير حي في سجل النشاط)
            _inbox("task", {"text": lesson_topic, "mode": "learn"})
            return {"ok": True,
                    "reply": "🎓 باشرتُ التعلّم الآن: «%s» — سترى خطواتي حيّة في سجل النشاط، والدرس يُحفظ في ذاكرتي الدائمة." % lesson_topic,
                    "engine": "teach"}
        _inbox("chat", {"text": text})
        try:
            reply, engine = _ask_chat(text)
            return {"ok": True, "reply": reply[:4000], "engine": engine}
        except RuntimeError as e:
            return {"ok": False, "message": str(e)}
        except Exception as e:
            return {"ok": False, "message": "تعذّر الرد: %s" % e}

    # ---- تعليم مباشر صريح (زر أو أمر) ----
    if kind == "teach":
        topic = str(payload.get("topic") or payload.get("text") or "").strip()
        if not topic:
            return {"ok": False, "message": "لا موضوع"}
        _inbox("task", {"text": topic, "mode": "learn"})
        return {"ok": True, "message": "أُرسل درس «%s» إلى منفّذ التعلم" % topic}

    # ---- الولوج الكامل (مفتاح المستخدم — بموافقة صريحة) ----
    if kind == "access":
        try:
            fa = _full_access_module()
        except Exception as e:
            return {"ok": False, "message": "تعذّر تحميل وحدة الولوج: %s" % e}
        enable = payload.get("enable")
        if enable is None:
            return {"ok": True, "access": fa.status()}
        try:
            return {"ok": True, "access": (fa.enable(payload.get("reason", "من اللوحة"))
                     if enable else fa.disable(payload.get("reason", "من اللوحة")))}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    # ---- مهمة محادثة → صندوق الوارد (+ تشغيل الوكيل اختيارياً) ----
    if kind == "task":
        text = payload.get("text", "").strip()
        if not text:
            return {"ok": False, "message": "نص فارغ"}
        mode = "learn" if _learn_topic(text) else None
        _inbox("task", {"text": text, "mode": mode} if mode else {"text": text})
        if AGENT_CMD:
            try:
                import subprocess
                cmd = [a.replace("{text}", text) for a in AGENT_CMD]
                subprocess.Popen(cmd, cwd=os.path.dirname(DATA_DIR) or None)
            except Exception as e:
                return {"ok": True, "message": "حُفظت المهمة (تعذّر تشغيل الوكيل: %s)" % e}
        return {"ok": True, "message": "أُرسلت المهمة إلى الوكيل"}

    # ---- أي إجراء آخر (اعتماد مكافأة...) → صندوق الوارد الآمن ----
    _inbox(kind, payload)
    return {"ok": True, "message": "أُدرج الطلب في صندوق وارد الوكيل"}

# ============================================================================
#  خادم HTTP
# ============================================================================
class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # CORS للسماح بفتح الـ HTML مباشرةً (محلي فقط)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # سجل هادئ
        pass

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html", "/agent-os-control.html"):
            try:
                with io.open(HTML_FILE, "r", encoding="utf-8") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            except Exception:
                return self._send(404, {"ok": False, "message": "ملف اللوحة غير موجود"})
        if path == "/api/health":
            return self._send(200, {"ok": True, "time": _now()})
        if path == "/api/all":
            try:
                return self._send(200, build_all())
            except Exception as e:
                return self._send(500, {"ok": False, "message": str(e)})
        if path == "/api/inbox_results":
            return self._send(200, read_inbox_results())
        if path == "/api/worker":
            return self._send(200, read_worker_status())
        return self._send(404, {"ok": False, "message": "مسار غير معروف"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path != "/api/action":
            return self._send(404, {"ok": False, "message": "مسار غير معروف"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
            kind = data.get("type", "")
            payload = data.get("payload", {}) or {}
            return self._send(200, do_action(kind, payload))
        except Exception as e:
            return self._send(500, {"ok": False, "message": str(e)})

class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def main():
    if not os.path.isdir(DATA_DIR):
        print("\n[تنبيه] مجلد البيانات غير موجود:\n  %s" % DATA_DIR)
        print("عدّل قيمة DATA_DIR في أعلى هذا الملف ثم أعد التشغيل.\n")
    print("=" * 60)
    print(" Agent OS · خادم الجسر يعمل الآن")
    print("=" * 60)
    print(" افتح المتصفح على:  http://%s:%d" % (HOST, PORT))
    print(" مجلد البيانات   :  %s" % DATA_DIR)
    print(" للإيقاف         :  Ctrl + C")
    print("=" * 60)
    try:
        Server((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nتم الإيقاف. مع السلامة 👋")

if __name__ == "__main__":
    main()
