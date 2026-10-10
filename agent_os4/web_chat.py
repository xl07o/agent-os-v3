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

from . import bots, decision, kernel, router

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
<header>agent_os4</header>
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
            else:
                self._send_json(404, {"error": "مسار غير معروف"})
        except Exception as e:  # noqa: BLE001 — خطأ غير متوقع يُرجَع للمتصفح، لا يُسقط السيرفر
            self._send_json(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        print("[web_chat] " + (fmt % args))


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[web_chat] يستمع على http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
