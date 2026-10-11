"""
نشر الشات على Daytona — "شات نسخ لصق" حقيقي بدل أوامر طرفية. هذا كان
الطلب الأصلي: تفتح رابطاً وتكتب، بلا تثبيت ولا طرفية على جهازك.

يرفع حزمة agent_os4 كاملة (sandbox.build_package_tarball_b64، نفس
الآلية المُختبرة أصلاً بـself_improve.py) لساندبوكس Daytona معزول،
يشغّل web_chat.py هناك، ويرجّع رابط معاينة موقَّع تفتحه بالمتصفح مباشرة.

مفاتيحك (.env المحلي على جهازك) تُمرَّر للساندبوكس عبر env_vars عند
الإنشاء (باراميتر Daytona SDK مخصص لهذا، لا تضمين بنص سكربت) — لا تُكشف
هنا أبداً، ولا أراها أنا.
"""

import os

from . import env, sandbox  # noqa: F401 — env يضمن تحميل .env المحلي

PORT = 8080

_PKG_REMOTE = "/root/os4pkg.b64"

_START_SCRIPT = """set -e
mkdir -p /root/app && cd /root/app
base64 -d /root/os4pkg.b64 | tar xz
pip install -q python-dotenv requests anthropic >/tmp/pip.log 2>&1 || true
cd /root/app
nohup python3 -m agent_os4.web_chat > /root/app/web_chat.log 2>&1 &
sleep 2
cat /root/app/web_chat.log 2>/dev/null || true
echo DEPLOY_READY
"""

_KEYS_TO_FORWARD = ("ANTHROPIC_API_KEY",)


def deploy(expires_in_seconds: int = 3600) -> dict:
    """يرفع agent_os4 كاملة لساندبوكس Daytona جديد، يشغّل web_chat.py
    هناك، ويرجّع رابطاً تفتحه بالمتصفح مباشرة. فشل أي مرحلة يُرجَع
    بصدق — لا رابط مزيّف لساندبوكس لم يشتغل فعلاً."""
    env_vars = {k: v for k in _KEYS_TO_FORWARD if (v := os.getenv(k))}
    if "ANTHROPIC_API_KEY" not in env_vars:
        return {"ok": False, "stage": "preflight", "error": "لا يوجد ANTHROPIC_API_KEY بـ.env — الشات بلا مخ لن يرد على شي"}

    steps = sandbox.upload_steps(sandbox.build_package_tarball_b64(), _PKG_REMOTE) + [_START_SCRIPT]

    try:
        sb_id = sandbox.create(label="os4-web-chat", ttl_minutes=120, env_vars=env_vars)
    except Exception as e:  # noqa: BLE001 — تعذّر الوصول لـDaytona نفسه = فشل واضح، لا تجاوز
        return {"ok": False, "stage": "create", "error": f"{type(e).__name__}: {e}"}

    try:
        result = sandbox.run_steps(sb_id, steps, timeout=90)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "stage": "start", "sandbox_id": sb_id, "error": f"{type(e).__name__}: {e}"}

    if result["exit_code"] != 0 or "DEPLOY_READY" not in str(result["output"]):
        return {"ok": False, "stage": "start", "sandbox_id": sb_id, "error": str(result["output"])[:2000]}

    try:
        link = sandbox.preview_url(sb_id, PORT, expires_in_seconds=expires_in_seconds)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "stage": "preview_url", "sandbox_id": sb_id, "error": f"{type(e).__name__}: {e}"}

    return {"ok": True, "sandbox_id": sb_id, "url": link["url"], "expires_in_seconds": link["expires_in_seconds"]}


def teardown(sandbox_id: str) -> dict:
    """يدمّر ساندبوكس الشات — نفس sandbox.destroy() الموجودة، غلاف
    بالاسم المناسب للسياق فقط."""
    try:
        sandbox.destroy(sandbox_id)
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
