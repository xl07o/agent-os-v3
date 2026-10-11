"""
يد معزولة تماماً عن جهاز المستخدم — عبر Daytona. أي تجربة/أمر خطير
يحتاج "يشتغل على كمبيوتر حقيقي" يصير هنا، أبداً على الجهاز الفعلي.

نسخة مُصلَحة من agent_os/computer_sandbox.py القديم: ذاك ما كان يحمّل
.env بنفسه (كان يعتمد ضمنياً على أن brain.py استُورد قبله) — هنا
نحمّله دائماً بشكل مضمون عبر env.py.
"""

import base64
import io
import os
import tarfile
import time

from . import env  # noqa: F401 — يضمن تحميل .env قبل getenv

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_DIR = os.path.dirname(_PKG_DIR)
_STATE_DIR = os.path.join(_PKG_DIR, "data")
_STATE_FILE = os.path.join(_STATE_DIR, "sandboxes.json")
DEFAULT_TTL_MINUTES = 15  # TTL قصير عمداً — حماية من فاتورة منسية


def _client():
    from daytona import Daytona, DaytonaConfig

    key = os.getenv("DAYTONA_API_KEY")
    if not key:
        raise RuntimeError("DAYTONA_API_KEY غير موجود بـ.env")
    return Daytona(DaytonaConfig(api_key=key))


def _load_state() -> dict:
    import json

    if not os.path.exists(_STATE_FILE):
        return {"sandboxes": {}}
    with open(_STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(state: dict) -> None:
    import json

    os.makedirs(_STATE_DIR, exist_ok=True)
    tmp = _STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _STATE_FILE)


def create(label: str = "os4", ttl_minutes: int = DEFAULT_TTL_MINUTES, env_vars: dict | None = None) -> str:
    from daytona import CreateSandboxBaseParams

    daytona = _client()
    sandbox = daytona.create(
        CreateSandboxBaseParams(
            name=f"{label}-{int(time.time())}",
            ttl_minutes=ttl_minutes,
            auto_stop_interval=ttl_minutes,
            env_vars=env_vars,
        )
    )
    state = _load_state()
    state["sandboxes"][sandbox.id] = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "label": label,
        "destroyed": False,
    }
    _save_state(state)
    return sandbox.id


def run_bash(sandbox_id: str, command: str, timeout: int = 60) -> dict:
    daytona = _client()
    sandbox = daytona.get(sandbox_id)
    result = sandbox.process.exec(command, timeout=timeout)
    return {"exit_code": result.exit_code, "output": result.result}


_UPLOAD_CHUNK = 60_000


def upload_steps(tar_b64: str, remote_path: str) -> list[str]:
    """أوامر ترفع الحزمة على دفعات. أمر واحد فيه الحزمة كاملة يتعدّى حد
    لينكس لطول الوسيط الواحد (128KB) — وحزمة agent_os4 صارت أكبر منه.
    base64 ما فيه علامات تنصيص، فالتضمين داخل '...' آمن."""
    steps = [f"rm -f {remote_path}"]
    for i in range(0, len(tar_b64), _UPLOAD_CHUNK):
        steps.append(f"printf '%s' '{tar_b64[i:i + _UPLOAD_CHUNK]}' >> {remote_path}")
    return steps


def run_steps(sandbox_id: str, steps: list[str], timeout: int = 120) -> dict:
    """ينفّذ الأوامر بالترتيب ويوقف عند أول فشل — يرجّع نتيجة آخر أمر نفّذ."""
    result = {"exit_code": 0, "output": ""}
    for step in steps:
        result = run_bash(sandbox_id, step, timeout=timeout)
        if result["exit_code"] != 0:
            break
    return result


def destroy(sandbox_id: str) -> None:
    daytona = _client()
    sandbox = daytona.get(sandbox_id)
    sandbox.delete()
    state = _load_state()
    if sandbox_id in state["sandboxes"]:
        state["sandboxes"][sandbox_id]["destroyed"] = True
        _save_state(state)


def preview_url(sandbox_id: str, port: int, expires_in_seconds: int = 3600) -> dict:
    """رابط يُفتح مباشرة بالمتصفح بلا أي ترويسة خاصة (موقَّع، التوكن
    مضمَّن بالرابط نفسه) — يُستخدم لإعطاء المستخدم رابطاً ينسخه ويفتحه.
    الافتراضي بمكتبة Daytona نفسها 60 ثانية فقط لو ما حدّدت المدة — هنا
    دائماً نحدّدها صراحة (ساعة افتراضياً) لنتفادى رابط ميت بسرعة."""
    daytona = _client()
    sandbox = daytona.get(sandbox_id)
    signed = sandbox.create_signed_preview_url(port, expires_in_seconds=expires_in_seconds)
    return {"url": signed.url, "expires_in_seconds": expires_in_seconds}


def build_package_tarball_b64(overrides: dict[str, str] | None = None) -> str:
    """يحزم agent_os4 كاملة + obsidian_vault.py بصيغة tar.gz بترميز
    base64 — لرفعها لساندبوكس Daytona (اختبار self_improve أو نشر
    web_chat). overrides: اسم ملف -> محتوى بديل، لاختبار تعديل مقترَح
    قبل تطبيقه فعلياً على القرص الحقيقي."""
    overrides = overrides or {}
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        vault_path = os.path.join(_REPO_DIR, "obsidian_vault.py")
        if os.path.exists(vault_path):
            tar.add(vault_path, arcname="obsidian_vault.py")
        for name in sorted(os.listdir(_PKG_DIR)):
            if not name.endswith(".py"):
                continue
            if name in overrides:
                data = overrides[name].encode("utf-8")
                info = tarfile.TarInfo(name=f"agent_os4/{name}")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            else:
                tar.add(os.path.join(_PKG_DIR, name), arcname=f"agent_os4/{name}")
    return base64.b64encode(buf.getvalue()).decode("ascii")
