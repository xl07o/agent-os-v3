"""
chat_api.py - جسر محادثة محلي بين واجهة ويب وbrain.py (v1.0)
================================================================
سيرفر HTTP محلي بحت — الأساس اللي أي واجهة ويب (Next.js أو غيرها) تتكلم
معه بدل ما تتكلم مباشرة مع brain.py. لاحقاً يضاف له مسار sandbox محوسب
(Daytona) لمّا يتوفر المفتاح — هذا الملف يبقى صالح بدون أي تغيير.

  • يعمل محلياً فقط على 127.0.0.1 — لا يفتح أي منفذ للإنترنت الخارجي.
  • POST /api/chat فقط — يمرّر الرسالة لـbrain.Brain نفسه (نفس العقل
    اللي يستخدمه selfrunner.py/chat_cli.py، بنفس أوضاع hybrid/smart/...).
  • CORS مفتوح فقط لأصول localhost/127.0.0.1 (أي منفذ) — نفس قاعدة
    web_bridge.py.
  • جلسة واحدة بالذاكرة لكل chat_id — بسيطة، تُعاد تهيئتها عند إعادة التشغيل.

التشغيل:
  python agent_os/chat_api.py
"""

import json
import os
import re
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8788

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

_LOCALHOST_ORIGIN = re.compile(
    r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?)$"
)

_sessions = {}  # chat_id -> brain.Brain
_pending_actions = {}  # chat_id -> نص المهمة بانتظار تأكيدك قبل تشغيلها عبر hermes

# ---- واجهة الويب المحلية (مدمجة) ----------------------------------------
_UI_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent OS</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;height:100vh;display:flex;flex-direction:column}
header{padding:10px 18px;background:#1e293b;border-bottom:1px solid #334155;font-weight:bold;font-size:1rem;display:flex;align-items:center;gap:10px}
header span{font-size:0.75rem;color:#64748b;font-weight:normal}
.wrap{display:flex;flex:1;overflow:hidden}
.chat{flex:1;display:flex;flex-direction:column;padding:14px;gap:10px;min-width:0}
#msgs{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding-bottom:4px}
.msg{padding:8px 12px;border-radius:8px;max-width:86%;white-space:pre-wrap;line-height:1.5;font-size:0.88rem}
.msg.user{background:#2563eb;align-self:flex-start}
.msg.bot{background:#1e293b;align-self:flex-end;border:1px solid #334155}
.msg.err{background:#450a0a;align-self:flex-end;border:1px solid #991b1b}
.irow{display:flex;gap:8px}
#inp{flex:1;padding:9px 13px;background:#1e293b;border:1px solid #334155;border-radius:8px;color:#e2e8f0;font-size:0.88rem;direction:rtl}
#inp:focus{outline:none;border-color:#3b82f6}
button{padding:9px 16px;background:#3b82f6;border:none;border-radius:8px;color:#fff;cursor:pointer;font-size:0.88rem;white-space:nowrap}
button:hover{background:#2563eb}
button:disabled{background:#475569;cursor:not-allowed}
.side{width:270px;background:#08111f;border-right:1px solid #1e293b;overflow-y:auto;padding:10px;display:flex;flex-direction:column;gap:10px;flex-shrink:0}
.card{background:#1e293b;border-radius:8px;padding:9px 11px}
.card h3{font-size:0.72rem;color:#64748b;margin-bottom:7px;text-transform:uppercase;letter-spacing:.05em}
.badge{display:inline-block;padding:2px 7px;border-radius:10px;font-size:0.72rem;margin:2px}
.ok{background:#14532d;color:#86efac}.warn{background:#713f12;color:#fde68a}.err{background:#7f1d1d;color:#fca5a5}.neu{background:#334155;color:#cbd5e1}
.ei{font-size:0.72rem;padding:3px 0;border-bottom:1px solid #334155}
.es{color:#64748b;font-size:0.68rem}
.ts{color:#475569;font-size:0.68rem;margin-top:2px;display:block}
</style>
</head>
<body>
<header>&#x1F916; Agent OS <span id="hts"></span></header>
<div class="wrap">
<div class="side" id="side"><div class="card"><h3>جارٍ التحميل…</h3></div></div>
<div class="chat">
  <div id="msgs"></div>
  <div class="irow">
    <input id="inp" placeholder="اكتب رسالتك…" autocomplete="off">
    <button id="btn" onclick="send()">إرسال</button>
  </div>
</div>
</div>
<script>
const B='http://127.0.0.1:8788';
let cid=null;
async function send(){
  const i=document.getElementById('inp'),m=i.value.trim();
  if(!m)return;i.value='';addMsg(m,'user');
  document.getElementById('btn').disabled=true;
  try{
    const r=await fetch(B+'/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m,chat_id:cid})});
    const d=await r.json();cid=d.chat_id||cid;
    if(d.needs_confirmation){addConfirm(d.reply||'تأكيد؟');}
    else{addMsg(d.reply||d.error||'(لا رد)','bot');}
  }catch(e){addMsg('خطأ: '+e.message,'err');}
  document.getElementById('btn').disabled=false;
  document.getElementById('inp').focus();
}
function addConfirm(t){
  addMsg(t,'bot');
  const row=document.createElement('div');
  row.id='confirmRow';row.className='irow';row.style.alignSelf='flex-end';
  row.innerHTML='<button onclick="confirmAction(true)">نفّذ</button>'
    +'<button onclick="confirmAction(false)" style="background:#475569">تجاهل</button>';
  const ms=document.getElementById('msgs');ms.appendChild(row);ms.scrollTop=ms.scrollHeight;
}
async function confirmAction(ok){
  const row=document.getElementById('confirmRow');if(row)row.remove();
  addMsg(ok?'نفّذ':'تجاهل','user');
  document.getElementById('btn').disabled=true;
  try{
    const r=await fetch(B+'/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chat_id:cid,confirm_action:ok})});
    const d=await r.json();
    addMsg(d.reply||d.error||'(لا رد)','bot');
  }catch(e){addMsg('خطأ: '+e.message,'err');}
  document.getElementById('btn').disabled=false;
}
function addMsg(t,c){
  const d=document.createElement('div');d.className='msg '+c;d.textContent=t;
  const ms=document.getElementById('msgs');ms.appendChild(d);ms.scrollTop=ms.scrollHeight;
}
async function refresh(){
  try{
    const r=await fetch(B+'/api/status');const d=await r.json();render(d);
    document.getElementById('hts').textContent=(d.health?.time||'').slice(11,19);
  }catch(e){document.getElementById('side').innerHTML='<div class="card"><h3>تعذر الاتصال</h3></div>';}
}
function render(d){
  const h=d.health||{},t=d.tasks||{},sb=d.sandboxes||{},errs=d.errors||[];
  const sbN=Object.keys(sb).length;
  let html='';
  html+=`<div class="card"><h3>الصحة</h3><span class="badge ${h.healthy?'ok':'err'}">${h.healthy?'سليم ✓':'خلل ✗'}</span></div>`;
  html+=`<div class="card"><h3>طابور المهام</h3>${Object.entries(t).map(([k,v])=>`<span class="badge ${k==='done'?'ok':k==='failed'?'err':k==='running'?'warn':'neu'}">${k}: ${v}</span>`).join('')||'<span class="badge neu">فارغ</span>'}</div>`;
  html+=`<div class="card"><h3>Sandboxes</h3><span class="badge ${sbN>0?'warn':'neu'}">${sbN} نشط</span>${Object.entries(sb).map(([id,v])=>`<div style="font-size:0.7rem;color:#64748b;margin-top:3px">● ${id.slice(0,8)}… ${v.label||''}</div>`).join('')}</div>`;
  html+=`<div class="card"><h3>آخر الأخطاء (${d.errors_today||0} اليوم)</h3>${errs.length?errs.slice(0,6).map(e=>`<div class="ei"><span class="es">[${e.source||'?'}]</span> ${e.type||'?'}: ${(e.msg||'').slice(0,55)}<span class="ts">${(e.ts||'').slice(0,16)}</span></div>`).join(''):'<div style="color:#4ade80;font-size:0.78rem">لا أخطاء ✓</div>'}</div>`;
  const da=d.daily_autopilot||{};
  html+=`<div class="card"><h3>المحرك اليومي</h3>${da.last_report_at?`<div style="font-size:0.72rem;color:#94a3b8">${(da.summary||'').slice(0,80)}</div><span class="ts">${da.last_report_at.slice(0,16)}</span>`:'<span class="badge neu">لم يشتغل بعد</span>'}</div>`;
  document.getElementById('side').innerHTML=html;
}
document.getElementById('inp').addEventListener('keydown',e=>{if(e.key==='Enter')send();});
refresh();setInterval(refresh,10000);
</script>
</body>
</html>"""


def _get_session(chat_id):
    import brain
    if chat_id not in _sessions:
        _sessions[chat_id] = brain.Brain(
            "أنت وكيل agent-os-v3 — رد مختصر مفيد بالعربية. "
            "إذا احتجت فعل حقيقي (تصفح/تحكم جهاز)، قل إنك تحتاج صلاحية sandbox."
        )
    return _sessions[chat_id]


def _wants_action(raw):
    """نفس كاشف النية بـchat_cli.py — بدون هذا، الشات بالنافذة محادثة فقط
    حتى لو الطرفية تقدر تنفّذ فعلياً لنفس الرسالة."""
    import chat_cli
    return chat_cli._wants_action(raw)


def _run_hermes(task):
    import chat_cli
    return chat_cli._run_hermes(task)


def _status_data():
    """يجمع بيانات حالة النظام لـ/api/status — كل قسم مغلّف بـtry/except."""
    data = {}
    try:
        from agent_os import computer_sandbox as cs
        data["sandboxes"] = cs.active_sandboxes()
    except Exception:
        data["sandboxes"] = {}
    try:
        from agent_os import task_queue as tq
        data["tasks"] = tq.summary()
    except Exception:
        data["tasks"] = {}
    try:
        from agent_os import error_tracker as et
        data["errors"] = et.recent(10)
        data["errors_today"] = et.count_today()
    except Exception:
        data["errors"] = []
        data["errors_today"] = 0
    try:
        from agent_os import health_report
        data["health"] = health_report.snapshot()
    except Exception:
        import datetime
        data["health"] = {"time": datetime.datetime.now().isoformat(), "healthy": None}
    try:
        from agent_os import inbox_worker
        data["worker_alive"] = inbox_worker.worker_alive()
    except Exception:
        data["worker_alive"] = None
    try:
        import datetime
        report_path = os.path.join(BASE_DIR, "output", "daily_autopilot_report.md")
        if os.path.exists(report_path):
            with open(report_path, encoding="utf-8", errors="replace") as f:
                first_line = f.readline().strip()
            data["daily_autopilot"] = {
                "last_report_at": datetime.datetime.fromtimestamp(
                    os.path.getmtime(report_path)
                ).isoformat(),
                "summary": first_line[:120],
            }
        else:
            data["daily_autopilot"] = {"last_report_at": None, "summary": None}
    except Exception:
        data["daily_autopilot"] = {"last_report_at": None, "summary": None}
    return data


class Handler(BaseHTTPRequestHandler):
    def _cors_headers(self):
        origin = self.headers.get("Origin", "")
        if _LOCALHOST_ORIGIN.match(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = _UI_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/status":
            data = _status_data()
            out = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(200)
            self._cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_response(404)
            self._cors_headers()
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            chat_id = str(body.get("chat_id") or uuid.uuid4())
            confirm = body.get("confirm_action")

            if confirm is not None and chat_id in _pending_actions:
                # رد على سؤال التأكيد اللي رجعناه بالرد السابق — ننفّذ أو نتجاهل
                pending_task = _pending_actions.pop(chat_id)
                if confirm:
                    reply = _run_hermes(pending_task)
                    payload = {"chat_id": chat_id, "reply": reply, "engine": "hermes"}
                else:
                    payload = {"chat_id": chat_id, "reply": "تم التجاهل — تفضل اسأل عادي."}
                status = 200
            else:
                message = str(body.get("message", "")).strip()
                if not message:
                    raise ValueError("empty message")

                if _wants_action(message):
                    _pending_actions[chat_id] = message
                    payload = {
                        "chat_id": chat_id,
                        "needs_confirmation": True,
                        "reply": "رسالتك تبدو مهمة تنفيذية — أشغّلها عبر hermes agent؟",
                    }
                else:
                    session = _get_session(chat_id)
                    text, engine = session.ask(message)
                    payload = {"chat_id": chat_id, "reply": text, "engine": engine}
                status = 200
        except Exception as e:
            payload = {"error": str(e)[:200]}
            status = 400

        out = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, fmt, *args):
        pass  # صامت — بدون طباعة كل طلب بالطرفية


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"chat_api.py يعمل على http://{HOST}:{PORT}/api/chat (POST)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
