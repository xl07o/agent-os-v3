/* JARVIS HUD — قمرة فوق نواة تنفيذ حقيقية. لا رقم يُعرض ما لم يُقاس. */
const $ = id => document.getElementById(id);
let mode = 'ask', pending = {}, runEl = null, soundOn = true, sr = null, listening = false;
let tTab = 'feed', engine = 'jarvis', hermesEl = null;

const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const api = async (p, b) => { const r = await fetch(p, { method: b ? 'POST' : 'GET', headers: b ? { 'Content-Type': 'application/json' } : undefined, body: b ? JSON.stringify(b) : undefined }); return r.json(); };

/* ---------- نواة الحالة + إشارات صوتية مُصنَّعة (بلا ملفات) ---------- */
let actx = null;
function ac() {
  if (!actx) { try { actx = new (window.AudioContext || window.webkitAudioContext)(); } catch (_) { actx = null; } }
  if (actx && actx.state === 'suspended') actx.resume();
  return actx;
}
function tone(f, d, ty, g, at) {
  const c = ac(); if (!c || !soundOn) return;
  const o = c.createOscillator(), v = c.createGain();
  o.type = ty || 'sine'; o.frequency.value = f;
  const n = c.currentTime + (at || 0);
  v.gain.setValueAtTime(0, n);
  v.gain.linearRampToValueAtTime(g == null ? .06 : g, n + .01);
  v.gain.exponentialRampToValueAtTime(.0001, n + d);
  o.connect(v); v.connect(c.destination); o.start(n); o.stop(n + d + .03);
}
const CUE = {
  boot: () => { tone(320, .12, 'sine', .05); tone(480, .18, 'sine', .04, .1); },
  step: () => tone(660, .05, 'square', .03),
  ok: () => { tone(720, .1, 'sine', .05); tone(1080, .16, 'sine', .045, .07); },
  fail: () => tone(210, .28, 'sawtooth', .05),
  done: () => { tone(520, .12, 'sine', .05); tone(780, .14, 'sine', .045, .1); tone(1040, .2, 'sine', .04, .2); }
};
function setState(s) { const c = $('core'); if (c) c.className = s || ''; }
document.addEventListener('pointerdown', () => ac(), { once: true });
document.addEventListener('keydown', () => ac(), { once: true });

/* ---------- telemetry (قراءة حقيقية من الخادم) ---------- */
function ring(arcId, v, color) {
  const a = $(arcId);
  if (a) { a.setAttribute('stroke-dashoffset', 132 * (1 - Math.max(0, Math.min(100, v)) / 100)); a.setAttribute('stroke', color); }
}
function gb(x) { return x == null ? '—' : (x / 1073741824).toFixed(1) + ' GB'; }
function mb(x) { return x == null ? '—' : Math.round(x / 1048576) + ' MB'; }
async function telemetry() {
  try {
    const t = await api('/api/telemetry');
    const cpu = t.cpu, ram = t.ram, dsk = t.disk, net = t.net;
    $('cpuP').textContent = cpu == null ? '—' : cpu + '%';
    $('cpuV').textContent = cpu == null ? '—' : Math.round(cpu) + '';
    ring('cpuArc', cpu || 0, '#4cc9f0');
    if (ram) {
      const p = Math.round(ram.used / ram.total * 100);
      $('ramP').textContent = p + '%'; $('ramV').textContent = gb(ram.used);
      $('ramSub').textContent = 'متاح ' + gb(ram.avail) + ' من ' + gb(ram.total);
      ring('ramArc', p, '#2de0a4');
    } else { $('ramP').textContent = $('ramV').textContent = $('ramSub').textContent = '—'; ring('ramArc', 0, '#5e7191'); }
    if (dsk && dsk.length) {
      const d = dsk[0], p = Math.round(d.used / d.total * 100);
      $('dskV').textContent = p + '%'; $('dskB').style.width = p + '%';
      $('dskSub').textContent = d.d + ' ' + gb(d.used) + ' من ' + gb(d.total);
    } else { $('dskV').textContent = $('dskSub').textContent = '—'; $('dskB').style.width = '0'; }
    $('netIn').textContent = net ? Math.round(net.in) + 'k' : '—';
    $('netOut').textContent = net ? Math.round(net.out) + 'k' : '—';
    $('upT').textContent = 'عمر التشغيل: ' + (t.uptime == null ? '—' : fmtUptime(t.uptime));
    if (t.procs && t.procs.length) $('procs').innerHTML = t.procs.slice(0, 7).map(p =>
      `<span><b>${esc(p.n)}</b> ${Math.round(p.m)} MB · ${Math.round(p.c)}ث CPU</span>`).join('');
    else $('procs').innerHTML = '<div class="lb">عمليات الأعلى · لا قراءة —</div>';
  } catch (e) { /* اللوحة تعيش بصمت عند انقطاع */ }
}
function fmtUptime(s) {
  const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
  return d + 'ي ' + h + 'س ' + m + 'د';
}
setInterval(telemetry, 2000);

/* ---------- SSE ---------- */
function feed(kind, html) {
  const el = document.createElement('div');
  el.className = 'msg ' + kind; el.innerHTML = html;
  $('feed').appendChild(el); $('feed').scrollTop = 1e9;
  $('term').style.display = 'none'; showTab('feed');
  return el;
}
function terminal(cmd, out, ok, ts) {
  const el = document.createElement('div');
  el.className = 'te ' + (ok ? '' : 'x');
  el.innerHTML = `<div><span class="ts">${esc(ts || '')}</span><span class="c">PS&gt; ${esc(cmd || '')}</span></div>` +
    (out ? `<div class="o">${esc(out)}</div>` : '') + (!ok ? `<div class="o x">EXIT ≠ 0</div>` : '');
  $('term').prepend(el);
}
function acard(ev) {
  const c = document.createElement('div');
  const s = (ev.status || 'run').toUpperCase();
  c.className = 'acard ' + (s === 'PENDING' || s === 'RUN' ? 'run' : s === 'OK' || s === 'ALLOWED' ? 'ok' : 'fail');
  const stt = s === 'PENDING' || s === 'RUN' ? 'b' : s === 'OK' || s === 'ALLOWED' ? 'g' : 'r';
  let html = `<div class="row"><span class="st ${stt}">${s}</span><span class="tool">${esc(ev.tool || '')}</span><span style="color:var(--t2);font-size:10px">${esc(ev.ts || '')}</span></div>`;
  if (ev.why) html += `<div class="why">${esc(ev.why)}</div>`;
  if ((ev.payload && ev.payload.args && Object.keys(ev.payload.args).length)) {
    const j = JSON.stringify(ev.payload.args);
    html += `<div class="out">${esc(j.length > 400 ? j.slice(0, 400) + '…' : j)}</div>`;
  }
  if (ev.out) html += `<div class="out">${esc(ev.out.length > 500 ? ev.out.slice(0, 500) + '…' : ev.out)}</div>`;
  if (ev.error) html += `<div class="err">${esc(ev.error)}</div>`;
  c.innerHTML = html;
  $('acts').insertBefore(c, $('acts').firstChild);
  if (ev.cmd) terminal(ev.cmd, ev.out, !ev.error && ev.status !== 'fail', ev.ts);
  if (ev.payload && ev.payload.aid && ev.status === 'pending') {
    const aid = ev.payload.aid;
    const ap = document.createElement('div'); ap.className = 'ap';
    ap.innerHTML = `<button class="yes">تنفيذ</button><button class="no">رفض</button>`;
    ap.querySelector('.yes').onclick = () => decide(aid, true);
    ap.querySelector('.no').onclick = () => decide(aid, false);
    c.appendChild(ap);
    pending[aid] = { c, t: setTimeout(() => { delete pending[aid]; if (ap.parentNode) ap.replaceWith(tag('انتهت المهلة', 'fail')); }, 120000) };
  }
}
const tag = (t, cls) => Object.assign(document.createElement('div'), { textContent: t, className: 'why', style: 'color:' + (cls === 'fail' ? 'var(--fail)' : 'var(--ok)') });
function decide(aid, allow) {
  const p = pending[aid];
  if (p && p.c.querySelector('.ap')) { const b = p.c.querySelectorAll('.ap button'); b.forEach(x => x.disabled = true); p.c.querySelector('.ap').style.opacity = '.4'; }
  api('/api/approve', { id: aid, allow });
}
function onEvent(ev) {
  if (ev.kind === 'run' && ev.status === 'start') {
    if (ev.engine === 'hermes') {
      hermesEl = feed('jv', `<span class="tag">🛰 Hermes</span><h4>${esc(ev.text)}</h4><div class="out" id="hout"></div>`);
    } else {
      runEl = feed('jv', `<span class="tag">▶ مهمة</span><h4>${esc(ev.text)}</h4>`);
      runEl.querySelector('h4').classList.add('blk');
    }
    $('runb').textContent = 'يعمل…'; $('runb').style.color = 'var(--warn)';
    setState('work'); CUE.boot();
  }
  if (ev.kind === 'hermes' && ev.status === 'out') {
    const o = document.getElementById('hout');
    if (o) { o.textContent += (o.textContent ? '\n' : '') + ev.text; o.scrollTop = 1e9; }
    if (!o && hermesEl) { const d = document.createElement('div'); d.className = 'out'; d.textContent = ev.text; hermesEl.appendChild(d); }
    $('feed').scrollTop = 1e9;
  }
  if (ev.kind === 'step') {
    if (runEl) { const h = runEl.querySelector('h4'); if (h) h.classList.remove('blk'); }
    $('runb').textContent = ev.status === 'ok' ? ev.tool : 'عطل: ' + ev.tool;
    acard(ev);
    if (ev.status === 'fail') { setState('fail'); CUE.fail(); } else { setState('work'); CUE.step(); }
    if (ev.status === 'fail') feed('fail', `<span class="tag">✘ عجز — الصدق</span>${esc(ev.error || ev.why || '')}`);
  }
  if (ev.kind === 'approval' && ev.payload && ev.payload.aid) updateApproval(ev.payload.aid, ev.status);
  if (ev.kind === 'verdict' && ev.status === 'done') {
    const h = document.createElement('div');
    h.className = 'msg jv';
    h.innerHTML = `<span class="tag">⚖ الحكم</span>${esc(ev.text || '')}` +
      (ev.report ? `<br><a class="report" href="/api/report?name=${encodeURIComponent(ev.report.split(/[\\/]/).pop())}">فتح تقرير الإثبات</a>` : '');
    $('feed').appendChild(h); $('feed').scrollTop = 1e9;
    if (ev.text) say(ev.text);
    $('runb').textContent = 'واقف'; $('runb').style.color = 'var(--t2)';
    const good = !/^\s*✘|فشل تشغيل/.test(ev.text || '');
    setState(good ? 'ok' : 'fail'); CUE.done();
    setTimeout(() => { const c = $('core'); if (c && (c.className === 'ok' || c.className === 'fail')) setState(''); }, 1400);
    $('in').disabled = $('send').disabled = false;
    runEl = null; hermesEl = null;
    loadSessions();
  }
}
function updateApproval(aid, status) {
  const p = pending[aid]; if (!p) return;
  clearTimeout(p.t); delete pending[aid];
  const c = p.c; c.classList.remove('run');
  c.classList.add(status === 'allowed' ? 'ok' : 'fail');
  const s = c.querySelector('.st'); if (s) { s.textContent = status === 'allowed' ? 'OK' : 'FAIL'; s.className = 'st ' + (status === 'allowed' ? 'g' : 'r'); }
  const ap = c.querySelector('.ap'); if (ap) ap.replaceWith(tag(status === 'allowed' ? 'نُفّذ بموافقتك' : 'رُفض', status === 'allowed' ? 'ok' : 'fail'));
}

/* ---------- tabs ---------- */
function showTab(t) {
  tTab = t;
  ['feed', 'term', 'ses', 'mem', 'set'].forEach(x => $('#' + (x === 'feed' ? 'feed' : x)).style.display = x === t ? 'block' : 'none');
  document.querySelectorAll('.phead button').forEach(b => b.classList.toggle('on', b.dataset.t === t));
  if (t === 'ses') loadSessions();
  if (t === 'mem') loadMemory();
  if (t === 'set') loadSettings();
}
document.querySelectorAll('.phead button').forEach(b => b.onclick = () => showTab(b.dataset.t));

/* ---------- حقول جلسات/ذاكرة/إعدادات ---------- */
async function loadSessions() {
  const rows = await api('/api/sessions');
  document.querySelector('#ses tbody').innerHTML = rows.map(x => {
    const rep = x.report ? `<a class="report" style="border:none;padding:0" href="/api/report?name=${encodeURIComponent(x.report)}">تقرير</a>` : '';
    return `<tr><td>${esc(x.session)}</td><td>${esc(x.text)}</td><td class="g">${x.ok}/${x.steps}</td><td class="b">${x.fail}</td><td>${esc(x.verdict)} ${rep}</td></tr>`;
  }).join('') || '<tr><td colspan="5" style="color:var(--t2)">لا جلسات بعد</td></tr>';
}
async function loadMemory() {
  const m = await api('/api/memory');
  $('mem').innerHTML = (m.facts || []).map((f, i) =>
    `<div class="fact">${esc(f.f)}<span style="margin-inline-start:auto;color:var(--t2);font-size:10px">${esc(f.t)}</span><button onclick="delFact(${i})">✕</button></div>`).join('') +
    `<div id="memadd"><input id="mf" placeholder="معلومة: أخي أحمد…"><button id="madd">حفظ</button></div>`;
  $('madd').onclick = async () => { const f = $('mf').value.trim(); if (f) { await api('/api/memory', { action: 'add', fact: f }); loadMemory(); } };
}
async function delFact(i) { await api('/api/memory', { action: 'del', index: i }); loadMemory(); }
async function loadSettings() {
  const h = await api('/api/health'), m = await api('/api/memory'), t = await api('/api/telemetry');
  const cpu = t.cpu == null ? 0 : t.cpu;
  $('set').innerHTML = `
   <div class="row"><label>اسم المساعد</label><input id="nm" value="${esc(m.assistant_name || 'جارفيس')}"><button id="svn">حفظ</button></div>
   <div class="row"><label>المقصود</label><span class="hint">${esc(m.user_name || 'مالك')}</span></div>
   <div class="row"><label>محرك العقل</label><span class="hint" dir="ltr">${esc(h.mode || 'hybrid')} — عقل هجين (Gemini محلي سابقًا عند توفر المفتاح، Ollama متى وُجد).</span></div>
   <div class="row"><label>وكيل Hermes</label><span class="hint" dir="ltr">${h.hermes && h.hermes.ok ? esc(h.hermes.version || 'Hermes') + ' — جاهز' : 'غير متاح'}</span></div>
   <div class="row"><label>هذه الآلة</label><span class="hint">${t.cores || '—'} نواة · ${gbm(t.ram)} · CPU الآن ${cpu}%</span></div>
   <div class="row"><label>بوابة الصدق</label><span class="hint">«تمام» تصدر فقط بدليل أداة موثّق في evidence.jsonl. رقم لا يُقرأ = شرطة.</span></div>
   <div class="row"><label>انتباه</label><span class="hint">كل أمر bash / كتابة يمرّ على زر موافقتك في وضع «آسك». استرجاع الإثبات متاح بالتقارير.</span></div>`;
  $('svn').onclick = async () => { await api('/api/memory', { action: 'name', name: $('nm').value }); loadSettings(); };
}
function gbm(ram) { return ram && ram.total ? (ram.total / 1073741824).toFixed(1) + ' GB' : '—'; }

/* ---------- أزرار أعلى ---------- */
document.querySelectorAll('#modes button').forEach(b => b.onclick = () => {
  mode = b.dataset.auto;
  document.querySelectorAll('#modes button').forEach(x => x.classList.toggle('on', x === b));
});
$('fsound').onclick = () => { soundOn = !soundOn; $('fsound').textContent = 'الصوت: ' + (soundOn ? 'تشغيل' : 'إيقاف'); };
$('feng').onclick = () => {
  engine = engine === 'hermes' ? 'jarvis' : 'hermes';
  $('feng').textContent = 'المحرك: ' + (engine === 'hermes' ? 'Hermes' : 'نواة');
  $('feng').style.color = engine === 'hermes' ? 'var(--acc)' : '';
  $('feng').style.borderColor = engine === 'hermes' ? 'var(--acc)' : '';
};
$('fclose').onclick = () => { $('wbox').style.display = 'none'; $('fbox').style.display = 'none'; };
document.querySelectorAll('[data-close]').forEach(x => x.onclick = () => document.getElementById(x.dataset.close).style.display = 'none');

/* ---------- نوافذ عائمة (سحب) ---------- */
document.querySelectorAll('.float').forEach(f => {
  const h = f.querySelector('.fh');
  h.addEventListener('mousedown', e => {
    const off = { x: e.clientX - f.offsetLeft, y: e.clientY - f.offsetTop };
    const mv = ev => { f.style.left = Math.max(0, Math.min(innerWidth - 80, ev.clientX - off.x)) + 'px'; f.style.top = Math.max(0, ev.clientY - off.y) + 'px'; };
    const up = () => { removeEventListener('mousemove', mv); removeEventListener('mouseup', up); };
    addEventListener('mousemove', mv); addEventListener('mouseup', up);
  });
});
async function weather() {
  const w = await api('/api/weather');
  const b = $('wbody');
  if (!w.ok) b.innerHTML = '<span class="nooff">لا قياس — ' + esc(w.error || '') + '</span>';
  else b.innerHTML = `<b>${esc(w.city)}</b> · ${esc(w.desc)}<br>حرارة <b>${esc(w.temp)}°</b> · رطوبة ${esc(w.hum)}% · رياح ${esc(w.wind)}كم/س`;
}
async function firewall() {
  const f = await api('/api/firewall');
  const b = $('fbody');
  if (!f || !f.length) b.innerHTML = '<span class="nooff">لا قراءة</span>';
  else b.innerHTML = f.map(x => `${esc(x.name)}: <span class="${x.enabled ? 'okok' : 'nooff'}">${x.enabled ? 'مفعّل' : 'مطفأ'}</span>`).join('<br>');
}

/* ---------- صوت: إملاء عربي + نطق ---------- */
function initVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SR) {
    sr = new SR(); sr.lang = 'ar-SA'; sr.continuous = true; sr.interimResults = false;
    sr.onresult = e => { $('in').value += Array.from(e.results).map(r => r[0].transcript).join(' '); $('in').focus(); };
    sr.onend = () => setMic(false);
  }
  $('mic').onclick = () => SR ? setMic(!listening) : ($('mic').textContent = 'لا دعم');
}
function setMic(on) {
  listening = on; $('mic').classList.toggle('live', on);
  $('mic').textContent = on ? '●' : 'MIC';
  on ? sr.start() : sr.stop();
}
function say(t) {
  if (!soundOn || !('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(String(t || ''));
  u.lang = 'ar-SA'; u.rate = 1;
  const v = speechSynthesis.getVoices().find(v => v.lang && v.lang.startsWith('ar'));
  if (v) u.voice = v;
  speechSynthesis.speak(u);
}

/* ---------- مهام ---------- */
async function runTask() {
  const t = $('in').value.trim(); if (!t) return;
  $('in').value = ''; $('send').disabled = $('in').disabled = true;
  feed('user', esc(t));
  const r = engine === 'hermes' ? await api('/api/hermes', { text: t }) : await api('/api/task', { text: t });
  if (r.error) { feed('fail', esc(r.error)); $('send').disabled = $('in').disabled = false; }
}
async function bootStatus() {
  const s = await api('/api/status');
  (s.bash || []).forEach(x => terminal(x.cmd, x.out, x.ok, x.ts));
  if (s.running) { $('runb').textContent = s.tool || 'يعمل…'; $('runb').style.color = 'var(--warn)'; }
}
function stream() {
  const es = new EventSource('/api/events');
  es.onmessage = e => { try { onEvent(JSON.parse(e.data)); } catch (_) {} };
  es.onerror = () => { $('sock').textContent = 'إعادة وصل'; es.close(); setTimeout(stream, 1500); };
}

/* ---------- نواة الحالة: نبض أثناء التشغيل الحقيقي ---------- */
async function stateLoop() {
  try {
    const s = await api('/api/status');
    if (s.running) setState('work');
    else { const c = $('core'); if (c && c.className === 'work') setState(''); }
  } catch (_) {}
}

/* ---------- إقلاع: سطور من قياسات حقيقية لا ادّعاء ---------- */
async function boot() {
  const ln = $('bootln'), out = [];
  const k = s => `<span class="k">${s}</span>`, g = s => `<span class="g">${s}</span>`, r = s => `<span class="r">${s}</span>`;
  const put = h => { out.push(h); ln.innerHTML = out.join('\n'); };
  const wait = ms => new Promise(res => setTimeout(res, ms));
  setTimeout(() => { const b = $('boot'); if (b) b.classList.add('gone'); }, 6000);
  put(k('JARVIS') + ' — تهيئة النواة…');
  await wait(320);
  let h = null, t = null;
  try { h = await api('/api/health'); } catch (_) {}
  try { t = await api('/api/telemetry'); } catch (_) {}
  put(h && h.ok ? g('✔') + ' الخادم متصل · المحرك ' + esc(h.mode || '—') : r('✘') + ' الخادم لا يستجيب');
  await wait(280);
  put(h && h.hermes && h.hermes.ok ? g('✔') + ' Hermes ' + esc((h.hermes.version || '').split('\n')[0]) : r('✘') + ' Hermes غير متاح');
  await wait(280);
  put(t ? g('✔') + ' ' + (t.cores || '—') + ' نواة · ' + (t.ram ? (t.ram.total / 1073741824).toFixed(1) + ' GB ذاكرة' : '—') + ' · CPU ' + (t.cpu == null ? '—' : t.cpu + '%') : r('✘') + ' قياسات غير متاحة');
  await wait(280);
  put(h && h.hermes && h.hermes.ok ? k('النظام جاهز.') : k('النظام جزئي —'));
  CUE.boot();
  await wait(680);
  const b = $('boot'); if (b) b.classList.add('gone');
}

/* ---------- بدء ---------- */
$('send').onclick = runTask;
$('in').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); runTask(); } });
initVoice(); weather(); firewall(); loadSessions(); setTimeout(bootStatus, 400);
setInterval(weather, 600000); setInterval(firewall, 20000);
stream(); telemetry(); boot(); setInterval(stateLoop, 3000);