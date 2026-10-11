"""
شات ويب حقيقي — "نسخ لصق" بدل أوامر طرفية. هذا بالضبط ما طُلب أصلاً:
تفتح رابطاً (من deploy.py، مستضاف بـDaytona) وتكتب، بلا أي سطر أوامر.

يستخدم نفس router.py/bots.py/kernel.py/decision.py الموجودين بالضبط —
لا منطق جديد، فقط واجهة HTTP + صفحة HTML. الفرق الوحيد عن cli.py: كل
استدعاءات kernel تمر بـinteractive=False (راجع kernel.py) لأن سيرفر
HTTP ما يقدر يحجب خيط بـinput() — أي خطوة تحتاج موافقة ترجع فوراً
كـ"needs_confirmation" للمتصفح، وزر "نفّذ/تجاهل" يكمل عبر /api/confirm.

يستمع على 0.0.0.0 عمداً (لا 127.0.0.1) لأنه يُستضاف داخل ساندبوكس
ويُفتح من المتصفح عبر رابط Daytona الخارجي — لا تشغّله على جهازك
الحقيقي مباشرة بدون جدار حماية.
"""

import json
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import approval, bots, decision, kernel, metrics, router, safety, status

HOST = "0.0.0.0"
PORT = int(os.environ.get("OS4_WEB_CHAT_PORT", "8080"))

_UI_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>agent_os4</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;height:100vh;display:flex;flex-direction:column}
header{padding:12px 18px;background:#1e293b;border-bottom:1px solid #334155;font-weight:bold}
.chat{flex:1;display:flex;flex-direction:column;padding:16px;gap:10px;overflow:hidden}
#msgs{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding-bottom:4px}
.msg{padding:9px 13px;border-radius:9px;max-width:86%;white-space:pre-wrap;line-height:1.55;font-size:0.9rem}
.msg.user{background:#2563eb;align-self:flex-start}
.msg.bot{background:#1e293b;align-self:flex-end;border:1px solid #334155}
.msg.err{background:#450a0a;align-self:flex-end;border:1px solid #991b1b}
.irow{display:flex;gap:8px}
#inp{flex:1;padding:10px 14px;background:#1e293b;border:1px solid #334155;border-radius:9px;color:#e2e8f0;font-size:0.9rem;direction:rtl}
#inp:focus{outline:none;border-color:#3b82f6}
button{padding:10px 18px;background:#3b82f6;border:none;border-radius:9px;color:#fff;cursor:pointer;font-size:0.9rem;white-space:nowrap}
button:hover{background:#2563eb}
button:disabled{background:#475569;cursor:not-allowed}
</style>
</head>
<body>
<header>agent_os4 <a href="/dashboard" style="float:left;color:#93c5fd;text-decoration:none;font-size:0.85rem">لوحة التحكم ←</a></header>
<div class="chat">
  <div id="msgs"></div>
  <div class="irow">
    <input id="inp" placeholder="اكتب رسالتك…" autocomplete="off">
    <button id="btn" onclick="send()">إرسال</button>
  </div>
</div>
<script>
let cid=null;
function addMsg(t,c){
  const d=document.createElement('div');d.className='msg '+c;d.textContent=t;
  document.getElementById('msgs').appendChild(d);
  document.getElementById('msgs').scrollTop=1e9;
}
function addConfirm(what,why,reqId){
  addMsg('يحتاج موافقتك: '+what+(why?' — '+why:''),'bot');
  const row=document.createElement('div');
  row.className='irow';row.style.alignSelf='flex-end';
  row.innerHTML='<button onclick="confirmAction(\\''+reqId+'\\',true)">نفّذ</button>'
    +'<button onclick="confirmAction(\\''+reqId+'\\',false)" style="background:#475569">تجاهل</button>';
  document.getElementById('msgs').appendChild(row);
  document.getElementById('msgs').scrollTop=1e9;
}
async function send(){
  const i=document.getElementById('inp'),m=i.value.trim();
  if(!m)return;i.value='';addMsg(m,'user');
  document.getElementById('btn').disabled=true;
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m,chat_id:cid})});
    const d=await r.json();cid=d.chat_id||cid;
    if(d.needs_confirmation){addConfirm(d.what,d.why,d.request_id);}
    else{addMsg(d.reply||d.error||'(لا رد)',d.error?'err':'bot');}
  }catch(e){addMsg('خطأ: '+e.message,'err');}
  document.getElementById('btn').disabled=false;
  document.getElementById('inp').focus();
}
async function confirmAction(reqId,approved){
  document.getElementById('btn').disabled=true;
  addMsg(approved?'نفّذ':'تجاهل','user');
  try{
    const r=await fetch('/api/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:reqId,approved:approved})});
    const d=await r.json();
    if(d.needs_confirmation){addConfirm(d.what,d.why,d.request_id);}
    else{addMsg(d.reply||d.error||'(لا رد)',d.error?'err':'bot');}
  }catch(e){addMsg('خطأ: '+e.message,'err');}
  document.getElementById('btn').disabled=false;
}
document.getElementById('inp').addEventListener('keydown',e=>{if(e.key==='Enter')send();});
</script>
</body>
</html>"""


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>لوحة تحكم agent_os4</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
header{padding:12px 18px;background:#1e293b;border-bottom:1px solid #334155;font-weight:bold;display:flex;justify-content:space-between;align-items:center}
header a{color:#93c5fd;text-decoration:none;font-size:0.85rem}
main{padding:16px;display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px}
.card h2{font-size:0.95rem;margin-bottom:10px;color:#93c5fd}
.row{display:flex;justify-content:space-between;padding:4px 0;font-size:0.88rem;border-bottom:1px solid #27344a}
.row:last-child{border-bottom:none}
.ok{color:#4ade80}.bad{color:#f87171}
.pending-item{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px;margin-bottom:8px;font-size:0.85rem}
.pending-item .what{font-weight:bold;margin-bottom:4px}
.pending-item .why{color:#94a3b8;font-size:0.8rem;margin-bottom:8px;white-space:pre-wrap}
.btns{display:flex;gap:6px}
button{padding:6px 14px;background:#3b82f6;border:none;border-radius:7px;color:#fff;cursor:pointer;font-size:0.82rem}
button.rej{background:#475569}
button:hover{opacity:0.85}
table{width:100%;font-size:0.82rem;border-collapse:collapse}
td,th{padding:5px 4px;text-align:right;border-bottom:1px solid #27344a}
.empty{color:#64748b;font-size:0.85rem;text-align:center;padding:10px 0}
#ts{font-size:0.75rem;color:#64748b}
</style>
</head>
<body>
<header><span>لوحة تحكم agent_os4 <span id="ts"></span></span><a href="/">← الشات</a></header>
<main id="main"></main>
<script>
async function decide(reqId, approved){
  await fetch('/api/dashboard/decide',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:reqId,approved:approved})});
  load();
}
function row(k,v,cls){return '<div class="row"><span>'+k+'</span><span'+(cls?' class="'+cls+'"':'')+'>'+v+'</span></div>';}
async function load(){
  const r = await fetch('/api/dashboard');
  const d = await r.json();
  document.getElementById('ts').textContent = 'آخر تحديث: ' + new Date().toLocaleTimeString('ar');

  let pendingHtml = '<div class="empty">لا طلبات معلّقة</div>';
  if(d.pending_approvals.length){
    pendingHtml = d.pending_approvals.map(p =>
      '<div class="pending-item"><div class="what">'+p.what+'</div>'
      +'<div class="why">'+(p.why||'')+'</div>'
      +'<div class="btns">'
      +'<button onclick="decide(\\''+p.id+'\\',true)">وافق</button>'
      +'<button class="rej" onclick="decide(\\''+p.id+'\\',false)">رفض</button>'
      +'</div></div>'
    ).join('');
  }

  const s = d.status, m = d.metrics;
  const statusHtml = row('Claude مفعّل', s.claude_configured?'نعم':'لا', s.claude_configured?'ok':'bad')
    + row('Daytona مفعّل', s.daytona_configured?'نعم':'لا', s.daytona_configured?'ok':'bad')
    + row('وضع الوصول الكامل للجهاز', d.pc_access_enabled?'مفعّل':'معطّل', d.pc_access_enabled?'ok':'bad')
    + row('طلبات معلّقة', d.pending_approvals.length)
    + row('سجلات الذاكرة', s.memory_entries);

  const metricsHtml = row('إجمالي القرارات', m.decisions.total)
    + row('موافَق عليها', m.decisions.approved, 'ok')
    + row('مرفوضة', m.decisions.rejected, 'bad')
    + row('معدّل الموافقة', m.decisions.approval_rate)
    + row('مهارات مسجّلة', m.skills_registered)
    + Object.entries(m.bot_usage||{}).map(([k,v])=>row('استخدام: '+k, v)).join('');

  const botsHtml = d.bots.length ? '<table><tr><th>البوت</th><th>المديرية</th><th>الأدوات</th></tr>'
    + d.bots.map(b=>'<tr><td>'+b.title_ar+'</td><td>'+b.directorate+'</td><td>'+(b.allowed_tools.join(', ')||'—')+'</td></tr>').join('')
    + '</table>' : '<div class="empty">لا بوتات</div>';

  const ledgerHtml = d.recent_decisions.length ? '<table><tr><th>المرحلة</th><th>ماذا</th><th>بواسطة</th><th>الوقت</th></tr>'
    + d.recent_decisions.map(e=>'<tr><td>'+e.stage+'</td><td>'+(e.what||'').slice(0,40)+'</td><td>'+(e.proposed_by||e.decided_by||'')+'</td><td>'+e.at+'</td></tr>').join('')
    + '</table>' : '<div class="empty">لا قرارات بعد</div>';

  document.getElementById('main').innerHTML =
    '<div class="card"><h2>طلبات معلّقة بانتظار موافقتك</h2>'+pendingHtml+'</div>'
    + '<div class="card"><h2>حالة النظام</h2>'+statusHtml+'</div>'
    + '<div class="card"><h2>مؤشرات</h2>'+metricsHtml+'</div>'
    + '<div class="card"><h2>البوتات</h2>'+botsHtml+'</div>'
    + '<div class="card"><h2>آخر القرارات</h2>'+ledgerHtml+'</div>';
}
load();
setInterval(load, 4000);
</script>
</body>
</html>"""


def _dashboard_data() -> dict:
    return {
        "metrics": metrics.snapshot(),
        "status": status.snapshot(),
        "pending_approvals": approval.pending(),
        "recent_decisions": list(reversed(decision.ledger(limit=15))),
        "bots": bots.list_bots(),
        "pc_access_enabled": safety.pc_access_enabled(),
    }


def _handle_dashboard_decide(body: dict) -> dict:
    request_id = body.get("request_id")
    approved = bool(body.get("approved"))
    if not request_id:
        return {"ok": False, "error": "يحتاج request_id"}

    ok = (decision.approve if approved else decision.reject)(request_id, decided_by="owner")
    if not ok:
        return {"ok": False, "error": "طلب غير موجود أو تم حسمه مسبقاً"}

    # لو الطلب جاء من حلقة kernel.run_task (مثل شات أو بوت) فيه حالة
    # معلّقة محفوظة — نكمل التنفيذ الفعلي. لو جاء من مسار آخر (مثل
    # self_improve.py/docs_sync.py) فليس له حالة kernel معلّقة أصلاً —
    # هذي المسارات تطبّق التغيير الفعلي عبر أمرها الخاص بعد ما تلقى
    # القرار معتمَداً، لا عبر هنا. لا نزعم تطبيقاً لم يحصل.
    if any(t["request_id"] == request_id for t in kernel.pending_tasks()):
        result = kernel.resume_task(request_id)
        return {"ok": True, "applied": True, "result": result}
    return {"ok": True, "applied": False, "note": "تم تسجيل القرار — تطبيقه الفعلي يحتاج أمره الخاص (مثل طبّق_توثيق)"}


def _handle_chat(body: dict) -> dict:
    chat_id = str(body.get("chat_id") or uuid.uuid4())
    message = str(body.get("message", "")).strip()
    if not message:
        return {"chat_id": chat_id, "error": "رسالة فاضية"}

    decided = router.classify(message)
    if decided["route"] == "bot":
        result = kernel.run_task(
            message,
            persona=bots.BOTS[decided["bot_key"]]["persona"],
            allowed_tools=bots.BOTS[decided["bot_key"]]["allowed_tools"],
            proposed_by=decided["bot_key"],
            interactive=False,
        )
    else:
        result = kernel.run_task(message, proposed_by="owner", interactive=False)

    return _format_result(chat_id, result)


def _handle_confirm(body: dict) -> dict:
    request_id = body.get("request_id")
    approved = bool(body.get("approved"))
    if not request_id:
        return {"error": "يحتاج request_id"}

    (decision.approve if approved else decision.reject)(request_id, decided_by="owner")
    result = kernel.resume_task(request_id)
    if not result.get("ok", True) and "error" in result and "verdict" not in result:
        return {"error": result["error"]}
    return _format_result(None, result)


def _format_result(chat_id: str | None, result: dict) -> dict:
    payload = {"chat_id": chat_id} if chat_id else {}
    if "pending_request_id" in result:
        payload.update({
            "needs_confirmation": True,
            "request_id": result["pending_request_id"],
            "what": result.get("what", ""),
            "why": result.get("why", ""),
        })
        return payload
    if result.get("reply"):
        payload["reply"] = result["reply"]
    else:
        payload["reply"] = result.get("verdict", "")
    return payload


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = _UI_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/dashboard":
            body = _DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/dashboard":
            self._send_json(200, _dashboard_data())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/chat":
                self._send_json(200, _handle_chat(body))
            elif self.path == "/api/confirm":
                self._send_json(200, _handle_confirm(body))
            elif self.path == "/api/dashboard/decide":
                self._send_json(200, _handle_dashboard_decide(body))
            else:
                self._send_json(404, {"error": "مسار غير معروف"})
        except Exception as e:  # noqa: BLE001 — خطأ غير متوقع يُرجَع للمتصفح، لا يُسقط السيرفر
            self._send_json(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        print("[web_chat] " + (fmt % args))


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[web_chat] يستمع على http://{HOST}:{PORT}  (شات: /  —  لوحة التحكم: /dashboard)")
    if safety.pc_access_enabled():
        print(f"[web_chat] ⚠️  وضع الوصول الكامل للجهاز مفعّل — الجذر: {os.environ.get('OS4_PC_ROOT') or os.getcwd()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
