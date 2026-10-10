"""اختبار Web API action detection + confirm flow"""
import sys, json, urllib.request, uuid, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "http://127.0.0.1:8788/api/chat"
MSG = "افتح لي sandbox جديد وخذ لقطة شاشة منه"
cid = "test-" + str(uuid.uuid4())[:8]

def post(payload, timeout=10):
    data = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(API, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

# 3a — إرسال الرسالة
print("="*60)
print(f"[3a] POST /api/chat: «{MSG}»")
r1 = post({"chat_id": cid, "message": MSG})
print(f"الرد الكامل: {json.dumps(r1, ensure_ascii=False)}")
needs_confirm = r1.get("needs_confirmation", False)
print(f"needs_confirmation: {needs_confirm} {'✓ ACTION اكتُشف!' if needs_confirm else '✗ لم يُكتشف'}")

if needs_confirm:
    # 3b — تأكيد التنفيذ (Hermes سيشتغل بالـserver context)
    print(f"\n[3b] POST /api/chat confirm_action=true")
    print("  (يستغرق وقتاً — Hermes ينفّذ الخطة)")
    r2 = post({"chat_id": cid, "confirm_action": True}, timeout=120)
    print(f"الرد: {json.dumps(r2, ensure_ascii=False)[:500]}")
    engine = r2.get("engine", "-")
    reply = r2.get("reply", "")
    print(f"engine: {engine}")
    print(f"reply (أول 300): {reply[:300]}")
    if "hermes" in str(engine).lower() or "hermes" in str(reply).lower():
        print("✓ Hermes تشغّل")
    else:
        print("ملاحظة: تحقق من الرد أعلاه لمعرفة ما شغّله")
else:
    print("(لا تأكيد — الـAPI لم يكتشف ACTION)")

# تنظيف sandbox لو أُنشئ
print("\n[تنظيف] active_sandboxes:")
import os; os.chdir("C:\\Users\\hhdjj\\agent-os-v3")
sys.path.insert(0, "C:\\Users\\hhdjj\\agent-os-v3")
try:
    from agent_os import computer_sandbox as cs
    active = cs.active_sandboxes()
    print(f"active = {list(active.keys())}")
    for sid, info in active.items():
        if not info.get("destroyed"):
            cs.destroy(sid)
            print(f"✓ دُمِّر: {sid}")
    print(f"بعد التنظيف: {cs.active_sandboxes()}")
except Exception as e:
    print(f"خطأ: {e}")
