"""
test_sandbox_flow2.py — إعادة اختبار السيناريو الفاشل بعد الإصلاحات (commit 6106517)
يختبر:
  1. _wants_action مع الصيغة الجديدة (A/C)
  2. Orchestrator sandbox_id passing بعد _substitute_refs
  3. Web API (chat_api) action detection و confirm flow
"""
import sys, json, os, time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

MSG = "افتح لي sandbox جديد وخذ لقطة شاشة منه"

# ══════════════════════════════════════
# الاختبار 1: _wants_action (الإصلاح الأول)
# ══════════════════════════════════════
print("\n" + "="*60)
print("[اختبار 1] _wants_action مع الصيغة الجديدة (A/C)")
print(f"  الرسالة: «{MSG}»")

wants_action = False
action_raw = None
action_engine = None
try:
    import chat_cli
    # نعترض brain.Brain.ask لنرى الرد الخام
    import brain as _brain
    _orig_brain_ask = _brain.Brain.ask
    _captured = {}
    def _spy_ask(self, prompt, mode=None, **kw):
        r = _orig_brain_ask(self, prompt, mode=mode, **kw)
        _captured['raw'] = r[0]
        _captured['engine'] = r[1]
        return r
    _brain.Brain.ask = _spy_ask

    wants_action = chat_cli._wants_action(MSG)
    action_raw = _captured.get('raw', '')
    action_engine = _captured.get('engine', '')
    _brain.Brain.ask = _orig_brain_ask  # استعادة

    print(f"  رد العقل الخام: «{str(action_raw).strip()[:120]}»")
    print(f"  المحرك: {action_engine}")
    print(f"  _wants_action → {wants_action}  {'✓ ACTION!' if wants_action else '✗ CHAT (فشل)'}")
except Exception as e:
    import traceback
    print(f"  [EXCEPTION] {e}")
    traceback.print_exc()

# ══════════════════════════════════════
# الاختبار 2: Orchestrator مع _substitute_refs (الإصلاح الثاني)
# ══════════════════════════════════════
print("\n" + "="*60)
print("[اختبار 2] Orchestrator.run() — هل sandbox_id يتمرّر صح الآن؟")

from jarvis_v2 import config as jconfig
jconfig.AUTORUN = "allow"

import jarvis_v2.orchestrator as jorch
import jarvis_v2.tools as jtools

tools_called = []
plan_captured = {}

_original_tool_run = jorch.tool_run
def _spy_tool_run(name, args, approver=None):
    record = {"tool": name, "args_before": json.dumps(args, ensure_ascii=False)[:200]}
    result = _original_tool_run(name, args, approver=approver)
    record["ok"] = result.get("ok", False)
    record["result_keys"] = list(result.keys()) if isinstance(result, dict) else []
    if result.get("sandbox_id"):
        record["returned_sandbox_id"] = result["sandbox_id"]
    if result.get("error"):
        record["error"] = result["error"]
    tools_called.append(record)
    print(f"  ⚡ {name} | args={record['args_before']}")
    print(f"     → ok={record['ok']} | keys={record['result_keys']}")
    if result.get("error"):
        print(f"     ✗ خطأ: {result['error'][:150]}")
    elif result.get("sandbox_id"):
        print(f"     sandbox_id الحقيقي: {result['sandbox_id']}")
    elif result.get("bytes") is not None:
        print(f"     لقطة شاشة: {result.get('bytes')} بايت")
    return result
jorch.tool_run = _spy_tool_run

_orig_parse = jorch._parse_plan
def _spy_parse(text):
    plan_captured['raw'] = text
    return _orig_parse(text)
jorch._parse_plan = _spy_parse

orch_result = None
try:
    oc = jorch.Orchestrator(approver=lambda name, args: True)
    orch_result = oc.run(MSG)
except Exception as e:
    import traceback
    print(f"  [ORCHESTRATOR EXCEPTION] {e}")
    traceback.print_exc()

# عرض الخطة
print("\n[الخطة JSON من العقل]:")
raw_plan = plan_captured.get('raw', '')
try:
    parsed_plan = json.loads(raw_plan.strip()) if raw_plan.strip().startswith("{") else None
    if parsed_plan:
        print(json.dumps(parsed_plan, ensure_ascii=False, indent=2)[:2000])
    else:
        print(raw_plan[:1500])
except Exception:
    print(raw_plan[:1500])

print(f"\n[ملخص الأدوات المُستدعاة: {len(tools_called)}]")
for i, r in enumerate(tools_called, 1):
    status = "✓" if r["ok"] else "✗"
    print(f"  {status} {i}. {r['tool']} | ok={r['ok']}")

if orch_result:
    print(f"\n[verdict] {orch_result.get('verdict', '-')}")
    print(f"[report]  {orch_result.get('report', '-')}")

# ══════════════════════════════════════
# الاختبار 3: Web API (chat_api) عبر HTTP
# ══════════════════════════════════════
print("\n" + "="*60)
print("[اختبار 3] اختبار chat_api عبر HTTP POST")

import urllib.request
import uuid as _uuid

API_URL = "http://127.0.0.1:8788/api/chat"
chat_id = "test-" + str(_uuid.uuid4())[:8]

def api_post(payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

# 3a: إرسال الرسالة الأصلية
print(f"  3a. POST /api/chat: «{MSG}»")
r1 = api_post({"chat_id": chat_id, "message": MSG})
print(f"  الرد: {json.dumps(r1, ensure_ascii=False)[:300]}")
needs_confirm = r1.get("needs_confirmation", False)
print(f"  needs_confirmation: {needs_confirm}  {'✓' if needs_confirm else '✗ (لم تُكتشف كـACTION)'}")

if needs_confirm:
    # 3b: تأكيد التنفيذ
    print(f"\n  3b. POST /api/chat: confirm_action=true")
    # نرسل confirm بتاريخ مختلف لأن الـhermes سيعمل async
    # نتوقع رداً طويلاً — نضع timeout أطول
    data2 = json.dumps({"chat_id": chat_id, "confirm_action": True}, ensure_ascii=False).encode()
    req2 = urllib.request.Request(API_URL, data=data2, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req2, timeout=120) as resp2:
            r2 = json.loads(resp2.read().decode("utf-8"))
        print(f"  الرد بعد التنفيذ (أول 400 حرف): {json.dumps(r2, ensure_ascii=False)[:400]}")
        print(f"  engine: {r2.get('engine', '-')}")
    except Exception as e:
        print(f"  [TIMEOUT/ERROR] {e}")
else:
    print("  (لا تأكيد — الرسالة لم تُكتشف كـACTION بالـAPI)")

# ══════════════════════════════════════
# تنظيف نهائي
# ══════════════════════════════════════
print("\n" + "="*60)
print("[تنظيف نهائي] active_sandboxes():")
try:
    from agent_os import computer_sandbox as cs
    active = cs.active_sandboxes()
    print(f"  active = {json.dumps(active, ensure_ascii=False, default=str)[:300]}")
    destroyed = []
    for sid in list(active):
        if not active[sid].get("destroyed"):
            try:
                cs.destroy(sid)
                destroyed.append(sid)
                print(f"  ✓ دُمِّر: {sid}")
            except Exception as e:
                print(f"  ✗ فشل تدمير {sid}: {e}")
    after = cs.active_sandboxes()
    print(f"  بعد التنظيف: {after}")
    if not any(not v.get("destroyed") for v in after.values()):
        print("  ✓ فاضية — لا sandboxes نشطة")
    else:
        print("  ✗ لا تزال توجد sandboxes!")
except Exception as e:
    print(f"  خطأ: {e}")

print("\n" + "="*60)
print("اكتمل الاختبار.")
