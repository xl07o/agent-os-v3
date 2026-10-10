"""
computer_sandbox.py - "يدان" آمنتان للوكيل عبر Daytona (v1.0)
================================================================
تحكم حاسوبي فعلي (فتح متصفح، كليك، كتابة، لقطة شاشة) — لكن دائماً داخل
جهاز سحابي معزول تماماً (Daytona sandbox)، أبداً على جهاز المستخدم
الحقيقي. هذا بالضبط الفرق بين "فتح صدفة على PC حقك" (مرفوض) و"يد
بجهاز وهمي منفصل" (آمن ومقبول) — العزل هو الحد الفاصل.

أمان التكلفة: كل sandbox يُنشأ بحد عمر تلقائي (TTL) ويُسجَّل كمصروف حقيقي
بـfinance_intel، ويُدمَّر صراحة بـdestroy() — لا sandbox يبقى يعمل منسياً.

الاستخدام:
  from agent_os import computer_sandbox as cs
  sb_id = cs.create()
  cs.run_bash(sb_id, "echo hello")
  png_bytes = cs.screenshot(sb_id)
  cs.click(sb_id, 500, 300)
  cs.type_text(sb_id, "hello world")
  cs.destroy(sb_id)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

STATE_FILE = os.path.join(C.AGENT_OS_DIR, "computer_sandboxes.json")
DEFAULT_TTL_MINUTES = 30  # يُدمَّر تلقائياً لو نُسي — حماية من فاتورة منسية


def _client():
    """عميل Daytona — يرفع استثناءً واضحاً لو المفتاح غايب، لا فشل صامت."""
    from daytona import Daytona, DaytonaConfig
    key = os.getenv("DAYTONA_API_KEY")
    if not key:
        raise RuntimeError("DAYTONA_API_KEY غير موجود بـ.env — سجّل بـdaytona.io وأضفه")
    return Daytona(DaytonaConfig(api_key=key))


def _load_state():
    return C.load_json(STATE_FILE, {"sandboxes": {}})


def _save_state(s):
    C.atomic_write(STATE_FILE, s)


def create(label="agent-os", ttl_minutes=DEFAULT_TTL_MINUTES):
    """ينشئ sandbox جديد معزول، يسجّله كمصروف، ويرجع معرّفه."""
    from daytona import CreateSandboxBaseParams

    daytona = _client()
    sandbox = daytona.create(
        CreateSandboxBaseParams(
            name=f"{label}-{C.now_iso()[:19].replace(':', '-')}",
            ttl_minutes=ttl_minutes,
            auto_stop_interval=ttl_minutes,
        )
    )
    state = _load_state()
    state["sandboxes"][sandbox.id] = {
        "created": C.now_iso(),
        "label": label,
        "ttl_minutes": ttl_minutes,
        "destroyed": False,
    }
    _save_state(state)

    try:
        from agent_os import finance_intel
        finance_intel.record_expense(f"daytona sandbox: {label}", 0.0, is_free_provider=False)
    except Exception:
        pass

    try:
        # لازم قبل أي screenshot/click/type — تشغّل Xvfb/xfce4/x11vnc داخل
        # الـsandbox، وإلا رجعت "empty display string" من الـdaemon.
        started = sandbox.computer_use.start()
        C.log(f"🖥️ سطح المكتب شغّال: {getattr(started, 'message', started)}")
    except Exception as e:
        C.log(f"⚠️ فشل تشغيل سطح المكتب (run_bash ما زال يعمل، لكن screenshot/click لا): {e}")

    C.log(f"🖥️ sandbox جديد: {sandbox.id} (TTL {ttl_minutes} دقيقة)")
    return sandbox.id


def _get_sandbox(sandbox_id):
    daytona = _client()
    return daytona.get(sandbox_id)


def run_bash(sandbox_id, command, timeout=60):
    """ينفّذ أمر bash داخل الـsandbox المعزول فقط — أبداً على جهاز المستخدم."""
    sandbox = _get_sandbox(sandbox_id)
    result = sandbox.process.exec(command, timeout=timeout)
    return {"exit_code": result.exit_code, "output": result.result}


def screenshot(sandbox_id):
    """لقطة شاشة كاملة من داخل الـsandbox — bytes لصورة PNG."""
    import base64
    sandbox = _get_sandbox(sandbox_id)
    resp = sandbox.computer_use.screenshot.take_full_screen()
    if resp and resp.screenshot:
        return base64.b64decode(resp.screenshot)
    return None


def click(sandbox_id, x, y):
    sandbox = _get_sandbox(sandbox_id)
    return sandbox.computer_use.mouse.click(x, y)


def type_text(sandbox_id, text):
    sandbox = _get_sandbox(sandbox_id)
    return sandbox.computer_use.keyboard.type(text)


def press_key(sandbox_id, key):
    sandbox = _get_sandbox(sandbox_id)
    return sandbox.computer_use.keyboard.press(key)


def preview_url(sandbox_id):
    """رابط معاينة موقّع — لو المستخدم يبي يشوف/يتحكم مباشرة."""
    sandbox = _get_sandbox(sandbox_id)
    return sandbox.get_preview_link()


def destroy(sandbox_id):
    """يدمّر الـsandbox صراحة — يوقف أي فاتورة إضافية فوراً."""
    sandbox = _get_sandbox(sandbox_id)
    sandbox.delete()
    state = _load_state()
    if sandbox_id in state["sandboxes"]:
        state["sandboxes"][sandbox_id]["destroyed"] = True
        state["sandboxes"][sandbox_id]["destroyed_at"] = C.now_iso()
        _save_state(state)
    C.log(f"🗑️ sandbox دُمِّر: {sandbox_id}")


def active_sandboxes():
    """قائمة sandboxes المسجّلة محلياً وغير مُدمَّرة بعد (قد تكون منتهية TTL فعلياً بجهة Daytona)."""
    state = _load_state()
    return {k: v for k, v in state["sandboxes"].items() if not v.get("destroyed")}


if __name__ == "__main__":
    import json
    print(json.dumps(active_sandboxes(), ensure_ascii=False, indent=2))
