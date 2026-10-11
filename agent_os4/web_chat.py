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

from . import approval, bots, decision, env, kernel, metrics, router, safety, status

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
  --bg:#06090f; --bg2:#0a0f18; --panel:#0c1220; --panel2:#0f1626; --border:#1c2740;
  --txt:#e6edf7; --muted:#64748b; --dim:#3b4961;
  --cyan:#22d3ee; --cyan-dim:#0e7490; --violet:#a78bfa; --amber:#fbbf24; --red:#f87171; --green:#34d399; --pink:#f472b6; --blue:#60a5fa;
  --glow-cyan:0 0 24px -4px rgba(34,211,238,.45); --glow-amber:0 0 24px -4px rgba(251,191,36,.45); --glow-red:0 0 24px -4px rgba(248,113,113,.5);
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  background:
    radial-gradient(1100px 600px at 85% -10%, rgba(34,211,238,.08), transparent 60%),
    radial-gradient(900px 500px at -10% 110%, rgba(167,139,250,.07), transparent 60%),
    var(--bg);
  color:var(--txt); min-height:100vh;
}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--dim);border-radius:8px}
* {scrollbar-width:thin; scrollbar-color:var(--dim) transparent}

.shell{display:flex;min-height:100vh}
.sidebar{
  width:58px;flex:none;display:flex;flex-direction:column;align-items:center;gap:6px;
  padding:16px 0;background:linear-gradient(180deg,var(--panel),var(--bg2));
  border-left:1px solid var(--border);
}
.sidebar .brand{
  width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(135deg,var(--cyan),var(--violet));color:#04131a;font-weight:800;font-size:.72rem;
  margin-bottom:14px;box-shadow:var(--glow-cyan);
}
.navicon{
  width:38px;height:38px;border-radius:10px;display:flex;align-items:center;justify-content:center;
  color:var(--muted);text-decoration:none;transition:.15s;position:relative;
}
.navicon svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.navicon:hover{color:var(--cyan);background:rgba(34,211,238,.08)}
.navicon-chat{margin-top:auto;color:var(--violet)}
.navicon-chat:hover{background:rgba(167,139,250,.1)}

.main{flex:1;min-width:0;display:flex;flex-direction:column}
.topbar{
  display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 22px;
  border-bottom:1px solid var(--border);background:rgba(10,15,24,.7);backdrop-filter:blur(8px);
  position:sticky;top:0;z-index:5;flex-wrap:wrap;
}
.topbar-left{display:flex;align-items:baseline;gap:10px}
.topbar-left h1{font-size:1.05rem;letter-spacing:.2px;font-weight:700;display:flex;align-items:center;gap:8px}
.topbar-left .subtitle{color:var(--muted);font-size:.78rem}
.pulse-dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 0 0 rgba(52,211,153,.6);animation:pulse 2s infinite}
.pulse-dot.err{background:var(--red);box-shadow:0 0 0 0 rgba(248,113,113,.6);animation:pulseRed 1.4s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(52,211,153,.55)}70%{box-shadow:0 0 0 8px rgba(52,211,153,0)}100%{box-shadow:0 0 0 0 rgba(52,211,153,0)}}
@keyframes pulseRed{0%{box-shadow:0 0 0 0 rgba(248,113,113,.6)}70%{box-shadow:0 0 0 8px rgba(248,113,113,0)}100%{box-shadow:0 0 0 0 rgba(248,113,113,0)}}
.topbar-right{display:flex;align-items:center;gap:10px}
.search{
  background:var(--panel2);border:1px solid var(--border);border-radius:9px;padding:8px 12px;color:var(--txt);
  font-size:.82rem;width:220px;direction:rtl;
}
.search:focus{outline:none;border-color:var(--cyan-dim)}
.clock{font-variant-numeric:tabular-nums;color:var(--muted);font-size:.8rem;min-width:70px;text-align:center}

.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;padding:18px 22px 0}
.kpi{
  background:linear-gradient(160deg,var(--panel),var(--panel2));border:1px solid var(--border);border-radius:14px;
  padding:14px 16px;position:relative;overflow:hidden;
}
.kpi::after{content:"";position:absolute;inset:0;border-radius:14px;padding:1px;pointer-events:none;
  background:linear-gradient(140deg,rgba(255,255,255,.06),transparent 40%)}
.kpi .klabel{color:var(--muted);font-size:.72rem;display:flex;align-items:center;gap:6px;margin-bottom:8px}
.kpi .klabel svg{width:13px;height:13px;stroke:currentColor;fill:none;stroke-width:1.8}
.kpi .kval{font-size:1.65rem;font-weight:800;font-variant-numeric:tabular-nums;line-height:1}
.kpi .ksub{color:var(--muted);font-size:.68rem;margin-top:5px}
.kpi.warn{border-color:rgba(251,191,36,.35);box-shadow:var(--glow-amber)}
.kpi.ok-glow{border-color:rgba(52,211,153,.3)}
.kpi.off{opacity:.55}
.gauge-wrap{display:flex;align-items:center;gap:10px}
.gauge-wrap svg{width:52px;height:52px;flex:none}

.pc-card{opacity:1 !important}
.pc-row{display:flex;align-items:center;gap:10px;margin-top:2px}
.switch{position:relative;display:inline-block;width:38px;height:21px;flex:none}
.switch input{opacity:0;width:0;height:0}
.switch .slider{position:absolute;inset:0;background:var(--dim);border-radius:99px;cursor:pointer;transition:.18s}
.switch .slider::before{content:"";position:absolute;height:15px;width:15px;left:3px;top:3px;background:#e2e8f0;border-radius:50%;transition:.18s}
.switch input:checked + .slider{background:var(--amber)}
.switch input:checked + .slider::before{transform:translateX(17px)}
.switch input:disabled + .slider{opacity:.5;cursor:not-allowed}

.grid-main{display:grid;grid-template-columns:1.3fr 1fr;gap:14px;padding:16px 22px 22px;align-items:start}
@media(max-width:980px){.grid-main{grid-template-columns:1fr}}
.col-left,.col-right{display:flex;flex-direction:column;gap:14px;min-width:0}

.panel{background:var(--panel);border:1px solid var(--border);border-radius:14px;overflow:hidden}
.panel-head{display:flex;align-items:center;justify-content:space-between;padding:13px 16px;border-bottom:1px solid var(--border)}
.panel-head h2{font-size:.85rem;font-weight:700;color:#cbd5e1}
.panel-tag{font-size:.65rem;color:var(--cyan);border:1px solid rgba(34,211,238,.35);padding:2px 8px;border-radius:99px;background:rgba(34,211,238,.06)}
.badge{font-size:.72rem;background:var(--dim);color:var(--txt);min-width:20px;text-align:center;padding:2px 7px;border-radius:99px}
.badge.has{background:rgba(251,191,36,.18);color:var(--amber);border:1px solid rgba(251,191,36,.4)}

#graph{width:100%;height:290px;display:block}
.legend{display:flex;flex-wrap:wrap;gap:8px 14px;padding:10px 16px 14px;border-top:1px solid var(--border)}
.legend span{font-size:.68rem;color:var(--muted);display:flex;align-items:center;gap:5px}
.legend i{width:8px;height:8px;border-radius:50%;display:inline-block}

.bots-list{padding:6px 10px 10px}
.bot-row{display:flex;align-items:center;gap:10px;padding:9px 8px;border-radius:9px;font-size:.8rem}
.bot-row:hover{background:var(--panel2)}
.bot-dot{width:9px;height:9px;border-radius:50%;flex:none}
.bot-name{font-weight:600;flex:none;min-width:118px}
.bot-dir{color:var(--muted);font-size:.72rem;flex:none}
.bot-tools{display:flex;gap:5px;flex-wrap:wrap;margin-right:auto}
.tag{font-size:.65rem;background:var(--panel2);border:1px solid var(--border);color:#9fb0c8;padding:2px 7px;border-radius:7px}
.bot-usage{font-size:.68rem;color:var(--cyan);min-width:30px;text-align:left}

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
  font-family:ui-monospace,"SF Mono",Consolas,monospace;font-size:.74rem;max-height:340px;overflow-y:auto;padding:4px 0;
}
.trow{display:flex;gap:9px;padding:7px 16px;border-right:2px solid transparent;align-items:baseline}
.trow:hover{background:var(--panel2)}
.trow .tt{color:var(--muted);flex:none;font-variant-numeric:tabular-nums}
.trow .tstage{flex:none;font-weight:700;width:76px}
.trow .twhat{color:#c3cedd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.trow .tby{color:var(--muted);flex:none}
.trow.proposed{border-color:rgba(96,165,250,.5)}
.trow.proposed .tstage{color:var(--blue)}
.trow.approved{border-color:rgba(52,211,153,.5)}
.trow.approved .tstage{color:var(--green)}
.trow.rejected{border-color:rgba(248,113,113,.5)}
.trow.rejected .tstage{color:var(--red)}

.empty{color:var(--muted);font-size:.82rem;text-align:center;padding:24px 10px}
.hidden{display:none !important}
footer{padding:14px 22px 22px;color:var(--dim);font-size:.7rem;text-align:center}
</style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="brand">OS4</div>
    <nav>
      <a href="#overview" class="navicon" title="نظرة عامة"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg></a>
      <a href="#network" class="navicon" title="شبكة البوتات"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="2.4"/><circle cx="4" cy="5" r="1.8"/><circle cx="20" cy="5" r="1.8"/><circle cx="4" cy="19" r="1.8"/><circle cx="20" cy="19" r="1.8"/><line x1="10.2" y1="10.6" x2="5.4" y2="6.2"/><line x1="13.8" y1="10.6" x2="18.6" y2="6.2"/><line x1="10.2" y1="13.4" x2="5.4" y2="17.8"/><line x1="13.8" y1="13.4" x2="18.6" y2="17.8"/></svg></a>
      <a href="#pending" class="navicon" title="طلبات معلّقة"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 3.2"/></svg></a>
      <a href="#feed" class="navicon" title="السجل الحي"><svg viewBox="0 0 24 24"><path d="M4 17V7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-5 3z"/><line x1="8" y1="9" x2="16" y2="9"/><line x1="8" y1="13" x2="13" y2="13"/></svg></a>
      <a href="#bots" class="navicon" title="البوتات"><svg viewBox="0 0 24 24"><rect x="5" y="8" width="14" height="11" rx="2.2"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/><circle cx="9.5" cy="13.2" r="1"/><circle cx="14.5" cy="13.2" r="1"/></svg></a>
    </nav>
    <a href="/" class="navicon navicon-chat" title="الشات"><svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></a>
  </aside>

  <div class="main">
    <header class="topbar">
      <div class="topbar-left">
        <h1>لوحة تحكم agent_os4 <span class="pulse-dot" id="pulse"></span></h1>
        <span class="subtitle">نواة واحدة · بوابة موافقة واحدة · بيانات حية فقط</span>
      </div>
      <div class="topbar-right">
        <input id="search" class="search" placeholder="فلتر البوتات أو السجل…">
        <span class="clock" id="clock">--:--:--</span>
      </div>
    </header>

    <section class="kpi-row" id="overview"></section>

    <section class="grid-main">
      <div class="col-left">
        <div class="panel" id="network">
          <div class="panel-head"><h2>شبكة البوتات (حول نواة kernel.py)</h2><span class="panel-tag">مباشر</span></div>
          <svg id="graph" viewBox="0 0 560 290"></svg>
          <div class="legend" id="legend"></div>
        </div>
        <div class="panel" id="bots">
          <div class="panel-head"><h2>البوتات المسجّلة</h2></div>
          <div class="bots-list" id="botsList"></div>
        </div>
      </div>
      <div class="col-right">
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

function kpiIcon(name){
  const icons = {
    pending:'<path d="M12 7v5l3.2 3.2"/><circle cx="12" cy="12" r="9"/>',
    rate:'<path d="M3 17l5-5 4 4 8-8"/>',
    memory:'<rect x="4" y="4" width="16" height="16" rx="2.5"/><line x1="4" y1="9" x2="20" y2="9"/><line x1="9" y1="9" x2="9" y2="20"/>',
    skills:'<path d="M12 3l2.4 5.6L20 9.3l-4.3 3.9L16.8 19 12 15.9 7.2 19l1.1-5.8L4 9.3l5.6-.7z"/>',
    decisions:'<path d="M4 6h16M4 12h10M4 18h7"/>',
    bots:'<rect x="5" y="8" width="14" height="11" rx="2.2"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    pc:'<rect x="3" y="4" width="18" height="12" rx="1.6"/><line x1="8" y1="20" x2="16" y2="20"/><line x1="12" y1="16" x2="12" y2="20"/>'
  };
  return icons[name] || '';
}
function kpi(label, value, sub, opts){
  opts = opts || {};
  const cls = ['kpi']; if(opts.warn) cls.push('warn'); if(opts.ok) cls.push('ok-glow'); if(opts.off) cls.push('off');
  return '<div class="'+cls.join(' ')+'">'
    + '<div class="klabel"><svg viewBox="0 0 24 24">'+kpiIcon(opts.icon)+'</svg>'+label+'</div>'
    + '<div class="kval">'+value+'</div>'
    + (sub?'<div class="ksub">'+sub+'</div>':'')
    + '</div>';
}
function gaugeSvg(pct, color){
  const r=21, c=2*Math.PI*r, off=c*(1-pct/100);
  return '<svg viewBox="0 0 52 52">'
    +'<circle cx="26" cy="26" r="'+r+'" fill="none" stroke="#1c2740" stroke-width="5"/>'
    +'<circle cx="26" cy="26" r="'+r+'" fill="none" stroke="'+color+'" stroke-width="5" stroke-linecap="round" '
    +'stroke-dasharray="'+c+'" stroke-dashoffset="'+off+'" transform="rotate(-90 26 26)" style="transition:stroke-dashoffset .5s"/>'
    +'<text x="26" y="30" text-anchor="middle" font-size="12" fill="#e6edf7" font-weight="700">'+Math.round(pct)+'%</text>'
    +'</svg>';
}
function escapeHtml(s){
  return String(s==null?'':s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function timeShort(at){ return (at||'').split(' ')[1] || at || ''; }

function renderKpis(d){
  const m = d.metrics, s = d.status, pendN = d.pending_approvals.length;
  const rate = m.decisions.approval_rate;
  const ratePct = rate==null ? 0 : Math.round(rate*100);
  const rateColor = rate==null ? '#3b4961' : (ratePct>=70?'#34d399':ratePct>=40?'#fbbf24':'#f87171');
  let html = '';
  html += kpi('طلبات معلّقة', pendN, pendN?'تحتاج قرارك الآن':'لا شيء بالانتظار', {icon:'pending', warn:pendN>0});
  html += '<div class="kpi'+(rate==null?' off':'')+'"><div class="klabel"><svg viewBox="0 0 24 24">'+kpiIcon('rate')+'</svg>معدّل الموافقة</div>'
    + '<div class="gauge-wrap">'+gaugeSvg(ratePct, rateColor)+'<div><div class="kval" style="font-size:1.1rem">'+m.decisions.approved+'/'+(m.decisions.approved+m.decisions.rejected)+'</div><div class="ksub">موافَق/محسوم</div></div></div></div>';
  html += kpi('إجمالي القرارات', m.decisions.total, m.decisions.proposed+' مُقترَحة', {icon:'decisions'});
  html += kpi('سجلات الذاكرة', s.memory_entries, 'memory.py', {icon:'memory'});
  html += kpi('مهارات مسجّلة', m.skills_registered, 'skills.py', {icon:'skills'});
  html += kpi('البوتات النشطة', d.bots.length, '8 مديريات', {icon:'bots'});
  html += kpi('Claude', s.claude_configured?'مفعّل':'غير مفعّل', 'brain.py', {ok:s.claude_configured, off:!s.claude_configured});
  html += kpi('Daytona', s.daytona_configured?'مفعّل':'غير مفعّل', 'sandbox.py', {ok:s.daytona_configured, off:!s.daytona_configured});
  html += '<div class="kpi pc-card'+(d.pc_access_enabled?' warn':' off')+'">'
    + '<div class="klabel"><svg viewBox="0 0 24 24">'+kpiIcon('pc')+'</svg>الوصول الكامل للجهاز</div>'
    + '<div class="pc-row">'
    + '<label class="switch"><input type="checkbox" id="pcToggle"'+(d.pc_access_enabled?' checked':'')+'><span class="slider"></span></label>'
    + '<span class="kval" style="font-size:1rem">'+(d.pc_access_enabled?'مفعّل':'معطّل')+'</span>'
    + '</div>'
    + '<div class="ksub" id="pcNote">'+(d.pc_access_enabled?'نشط الآن — كل أمر يحتاج موافقتك رغم ذلك':'يعمل فقط من جهازك (localhost)')+'</div>'
    + '</div>';
  document.getElementById('overview').innerHTML = html;
}

function renderGraph(d){
  const bots = d.bots, usage = d.metrics.bot_usage || {};
  const W=560,H=290,cx=W/2,cy=H/2+4,R=112;
  let svg = '';
  const pts = bots.map((b,i)=>{
    const a = -Math.PI/2 + i*(2*Math.PI/bots.length);
    return {x:cx+R*Math.cos(a), y:cy+R*Math.sin(a), b};
  });
  pts.forEach(p=>{
    const used = (usage[p.b.key]||0) > 0;
    svg += '<line x1="'+cx+'" y1="'+cy+'" x2="'+p.x+'" y2="'+p.y+'" stroke="'+(DIR_COLOR[p.b.directorate]||'#3b4961')+'" '
      + 'stroke-width="'+(used?1.6:1)+'" stroke-opacity="'+(used?0.75:0.28)+'" stroke-dasharray="3 4">'
      + '<animate attributeName="stroke-dashoffset" from="14" to="0" dur="1.1s" repeatCount="indefinite"/></line>';
  });
  svg += '<circle cx="'+cx+'" cy="'+cy+'" r="22" fill="#0c1220" stroke="#22d3ee" stroke-width="2"><animate attributeName="r" values="22;24;22" dur="2.4s" repeatCount="indefinite"/></circle>';
  svg += '<text x="'+cx+'" y="'+(cy+4)+'" text-anchor="middle" font-size="9.5" fill="#22d3ee" font-weight="700">kernel</text>';
  pts.forEach(p=>{
    const n = usage[p.b.key]||0, used = n>0, color = DIR_COLOR[p.b.directorate]||'#3b4961';
    svg += '<circle cx="'+p.x+'" cy="'+p.y+'" r="'+(used?15:12)+'" fill="#0c1220" stroke="'+color+'" stroke-width="'+(used?2.2:1.4)+'" opacity="'+(used?1:.6)+'"><title>'+escapeHtml(p.b.title_ar)+' — '+escapeHtml(DIR_LABEL[p.b.directorate]||p.b.directorate)+' — استُخدم '+n+' مرة</title></circle>';
    if(used) svg += '<text x="'+p.x+'" y="'+(p.y+3.5)+'" text-anchor="middle" font-size="9" fill="'+color+'" font-weight="800">'+n+'</text>';
    svg += '<text x="'+p.x+'" y="'+(p.y+(used?27:23))+'" text-anchor="middle" font-size="9" fill="#9fb0c8">'+escapeHtml(p.b.title_ar)+'</text>';
  });
  document.getElementById('graph').innerHTML = svg;
  document.getElementById('legend').innerHTML = Object.keys(DIR_LABEL).map(k=>
    '<span><i style="background:'+DIR_COLOR[k]+'"></i>'+DIR_LABEL[k]+'</span>'
  ).join('');
}

function renderBots(d, filter){
  const usage = d.metrics.bot_usage || {};
  const rows = d.bots.filter(b => !filter || (b.title_ar+b.directorate).toLowerCase().includes(filter));
  document.getElementById('botsList').innerHTML = rows.length ? rows.map(b=>
    '<div class="bot-row" data-k="'+(b.title_ar+' '+b.directorate).toLowerCase()+'">'
    + '<span class="bot-dot" style="background:'+(DIR_COLOR[b.directorate]||'#3b4961')+'"></span>'
    + '<span class="bot-name">'+escapeHtml(b.title_ar)+'</span>'
    + '<span class="bot-dir">'+escapeHtml(DIR_LABEL[b.directorate]||b.directorate)+'</span>'
    + '<span class="bot-tools">'+(b.allowed_tools.length?b.allowed_tools.map(t=>'<span class="tag">'+escapeHtml(t)+'</span>').join(''):'<span class="tag">محادثة فقط</span>')+'</span>'
    + '<span class="bot-usage">×'+(usage[b.key]||0)+'</span>'
    + '</div>'
  ).join('') : '<div class="empty">لا تطابق</div>';
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
      + '<span class="twhat" title="'+escapeHtml(e.what||'')+'">'+escapeHtml((e.what||'').slice(0,54))+'</span>'
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
  renderBots(lastData, f);
  renderFeed(lastData, f);
});
document.getElementById('overview').addEventListener('change', async e=>{
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

async function load(){
  const pulse = document.getElementById('pulse');
  try{
    const r = await fetch('/api/dashboard');
    const d = await r.json();
    lastData = d;
    renderKpis(d);
    renderGraph(d);
    renderBots(d, document.getElementById('search').value.trim().toLowerCase());
    renderPending(d);
    renderFeed(d, document.getElementById('search').value.trim().toLowerCase());
    pulse.className = 'pulse-dot';
  }catch(e){
    pulse.className = 'pulse-dot err';
  }
}
load();
setInterval(load, 4000);
</script>
</body>
</html>"""


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
