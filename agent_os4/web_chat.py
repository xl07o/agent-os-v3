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

from dotenv import set_key

from . import approval, bots, decision, env, evidence, kernel, metrics, router, safety, status

_LOOPBACK_IPS = {"127.0.0.1", "::1"}

HOST = "0.0.0.0"
PORT = int(os.environ.get("OS4_WEB_CHAT_PORT", "8080"))

_UI_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>agent_os4</title>
<style>
:root{--bg:#06090f;--panel:#0c1220;--panel2:#0f1626;--border:#1c2740;--txt:#e6edf7;--muted:#64748b;--cyan:#22d3ee;--violet:#a78bfa}
*{box-sizing:border-box;margin:0;padding:0}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  background:radial-gradient(1100px 600px at 85% -10%,rgba(34,211,238,.08),transparent 60%),
             radial-gradient(900px 500px at -10% 110%,rgba(167,139,250,.07),transparent 60%),var(--bg);
  color:var(--txt);height:100vh;display:flex;flex-direction:column;
}
header{
  padding:13px 20px;background:rgba(10,15,24,.75);backdrop-filter:blur(8px);border-bottom:1px solid var(--border);
  font-weight:700;display:flex;align-items:center;justify-content:space-between;
}
header .brand{display:flex;align-items:center;gap:9px}
header .dot{width:7px;height:7px;border-radius:50%;background:#34d399;box-shadow:0 0 0 0 rgba(52,211,153,.6);animation:p 2s infinite}
@keyframes p{0%{box-shadow:0 0 0 0 rgba(52,211,153,.55)}70%{box-shadow:0 0 0 7px rgba(52,211,153,0)}100%{box-shadow:0 0 0 0 rgba(52,211,153,0)}}
header a{color:var(--cyan);text-decoration:none;font-size:0.82rem;font-weight:600;border:1px solid rgba(34,211,238,.3);padding:5px 12px;border-radius:99px;background:rgba(34,211,238,.06)}
header a:hover{background:rgba(34,211,238,.12)}
.chat{flex:1;display:flex;flex-direction:column;padding:16px;gap:10px;overflow:hidden;max-width:880px;width:100%;margin:0 auto}
#msgs{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding-bottom:4px}
.msg{padding:10px 14px;border-radius:12px;max-width:86%;white-space:pre-wrap;line-height:1.55;font-size:0.9rem}
.msg.user{background:linear-gradient(135deg,#2563eb,#1d4ed8);align-self:flex-start}
.msg.bot{background:var(--panel);align-self:flex-end;border:1px solid var(--border)}
.msg.err{background:#2a0a0a;align-self:flex-end;border:1px solid #7f1d1d;color:#fca5a5}
.irow{display:flex;gap:8px}
#inp{flex:1;padding:11px 15px;background:var(--panel);border:1px solid var(--border);border-radius:11px;color:var(--txt);font-size:0.9rem;direction:rtl}
#inp:focus{outline:none;border-color:var(--cyan)}
button{padding:10px 20px;background:linear-gradient(135deg,var(--cyan),#0e9fb8);border:none;border-radius:11px;color:#04131a;cursor:pointer;font-size:0.9rem;font-weight:700;white-space:nowrap}
button:hover{filter:brightness(1.08)}
button:disabled{background:#334155;color:#94a3b8;cursor:not-allowed;filter:none}
</style>
</head>
<body>
<header><span class="brand">agent_os4 <span class="dot"></span></span><a href="/dashboard">لوحة التحكم ←</a></header>
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
:root{
  --bg:#060708; --bg2:#0a0b0d; --panel:#0b0d10; --panel2:#0e1114; --border:#1e2228;
  --txt:#eef1f5; --muted:#687080; --dim:#2c323c;
  --cyan:#22d3ee; --cyan-dim:#0e7490; --violet:#a78bfa; --amber:#fbbf24; --red:#f87171; --green:#34d399; --pink:#f472b6; --blue:#60a5fa;
  --ember:#ff6a3d; --ember-dim:#b3291f; --ember-glow:0 0 32px -6px rgba(255,106,61,.55);
  --glow-cyan:0 0 24px -4px rgba(34,211,238,.4); --glow-amber:0 0 24px -4px rgba(251,191,36,.45); --glow-red:0 0 24px -4px rgba(248,113,113,.5);
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  background:
    radial-gradient(1000px 520px at 50% 0%, rgba(255,90,50,.07), transparent 60%),
    radial-gradient(900px 500px at -10% 110%, rgba(34,211,238,.05), transparent 60%),
    var(--bg);
  color:var(--txt); min-height:100vh;
}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--dim);border-radius:8px}
* {scrollbar-width:thin; scrollbar-color:var(--dim) transparent}

.shell{display:flex;min-height:100vh}
.sidebar{
  width:54px;flex:none;display:flex;flex-direction:column;align-items:center;gap:6px;
  padding:16px 0;background:linear-gradient(180deg,var(--panel),var(--bg2));
  border-left:1px solid var(--border);
}
.sidebar .brand{
  width:32px;height:32px;border-radius:9px;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(135deg,var(--ember),var(--ember-dim));color:#1a0804;font-weight:800;font-size:.68rem;
  margin-bottom:14px;box-shadow:var(--ember-glow);
}
.navicon{
  width:36px;height:36px;border-radius:9px;display:flex;align-items:center;justify-content:center;
  color:var(--muted);text-decoration:none;transition:.15s;position:relative;
}
.navicon svg{width:17px;height:17px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.navicon:hover{color:var(--ember);background:rgba(255,106,61,.08)}
.navicon-chat{margin-top:auto;color:var(--violet)}
.navicon-chat:hover{background:rgba(167,139,250,.1)}

.main{flex:1;min-width:0;display:flex;flex-direction:column}

/* ===== ticker (top identity + live stat strip) ===== */
.ticker{
  display:flex;align-items:center;gap:18px;padding:10px 20px;border-bottom:1px solid var(--border);
  background:rgba(10,11,13,.85);backdrop-filter:blur(8px);position:sticky;top:0;z-index:6;flex-wrap:wrap;
}
.tick-brand{display:flex;align-items:center;gap:9px;flex:none}
.tick-logo{
  font-weight:900;font-size:.72rem;letter-spacing:.5px;color:#1a0804;background:linear-gradient(135deg,var(--ember),#ffb199);
  padding:5px 9px;border-radius:7px;box-shadow:var(--ember-glow);
}
.tick-id b{display:block;font-size:.88rem;letter-spacing:.3px}
.tick-id small{color:var(--muted);font-size:.66rem}
.tick-stats{display:flex;align-items:stretch;gap:0;flex:1;overflow-x:auto;min-width:0}
.tstat{
  display:flex;flex-direction:column;justify-content:center;padding:2px 18px;border-right:1px solid var(--border);
  white-space:nowrap;
}
.tstat:first-child{border-right:none;padding-right:0}
.tstat b{font-size:1.05rem;font-weight:800;font-variant-numeric:tabular-nums;line-height:1.1}
.tstat small{color:var(--muted);font-size:.64rem;letter-spacing:.2px}
.tstat.warn b{color:var(--amber)}
.tick-right{display:flex;align-items:center;gap:10px;flex:none}
.search{
  background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:7px 11px;color:var(--txt);
  font-size:.78rem;width:160px;direction:rtl;
}
.search:focus{outline:none;border-color:var(--ember-dim)}
.pulse-dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 0 0 rgba(52,211,153,.6);animation:pulse 2s infinite}
.pulse-dot.err{background:var(--red);box-shadow:0 0 0 0 rgba(248,113,113,.6);animation:pulseRed 1.4s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(52,211,153,.55)}70%{box-shadow:0 0 0 7px rgba(52,211,153,0)}100%{box-shadow:0 0 0 0 rgba(52,211,153,0)}}
@keyframes pulseRed{0%{box-shadow:0 0 0 0 rgba(248,113,113,.6)}70%{box-shadow:0 0 0 7px rgba(248,113,113,0)}100%{box-shadow:0 0 0 0 rgba(248,113,113,0)}}
.clock{font-variant-numeric:tabular-nums;color:var(--muted);font-size:.74rem;min-width:62px;text-align:center}

/* ===== status strip ===== */
.status-strip{display:flex;align-items:center;gap:8px;padding:8px 20px;border-bottom:1px solid var(--border);flex-wrap:wrap}
.pill{
  display:flex;align-items:center;gap:6px;font-size:.68rem;color:var(--muted);background:var(--panel2);
  border:1px solid var(--border);padding:4px 10px;border-radius:99px;
}
.pill b{color:var(--txt);font-weight:700}
.pill .dot{width:6px;height:6px;border-radius:50%;background:var(--dim)}
.pill.ok .dot{background:var(--green)}
.pill.off .dot{background:var(--dim)}
.pill.warn{border-color:rgba(251,191,36,.4)}
.pill.warn .dot{background:var(--amber)}
.switch{position:relative;display:inline-block;width:32px;height:18px;flex:none}
.switch input{opacity:0;width:0;height:0}
.switch .slider{position:absolute;inset:0;background:var(--dim);border-radius:99px;cursor:pointer;transition:.18s}
.switch .slider::before{content:"";position:absolute;height:13px;width:13px;left:2.5px;top:2.5px;background:#e2e8f0;border-radius:50%;transition:.18s}
.switch input:checked + .slider{background:var(--amber)}
.switch input:checked + .slider::before{transform:translateX(14px)}
.switch input:disabled + .slider{opacity:.5;cursor:not-allowed}

/* ===== agent ledger row ===== */
.ledger-row{display:flex;gap:10px;padding:14px 20px;overflow-x:auto}
.agent-card{
  flex:0 0 190px;background:linear-gradient(160deg,var(--panel),var(--panel2));border:1px solid var(--border);
  border-radius:12px;padding:12px 13px;position:relative;
}
.agent-card.active{box-shadow:0 0 0 1px var(--accent) inset}
.ac-top{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.ac-dot{width:9px;height:9px;border-radius:50%;background:var(--accent);box-shadow:0 0 10px -1px var(--accent);flex:none}
.ac-name{font-size:.8rem;font-weight:700}
.ac-role{font-size:.63rem;color:var(--muted)}
.ac-status{margin-right:auto;font-size:.6rem;padding:2px 7px;border-radius:99px;border:1px solid var(--border);color:var(--muted)}
.ac-status.on{color:var(--accent);border-color:var(--accent)}
.ac-tools{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:9px;min-height:20px}
.ac-bars{display:flex;height:5px;border-radius:4px;overflow:hidden;background:var(--dim);margin-bottom:7px}
.ac-bars span{height:100%}
.ac-foot{display:flex;justify-content:space-between;font-size:.62rem;color:var(--muted)}
.ac-foot b{color:var(--txt);font-variant-numeric:tabular-nums}

/* ===== main grid ===== */
.grid-main{display:grid;grid-template-columns:1.35fr 1fr;gap:14px;padding:0 20px 16px;align-items:start}
@media(max-width:1040px){.grid-main{grid-template-columns:1fr}}
.col-left,.col-right{display:flex;flex-direction:column;gap:14px;min-width:0}

.panel{background:var(--panel);border:1px solid var(--border);border-radius:14px;overflow:hidden}
.panel-head{display:flex;align-items:center;justify-content:space-between;padding:12px 15px;border-bottom:1px solid var(--border)}
.panel-head h2{font-size:.82rem;font-weight:700;color:#d7dde6}
.panel-tag{font-size:.63rem;color:var(--ember);border:1px solid rgba(255,106,61,.35);padding:2px 8px;border-radius:99px;background:rgba(255,106,61,.07)}
.badge{font-size:.7rem;background:var(--dim);color:var(--txt);min-width:19px;text-align:center;padding:2px 7px;border-radius:99px}
.badge.has{background:rgba(251,191,36,.18);color:var(--amber);border:1px solid rgba(251,191,36,.4)}

/* ===== vortex ===== */
.vortex-wrap{position:relative;height:330px}
#vortexCanvas{width:100%;height:100%;display:block}
.vortex-stat{
  position:absolute;background:rgba(11,13,16,.72);backdrop-filter:blur(4px);border:1px solid var(--border);
  border-radius:9px;padding:6px 10px;pointer-events:none;
}
.vortex-stat b{display:block;font-size:.98rem;font-weight:800;font-variant-numeric:tabular-nums;color:var(--ember)}
.vortex-stat small{color:var(--muted);font-size:.6rem}
.vs-tl{top:10px;right:10px}
.vs-tr{top:10px;left:10px}
.vs-bl{bottom:10px;right:10px}
.vs-br{bottom:10px;left:10px}
.legend{display:flex;flex-wrap:wrap;gap:7px 13px;padding:10px 15px 13px;border-top:1px solid var(--border)}
.legend span{font-size:.64rem;color:var(--muted);display:flex;align-items:center;gap:5px}
.legend i{width:7px;height:7px;border-radius:50%;display:inline-block}

/* ===== bottom mini charts ===== */
.grid-sub{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
@media(max-width:700px){.grid-sub{grid-template-columns:1fr}}
.panel.mini .panel-head{padding:10px 13px}
.panel.mini h2{font-size:.72rem}
.panel.mini svg{width:100%;height:112px;display:block}

/* ===== gate (approval) panel ===== */
.gate-body{padding:16px 16px 6px;display:flex;align-items:center;gap:14px}
.gate-body svg.g{width:78px;height:78px;flex:none}
.gate-num{font-size:1.5rem;font-weight:800}
.gate-sub{color:var(--muted);font-size:.72rem;margin-top:2px}
.trend-wrap{padding:0 16px 14px}
.trend-wrap svg{width:100%;height:46px;display:block}

/* ===== pending / feed (carried over) ===== */
.pending-list{padding:10px}
.pending-card{
  background:var(--panel2);border:1px solid var(--border);border-radius:11px;padding:11px 13px;margin-bottom:9px;
  border-right:3px solid var(--amber);box-shadow:var(--glow-amber);
}
.pending-card .what{font-weight:700;font-size:.83rem;margin-bottom:4px;word-break:break-word}
.pending-card .meta{color:var(--muted);font-size:.68rem;margin-bottom:3px}
.pending-card .why{color:#9fb0c8;font-size:.76rem;margin-bottom:10px;white-space:pre-wrap;line-height:1.5}
.btns{display:flex;gap:7px}
button{
  padding:7px 16px;border:none;border-radius:8px;color:#04131a;cursor:pointer;font-size:.78rem;font-weight:700;
  background:linear-gradient(135deg,var(--green),#10b981);transition:.15s;
}
button:hover{filter:brightness(1.1);transform:translateY(-1px)}
button.rej{background:var(--panel);color:var(--txt);border:1px solid var(--border)}
button.rej:hover{border-color:var(--red);color:var(--red)}

.terminal{
  font-family:ui-monospace,"SF Mono",Consolas,monospace;font-size:.72rem;max-height:280px;overflow-y:auto;padding:4px 0;
}
.trow{display:flex;gap:9px;padding:6px 15px;border-right:2px solid transparent;align-items:baseline}
.trow:hover{background:var(--panel2)}
.trow .tt{color:var(--muted);flex:none;font-variant-numeric:tabular-nums}
.trow .tstage{flex:none;font-weight:700;width:70px}
.trow .twhat{color:#c3cedd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.trow .tby{color:var(--muted);flex:none}
.trow.proposed{border-color:rgba(96,165,250,.5)}
.trow.proposed .tstage{color:var(--blue)}
.trow.approved{border-color:rgba(52,211,153,.5)}
.trow.approved .tstage{color:var(--green)}
.trow.rejected{border-color:rgba(248,113,113,.5)}
.trow.rejected .tstage{color:var(--red)}

.empty{color:var(--muted);font-size:.8rem;text-align:center;padding:22px 10px}
.hidden{display:none !important}
footer{padding:12px 20px 20px;color:var(--dim);font-size:.68rem;text-align:center}
</style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="brand">OS4</div>
    <nav>
      <a href="#ledger" class="navicon" title="البوتات"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg></a>
      <a href="#vortex" class="navicon" title="الدوّامة"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="2.4"/><circle cx="4" cy="5" r="1.8"/><circle cx="20" cy="5" r="1.8"/><circle cx="4" cy="19" r="1.8"/><circle cx="20" cy="19" r="1.8"/><line x1="10.2" y1="10.6" x2="5.4" y2="6.2"/><line x1="13.8" y1="10.6" x2="18.6" y2="6.2"/><line x1="10.2" y1="13.4" x2="5.4" y2="17.8"/><line x1="13.8" y1="13.4" x2="18.6" y2="17.8"/></svg></a>
      <a href="#gate" class="navicon" title="بوابة الموافقة"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 3.2"/></svg></a>
      <a href="#pending" class="navicon" title="طلبات معلّقة"><svg viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></a>
      <a href="#feed" class="navicon" title="السجل الحي"><svg viewBox="0 0 24 24"><path d="M4 17V7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-5 3z"/><line x1="8" y1="9" x2="16" y2="9"/><line x1="8" y1="13" x2="13" y2="13"/></svg></a>
    </nav>
    <a href="/" class="navicon navicon-chat" title="الشات"><svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></a>
  </aside>

  <div class="main">
    <header class="ticker">
      <div class="tick-brand">
        <span class="tick-logo">OS4</span>
        <div class="tick-id"><b>AGENT_OS4</b><small>نواة واحدة · بوابة موافقة واحدة</small></div>
      </div>
      <div class="tick-stats" id="tickStats"></div>
      <div class="tick-right">
        <input id="search" class="search" placeholder="فلتر…">
        <span class="pulse-dot" id="pulse"></span>
        <span class="clock" id="clock">--:--:--</span>
      </div>
    </header>

    <div class="status-strip" id="statusStrip"></div>

    <section class="ledger-row" id="ledgerRow"></section>

    <section class="grid-main">
      <div class="col-left">
        <div class="panel" id="vortex">
          <div class="panel-head"><h2>الدوّامة — شبكة البوتات حول kernel.py</h2><span class="panel-tag">مباشر</span></div>
          <div class="vortex-wrap">
            <canvas id="vortexCanvas"></canvas>
            <div class="vortex-stat vs-tl"><b id="vsActive">0/0</b><small>عُقَد نشطة</small></div>
            <div class="vortex-stat vs-tr"><b id="vsRate">—</b><small>تماسك القرار</small></div>
            <div class="vortex-stat vs-bl"><b id="vsTotal">0</b><small>قرارات كلية</small></div>
            <div class="vortex-stat vs-br"><b id="vsPending">0</b><small>بانتظار الحسم</small></div>
          </div>
          <div class="legend" id="legend"></div>
        </div>

        <div class="grid-sub">
          <div class="panel mini">
            <div class="panel-head"><h2>نمو القرارات</h2></div>
            <svg id="chartGrowth" viewBox="0 0 280 112"></svg>
          </div>
          <div class="panel mini">
            <div class="panel-head"><h2>أثر القرارات بالزمن</h2></div>
            <svg id="chartSpikes" viewBox="0 0 280 112"></svg>
          </div>
          <div class="panel mini">
            <div class="panel-head"><h2>خريطة الترابط</h2></div>
            <svg id="chartSynapse" viewBox="0 0 280 112"></svg>
          </div>
        </div>
      </div>

      <div class="col-right">
        <div class="panel" id="gate">
          <div class="panel-head"><h2>بوابة الموافقة — الإشارة للتنفيذ</h2></div>
          <div class="gate-body">
            <svg class="g" id="gateGauge"></svg>
            <div><div class="gate-num" id="gateNum">0/0</div><div class="gate-sub">موافَق / محسوم</div></div>
          </div>
          <div class="trend-wrap"><svg id="gateTrend" viewBox="0 0 280 46"></svg></div>
        </div>
        <div class="panel" id="pending">
          <div class="panel-head"><h2>طلبات معلّقة بانتظار موافقتك</h2><span class="badge" id="pendingBadge">0</span></div>
          <div class="pending-list" id="pendingList"></div>
        </div>
        <div class="panel" id="feed">
          <div class="panel-head"><h2>سجل القرارات الحي</h2></div>
          <div class="terminal" id="feedList"></div>
        </div>
      </div>
    </section>

    <footer>agent_os4 — نواة واحدة، بوابة موافقة واحدة، بلا أرقام وهمية. يتحدّث كل 4 ثوانٍ.</footer>
  </div>
</div>

<script>
const DIR_COLOR = {
  intelligence:'#60a5fa', engineering:'#22d3ee', financial:'#34d399', security:'#f87171',
  operations:'#fbbf24', research:'#a78bfa', customer_business:'#f472b6', learning_evolution:'#2dd4bf'
};
const DIR_LABEL = {
  intelligence:'الاستخبارات والتخطيط', engineering:'الهندسة', financial:'المالية', security:'الأمن',
  operations:'العمليات', research:'البحث', customer_business:'المنتج والنمو', learning_evolution:'التعلّم والتطور'
};
let lastData = null;

function escapeHtml(s){
  return String(s==null?'':s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function timeShort(at){ return (at||'').split(' ')[1] || at || ''; }
function hexToRgba(hex, a){
  const h = (hex||'#3b4961').replace('#','');
  const r = parseInt(h.substring(0,2),16), g = parseInt(h.substring(2,4),16), b = parseInt(h.substring(4,6),16);
  return 'rgba('+r+','+g+','+b+','+a+')';
}
function tstat(label, value, cls){
  return '<div class="tstat'+(cls?' '+cls:'')+'"><b>'+value+'</b><small>'+label+'</small></div>';
}
function pill(label, on, extra){
  return '<span class="pill '+(on?'ok':'off')+(extra||'')+'"><span class="dot"></span>'+label+'</span>';
}

/* ===== ticker + status strip ===== */
function renderTicker(d){
  const m = d.metrics, s = d.status, pendN = d.pending_approvals.length;
  const rate = m.decisions.approval_rate;
  const ratePct = rate==null ? null : Math.round(rate*100);
  const activeBots = d.bots.filter(b => (m.bot_usage[b.key]||0) > 0).length;
  document.getElementById('tickStats').innerHTML =
    tstat('قرارات كلية', m.decisions.total)
    + tstat('معدّل الموافقة', ratePct==null?'—':ratePct+'%')
    + tstat('سجلات الذاكرة', s.memory_entries)
    + tstat('مهارات مسجّلة', m.skills_registered)
    + tstat('بوتات نشطة', activeBots+'/'+d.bots.length)
    + tstat('معلّقة', pendN, pendN?'warn':'');

  document.getElementById('statusStrip').innerHTML =
    pill('Claude', s.claude_configured)
    + pill('Daytona', s.daytona_configured)
    + '<span class="pill'+(d.pc_access_enabled?' warn':' off')+'"><label class="switch"><input type="checkbox" id="pcToggle"'+(d.pc_access_enabled?' checked':'')+'><span class="slider"></span></label>وصول الجهاز الكامل: <b id="pcState">'+(d.pc_access_enabled?'مفعّل':'معطّل')+'</b></span>'
    + '<span class="pill" id="pcNoteWrap"><small id="pcNote">'+(d.pc_access_enabled?'نشط — كل أمر يحتاج موافقتك رغم ذلك':'يعمل فقط من جهازك (localhost)')+'</small></span>';
}

/* ===== agent ledger cards ===== */
function renderLedger(d, filter){
  const usage = d.metrics.bot_usage || {};
  const bd = d.bot_breakdown || {};
  const rows = d.bots.filter(b => !filter || (b.title_ar+b.directorate).toLowerCase().includes(filter));
  document.getElementById('ledgerRow').innerHTML = rows.length ? rows.map(b=>{
    const color = DIR_COLOR[b.directorate] || '#3b4961';
    const n = usage[b.key] || 0;
    const stat = bd[b.key] || {};
    const pr = stat.proposed||0, ap = stat.approved||0, rj = stat.rejected||0, tot = Math.max(pr,1);
    const tools = b.allowed_tools.length ? b.allowed_tools.map(t=>'<span class="tag" style="font-size:.6rem;background:var(--panel2);border:1px solid var(--border);color:#9fb0c8;padding:2px 6px;border-radius:6px">'+escapeHtml(t)+'</span>').join('') : '<span class="tag" style="font-size:.6rem;background:var(--panel2);border:1px solid var(--border);color:#9fb0c8;padding:2px 6px;border-radius:6px">محادثة فقط</span>';
    return '<div class="agent-card'+(n>0?' active':'')+'" style="--accent:'+color+'">'
      + '<div class="ac-top"><span class="ac-dot"></span><div><div class="ac-name">'+escapeHtml(b.title_ar)+'</div><div class="ac-role">'+escapeHtml(DIR_LABEL[b.directorate]||b.directorate)+'</div></div>'
      + '<span class="ac-status'+(n>0?' on':'')+'">'+(n>0?'نشط':'بلا نشاط')+'</span></div>'
      + '<div class="ac-tools">'+tools+'</div>'
      + '<div class="ac-bars"><span style="width:'+(100*ap/tot)+'%;background:'+color+'"></span><span style="width:'+(100*rj/tot)+'%;background:var(--red)"></span></div>'
      + '<div class="ac-foot"><span>مقترَح <b>'+pr+'</b></span><span>موافَق <b>'+ap+'</b></span><span>مرفوض <b>'+rj+'</b></span></div>'
      + '</div>';
  }).join('') : '<div class="empty">لا تطابق</div>';

  document.getElementById('legend').innerHTML = Object.keys(DIR_LABEL).map(k=>
    '<span><i style="background:'+DIR_COLOR[k]+'"></i>'+DIR_LABEL[k]+'</span>'
  ).join('');
}

/* ===== vortex (canvas particle visualization) ===== */
const VORTEX = {particles:[], bot:{}, t:0};
function vortexEnsureParticles(n){
  if(VORTEX.particles.length) return;
  for(let i=0;i<n;i++){
    VORTEX.particles.push({a:Math.random()*Math.PI*2, rx:0.30+Math.random()*0.60, ry:0.10+Math.random()*0.30,
      speed:0.05+Math.random()*0.30, size:0.5+Math.random()*1.3, tilt:Math.random()*Math.PI*2});
  }
}
function vortexEnsureBots(bots){
  bots.forEach((b,i)=>{
    if(!VORTEX.bot[b.key]) VORTEX.bot[b.key] = {a: i*(Math.PI*2/Math.max(bots.length,1))};
  });
}
function drawVortex(){
  const canvas = document.getElementById('vortexCanvas');
  if(!canvas || !lastData) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if(w===0||h===0) return;
  if(canvas.width !== Math.round(w*dpr) || canvas.height !== Math.round(h*dpr)){
    canvas.width = Math.round(w*dpr); canvas.height = Math.round(h*dpr);
  }
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,w,h);
  const cx=w/2, cy=h/2, R=Math.min(w,h)*0.42;
  vortexEnsureParticles(150);
  vortexEnsureBots(lastData.bots);
  VORTEX.t += 1;

  ctx.globalCompositeOperation = 'lighter';
  VORTEX.particles.forEach(p=>{
    p.a += p.speed*0.004;
    const wob = Math.cos(p.tilt + VORTEX.t*0.0025);
    const x = cx + Math.cos(p.a)*R*p.rx;
    const y = cy + Math.sin(p.a)*R*p.ry*wob;
    const alpha = 0.08 + 0.10*Math.abs(Math.sin(p.a*2));
    ctx.beginPath(); ctx.fillStyle = 'rgba(255,120,70,'+alpha+')'; ctx.arc(x,y,p.size,0,Math.PI*2); ctx.fill();
  });

  const pulse = 1 + 0.07*Math.sin(VORTEX.t*0.045);
  const grad = ctx.createRadialGradient(cx,cy,0,cx,cy,32*pulse);
  grad.addColorStop(0,'rgba(255,160,90,.85)'); grad.addColorStop(1,'rgba(255,90,40,0)');
  ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(cx,cy,32*pulse,0,Math.PI*2); ctx.fill();

  ctx.globalCompositeOperation = 'source-over';
  ctx.beginPath(); ctx.fillStyle = '#0b0d10'; ctx.arc(cx,cy,14,0,Math.PI*2); ctx.fill();
  ctx.lineWidth = 1.6; ctx.strokeStyle = '#ff6a3d'; ctx.stroke();
  ctx.fillStyle = '#ffb199'; ctx.font = '700 9px system-ui'; ctx.textAlign = 'center';
  ctx.fillText('kernel', cx, cy+3);

  const usage = lastData.metrics.bot_usage || {};
  (lastData.bots||[]).forEach(b=>{
    const st = VORTEX.bot[b.key]; if(!st) return;
    const n = usage[b.key]||0;
    st.a += 0.0020 + Math.min(n,10)*0.0009;
    const orbitR = R*0.86;
    const x = cx + Math.cos(st.a)*orbitR, y = cy + Math.sin(st.a)*orbitR*0.50;
    const color = DIR_COLOR[b.directorate] || '#94a3b8';
    const rad = n>0 ? 8+Math.min(n,8) : 5.5;
    ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(x,y);
    ctx.strokeStyle = hexToRgba(color, n>0?0.5:0.14); ctx.lineWidth = n>0?1.3:0.7; ctx.stroke();
    ctx.beginPath(); ctx.fillStyle = '#0b0d10'; ctx.arc(x,y,rad,0,Math.PI*2); ctx.fill();
    ctx.lineWidth = n>0?2.1:1.1; ctx.strokeStyle = color; ctx.stroke();
    if(n>0){ ctx.fillStyle = color; ctx.font='800 9px system-ui'; ctx.textAlign='center'; ctx.fillText(String(n), x, y+3); }
    ctx.fillStyle = '#9fb0c8'; ctx.font='9px system-ui'; ctx.textAlign='center';
    ctx.fillText(b.title_ar, x, y+rad+12);
  });

  requestAnimationFrame(drawVortex);
}

function renderVortexStats(d){
  const m = d.metrics, pendN = d.pending_approvals.length;
  const activeBots = d.bots.filter(b => (m.bot_usage[b.key]||0) > 0).length;
  const rate = m.decisions.approval_rate;
  document.getElementById('vsActive').textContent = activeBots+'/'+d.bots.length;
  document.getElementById('vsRate').textContent = rate==null ? '—' : Math.round(rate*100)+'%';
  document.getElementById('vsTotal').textContent = m.decisions.total;
  document.getElementById('vsPending').textContent = pendN;
}

/* ===== gate gauge + trend ===== */
function gaugeSvg(pct, color){
  const r=30, c=2*Math.PI*r, off = pct==null ? c : c*(1-pct/100);
  return '<svg viewBox="0 0 78 78">'
    +'<circle cx="39" cy="39" r="'+r+'" fill="none" stroke="#1e2228" stroke-width="7"/>'
    +'<circle cx="39" cy="39" r="'+r+'" fill="none" stroke="'+color+'" stroke-width="7" stroke-linecap="round" '
    +'stroke-dasharray="'+c+'" stroke-dashoffset="'+off+'" transform="rotate(-90 39 39)" style="transition:stroke-dashoffset .5s"/>'
    +'<text x="39" y="44" text-anchor="middle" font-size="15" fill="#eef1f5" font-weight="800">'+(pct==null?'—':Math.round(pct)+'%')+'</text>'
    +'</svg>';
}
function renderGate(d){
  const m = d.metrics, rate = m.decisions.approval_rate;
  const pct = rate==null?null:rate*100;
  const color = pct==null ? '#3b4961' : (pct>=70?'#34d399':pct>=40?'#fbbf24':'#f87171');
  document.getElementById('gateGauge').outerHTML = gaugeSvg(pct, color).replace('<svg ','<svg id="gateGauge" class="g" ');
  document.getElementById('gateNum').textContent = m.decisions.approved+'/'+(m.decisions.approved+m.decisions.rejected);

  const trend = d.rate_trend || [];
  const svg = document.getElementById('gateTrend');
  if(trend.length < 2){ svg.innerHTML = '<text x="140" y="26" text-anchor="middle" font-size="10" fill="#687080">لا تاريخ كافٍ بعد</text>'; return; }
  const W=280,H=46, step = W/(trend.length-1);
  const pts = trend.map((v,i)=>[i*step, H-4-(v/100)*(H-10)]);
  const line = pts.map(p=>p[0]+','+p[1]).join(' ');
  const area = 'M'+pts[0][0]+','+H+' L'+line.replace(/ /g,' L')+' L'+pts[pts.length-1][0]+','+H+' Z';
  svg.innerHTML = '<polygon points="'+area.replace(/[ML]/g,'').trim()+'" fill="rgba(255,106,61,.12)"/>'
    + '<polyline points="'+line+'" fill="none" stroke="#ff6a3d" stroke-width="1.6"/>';
}

/* ===== bottom charts (real timeline-derived) ===== */
function renderBottomCharts(d){
  const tl = d.timeline || [];
  // نمو القرارات: تراكمي حقيقي لعدد كل القرارات بترتيبها الزمني
  const g = document.getElementById('chartGrowth');
  if(tl.length < 2){ g.innerHTML = '<text x="140" y="56" text-anchor="middle" font-size="10" fill="#687080">لا بيانات كافية</text>'; }
  else{
    const W=280,H=112,step=W/(tl.length-1);
    const pts = tl.map((e,i)=>[i*step, H-10-(i/(tl.length-1))*(H-20)]);
    const line = pts.map(p=>p[0]+','+p[1]).join(' ');
    g.innerHTML = '<polyline points="'+line+'" fill="none" stroke="#22d3ee" stroke-width="1.6"/>'
      + '<text x="4" y="14" font-size="9" fill="#687080">'+tl.length+' قيد آخر 60</text>';
  }
  // أثر القرارات بالزمن: علامة لكل حدث، لون حسب المرحلة
  const sp = document.getElementById('chartSpikes');
  if(!tl.length){ sp.innerHTML = '<text x="140" y="56" text-anchor="middle" font-size="10" fill="#687080">لا أحداث بعد</text>'; }
  else{
    const W=280,H=112,step=tl.length>1?W/(tl.length-1):0;
    const col = {proposed:'#60a5fa', approved:'#34d399', rejected:'#f87171'};
    const lane = {proposed:18, approved:46, rejected:74};
    const marks = tl.map((e,i)=>{
      const x = tl.length>1 ? i*step : W/2;
      const y = H - 14 - (lane[e.stage] || 18);
      return '<circle cx="'+x+'" cy="'+y+'" r="2.6" fill="'+(col[e.stage]||'#687080')+'"/>';
    }).join('');
    sp.innerHTML = '<line x1="0" y1="94" x2="280" y2="94" stroke="#1e2228"/>' + marks;
  }
  // خريطة الترابط: شبكة مصغّرة لنفس بيانات الدوّامة
  const syn = document.getElementById('chartSynapse');
  const bots = d.bots||[], usage = d.metrics.bot_usage||{};
  const W=280,H=112,cx=W/2,cy=H/2+4,R=40;
  let html='';
  const pts = bots.map((b,i)=>{ const a=-Math.PI/2+i*(2*Math.PI/Math.max(bots.length,1)); return {x:cx+R*Math.cos(a), y:cy+R*Math.sin(a), b}; });
  pts.forEach(p=>{ const used=(usage[p.b.key]||0)>0; html+='<line x1="'+cx+'" y1="'+cy+'" x2="'+p.x+'" y2="'+p.y+'" stroke="'+(DIR_COLOR[p.b.directorate]||'#3b4961')+'" stroke-width="'+(used?1.2:.7)+'" stroke-opacity="'+(used?.7:.25)+'"/>'; });
  pts.forEach(p=>{ const used=(usage[p.b.key]||0)>0; html+='<circle cx="'+p.x+'" cy="'+p.y+'" r="'+(used?4.2:3)+'" fill="'+(DIR_COLOR[p.b.directorate]||'#3b4961')+'" opacity="'+(used?1:.55)+'"><title>'+escapeHtml(p.b.title_ar)+'</title></circle>'; });
  html += '<circle cx="'+cx+'" cy="'+cy+'" r="5" fill="#0b0d10" stroke="#ff6a3d" stroke-width="1.4"/>';
  syn.innerHTML = html;
}

function renderPending(d){
  document.getElementById('pendingBadge').textContent = d.pending_approvals.length;
  document.getElementById('pendingBadge').className = 'badge'+(d.pending_approvals.length?' has':'');
  document.getElementById('pendingList').innerHTML = d.pending_approvals.length ? d.pending_approvals.map(p=>
    '<div class="pending-card">'
    + '<div class="meta">بواسطة: '+escapeHtml(p.proposed_by||'owner')+' · '+escapeHtml(p.created_at||'')+'</div>'
    + '<div class="what">'+escapeHtml(p.what)+'</div>'
    + '<div class="why">'+escapeHtml(p.why||'')+'</div>'
    + '<div class="btns"><button data-act="approve" data-id="'+p.id+'">وافق</button>'
    + '<button class="rej" data-act="reject" data-id="'+p.id+'">رفض</button></div>'
    + '</div>'
  ).join('') : '<div class="empty">لا طلبات معلّقة الآن</div>';
}

function renderFeed(d, filter){
  const rows = d.recent_decisions.filter(e => !filter || ((e.what||'')+(e.proposed_by||'')+(e.decided_by||'')).toLowerCase().includes(filter));
  document.getElementById('feedList').innerHTML = rows.length ? rows.map(e=>{
    const stageAr = {proposed:'اقتراح', approved:'موافقة', rejected:'رفض'}[e.stage] || e.stage;
    return '<div class="trow '+e.stage+'">'
      + '<span class="tt">'+timeShort(e.at)+'</span>'
      + '<span class="tstage">'+stageAr+'</span>'
      + '<span class="twhat" title="'+escapeHtml(e.what||'')+'">'+escapeHtml((e.what||'').slice(0,50))+'</span>'
      + '<span class="tby">'+escapeHtml(e.proposed_by||e.decided_by||'')+'</span>'
      + '</div>';
  }).join('') : '<div class="empty">لا قرارات بعد</div>';
}

async function decide(id, approved){
  try{
    await fetch('/api/dashboard/decide',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:id,approved:approved})});
  }catch(e){}
  load();
}
document.getElementById('pendingList').addEventListener('click', e=>{
  const b = e.target.closest('button[data-act]');
  if(!b) return;
  decide(b.dataset.id, b.dataset.act==='approve');
});
document.getElementById('search').addEventListener('input', e=>{
  if(!lastData) return;
  const f = e.target.value.trim().toLowerCase();
  renderLedger(lastData, f);
  renderFeed(lastData, f);
});
document.getElementById('statusStrip').addEventListener('change', async e=>{
  if(e.target.id !== 'pcToggle') return;
  const cb = e.target, enabling = cb.checked;
  const note = document.getElementById('pcNote');
  if(enabling && !confirm('تفعيل الوصول الكامل لهذا الجهاز؟ كل أمر/ملف يحتاج موافقتك قبل أي تنفيذ، لكن النطاق يصير جهازك كله.')){
    cb.checked = false; return;
  }
  cb.disabled = true; note.textContent = 'جاري التحديث…';
  try{
    const r = await fetch('/api/dashboard/pc-toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enable:enabling})});
    const d = await r.json();
    if(!d.ok){ cb.checked = !enabling; note.textContent = d.error; }
    else if(d.warning){ note.textContent = d.warning; }
  }catch(err){ cb.checked = !enabling; note.textContent = 'تعذّر الاتصال: '+err.message; }
  cb.disabled = false;
  load();
});

function tickClock(){ document.getElementById('clock').textContent = new Date().toLocaleTimeString('ar-SA'); }
setInterval(tickClock, 1000); tickClock();

let vortexStarted = false;
async function load(){
  const pulse = document.getElementById('pulse');
  try{
    const r = await fetch('/api/dashboard');
    const d = await r.json();
    lastData = d;
    renderTicker(d);
    renderLedger(d, document.getElementById('search').value.trim().toLowerCase());
    renderVortexStats(d);
    renderGate(d);
    renderBottomCharts(d);
    renderPending(d);
    renderFeed(d, document.getElementById('search').value.trim().toLowerCase());
    pulse.className = 'pulse-dot';
    if(!vortexStarted){ vortexStarted = true; requestAnimationFrame(drawVortex); }
  }catch(e){
    pulse.className = 'pulse-dot err';
  }
}
load();
setInterval(load, 4000);
</script>
</body>
</html>"""


def _rate_trend(full_ledger: list[dict], points: int = 40) -> list[int]:
    """سلسلة تاريخية حقيقية لمعدّل الموافقة التراكمي — نحسبها بأنفسنا
    بالمرور الزمني على السجل الكامل (لا بيانات مصطنعة): عند كل قرار
    موافَق/مرفوض نسجّل النسبة التراكمية لحظتها. تُستخدم لرسم خط اتجاه
    حقيقي بدل رقم ثابت وحيد."""
    approved = decided = 0
    trend: list[int] = []
    for e in full_ledger:
        if e.get("stage") == "approved":
            approved += 1
            decided += 1
        elif e.get("stage") == "rejected":
            decided += 1
        else:
            continue
        trend.append(round(100 * approved / decided))
    return trend[-points:]


def _dashboard_data() -> dict:
    full_ledger = decision.ledger(limit=200)
    what_by_request: dict[str, str] = {
        e["request_id"]: e.get("what", "") for e in full_ledger if e.get("stage") == "proposed"
    }
    recent = list(reversed(full_ledger[-20:]))
    for e in recent:
        if not e.get("what"):
            e["what"] = what_by_request.get(e.get("request_id", ""), "")

    return {
        "metrics": metrics.snapshot(),
        "status": status.snapshot(),
        "pending_approvals": approval.pending(),
        "recent_decisions": recent,
        "bots": bots.list_bots(),
        "pc_access_enabled": safety.pc_access_enabled(),
        # إضافات لوحة التحكم الحيّة — كلها حقيقية من نفس evidence.py/decision.py
        # الموجودين، لا مصدر بيانات جديد: تفصيل لكل بوت (اقتراح/موافقة/رفض)
        # لبطاقات العقدة الكثيفة، الخط الزمني الكامل للرسوم السفلية، واتجاه
        # معدّل الموافقة التاريخي الحقيقي بدل رقم لحظي وحيد.
        "bot_breakdown": evidence.audit()["by_actor"],
        "timeline": full_ledger[-60:],
        "rate_trend": _rate_trend(full_ledger),
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


def _handle_pc_toggle(body: dict, client_ip: str) -> dict:
    """تفعيل/تعطيل وضع الوصول الكامل للجهاز من اللوحة نفسها — بشرط واحد
    لا استثناء له: الطلب لازم يجي من نفس الجهاز (loopback) حرفياً. لو
    اللوحة مفتوحة عبر رابط Daytona/Fly.io مستضاف، أي زائر يوصل للرابط
    يقدر يفتح /dashboard — لولا هذا الشرط كان بإمكانه يفعّل وصولاً
    حقيقياً لجهاز المضيف عن بعد بضغطة واحدة بلا أي حاجز. هذا الشرط هو
    الحاجز الحقيقي هنا، لا مجرد تلميح بالواجهة."""
    if client_ip not in _LOOPBACK_IPS:
        return {
            "ok": False,
            "error": "تفعيل/تعطيل وصول الجهاز من اللوحة متاح فقط من جهازك مباشرة "
                     "(localhost) — لا عبر رابط مستضاف (Daytona/Fly.io)، منعاً لتفعيل "
                     "عن بعد من أي زائر يملك الرابط.",
        }

    enable = bool(body.get("enable"))
    os.environ["OS4_ALLOW_PC_ACCESS"] = "1" if enable else "0"
    try:
        set_key(env._ENV_PATH, "OS4_ALLOW_PC_ACCESS", "1" if enable else "0")
        persisted = True
    except OSError as e:  # noqa: BLE001 — فشل كتابة .env يُبلَّغ بصدق، التفعيل بالذاكرة نجح رغم ذلك
        persisted = False
        persisted_error = str(e)

    what = "تفعيل وضع الوصول الكامل للجهاز" if enable else "تعطيل وضع الوصول الكامل للجهاز"
    req = decision.propose(what=what, why="تغيير من لوحة التحكم مباشرة (localhost)", proposed_by="owner")
    decision.approve(req["request_id"], decided_by="owner-dashboard-loopback")

    result = {"ok": True, "pc_access_enabled": safety.pc_access_enabled(), "persisted": persisted}
    if not persisted:
        result["warning"] = "فُعِّل للجلسة الحالية فقط — فشلت كتابة .env على القرص: " + persisted_error
    return result


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
            elif self.path == "/api/dashboard/pc-toggle":
                self._send_json(200, _handle_pc_toggle(body, self.client_address[0]))
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
