"""
اختبار سلوكي سريع — يشتغل داخل ساندبوكس self_improve قبل ما يوصلك أي
تعديل كود. مو بس "الكود يستورد بدون خطأ": يتأكد أن الحواجز الأساسية
لسا شغالة فعلياً. أي تعديل يكسر واحد منها = فشل بالساندبوكس = ما يوصلك
طلب موافقة أصلاً.

بدون إنترنت وبدون Claude (brain.ask محاكى هنا)، وبمجلد بيانات مؤقت —
ما يلمس بياناتك الحقيقية. تشغيل: python3 -m agent_os4.selftest
"""

import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from unittest import mock


def _isolate(tmp: str) -> None:
    import obsidian_vault

    from . import agent_memory, agent_skills, approval, sessions, bots, ceo, decision, kernel, memory, obsidian, rooms, spend, tools, widgets
    approval._FILE = os.path.join(tmp, "approvals.json")
    decision._LEDGER_FILE = os.path.join(tmp, "ledger.json")
    kernel._PENDING_FILE = os.path.join(tmp, "pending.json")
    memory._FILE = os.path.join(tmp, "memory.json")
    rooms._ROOMS_FILE = os.path.join(tmp, "rooms.json")
    bots._EMPLOYEES_FILE = os.path.join(tmp, "employees.json")
    ceo._PENDING_FILE = os.path.join(tmp, "ceo_pending.json")
    spend._FILE = os.path.join(tmp, "spend.json")
    widgets._FILE = os.path.join(tmp, "widgets.json")
    agent_memory._DIR = os.path.join(tmp, "agent_memory")
    sessions._DB = os.path.join(tmp, "sessions.db")
    agent_skills._DIR = os.path.join(tmp, "agent_skills")
    tools.WORKSPACE = os.path.join(tmp, "workspace")
    obsidian_vault.VAULT_DIR = os.path.join(tmp, "vault")
    obsidian.VAULT_DIR = os.path.join(tmp, "vault")


def _checks(tmp: str) -> list[tuple[str, bool]]:
    from . import bots, kernel, safety, spend, web, web_chat
    results = []

    critical = {"write_file", "run_command", "sandbox_create", "sandbox_bash",
                "pc_read_file", "pc_write_file", "pc_list_dir", "pc_run_command"}
    results.append(("الأدوات الخطرة كلها تحتاج موافقة", critical <= kernel.NEEDS_APPROVAL))

    plan = '{"steps": [{"tool": "write_file", "args": {"path": "x.txt", "content": "y"}, "why": "t"}]}'
    with mock.patch("agent_os4.brain.ask", return_value=plan):
        out = kernel.run_task("اكتب ملف", interactive=False)
    written = os.path.exists(os.path.join(tmp, "workspace", "x.txt"))
    results.append(("كتابة ملف تتوقف عند الموافقة وما تتنفذ", "pending_request_id" in out and not written))

    for tool in ("run_command", "pc_run_command", "pc_write_file"):
        _, error = bots.validate_hire({"key": "x_bot", "title_ar": "x", "directorate": "research",
                                       "persona": "x", "allowed_tools": [tool]})
        results.append((f"موظف جديد ما يقدر ياخذ {tool}", error is not None))
    host_tools = {"run_command", "pc_read_file", "pc_write_file", "pc_list_dir", "pc_run_command"}
    results.append(("ما فيه موظف عنده أدوات جهازك",
                    all(not host_tools & set(b["allowed_tools"]) for b in bots.BOTS.values())))

    results.append(("أوامر الجهاز الخطرة ممنوعة", not safety.is_safe_pc_command("rm -rf /")[0]))
    with mock.patch.dict(os.environ):
        os.environ.pop("OS4_ALLOW_PC_ACCESS", None)
        results.append(("وصول الجهاز معطّل افتراضياً", not safety.pc_access_enabled()))
    for url in ("http://127.0.0.1/", "http://169.254.169.254/", "file:///etc/passwd"):
        results.append((f"بحث الويب يرفض {url}", not web.check_url(url)[0]))

    spend.set_budget(0)
    try:
        spend.reserve("claude-opus-5-5", "x", 16000)
        blocked = False
    except spend.BudgetExceeded:
        blocked = True
    results.append(("سقف الصرف يمنع الاستدعاء", blocked))

    server = web_chat.ThreadingHTTPServer(("127.0.0.1", 0), web_chat.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]

    def status_of(ctype: str, origin: str | None = None) -> int:
        headers = {"Content-Type": ctype}
        if origin:
            headers["Origin"] = origin
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/dashboard/budget",
                                     data=json.dumps({"amount": 999}).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    urllib.request.install_opener(opener)
    results.append(("حماية CSRF: text/plain مرفوض", status_of("text/plain") == 415))
    results.append(("حماية CSRF: موقع ثاني مرفوض", status_of("application/json", "http://evil.example") == 403))
    server.shutdown()
    results.append(("السقف ما تغيّر من طلب مرفوض", spend.budget_usd() == 0))
    return results


def main() -> int:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with tempfile.TemporaryDirectory() as tmp:
        _isolate(tmp)
        results = _checks(tmp)
    failed = [name for name, ok in results if not ok]
    for name, ok in results:
        print(("✓ " if ok else "✗ ") + name)
    if failed:
        print(f"SELFTEST_FAILED: {len(failed)}/{len(results)}")
        return 1
    print(f"SELFTEST_OK ({len(results)} فحص)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
