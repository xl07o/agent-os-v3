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
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from dotenv import set_key

from . import agent_memory, agent_skills, approval, bots, ceo, chatroom, sessions, decision, env, evidence, kernel, market, metrics, rooms, router, safety, self_improve, spend, status, widgets

_LOOPBACK_IPS = {"127.0.0.1", "::1"}
_LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}
_LOCAL_ONLY_ERROR = (
    "{what} من اللوحة متاح فقط من جهازك مباشرة (localhost) — لا عبر رابط "
    "مستضاف (Daytona/Fly.io)، منعاً لأي زائر يملك الرابط."
)

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
.msg.review{background:transparent;align-self:flex-end;border:1px dashed #a78bfa55;color:#c9bbfa;font-size:.82rem}
.msg.review b{color:#a78bfa}
.irow{display:flex;gap:8px}
#inp{flex:1;padding:11px 15px;background:var(--panel);border:1px solid var(--border);border-radius:11px;color:var(--txt);font-size:0.9rem;direction:rtl}
#inp:focus{outline:none;border-color:var(--cyan)}
button{padding:10px 20px;background:linear-gradient(135deg,var(--cyan),#0e9fb8);border:none;border-radius:11px;color:#04131a;cursor:pointer;font-size:0.9rem;font-weight:700;white-space:nowrap}
button:hover{filter:brightness(1.08)}
button:disabled{background:#334155;color:#94a3b8;cursor:not-allowed;filter:none}
</style>
</head>
<body>
<header><span class="brand">agent_os4 <span class="dot"></span></span><span style="display:flex;gap:8px"><a href="/rooms">غرف الأقسام</a><a href="/dashboard">لوحة التحكم ←</a></span></header>
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
function addConfirm(what,why,reqId,review){
  addMsg('يحتاج موافقتك: '+what+(why?' — '+why:''),'bot');
  if(review){
    const r=document.createElement('div');r.className='msg review';
    const label=document.createElement('b');label.textContent='رأي المراجع المستقل:';
    r.appendChild(label);r.appendChild(document.createElement('br'));
    r.appendChild(document.createTextNode(review));
    document.getElementById('msgs').appendChild(r);
  }
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
    if(d.needs_confirmation){addConfirm(d.what,d.why,d.request_id,d.independent_review);}
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
    if(d.needs_confirmation){addConfirm(d.what,d.why,d.request_id,d.independent_review);}
    else{addMsg(d.reply||d.error||'(لا رد)',d.error?'err':'bot');}
  }catch(e){addMsg('خطأ: '+e.message,'err');}
  document.getElementById('btn').disabled=false;
}
document.getElementById('inp').addEventListener('keydown',e=>{if(e.key==='Enter')send();});
</script>
</body>
</html>"""


_ROOMS_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>غرف الأقسام — agent_os4</title>
<style>
:root{
  --bg:#060708; --panel:#0b0d10; --panel2:#0e1114; --border:#1e2228;
  --txt:#eef1f5; --muted:#687080; --dim:#2c323c;
  --cyan:#22d3ee; --ember:#ff6a3d; --green:#34d399; --red:#f87171; --amber:#fbbf24; --violet:#a78bfa;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;background:var(--bg);color:var(--txt);min-height:100vh}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--dim);border-radius:8px}

.shell{display:flex;min-height:100vh}
.sidebar{width:54px;flex:none;display:flex;flex-direction:column;align-items:center;gap:6px;padding:16px 0;background:var(--panel);border-left:1px solid var(--border)}
.sidebar .brand{width:32px;height:32px;border-radius:9px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,var(--ember),#b3291f);color:#1a0804;font-weight:800;font-size:.68rem;margin-bottom:14px}
.navicon{width:36px;height:36px;border-radius:9px;display:flex;align-items:center;justify-content:center;color:var(--muted);text-decoration:none}
.navicon svg{width:17px;height:17px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.navicon:hover{color:var(--ember);background:rgba(255,106,61,.08)}
.navicon.on{color:var(--ember);background:rgba(255,106,61,.1)}

.main{flex:1;min-width:0;display:flex;flex-direction:column}
header.top{display:flex;align-items:center;justify-content:space-between;padding:12px 18px;border-bottom:1px solid var(--border);background:rgba(10,11,13,.85)}
header.top h1{font-size:.95rem;font-weight:700}
header.top small{color:var(--muted);font-size:.72rem;display:block;margin-top:2px}

.rooms-shell{flex:1;display:flex;min-height:0}
.room-list{width:270px;flex:none;border-left:1px solid var(--border);overflow-y:auto;padding:8px}
.room-item{display:flex;align-items:center;gap:9px;padding:10px 10px;border-radius:10px;cursor:pointer;margin-bottom:3px}
.room-item:hover{background:var(--panel2)}
.room-item.sel{background:var(--panel2);box-shadow:0 0 0 1px var(--ember) inset}
.room-dot{width:9px;height:9px;border-radius:50%;flex:none}
.room-item .ri-name{font-size:.82rem;font-weight:700}
.room-item .ri-prev{font-size:.68rem;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px}
.room-item .ri-time{font-size:.6rem;color:var(--dim);margin-right:auto}

.room-main{flex:1;min-width:0;display:flex;flex-direction:column}
.room-head{padding:12px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px}
.room-head b{font-size:.9rem}
.room-head small{color:var(--muted);font-size:.72rem}
.room-msgs{flex:1;overflow-y:auto;padding:16px 18px;display:flex;flex-direction:column;gap:9px}
.msg{padding:9px 13px;border-radius:11px;max-width:72%;white-space:pre-wrap;line-height:1.55;font-size:.86rem}
.msg.user{background:linear-gradient(135deg,#2563eb,#1d4ed8);align-self:flex-start}
.msg.bot{background:var(--panel);align-self:flex-end;border:1px solid var(--border)}
.msg.review{background:transparent;align-self:flex-end;border:1px dashed #a78bfa55;color:#c9bbfa;font-size:.8rem}
.msg.review b{color:#a78bfa}
.msg .who{display:block;font-size:.64rem;color:rgba(255,255,255,.65);margin-bottom:3px}
.mon-row{display:flex;gap:9px;align-items:baseline;font-size:.8rem;padding:6px 0;border-bottom:1px solid var(--border)}
.mon-room{flex:none;font-size:.66rem;padding:2px 8px;border-radius:99px;border:1px solid var(--border)}
.mon-speaker{flex:none;color:var(--muted);font-size:.72rem}
.mon-text{color:#c3cedd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mon-time{flex:none;color:var(--dim);font-size:.66rem}
.irow{display:flex;gap:8px;padding:12px 18px;border-top:1px solid var(--border)}
#roomInp{flex:1;padding:10px 14px;background:var(--panel2);border:1px solid var(--border);border-radius:10px;color:var(--txt);font-size:.86rem;direction:rtl}
#roomInp:focus{outline:none;border-color:var(--ember)}
button{padding:9px 18px;background:linear-gradient(135deg,var(--cyan),#0e9fb8);border:none;border-radius:10px;color:#04131a;cursor:pointer;font-size:.84rem;font-weight:700}
button:hover{filter:brightness(1.08)}
button:disabled{background:#334155;color:#94a3b8;cursor:not-allowed}
button.rej{background:var(--panel2);color:var(--txt);border:1px solid var(--border)}
.confirm-row{display:flex;gap:7px;align-self:flex-end}
.empty{color:var(--muted);font-size:.84rem;text-align:center;padding:30px 10px}
.hidden{display:none !important}

.meeting-panel{padding:14px 18px;border-bottom:1px solid var(--border);background:var(--panel)}
.bot-check-row{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:10px}
.bot-check{display:flex;align-items:center;gap:6px;font-size:.76rem;background:var(--panel2);border:1px solid var(--border);border-radius:99px;padding:5px 11px;cursor:pointer;user-select:none}
.bot-check input{accent-color:var(--ember)}
.bot-check.checked{border-color:var(--ember)}
#meetingTopic{width:100%;background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:10px 14px;color:var(--txt);font-size:.84rem;direction:rtl;resize:vertical;min-height:52px;font-family:inherit}
#meetingTopic:focus{outline:none;border-color:var(--ember)}
.meeting-controls{display:flex;justify-content:space-between;align-items:center;margin-top:9px;gap:10px}
.meeting-controls label{font-size:.76rem;color:var(--muted);display:flex;align-items:center;gap:6px}
.meeting-controls select{background:var(--panel2);border:1px solid var(--border);border-radius:7px;color:var(--txt);padding:5px 8px;font-size:.78rem}
.outcome-card{background:var(--panel2);border:1px solid var(--border);border-right:3px solid var(--amber);border-radius:11px;padding:11px 13px;align-self:stretch;margin-bottom:4px}
.outcome-card .oc-title{font-size:.7rem;color:var(--muted);margin-bottom:4px}
.outcome-card .oc-rec{font-weight:700;font-size:.86rem;margin-bottom:6px}
.outcome-card .oc-sup{font-size:.68rem;color:var(--muted);margin-bottom:8px}
</style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="brand">OS4</div>
    <a href="/" class="navicon" title="الشات"><svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></a>
    <a href="/dashboard" class="navicon" title="لوحة التحكم"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg></a>
    <a href="/rooms" class="navicon on" title="غرف الأقسام"><svg viewBox="0 0 24 24"><rect x="5" y="8" width="14" height="11" rx="2.2"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/><circle cx="9.5" cy="13.2" r="1"/><circle cx="14.5" cy="13.2" r="1"/></svg></a>
  </aside>
  <div class="main">
    <header class="top">
      <div><h1>غرف الأقسام</h1><small>كل مديرية بخيطها الخاص — غرفة "مراقبة" تجمعها كلها قدامك حيّاً</small></div>
    </header>
    <div class="rooms-shell">
      <aside class="room-list" id="roomList"></aside>
      <div class="room-main">
        <div class="room-head" id="roomHead"></div>
        <div class="meeting-panel hidden" id="meetingPanel">
          <div class="bot-check-row" id="botCheckRow"></div>
          <textarea id="meetingTopic" placeholder="موضوع الاجتماع — مثلاً: هل نطلق الميزة الجديدة الآن؟"></textarea>
          <div class="meeting-controls">
            <label>جولات النقاش
              <select id="meetingRounds"><option value="1">1</option><option value="2">2</option><option value="3">3</option></select>
            </label>
            <button id="meetingStartBtn">ابدأ الاجتماع</button>
          </div>
        </div>
        <div class="room-msgs" id="roomMsgs"></div>
        <div class="irow" id="roomInputRow">
          <input id="roomInp" placeholder="اكتب رسالتك…" autocomplete="off">
          <button id="roomSendBtn">إرسال</button>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
const MONITOR = '__monitor__';
const MEETING = '__meeting__';
const DIR_COLOR = {
  intelligence:'#60a5fa', engineering:'#22d3ee', financial:'#34d399', security:'#f87171',
  operations:'#fbbf24', research:'#a78bfa', customer_business:'#f472b6', learning_evolution:'#2dd4bf'
};
let selected = MONITOR;
let roomsCache = [];
let checkedBots = new Set();
// بطاقات تنتظر قرارك (نفّذ/تجاهل، وافق/رفض) — التحديث الدوري كل 4 ثوانٍ
// يعيد رسم المحادثة من السيرفر، فنعيد تركيبها بعده بدل ما تختفي قبل ما تقرر.
const liveCards = [];
function keepCard(el){ liveCards.push({room: selected, el: el}); }
function dropCard(el){ const i = liveCards.findIndex(c=>c.el===el); if(i>=0) liveCards.splice(i,1); }
function reattachCards(wrap){ liveCards.filter(c=>c.room===selected).forEach(c=>wrap.appendChild(c.el)); }

function escapeHtml(s){
  return String(s==null?'':s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function roomColor(key){
  if(key===MONITOR) return '#ff6a3d';
  if(key===MEETING) return '#a78bfa';
  if(key==='executive') return '#fbbf24';
  if(key==='chief_decision_officer') return '#f472b6';
  const r = roomsCache.find(x=>x.key===key);
  return (r && DIR_COLOR[r.directorate]) || '#687080';
}
function speakerLabel(speaker, room){
  if(speaker==='owner') return 'أنت';
  if(speaker==='ceo') return 'الرئيس التنفيذي';
  if(speaker==='executive') return 'الإدارة العليا';
  if(speaker==='chief_decision_officer') return 'مدير القرارات';
  return roomTitle(speaker || room);
}
function roomTitle(key){
  if(key===MONITOR) return 'مراقبة — كل الأقسام';
  if(key===MEETING) return 'الاجتماع الجماعي';
  const r = roomsCache.find(x=>x.key===key);
  return r ? r.title_ar : key;
}

async function loadRoomList(){
  const r = await fetch('/api/rooms');
  const d = await r.json();
  roomsCache = d.rooms;
  const items = [
    {key:MONITOR, title_ar:'مراقبة — كل الأقسام', last_text:'عرض حي لكل محادثات الأقسام مجتمعة', last_at:''},
    {key:MEETING, title_ar:'الاجتماع الجماعي', last_text:'نقاش جماعي بين أقسام تختارها → توصية → بوابة الموافقة', last_at:''},
    ...d.rooms,
  ];
  document.getElementById('roomList').innerHTML = items.map(r=>
    '<div class="room-item'+(selected===r.key?' sel':'')+'" data-key="'+r.key+'">'
    + '<span class="room-dot" style="background:'+roomColor(r.key)+'"></span>'
    + '<div style="min-width:0;flex:1"><div class="ri-name">'+escapeHtml(r.title_ar)+'</div>'
    + '<div class="ri-prev">'+escapeHtml(r.last_text||'لا رسائل بعد')+'</div></div>'
    + '<span class="ri-time">'+escapeHtml((r.last_at||'').split(' ')[1]||'')+'</span>'
    + '</div>'
  ).join('');
  if(document.getElementById('botCheckRow').children.length === 0) renderBotChecks();
}

function renderBotChecks(){
  document.getElementById('botCheckRow').innerHTML = roomsCache.filter(r=>r.key!=='executive').map(r=>
    '<label class="bot-check" data-key="'+r.key+'"><input type="checkbox" value="'+r.key+'">'+escapeHtml(r.title_ar)+'</label>'
  ).join('');
}

function renderHead(){
  document.getElementById('roomHead').innerHTML =
    '<span class="room-dot" style="background:'+roomColor(selected)+'"></span><b>'+escapeHtml(roomTitle(selected))+'</b>'
    + (selected===MONITOR?'<small>— قراءة فقط</small>':'')
    + (selected===MEETING?'<small>اختر الأقسام، اكتب الموضوع، وابدأ</small>':'');
  document.getElementById('roomInputRow').className = (selected===MONITOR||selected===MEETING) ? 'irow hidden' : 'irow';
  document.getElementById('meetingPanel').className = selected===MEETING ? 'meeting-panel' : 'meeting-panel hidden';
}

function addConfirm(what, why, reqId, review){
  const wrap = document.getElementById('roomMsgs');
  const block = document.createElement('div');
  const d = document.createElement('div');
  d.className = 'msg bot';
  d.innerHTML = '<span class="who">'+escapeHtml(roomTitle(selected))+'</span>يحتاج موافقتك: '+escapeHtml(what)+(why?' — '+escapeHtml(why):'');
  block.appendChild(d);
  if(review){
    const rv = document.createElement('div');
    rv.className = 'msg review';
    rv.innerHTML = '<b>رأي المراجع المستقل:</b><br>'+escapeHtml(review);
    block.appendChild(rv);
  }
  const row = document.createElement('div');
  row.className = 'confirm-row';
  row.innerHTML = '<button data-conf="1" data-id="'+escapeHtml(reqId)+'">نفّذ</button><button class="rej" data-conf="0" data-id="'+escapeHtml(reqId)+'">تجاهل</button>';
  block.appendChild(row);
  wrap.appendChild(block);
  keepCard(block);
  wrap.scrollTop = 1e9;
}

async function loadThread(){
  if(selected===MONITOR){
    const r = await fetch('/api/rooms/monitor');
    const d = await r.json();
    const wrap = document.getElementById('roomMsgs');
    wrap.innerHTML = d.messages.length ? d.messages.map(m=>
      '<div class="mon-row"><span class="mon-room" style="color:'+roomColor(m.room)+';border-color:'+roomColor(m.room)+'66">'+escapeHtml(roomTitle(m.room))+'</span>'
      + '<span class="mon-speaker">'+escapeHtml(speakerLabel(m.speaker, m.room))+'</span>'
      + '<span class="mon-text">'+escapeHtml(m.text)+'</span>'
      + '<span class="mon-time">'+escapeHtml((m.at||'').split(' ')[1]||'')+'</span></div>'
    ).join('') : '<div class="empty">لا محادثات بعد بأي قسم</div>';
    return;
  }
  if(selected===MEETING){
    const r = await fetch('/api/meeting');
    const d = await r.json();
    const wrap = document.getElementById('roomMsgs');
    wrap.innerHTML = d.messages.length ? d.messages.map(m=>{
      const mine = m.speaker === 'owner';
      const color = roomColor(m.speaker);
      return '<div class="msg '+(mine?'user':'bot')+'">'+(mine?'':'<span class="who" style="color:'+color+'">'+escapeHtml(speakerLabel(m.speaker, m.speaker))+'</span>')+escapeHtml(m.text)+'</div>';
    }).join('') : '<div class="empty">ما فيه اجتماعات بعد — اختر الأقسام واكتب موضوعاً وابدأ</div>';
    reattachCards(wrap);
    wrap.scrollTop = 1e9;
    return;
  }
  const r = await fetch('/api/room?key='+encodeURIComponent(selected));
  const d = await r.json();
  const wrap = document.getElementById('roomMsgs');
  wrap.innerHTML = d.messages.length ? d.messages.map(m=>{
    const mine = m.speaker === 'owner';
    return '<div class="msg '+(mine?'user':'bot')+'">'+(mine?'':'<span class="who">'+escapeHtml(speakerLabel(m.speaker, selected))+'</span>')+escapeHtml(m.text)+'</div>';
  }).join('') : '<div class="empty">'+(selected==='executive'?'اكتب للرئيس التنفيذي — هو يوزّع الشغل على الموظفين أو يقترح توظيف':'ابدأ المحادثة مع '+escapeHtml(roomTitle(selected)))+'</div>';
  reattachCards(wrap);
  wrap.scrollTop = 1e9;
}

function addProposalCard(p){
  const wrap = document.getElementById('roomMsgs');
  const card = document.createElement('div'); card.className='outcome-card';
  card.innerHTML = '<div class="oc-title">اقتراح من الرئيس التنفيذي ('+escapeHtml(p.kind)+')</div>'
    + '<div class="oc-rec">'+escapeHtml(p.what)+'</div>'
    + (p.diff ? '<pre class="oc-sup" style="white-space:pre-wrap;direction:ltr;text-align:left;max-height:260px;overflow:auto">'+escapeHtml(p.diff)+'</pre>' : '')
    + (p.independent_review ? '<div class="oc-sup">رأي المراجع المستقل: '+escapeHtml(p.independent_review)+'</div>' : '')
    + '<div class="btns"><button data-decide="1" data-id="'+escapeHtml(p.request_id)+'">وافق</button>'
    + '<button class="rej" data-decide="0" data-id="'+escapeHtml(p.request_id)+'">رفض</button></div>';
  wrap.appendChild(card); keepCard(card); wrap.scrollTop = 1e9;
}

async function selectRoom(key){
  selected = key;
  document.querySelectorAll('.room-item').forEach(el=>el.classList.toggle('sel', el.dataset.key===key));
  renderHead();
  await loadThread();
}

async function sendMsg(){
  const inp = document.getElementById('roomInp');
  const msg = inp.value.trim();
  if(!msg || selected===MONITOR) return;
  inp.value='';
  document.getElementById('roomSendBtn').disabled = true;
  const wrap = document.getElementById('roomMsgs');
  const u = document.createElement('div'); u.className='msg user'; u.textContent=msg;
  wrap.appendChild(u); wrap.scrollTop = 1e9;
  try{
    const r = await fetch('/api/room/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room:selected,message:msg})});
    const d = await r.json();
    if(d.needs_confirmation){ addConfirm(d.what, d.why, d.request_id, d.independent_review); }
    else{
      const b = document.createElement('div'); b.className='msg bot';
      b.innerHTML = '<span class="who">'+escapeHtml(selected==='executive'?'الرئيس التنفيذي':roomTitle(selected))+'</span>'+escapeHtml(d.reply||d.error||'(لا رد)');
      wrap.appendChild(b); wrap.scrollTop = 1e9;
      (d.proposals||[]).forEach(addProposalCard);
    }
  }catch(e){
    const b = document.createElement('div'); b.className='msg bot'; b.textContent='خطأ: '+e.message;
    wrap.appendChild(b);
  }
  document.getElementById('roomSendBtn').disabled = false;
  loadRoomList();
}

function addMeetingOutcome(result){
  const wrap = document.getElementById('roomMsgs');
  if(result.error){
    const e = document.createElement('div'); e.className='msg bot'; e.textContent='خطأ: '+result.error;
    wrap.appendChild(e); wrap.scrollTop = 1e9; return;
  }
  if(result.outcome === 'failed'){
    const e = document.createElement('div'); e.className='msg bot';
    e.textContent = 'فشل الاجتماع — كل البوتات تعذّر الوصول لها (لا إجماع، لا طلب موافقة فُتح على فراغ).';
    wrap.appendChild(e); wrap.scrollTop = 1e9; return;
  }
  if(result.outcome === 'arbitrated'){
    const card = document.createElement('div'); card.className='outcome-card';
    card.innerHTML = '<div class="oc-title">تعارض — حسمه مدير القرارات، والقرار الأخير لك</div>'
      + '<div class="oc-rec">'+escapeHtml(result.recommendation)+'</div>'
      + '<div class="oc-sup">يؤيدها: '+escapeHtml((result.supporters||[]).map(roomTitle).join('، '))+'</div>'
      + '<div class="oc-sup"><b>سبب مدير القرارات:</b> '+escapeHtml(result.arbiter_reason||'—')+'</div>'
      + '<div class="oc-sup"><b>الخيارات اللي ما اختارها:</b> '+escapeHtml((result.alternatives||[]).map(a=>a.recommendation+' ('+a.supporters.map(roomTitle).join('، ')+')').join(' | '))+'</div>'
      + (result.independent_review ? '<div class="oc-sup">رأي المراجع المستقل: '+escapeHtml(result.independent_review)+'</div>' : '')
      + '<div class="btns"><button data-decide="1" data-id="'+escapeHtml(result.request_id)+'">وافق</button>'
      + '<button class="rej" data-decide="0" data-id="'+escapeHtml(result.request_id)+'">رفض</button></div>';
    wrap.appendChild(card); keepCard(card); wrap.scrollTop = 1e9;
    return;
  }
  const proposals = result.outcome === 'consensus'
    ? [{recommendation: result.recommendation, supporters: result.supporters, request_id: result.request_id, independent_review: result.independent_review}]
    : result.proposals;
  if(result.outcome === 'conflict'){
    const h = document.createElement('div'); h.className='msg bot';
    h.textContent = 'تعارض حقيقي — '+proposals.length+' توصيات مختلفة، راجعها كلها قبل ما تختار:';
    wrap.appendChild(h);
  }
  proposals.forEach(p=>{
    const card = document.createElement('div'); card.className='outcome-card';
    card.innerHTML = '<div class="oc-title">توصية من: '+escapeHtml((p.supporters||[]).map(roomTitle).join('، '))+'</div>'
      + '<div class="oc-rec">'+escapeHtml(p.recommendation)+'</div>'
      + (p.independent_review ? '<div class="oc-sup">رأي المراجع المستقل: '+escapeHtml(p.independent_review)+'</div>' : '')
      + '<div class="btns"><button data-decide="1" data-id="'+p.request_id+'">وافق</button>'
      + '<button class="rej" data-decide="0" data-id="'+p.request_id+'">رفض</button></div>';
    wrap.appendChild(card);
    keepCard(card);
  });
  wrap.scrollTop = 1e9;
}

async function startMeeting(){
  const botKeys = [...checkedBots];
  const topic = document.getElementById('meetingTopic').value.trim();
  if(!botKeys.length || !topic) return;
  const btn = document.getElementById('meetingStartBtn');
  btn.disabled = true; btn.textContent = 'النقاش جارٍ…';
  try{
    const r = await fetch('/api/meeting/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      bot_keys: botKeys, topic: topic, rounds: parseInt(document.getElementById('meetingRounds').value,10),
    })});
    const d = await r.json();
    document.getElementById('meetingTopic').value = '';
    await loadThread();
    addMeetingOutcome(d);
  }catch(e){
    addMeetingOutcome({error: e.message});
  }
  btn.disabled = false; btn.textContent = 'ابدأ الاجتماع';
  loadRoomList();
}

document.getElementById('roomList').addEventListener('click', e=>{
  const item = e.target.closest('.room-item');
  if(item) selectRoom(item.dataset.key);
});
document.getElementById('roomSendBtn').addEventListener('click', sendMsg);
document.getElementById('roomInp').addEventListener('keydown', e=>{ if(e.key==='Enter') sendMsg(); });
document.getElementById('botCheckRow').addEventListener('change', e=>{
  if(e.target.type !== 'checkbox') return;
  const label = e.target.closest('.bot-check');
  if(e.target.checked){ checkedBots.add(e.target.value); label.classList.add('checked'); }
  else{ checkedBots.delete(e.target.value); label.classList.remove('checked'); }
});
document.getElementById('meetingStartBtn').addEventListener('click', startMeeting);
document.getElementById('roomMsgs').addEventListener('click', async e=>{
  const confBtn = e.target.closest('button[data-conf]');
  const decideBtn = e.target.closest('button[data-decide]');
  if(confBtn){
    const block = confBtn.closest('.confirm-row').parentElement;
    dropCard(block);
    confBtn.closest('.confirm-row').remove();
    const r = await fetch('/api/room/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room:selected,request_id:confBtn.dataset.id,approved:confBtn.dataset.conf==='1'})});
    const d = await r.json();
    const wrap = document.getElementById('roomMsgs');
    if(d.needs_confirmation){ addConfirm(d.what, d.why, d.request_id, d.independent_review); }
    else{
      const el = document.createElement('div'); el.className='msg bot';
      el.innerHTML = '<span class="who">'+escapeHtml(roomTitle(selected))+'</span>'+escapeHtml(d.reply||d.error||'(لا رد)');
      wrap.appendChild(el); wrap.scrollTop = 1e9;
    }
    loadRoomList();
    return;
  }
  if(decideBtn){
    const card = decideBtn.closest('.outcome-card');
    dropCard(card);
    const approved = decideBtn.dataset.decide === '1';
    const r = await fetch('/api/dashboard/decide',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:decideBtn.dataset.id,approved:approved})});
    const d = await r.json();
    card.innerHTML = '<div class="oc-rec">'+(d.ok===false ? escapeHtml(d.error||'تعذّر') : (approved?'تمت الموافقة':'تم الرفض'))+'</div>'
      + (d.note ? '<div class="oc-sup">'+escapeHtml(d.note)+'</div>' : '')
      + (d.hired ? '<div class="oc-sup">انضم للفريق: '+escapeHtml(roomTitle(d.hired)||d.hired)+' — غرفته ظهرت بالقائمة</div>' : '');
    loadRoomList();
  }
});

async function init(){
  await loadRoomList();
  renderHead();
  await loadThread();
}
init();
setInterval(()=>{ loadRoomList(); loadThread(); }, 4000);
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
.spend-bar{display:inline-block;width:70px;height:5px;border-radius:99px;background:var(--dim);overflow:hidden}
.spend-bar i{display:block;height:100%;background:var(--green);transition:width .4s}
.pill.warn .spend-bar i{background:var(--amber)}
.spend-edit{font:inherit;font-size:.64rem;color:var(--txt);background:transparent;border:1px solid var(--border);border-radius:99px;padding:1px 8px;cursor:pointer}
.spend-edit:hover{border-color:var(--ember-dim)}
.switch{position:relative;display:inline-block;width:32px;height:18px;flex:none}
.switch input{opacity:0;width:0;height:0}
.switch .slider{position:absolute;inset:0;background:var(--dim);border-radius:99px;cursor:pointer;transition:.18s}
.switch .slider::before{content:"";position:absolute;height:13px;width:13px;left:2.5px;top:2.5px;background:#e2e8f0;border-radius:50%;transition:.18s}
.switch input:checked + .slider{background:var(--amber)}
.switch input:checked + .slider::before{transform:translateX(14px)}
.switch input:disabled + .slider{opacity:.5;cursor:not-allowed}

/* ===== broadcast to all departments ===== */
.broadcast-bar{display:flex;gap:9px;padding:12px 20px 0}
.broadcast-bar input{
  flex:1;background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:10px 14px;
  color:var(--txt);font-size:.84rem;direction:rtl;
}
.broadcast-bar input:focus{outline:none;border-color:var(--ember)}
.broadcast-bar button{
  padding:10px 20px;border:none;border-radius:10px;color:#1a0804;cursor:pointer;font-size:.84rem;font-weight:800;
  background:linear-gradient(135deg,var(--ember),#ffb199);white-space:nowrap;
}
.broadcast-bar button:hover{filter:brightness(1.08)}
.broadcast-bar button:disabled{background:var(--dim);color:#94a3b8;cursor:not-allowed;filter:none}
.bc-result{margin:10px 20px 0;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:10px 14px}
.bc-row{display:flex;justify-content:space-between;align-items:center;padding:5px 2px;font-size:.78rem;border-bottom:1px solid var(--border)}
.bc-row:last-child{border-bottom:none}
.bc-row span{font-size:.68rem;padding:2px 9px;border-radius:99px;border:1px solid var(--border)}
.bc-row.ok span{color:var(--green);border-color:rgba(52,211,153,.4)}
.bc-row.warn span{color:var(--amber);border-color:rgba(251,191,36,.4)}
.bc-row.err{color:var(--red)}
.bc-note{font-size:.7rem;color:var(--muted);margin-top:8px;text-align:left}
.bc-note a{color:var(--ember)}
.bc-ceo{font-size:.82rem;line-height:1.7;padding:4px 2px 8px;border-bottom:1px solid var(--border);white-space:pre-wrap}
.bc-ceo b{color:var(--ember)}
.bc-prop{font-size:.74rem;color:var(--amber);padding:5px 2px;border-bottom:1px solid var(--border)}


/* ===== agent brain: memory + skills (Hermes-style learning loop) ===== */
.brain-row{padding:0 20px 14px}
.brain-grid{display:grid;grid-template-columns:1fr 1fr 1.2fr;gap:12px;padding:14px 15px}
@media (max-width:1000px){.brain-grid{grid-template-columns:1fr}}
.bcol{background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:11px 13px;min-height:160px}
.bcol h3{font-size:.78rem;font-weight:800;display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.bcol h3 small{font-size:.62rem;color:var(--muted);font-weight:600;direction:ltr}
.bbar{height:4px;border-radius:99px;background:var(--dim);overflow:hidden;margin-bottom:8px}
.bbar i{display:block;height:100%;background:var(--violet)}
.bentry{display:flex;gap:6px;align-items:flex-start;font-size:.72rem;line-height:1.55;padding:5px 0;border-bottom:1px solid var(--border)}
.bentry span{flex:1;unicode-bidi:plaintext}
.bentry button,.bskill button.bx{background:none;border:none;color:var(--muted);cursor:pointer;font-size:.9rem;line-height:1}
.bentry button:hover,.bskill button.bx:hover{color:var(--red)}
.badd{display:flex;gap:6px;margin-top:8px}
.badd input{flex:1;background:var(--panel);border:1px solid var(--border);color:var(--txt);border-radius:8px;padding:5px 8px;font:inherit;font-size:.7rem}
.badd button{background:var(--violet);color:#120a24;border:none;border-radius:8px;padding:5px 10px;font:inherit;font-weight:800;font-size:.7rem;cursor:pointer}
.bskill{padding:6px 0;border-bottom:1px solid var(--border)}
.bskill .bs-head{display:flex;gap:6px;align-items:center;cursor:pointer}
.bskill .bs-name{font-size:.74rem;font-weight:800;direction:ltr;flex:1;text-align:right}
.bskill .bs-desc{font-size:.66rem;color:var(--muted);margin-top:2px;unicode-bidi:plaintext}
.bskill pre{white-space:pre-wrap;font-size:.66rem;background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:8px;margin-top:6px;max-height:240px;overflow:auto;unicode-bidi:plaintext}
.bempty{font-size:.7rem;color:var(--muted);padding:6px 0}
.berr{font-size:.66rem;color:var(--red);margin-top:4px}

/* ===== market widgets (widgets.py / market.py) ===== */
.widgets-row{padding:0 20px 14px}
.widget-add{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:12px 15px;border-bottom:1px solid var(--border)}
.widget-add select,.widget-add input{background:var(--panel2);border:1px solid var(--border);color:var(--txt);border-radius:9px;padding:7px 10px;font:inherit;font-size:.76rem}
.widget-add input{flex:1;min-width:220px;direction:ltr;text-align:right}
.widget-add button{background:var(--ember);color:#1a0904;border:none;border-radius:9px;padding:7px 16px;font:inherit;font-weight:800;font-size:.76rem;cursor:pointer}
.widget-add small{font-size:.68rem;color:var(--muted);flex-basis:100%}
.widget-add small.err{color:var(--red)}
.widget-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px;padding:14px 15px}
.wcard{background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:12px 14px;position:relative;min-height:150px}
.wcard .w-x{position:absolute;top:8px;left:10px;background:none;border:none;color:var(--muted);font-size:1rem;cursor:pointer}
.wcard .w-x:hover{color:var(--red)}
.wcard .w-title{font-weight:800;font-size:.84rem;unicode-bidi:plaintext;text-align:right}
.wcard .w-sub{font-size:.64rem;color:var(--muted);margin-top:2px;direction:ltr;text-align:right}
.wcard .w-price{font-size:1.5rem;font-weight:800;font-variant-numeric:tabular-nums;margin-top:8px;direction:ltr;text-align:right}
.wcard .w-price small{font-size:.7rem;color:var(--muted);font-weight:600}
.w-up{color:var(--green)} .w-down{color:var(--red)}
.wcard .w-chg{font-size:.74rem;font-weight:700;text-align:right}
.wcard svg{width:100%;height:64px;margin-top:6px}
.wcard .w-foot{font-size:.6rem;color:var(--muted);margin-top:4px}
.wcard .w-err{font-size:.74rem;color:var(--red);margin-top:10px}
.wcard table{width:100%;border-collapse:collapse;font-size:.72rem;margin-top:8px;font-variant-numeric:tabular-nums}
.wcard td,.wcard th{padding:4px 3px;border-bottom:1px solid var(--border);text-align:right}
.wcard th{color:var(--muted);font-weight:600;font-size:.64rem}
.wcard td.sym{direction:ltr;font-weight:700}
.wcard .w-total{margin-top:8px;font-size:.8rem;font-weight:800;direction:ltr;text-align:right}
.widgets-empty{font-size:.76rem;color:var(--muted);padding:16px 15px}

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

/* ===== analytics row (heatmap / rankings / hourly / donut) ===== */
.grid-analytics{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:12px;padding:0 20px 20px}
@media(max-width:1100px){.grid-analytics{grid-template-columns:1fr 1fr}}
@media(max-width:620px){.grid-analytics{grid-template-columns:1fr}}
.heatmap-grid{display:grid;grid-template-columns:repeat(12,1fr);gap:4px;padding:14px 16px}
@media(max-width:480px){.heatmap-grid{grid-template-columns:repeat(8,1fr)}}
.heat-cell{aspect-ratio:1;border-radius:3px;background:var(--panel2)}
.rank-row{display:flex;align-items:center;gap:8px;padding:6px 14px;font-size:.74rem}
.rank-name{flex:0 0 96px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#c3cedd}
.rank-bar-wrap{flex:1;height:7px;background:var(--dim);border-radius:4px;overflow:hidden}
.rank-bar{height:100%;border-radius:4px;transition:width .4s}
.rank-n{flex:none;color:var(--muted);font-variant-numeric:tabular-nums;width:20px;text-align:left}
.donut-body{display:flex;align-items:center;gap:10px;padding:8px 14px 14px}
.donut-body svg{width:90px;height:90px;flex:none}
.donut-panel .legend span{font-size:.68rem}

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
    <a href="/rooms" class="navicon" title="غرف الأقسام" style="margin-top:auto"><svg viewBox="0 0 24 24"><rect x="5" y="8" width="14" height="11" rx="2.2"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/><circle cx="9.5" cy="13.2" r="1"/><circle cx="14.5" cy="13.2" r="1"/></svg></a>
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

    <section class="broadcast-bar">
      <input id="bcInput" placeholder="اكتب للـCEO — هو يوزّع على الموظف المناسب، أو يقترح توظيف واحد جديد…" autocomplete="off">
      <button id="bcSend">أرسل للـCEO</button>
    </section>
    <div class="bc-result hidden" id="bcResult"></div>

    <section class="ledger-row" id="ledgerRow"></section>

    <section class="brain-row">
      <div class="panel">
        <div class="panel-head"><h2>ذاكرة الوكيل ومهاراته — يتعلّم من الشغل (أسلوب Hermes)</h2><span class="panel-tag">تشوف كل شي وتحذف أي شي</span></div>
        <div class="brain-grid">
          <div class="bcol" id="bUser"></div>
          <div class="bcol" id="bMemory"></div>
          <div class="bcol" id="bSkills"></div>
        </div>
      </div>
    </section>

    <section class="widgets-row">
      <div class="panel">
        <div class="panel-head"><h2>الأسواق — ودجت حيّة</h2><span class="panel-tag">المصدر: Yahoo Finance · تحديث كل دقيقة · قد يتأخر حسب السوق</span></div>
        <div class="widget-add">
          <select id="wType"><option value="stock">سهم</option><option value="watchlist">قائمة متابعة</option><option value="portfolio">محفظة</option></select>
          <input id="wSymbol" placeholder="AAPL  أو  2222.SR  أو  BTC-USD" autocomplete="off">
          <select id="wRange"><option value="1d">يوم (كل 5 دقائق)</option><option value="5d">5 أيام</option><option value="1mo">شهر</option><option value="6mo">6 شهور</option><option value="1y">سنة</option></select>
          <button id="wAdd">أضف</button>
          <small id="wNote">أو اكتب للرئيس التنفيذي فوق: "ابي أتابع أرامكو والبتكوين" — يقترح الودجت وأنت توافق.</small>
        </div>
        <div class="widget-grid" id="widgetGrid"></div>
      </div>
    </section>

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

    <section class="grid-analytics">
      <div class="panel mini wide" id="heatmapPanel">
        <div class="panel-head"><h2>نشاط آخر 48 ساعة</h2><span class="panel-tag">حقيقي، لا تلوين وهمي</span></div>
        <div class="heatmap-grid" id="heatmapGrid"></div>
      </div>
      <div class="panel mini">
        <div class="panel-head"><h2>أكثر البوتات نشاطاً</h2></div>
        <div id="topBotsList"></div>
      </div>
      <div class="panel mini">
        <div class="panel-head"><h2>القرارات حسب ساعة اليوم</h2></div>
        <svg id="chartHourly" viewBox="0 0 280 112"></svg>
      </div>
      <div class="panel mini donut-panel">
        <div class="panel-head"><h2>توزيع الحالة</h2></div>
        <div class="donut-body">
          <svg id="chartDonut" viewBox="0 0 140 140"></svg>
          <div class="legend" id="donutLegend" style="border-top:none;padding:0;flex-direction:column;gap:6px"></div>
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
    + '<span class="pill" id="pcNoteWrap"><small id="pcNote">'+(d.pc_access_enabled?'نشط — كل أمر يحتاج موافقتك رغم ذلك':'يعمل فقط من جهازك (localhost)')+'</small></span>'
    + spendPill(d.claude_spend);
}

/* سقف صرف Claude — أرقام حقيقية من usage حق Anthropic (spend.py) */
function spendPill(sp){
  if(!sp) return '';
  const pct = sp.budget_usd > 0 ? Math.min(100, Math.round(sp.spent_usd / sp.budget_usd * 100)) : 100;
  return '<span class="pill'+(pct >= 80 ? ' warn' : ' ok')+'"><span class="dot"></span>Claude هالشهر: <b>$'+sp.spent_usd.toFixed(2)+'</b> / $'+sp.budget_usd.toFixed(2)
    + '<span class="spend-bar"><i style="width:'+pct+'%"></i></span>'
    + '<small>'+sp.calls+' استدعاء</small>'
    + '<button class="spend-edit" id="budgetEdit" title="من جهازك فقط (localhost)">تعديل السقف</button></span>';
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

function renderHeatmap(d){
  const buckets = d.activity_heatmap || [];
  const max = Math.max(1, ...buckets);
  document.getElementById('heatmapGrid').innerHTML = buckets.map((v,i)=>{
    const alpha = v===0 ? 0.07 : 0.22 + 0.78*(v/max);
    const hoursAgo = buckets.length - 1 - i;
    return '<div class="heat-cell" style="background:rgba(255,106,61,'+alpha.toFixed(2)+')" title="منذ '+hoursAgo+' ساعة: '+v+' '+(v===1?'قرار':'قرارات')+'"></div>';
  }).join('');
}

function renderTopBots(d){
  const usage = d.metrics.bot_usage || {};
  const rows = d.bots.map(b=>({...b, n: usage[b.key]||0})).sort((a,b)=>b.n-a.n).slice(0,6);
  const max = Math.max(1, ...rows.map(r=>r.n));
  document.getElementById('topBotsList').innerHTML = rows.length ? rows.map(r=>
    '<div class="rank-row"><span class="rank-name">'+escapeHtml(r.title_ar)+'</span>'
    + '<div class="rank-bar-wrap"><div class="rank-bar" style="width:'+(100*r.n/max)+'%;background:'+(DIR_COLOR[r.directorate]||'#3b4961')+'"></div></div>'
    + '<span class="rank-n">'+r.n+'</span></div>'
  ).join('') : '<div class="empty">لا نشاط بعد</div>';
}

function renderHourChart(d){
  const buckets = d.hour_histogram || [];
  const svg = document.getElementById('chartHourly');
  if(!buckets.length || buckets.every(v=>v===0)){
    svg.innerHTML = '<text x="140" y="56" text-anchor="middle" font-size="10" fill="#687080">لا بيانات كافية بعد</text>';
    return;
  }
  const W=280,H=112,max=Math.max(1,...buckets),barW=W/24;
  let html='';
  buckets.forEach((v,i)=>{
    const h = v===0 ? 1 : (v/max)*(H-24);
    html += '<rect x="'+(i*barW+1).toFixed(1)+'" y="'+(H-14-h).toFixed(1)+'" width="'+(barW-2).toFixed(1)+'" height="'+h.toFixed(1)+'" rx="1.5" fill="#22d3ee" opacity="'+(v===0?0.14:0.85)+'"><title>الساعة '+i+':00 — '+v+' '+(v===1?'قرار':'قرارات')+'</title></rect>';
  });
  html += '<text x="2" y="'+(H-2)+'" font-size="8" fill="#687080">00</text><text x="'+(W-16)+'" y="'+(H-2)+'" font-size="8" fill="#687080">23</text>';
  svg.innerHTML = html;
}

function renderDonut(d){
  const m = d.metrics, pendN = d.pending_approvals.length;
  const approved = m.decisions.approved, rejected = m.decisions.rejected;
  const total = approved + rejected + pendN;
  const svg = document.getElementById('chartDonut');
  if(total === 0){
    svg.innerHTML = '<text x="70" y="74" text-anchor="middle" font-size="9" fill="#687080">لا بيانات بعد</text>';
    document.getElementById('donutLegend').innerHTML = '';
    return;
  }
  const segs = [['موافَق', approved, '#34d399'], ['مرفوض', rejected, '#f87171'], ['معلّق', pendN, '#fbbf24']];
  const r=52, cx=70, cy=70, circ=2*Math.PI*r;
  let offset=0, html='';
  segs.forEach(([label,val,color])=>{
    if(val===0) return;
    const frac = val/total, len = frac*circ;
    html += '<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" stroke="'+color+'" stroke-width="16" '
      + 'stroke-dasharray="'+len.toFixed(1)+' '+(circ-len).toFixed(1)+'" stroke-dashoffset="'+(-offset).toFixed(1)+'" transform="rotate(-90 '+cx+' '+cy+')"/>';
    offset += len;
  });
  html += '<text x="'+cx+'" y="'+(cy+4)+'" text-anchor="middle" font-size="15" fill="#eef1f5" font-weight="800">'+total+'</text>';
  svg.innerHTML = html;
  document.getElementById('donutLegend').innerHTML = segs.filter(s=>s[1]>0).map(([label,val,color])=>
    '<span><i style="background:'+color+'"></i>'+label+' ('+val+')</span>'
  ).join('');
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

document.getElementById('statusStrip').addEventListener('click', async e=>{
  if(e.target.id !== 'budgetEdit') return;
  const current = lastData && lastData.claude_spend ? lastData.claude_spend.budget_usd : '';
  const raw = prompt('سقف صرف Claude الشهري بالدولار (Claude يتوقف تلقائياً قبل ما يتعداه):', current);
  if(raw === null) return;
  try{
    const r = await fetch('/api/dashboard/budget',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount:raw.trim()})});
    const d = await r.json();
    if(!d.ok) alert(d.error);
  }catch(err){ alert('تعذّر الاتصال: '+err.message); }
  load();
});

async function sendBroadcast(){
  const inp = document.getElementById('bcInput');
  const msg = inp.value.trim();
  if(!msg) return;
  const btn = document.getElementById('bcSend');
  const box = document.getElementById('bcResult');
  btn.disabled = true; btn.textContent = 'الرئيس التنفيذي يشتغل…';
  box.className = 'hidden';
  try{
    const r = await fetch('/api/ceo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
    const d = await r.json();
    if(d.error){
      box.innerHTML = '<div class="bc-row err">'+escapeHtml(d.error)+'</div>';
    }else{
      box.innerHTML = '<div class="bc-ceo"><b>الرئيس التنفيذي:</b> '+escapeHtml(d.reply||'')+'</div>'
        + (d.notes||[]).map(n=>'<div class="bc-prop">'+escapeHtml(n)+'</div>').join('')
        + (d.assignments||[]).map(x=>{
          const working = !!x.needs_confirmation;
          return '<div class="bc-row '+(working?'warn':'ok')+'"><b>'+escapeHtml(x.title_ar)+'</b><span>'+(working?'يحتاج موافقتك':'ردّ')+'</span></div>';
        }).join('')
        + (d.proposals||[]).map(p=>'<div class="bc-prop">بانتظار موافقتك ('+escapeHtml(p.kind)+'): '+escapeHtml(p.what)+'</div>').join('')
        + (d.code_proposal && !d.code_proposal.ok ? '<div class="bc-row err">تعديل الكود ما اكتمل: '+escapeHtml(String(d.code_proposal.error||'').slice(0,300))+'</div>' : '')
        + '<div class="bc-note">الردود الكاملة بـ<a href="/rooms">غرف الأقسام ←</a> — والموافقات بالطلبات المعلّقة تحت</div>';
      inp.value = '';
    }
    box.className = 'bc-result';
  }catch(e){
    box.innerHTML = '<div class="bc-row err">تعذّر الاتصال: '+escapeHtml(e.message)+'</div>';
    box.className = 'bc-result';
  }
  btn.disabled = false; btn.textContent = 'أرسل للـCEO';
  load();
}
document.getElementById('bcSend').addEventListener('click', sendBroadcast);
document.getElementById('bcInput').addEventListener('keydown', e=>{ if(e.key==='Enter') sendBroadcast(); });

/* ===== agent brain (agent_memory.py + agent_skills.py) ===== */
function memCol(key, title, hint, st){
  const pct = Math.min(100, Math.round(st.chars / st.limit * 100));
  return '<h3>'+title+'<small>'+st.chars+'/'+st.limit+'</small></h3><div class="bbar"><i style="width:'+pct+'%"></i></div>'
    + (st.entries.length ? st.entries.map(e=>'<div class="bentry"><span>'+escapeHtml(e)+'</span><button data-mrm="'+key+'" data-old="'+escapeHtml(e)+'" title="احذف">×</button></div>').join('')
                         : '<div class="bempty">'+hint+'</div>')
    + '<div class="badd"><input data-madd-in="'+key+'" placeholder="أضف بنفسك…"><button data-madd="'+key+'">أضف</button></div><div class="berr" data-merr="'+key+'"></div>';
}
async function loadBrain(){
  try{
    const d = await (await fetch('/api/brain-state')).json();
    document.getElementById('bUser').innerHTML = memCol('user', 'ملفك (USER.md)', 'لسا ما عرف عنك شي — يتعلّم من طلباتك', d.user);
    document.getElementById('bMemory').innerHTML = memCol('memory', 'ملاحظاته (MEMORY.md)', 'ما فيه ملاحظات بعد', d.memory);
    const open = new Set([...document.querySelectorAll('.bskill pre')].map(p=>p.dataset.for));
    document.getElementById('bSkills').innerHTML = '<h3>مهاراته (SKILL.md)<small>'+d.skills.length+'</small></h3>'
      + (d.skills.length ? d.skills.map(sk=>'<div class="bskill"><div class="bs-head" data-skill="'+escapeHtml(sk.name)+'">'
          + '<span class="bs-name">'+escapeHtml(sk.name)+'</span><button class="bx" data-skrm="'+escapeHtml(sk.name)+'" title="احذف">×</button></div>'
          + '<div class="bs-desc">'+escapeHtml(sk.description)+' · '+escapeHtml(sk.updated_at)+'</div></div>').join('')
        : '<div class="bempty">يصنع مهارة بنفسه لما يخلص مهمة متعددة الخطوات بنجاح وتكون تتكرر.</div>');
    open.forEach(n=>{ const h = document.querySelector('.bs-head[data-skill="'+CSS.escape(n)+'"]'); if(h) toggleSkill(h); });
  }catch(e){}
}
async function toggleSkill(head){
  const box = head.parentElement, name = head.dataset.skill;
  const existing = box.querySelector('pre');
  if(existing){ existing.remove(); return; }
  const sk = await (await fetch('/api/skill?name='+encodeURIComponent(name))).json();
  const pre = document.createElement('pre'); pre.dataset.for = name; pre.textContent = sk.body || sk.error || '';
  box.appendChild(pre);
}
document.querySelector('.brain-grid').addEventListener('click', async e=>{
  const rm = e.target.closest('button[data-mrm]'), add = e.target.closest('button[data-madd]');
  const skrm = e.target.closest('button[data-skrm]'), head = e.target.closest('.bs-head');
  if(rm){
    await fetch('/api/memory',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({op:'remove',target:rm.dataset.mrm,old_text:rm.dataset.old})});
    loadBrain();
  }else if(add){
    const key = add.dataset.madd, inp = document.querySelector('input[data-madd-in="'+key+'"]');
    if(!inp.value.trim()) return;
    const d = await (await fetch('/api/memory',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({op:'add',target:key,content:inp.value.trim()})})).json();
    if(!d.ok){ document.querySelector('[data-merr="'+key+'"]').textContent = d.error; return; }
    loadBrain();
  }else if(skrm){
    if(!confirm('حذف المهارة '+skrm.dataset.skrm+'؟')) return;
    await fetch('/api/skills/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:skrm.dataset.skrm})});
    loadBrain();
  }else if(head){
    toggleSkill(head);
  }
});
loadBrain();
setInterval(loadBrain, 15000);

/* ===== market widgets ===== */
const W_HINTS = {
  stock: ['AAPL  أو  2222.SR  أو  BTC-USD', 'أو اكتب للرئيس التنفيذي فوق: "ابي أتابع أرامكو والبتكوين" — يقترح الودجت وأنت توافق.'],
  watchlist: ['2222.SR, AAPL, BTC-USD', 'رموز مفصولة بفاصلة — حد أقصى 12'],
  portfolio: ['AAPL:10, 2222.SR:150', 'رمز:كمية لكل عنصر — الكميات منك أنت، والأسعار من السوق'],
};
function fmtNum(n, d){ return (n==null||isNaN(n)) ? '—' : Number(n).toLocaleString('en-US',{maximumFractionDigits:d==null?2:d}); }
function chgHtml(chg, pct){
  if(chg==null) return '<span>—</span>';
  const cls = chg >= 0 ? 'w-up' : 'w-down';
  return '<bdi dir="ltr" class="'+cls+'">'+(chg>=0?'+':'')+fmtNum(chg)+(pct==null?'':' ('+(pct>=0?'+':'')+fmtNum(pct)+'%)')+'</bdi>';
}
function sparkline(points){
  if(!points || points.length < 2) return '';
  const cs = points.map(p=>p.c), min = Math.min(...cs), max = Math.max(...cs), span = (max-min)||1;
  const pts = cs.map((c,i)=>(i/(cs.length-1)*280).toFixed(1)+','+(60-(c-min)/span*54).toFixed(1)).join(' ');
  const up = cs[cs.length-1] >= cs[0];
  const col = up ? 'var(--green)' : 'var(--red)';
  return '<svg viewBox="0 0 280 64" preserveAspectRatio="none" role="img" aria-label="رسم سعر الإغلاق خلال المدى">'
    + '<polyline points="0,64 '+pts+' 280,64" fill="'+(up?'rgba(52,211,153,.10)':'rgba(248,113,113,.10)')+'" stroke="none"/>'
    + '<polyline points="'+pts+'" fill="none" stroke="'+col+'" stroke-width="1.6"/></svg>';
}
function timeOf(ts){ return ts ? new Date(ts*1000).toLocaleString('ar-SA',{hour:'2-digit',minute:'2-digit',day:'numeric',month:'short'}) : '—'; }
const RANGE_AR = {'1d':'اليوم','5d':'5 أيام','1mo':'شهر','6mo':'6 شهور','1y':'سنة'};
function widgetCard(w){
  const d = w.data || {};
  let body = '';
  if(!d.ok){
    body = '<div class="w-err">ما قدرنا نجيب السعر: '+escapeHtml(d.error||'خطأ غير معروف')+'</div>';
  }else if(w.type === 'stock'){
    body = '<div class="w-sub">'+escapeHtml(d.symbol)+' · '+escapeHtml(d.exchange||'')+(d.name?' · '+escapeHtml(d.name):'')+'</div>'
      + '<div class="w-price">'+fmtNum(d.price)+' <small>'+escapeHtml(d.currency||'')+'</small></div>'
      + '<div class="w-chg"><small style="color:var(--muted)">التغيّر خلال '+escapeHtml(RANGE_AR[d.range]||d.range)+':</small> '+chgHtml(d.change, d.change_pct)+'</div>'
      + sparkline(d.points)
      + '<div class="w-foot">آخر سعر من المصدر: '+escapeHtml(timeOf(d.market_time))+'</div>';
  }else if(w.type === 'watchlist'){
    body = '<table><tr><th>الرمز</th><th>السعر</th><th>اليوم</th></tr>'
      + d.rows.map(r=>'<tr><td class="sym">'+escapeHtml(r.symbol||'')+'</td>'
        + (r.ok ? '<td><bdi dir="ltr">'+fmtNum(r.price)+' <small>'+escapeHtml(r.currency||'')+'</small></bdi></td><td>'+chgHtml(r.change_pct==null?null:r.change, r.change_pct)+'</td>'
                : '<td colspan="2" class="w-down">'+escapeHtml(r.error||'تعذّر')+'</td>')+'</tr>').join('')
      + '</table>';
  }else{
    body = '<table><tr><th>الرمز</th><th>الكمية</th><th>السعر</th><th>القيمة</th></tr>'
      + d.rows.map(r=>'<tr><td class="sym">'+escapeHtml(r.symbol)+'</td><td>'+fmtNum(r.qty,4)+'</td>'
        + (r.ok ? '<td>'+fmtNum(r.price)+'</td><td><bdi dir="ltr">'+fmtNum(r.value)+' <small>'+escapeHtml(r.currency||'')+'</small></bdi></td>'
                : '<td colspan="2" class="w-down">'+escapeHtml(r.error||'تعذّر')+'</td>')+'</tr>').join('')
      + '</table>'
      + Object.entries(d.totals||{}).map(([cur,val])=>'<div class="w-total">'+fmtNum(val)+' '+escapeHtml(cur)+'</div>').join('')
      + ((d.missing||[]).length ? '<div class="w-foot w-down">غير محسوب بالمجموع (ما وصل سعره): '+escapeHtml(d.missing.join(', '))+'</div>' : '')
      + '<div class="w-foot">مجموع لكل عملة على حدة — بدون تحويل عملات</div>';
  }
  return '<div class="wcard"><button class="w-x" data-wid="'+escapeHtml(w.id)+'" title="احذف">×</button>'
    + '<div class="w-title">'+escapeHtml(w.title)+'</div>' + body
    + (w.added_by==='ceo' ? '<div class="w-foot">أضافه الرئيس التنفيذي بموافقتك</div>' : '') + '</div>';
}
async function loadWidgets(){
  try{
    const r = await fetch('/api/widgets');
    const d = await r.json();
    document.getElementById('widgetGrid').innerHTML = d.widgets.length ? d.widgets.map(widgetCard).join('')
      : '<div class="widgets-empty">ما فيه ودجت بعد — أضف سهم فوق، أو اطلب من الرئيس التنفيذي.</div>';
  }catch(e){}
}
document.getElementById('wType').addEventListener('change', e=>{
  const h = W_HINTS[e.target.value];
  document.getElementById('wSymbol').placeholder = h[0];
  const note = document.getElementById('wNote'); note.textContent = h[1]; note.className = '';
  document.getElementById('wRange').style.display = e.target.value==='stock' ? '' : 'none';
});
document.getElementById('wAdd').addEventListener('click', async ()=>{
  const type = document.getElementById('wType').value;
  const raw = document.getElementById('wSymbol').value.trim();
  const note = document.getElementById('wNote');
  if(!raw) return;
  let config;
  if(type==='stock') config = {symbol: raw, range: document.getElementById('wRange').value};
  else if(type==='watchlist') config = {symbols: raw.split(/[,،\\s]+/).filter(Boolean)};
  else config = {holdings: raw.split(/[,،]+/).map(x=>x.trim()).filter(Boolean).map(x=>{ const [sym, q] = x.split(':'); return {symbol:(sym||'').trim(), qty:(q||'').trim()}; })};
  const r = await fetch('/api/widgets/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:type, config:config})});
  const d = await r.json();
  if(!d.ok){ note.textContent = d.error; note.className = 'err'; return; }
  document.getElementById('wSymbol').value = '';
  note.textContent = 'انضاف.'; note.className = '';
  loadWidgets();
});
document.getElementById('widgetGrid').addEventListener('click', async e=>{
  const x = e.target.closest('button[data-wid]');
  if(!x) return;
  await fetch('/api/widgets/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:x.dataset.wid})});
  loadWidgets();
});
loadWidgets();
setInterval(loadWidgets, 60000);

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
    renderHeatmap(d);
    renderTopBots(d);
    renderHourChart(d);
    renderDonut(d);
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


def _activity_heatmap(full_ledger: list[dict], hours: int = 48) -> list[int]:
    """شبكة نشاط حقيقية — عدد القرارات الفعلية بكل ساعة من آخر 48 ساعة،
    من الأقدم للأحدث. فاضية بصدق لو ما فيه نشاط، لا تلوين وهمي."""
    buckets = [0] * hours
    now = datetime.now()
    for e in full_ledger:
        try:
            ts = datetime.strptime(e.get("at", ""), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        delta_hours = int((now - ts).total_seconds() // 3600)
        if 0 <= delta_hours < hours:
            buckets[hours - 1 - delta_hours] += 1
    return buckets


def _hour_of_day_histogram(full_ledger: list[dict]) -> list[int]:
    """متى تصير القرارات عادة؟ توزيع حقيقي على 24 ساعة اليوم، مجمّع من
    كل القرارات المتاحة (لا آخر 48 ساعة فقط) — نمط حقيقي لا تخمين."""
    buckets = [0] * 24
    for e in full_ledger:
        try:
            ts = datetime.strptime(e.get("at", ""), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        buckets[ts.hour] += 1
    return buckets


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
        "activity_heatmap": _activity_heatmap(full_ledger),
        "hour_histogram": _hour_of_day_histogram(full_ledger),
        "claude_spend": spend.summary(),
    }


def _handle_dashboard_decide(body: dict) -> dict:
    request_id = body.get("request_id")
    approved = bool(body.get("approved"))
    if not request_id:
        return {"ok": False, "error": "يحتاج request_id"}

    ok = (decision.approve if approved else decision.reject)(request_id, decided_by="owner")
    if not ok:
        return {"ok": False, "error": "طلب غير موجود أو تم حسمه مسبقاً"}

    ceo_result = ceo.apply_decision(request_id, approved, _ceo_dispatch)
    if ceo_result is not None:
        return {"ok": True, **ceo_result}

    if request_id in self_improve._load_proposals():
        if not approved:
            return {"ok": True, "applied": False, "note": "رُفض تعديل الكود — ما تغيّر شي"}
        applied = self_improve.apply(request_id)
        note = ("طُبّق التعديل (فيه نسخة احتياطية) — يتفعّل بعد إعادة تشغيل web_chat"
                if applied.get("ok") else f"ما تطبّق: {applied.get('error')}")
        return {"ok": True, "applied": bool(applied.get("ok")), "result": applied, "note": note}

    # لو الطلب جاء من حلقة kernel.run_task (مثل شات أو بوت) فيه حالة
    # معلّقة محفوظة — نكمل التنفيذ الفعلي. لو جاء من مسار آخر (مثل
    # self_improve.py/docs_sync.py) فليس له حالة kernel معلّقة أصلاً —
    # هذي المسارات تطبّق التغيير الفعلي عبر أمرها الخاص بعد ما تلقى
    # القرار معتمَداً، لا عبر هنا. لا نزعم تطبيقاً لم يحصل.
    if any(t["request_id"] == request_id for t in kernel.pending_tasks()):
        result = kernel.resume_task(request_id)
        return {"ok": True, "applied": True, "result": result}
    return {"ok": True, "applied": False, "note": "تم تسجيل القرار — تطبيقه الفعلي يحتاج أمره الخاص (مثل طبّق_توثيق)"}


def _handle_pc_toggle(body: dict, is_local: bool) -> dict:
    """تفعيل/تعطيل وضع الوصول الكامل للجهاز من اللوحة نفسها — بشرط واحد
    لا استثناء له: الطلب لازم يجي من نفس الجهاز (loopback) حرفياً، وباسم
    مضيف محلي (راجع Handler._is_local_request). لو اللوحة مفتوحة عبر رابط
    Daytona/Fly.io مستضاف، أي زائر يوصل للرابط يقدر يفتح /dashboard —
    لولا هذا الشرط كان بإمكانه يفعّل وصولاً حقيقياً لجهاز المضيف عن بعد
    بضغطة واحدة بلا أي حاجز. هذا الشرط هو الحاجز الحقيقي هنا، لا مجرد
    تلميح بالواجهة."""
    if not is_local:
        return {"ok": False, "error": _LOCAL_ONLY_ERROR.format(what="تفعيل/تعطيل وصول الجهاز")}

    enable = bool(body.get("enable"))
    os.environ["OS4_ALLOW_PC_ACCESS"] = "1" if enable else "0"
    try:
        set_key(env._ENV_PATH, "OS4_ALLOW_PC_ACCESS", "1" if enable else "0")
        persisted = True
    except OSError as e:  # noqa: BLE001 — فشل كتابة .env يُبلَّغ بصدق، التفعيل بالذاكرة نجح رغم ذلك
        persisted = False
        persisted_error = str(e)

    what = "تفعيل وضع الوصول الكامل للجهاز" if enable else "تعطيل وضع الوصول الكامل للجهاز"
    decision.record_owner_action(what, "تغيير من لوحة التحكم مباشرة (localhost)", decided_by="owner-dashboard-loopback")

    result = {"ok": True, "pc_access_enabled": safety.pc_access_enabled(), "persisted": persisted}
    if not persisted:
        result["warning"] = "فُعِّل للجلسة الحالية فقط — فشلت كتابة .env على القرص: " + persisted_error
    return result


def _handle_budget(body: dict, is_local: bool) -> dict:
    """تعديل سقف صرف Claude الشهري — نفس شرط loopback حق وصول الجهاز،
    لأنه فلوس حقيقية: زائر رابط مستضاف ما يقدر يرفع السقف."""
    if not is_local:
        return {"ok": False, "error": _LOCAL_ONLY_ERROR.format(what="تعديل سقف صرف Claude")}
    try:
        value = spend.set_budget(body.get("amount"))
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    decision.record_owner_action(
        f"تعديل سقف صرف Claude الشهري إلى {value}$",
        "تغيير من لوحة التحكم مباشرة (localhost)",
        decided_by="owner-dashboard-loopback",
    )
    return {"ok": True, "budget_usd": value, "claude_spend": spend.summary()}


def _brain_state() -> dict:
    return {"memory": agent_memory.usage("memory"), "user": agent_memory.usage("user"),
            "skills": agent_skills.list_skills()}


def _handle_memory_edit(body: dict) -> dict:
    op = {k: body.get(k) for k in ("op", "target", "content", "old_text") if body.get(k) is not None}
    result = agent_memory.apply([op], source="owner")
    return {**result, **_brain_state()} if result.get("ok") else result


def _handle_skill_delete(body: dict) -> dict:
    if not agent_skills.delete(str(body.get("name", ""))):
        return {"ok": False, "error": "مهارة غير موجودة"}
    return {"ok": True}


def _widgets_data() -> dict:
    return {"widgets": widgets.snapshot(), "types": widgets.TYPES, "ranges": list(market.RANGES)}


def _handle_widget_add(body: dict) -> dict:
    try:
        widget = widgets.add({"type": body.get("type"), "title": body.get("title"), "config": body.get("config")})
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "widget": widget}


def _handle_widget_remove(body: dict) -> dict:
    if not widgets.remove(str(body.get("id", ""))):
        return {"ok": False, "error": "ودجت غير موجود"}
    return {"ok": True}


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
            "independent_review": result.get("independent_review", ""),
        })
        return payload
    if result.get("reply"):
        payload["reply"] = result["reply"]
    else:
        payload["reply"] = result.get("verdict", "")
    return payload


def _format_room_result(room: str, result: dict) -> dict:
    """نفس _format_result لكن تسجّل الرد (أو طلب الموافقة) بسجل الغرفة
    نفسها أيضاً — عشان خيط المحادثة يبقى كامل ومراقَب لاحقاً، لا يختفي
    بعد انتهاء الطلب."""
    if "pending_request_id" in result:
        what, why = result.get("what", ""), result.get("why", "")
        review = result.get("independent_review", "")
        note = f"يحتاج موافقتك: {what}" + (f" — {why}" if why else "")
        if review:
            note += f"\n\nرأي المراجع المستقل: {review}"
        rooms.post(room, room, note)
        return {
            "needs_confirmation": True, "request_id": result["pending_request_id"],
            "what": what, "why": why, "independent_review": review,
        }
    reply = result.get("reply") or result.get("verdict", "")
    rooms.post(room, room, reply)
    return {"reply": reply}


def _run_in_room(room: str, message: str, speaker: str = "owner") -> dict:
    """رسالة لموظف بغرفته — من صاحب الشركة أو من الـCEO (speaker)."""
    rooms.post(room, speaker, message)
    bot = bots.BOTS[room]
    result = kernel.run_task(
        message, persona=bot["persona"], allowed_tools=bot["allowed_tools"],
        proposed_by=room, interactive=False,
    )
    return _format_room_result(room, result)


def _ceo_dispatch(room: str, task: str) -> dict:
    return _run_in_room(room, task, speaker="ceo")


def _ceo_proposals(resp: dict) -> list[dict]:
    """طلبات الـCEO اللي تنتظر موافقتك (توظيف/أداة/كود) بشكل موحّد للواجهة."""
    out = []
    for key, label in (("hire_proposal", "توظيف"), ("grant_proposal", "أدوات"), ("widget_proposal", "ودجت")):
        p = resp.get(key)
        if p:
            out.append({"kind": label, "request_id": p["request_id"], "what": p["what"],
                        "independent_review": p.get("independent_review")})
    code = resp.get("code_proposal")
    if code and code.get("ok"):
        out.append({"kind": "كود", "request_id": code["request_id"], "what": "تعديل كود agent_os4 (نجح باختبار الساندبوكس)",
                    "diff": code.get("diff", "")[:4000], "independent_review": code.get("independent_review")})
    return out


def _handle_ceo(body: dict) -> dict:
    message = str(body.get("message", "")).strip()
    if not message:
        return {"error": "رسالة فاضية"}
    resp = ceo.handle(message, _ceo_dispatch)
    resp["proposals"] = _ceo_proposals(resp)
    return resp


def _ceo_summary_text(resp: dict) -> str:
    lines = [resp.get("reply") or ""]
    for a in resp.get("assignments", []):
        state = "يحتاج موافقتك" if a.get("needs_confirmation") else "ردّ"
        lines.append(f"← {a['title_ar']}: {state}")
    lines += resp.get("notes", [])
    code = resp.get("code_proposal")
    if code and not code.get("ok"):
        lines.append(f"تعديل الكود ما اكتمل ({code.get('stage')}): {str(code.get('error'))[:300]}")
    return "\n".join(x for x in lines if x)


def _handle_room_send(body: dict) -> dict:
    room = str(body.get("room", "")).strip()
    message = str(body.get("message", "")).strip()
    if not rooms.is_valid(room):
        return {"error": "غرفة غير معروفة"}
    if not message:
        return {"error": "رسالة فاضية"}
    if room == rooms.EXECUTIVE:
        # مكتب الإدارة العليا = الـCEO: يوزّع أو يوظّف، راجع ceo.py
        resp = _handle_ceo({"message": message})
        if resp.get("error"):
            return resp
        return {"reply": _ceo_summary_text(resp), "proposals": resp["proposals"]}
    return _run_in_room(room, message)


def _handle_room_confirm(body: dict) -> dict:
    room = str(body.get("room", "")).strip()
    request_id = body.get("request_id")
    approved = bool(body.get("approved"))
    if not rooms.is_valid(room):
        return {"error": "غرفة غير معروفة"}
    if not request_id:
        return {"error": "يحتاج request_id"}

    (decision.approve if approved else decision.reject)(request_id, decided_by="owner")
    result = kernel.resume_task(request_id)
    if not result.get("ok", True) and "error" in result and "verdict" not in result:
        return {"error": result["error"]}
    return _format_room_result(room, result)


def _rooms_list_data() -> dict:
    """لِـsidebar صفحة /rooms: كل غرفة + آخر رسالة فيها، عشان تشوف
    لمحة سريعة بلا ما تفتح كل غرفة لحالها."""
    out = []
    for r in rooms.list_rooms():
        last_list = rooms.history(r["key"], limit=1)
        last = last_list[-1] if last_list else None
        out.append({
            **r,
            "last_text": (last["text"][:90] if last else ""),
            "last_at": (last["at"] if last else ""),
            "last_speaker": (last["speaker"] if last else ""),
        })
    return {"rooms": out}


def _handle_broadcast(body: dict) -> dict:
    """أمر واحد يُرسَل لكل الموظفين (البوتات الثمانية) دفعة وحدة — كل
    واحد يستلمه بغرفته الخاصة ويشتغل عليه بنفس مساره العادي تماماً
    (kernel.run_task بشخصيته وأدواته المحصورة). لا غرفة تنفيذية هنا —
    "الموظفون" يعني المديريات الثمانية، لا مكتب صاحب النظام نفسه.

    تنفيذ متسلسل عمداً لا متوازٍ: approval.py/decision.py/rooms.py كلها
    تحفظ بقراءة-تعديل-كتابة لملف JSON واحد — تنفيذ متزامن بعدة خيوط
    يفتح سباق كتابة حقيقي (قرار بوت يضيع لو كتب بوت ثانٍ بنفس اللحظة).
    التسلسل أبطأ لكنه الوحيد المضمون الصحة هنا."""
    message = str(body.get("message", "")).strip()
    if not message:
        return {"error": "رسالة فاضية"}

    results = []
    for bot_key, bot in bots.BOTS.items():
        rooms.post(bot_key, "owner", message)
        result = kernel.run_task(
            message, persona=bot["persona"], allowed_tools=bot["allowed_tools"],
            proposed_by=bot_key, interactive=False,
        )
        formatted = _format_room_result(bot_key, result)
        formatted["room"] = bot_key
        formatted["title_ar"] = bot["title_ar"]
        results.append(formatted)
    return {"results": results}


def _meeting_data() -> dict:
    """نفس chatroom.history() — غرفة جماعية واحدة مشتركة (لا غرفة لكل
    موضوع)، عشان لو رجعوا يناقشون موضوعاً سابقاً بعد رفضك يبان استمراراً
    طبيعياً لنفس المحادثة، لا جلسة منفصلة مبتورة."""
    return {"messages": chatroom.history(limit=200)}


def _handle_meeting_start(body: dict) -> dict:
    """يغلّف chatroom.resolve() الموجودة فعلياً بالضبط — نقاش جماعي
    حقيقي بين البوتات المختارة، ثم توصية نهائية تُفتح كطلب موافقة عبر
    decision.propose() (نفس بوابة الموافقة الوحيدة، الآن بمراجعة مستقلة
    مغذّاة بسياق حقيقي تلقائياً لكل توصية). لا تنفيذ هنا إطلاقاً — فقط
    نقاش وتوصية؛ الموافقة تُحسم من نفس /api/dashboard/decide الموجود."""
    bot_keys = body.get("bot_keys") or []
    topic = str(body.get("topic", "")).strip()
    rounds = body.get("rounds", 1)
    if not topic:
        return {"error": "الموضوع فاضي"}
    if not bot_keys:
        return {"error": "اختر بوتاً واحداً على الأقل"}
    unknown = [k for k in bot_keys if k not in bots.BOTS]
    if unknown:
        return {"error": f"بوتات غير معروفة: {unknown}"}
    try:
        rounds = max(1, min(int(rounds), 3))  # حد أعلى معقول — لا جدل بلا نهاية
    except (TypeError, ValueError):
        rounds = 1
    try:
        return chatroom.resolve(bot_keys, topic, rounds=rounds)
    except Exception as e:  # noqa: BLE001 — خطأ غير متوقع يُرجَع صادقاً، لا يُسقط السيرفر
        return {"error": f"{type(e).__name__}: {e}"}


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path, qs = parsed.path, parse_qs(parsed.query)
        if path in ("/", "/index.html"):
            body = _UI_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/dashboard":
            body = _DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/rooms":
            body = _ROOMS_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/dashboard":
            self._send_json(200, _dashboard_data())
        elif path == "/api/rooms":
            self._send_json(200, _rooms_list_data())
        elif path == "/api/room":
            key = (qs.get("key") or [""])[0]
            if not rooms.is_valid(key):
                self._send_json(404, {"error": "غرفة غير معروفة"})
            else:
                self._send_json(200, {"room": key, "messages": rooms.history(key)})
        elif path == "/api/rooms/monitor":
            self._send_json(200, {"messages": rooms.recent_all()})
        elif path == "/api/meeting":
            self._send_json(200, _meeting_data())
        elif path == "/api/widgets":
            self._send_json(200, _widgets_data())
        elif path == "/api/brain-state":
            self._send_json(200, _brain_state())
        elif path == "/api/skill":
            skill = agent_skills.get((qs.get("name") or [""])[0])
            self._send_json(200 if skill else 404, skill or {"error": "مهارة غير موجودة"})
        else:
            self.send_response(404)
            self.end_headers()

    def _is_local_request(self) -> bool:
        """محلي فعلاً = الاتصال من loopback **و** اسم المضيف محلي. الشرط
        الثاني يسد DNS rebinding: موقع خبيث يخلي نطاقه يشير لـ127.0.0.1
        فيصير الاتصال loopback، لكن Host يبقى اسم نطاقه هو."""
        host = urlparse("//" + (self.headers.get("Host") or "")).hostname or ""
        return self.client_address[0] in _LOOPBACK_IPS and host in _LOOPBACK_HOSTNAMES

    def _reject_cross_site(self) -> bool:
        """حماية CSRF: موقع ثاني مفتوح بمتصفحك ما يقدر يرسل طلب POST هنا.
        نشترط Content-Type: application/json (المتصفح ما يرسله لموقع ثاني
        بدون preflight، وهذا السيرفر ما يرد على OPTIONS)، ولو فيه Origin
        لازم يطابق Host نفسه."""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._send_json(415, {"error": "الطلب لازم يكون Content-Type: application/json"})
            return True
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != (self.headers.get("Host") or ""):
            self._send_json(403, {"error": "طلب من موقع آخر — مرفوض (حماية CSRF)"})
            return True
        return False

    def do_POST(self):
        if self._reject_cross_site():
            return
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/chat":
                self._send_json(200, _handle_chat(body))
            elif path == "/api/confirm":
                self._send_json(200, _handle_confirm(body))
            elif path == "/api/dashboard/decide":
                self._send_json(200, _handle_dashboard_decide(body))
            elif path == "/api/dashboard/pc-toggle":
                self._send_json(200, _handle_pc_toggle(body, self._is_local_request()))
            elif path == "/api/dashboard/budget":
                self._send_json(200, _handle_budget(body, self._is_local_request()))
            elif path == "/api/room/send":
                self._send_json(200, _handle_room_send(body))
            elif path == "/api/room/confirm":
                self._send_json(200, _handle_room_confirm(body))
            elif path == "/api/memory":
                self._send_json(200, _handle_memory_edit(body))
            elif path == "/api/skills/delete":
                self._send_json(200, _handle_skill_delete(body))
            elif path == "/api/widgets/add":
                self._send_json(200, _handle_widget_add(body))
            elif path == "/api/widgets/remove":
                self._send_json(200, _handle_widget_remove(body))
            elif path == "/api/ceo":
                self._send_json(200, _handle_ceo(body))
            elif path == "/api/rooms/broadcast":
                self._send_json(200, _handle_broadcast(body))
            elif path == "/api/meeting/start":
                self._send_json(200, _handle_meeting_start(body))
            else:
                self._send_json(404, {"error": "مسار غير معروف"})
        except Exception as e:  # noqa: BLE001 — خطأ غير متوقع يُرجَع للمتصفح، لا يُسقط السيرفر
            self._send_json(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        print("[web_chat] " + (fmt % args))


def main() -> None:
    try:
        indexed = sessions.backfill(rooms._ROOMS_FILE)
        if indexed:
            print(f"[web_chat] فهرسة {indexed} رسالة قديمة للبحث بالمحادثات")
    except Exception as e:  # noqa: BLE001
        print(f"[web_chat] تعذّرت فهرسة المحادثات القديمة: {e}")
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
