"""
يد معزولة تماماً عن جهاز المستخدم — عبر Daytona. أي تجربة/أمر خطير
يحتاج "يشتغل على كمبيوتر حقيقي" يصير هنا، أبداً على الجهاز الفعلي.

نسخة مُصلَحة من agent_os/computer_sandbox.py القديم: ذاك ما كان يحمّل
.env بنفسه (كان يعتمد ضمنياً على أن brain.py استُورد قبله) — هنا
نحمّله دائماً بشكل مضمون عبر env.py.
"""

import os
import time

from . import env  # noqa: F401 — يضمن تحميل .env قبل getenv

_STATE_DIR = os.path.join(os.path.dirname(__file__), "data")
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


def create(label: str = "os4", ttl_minutes: int = DEFAULT_TTL_MINUTES) -> str:
    from daytona import CreateSandboxBaseParams

    daytona = _client()
    sandbox = daytona.create(
        CreateSandboxBaseParams(
            name=f"{label}-{int(time.time())}",
            ttl_minutes=ttl_minutes,
            auto_stop_interval=ttl_minutes,
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


def destroy(sandbox_id: str) -> None:
    daytona = _client()
    sandbox = daytona.get(sandbox_id)
    sandbox.delete()
    state = _load_state()
    if sandbox_id in state["sandboxes"]:
        state["sandboxes"][sandbox_id]["destroyed"] = True
        _save_state(state)
