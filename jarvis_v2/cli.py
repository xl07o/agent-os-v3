# -*- coding: utf-8 -*-
"""واجهة أمر جارفيس v2 — سطر الأوامر مثل opencode: ترى كل تنفيذ حي، وتعتمد على سؤال قبل الخطير.
الاستخدام:
    python jarvis_v2/cli.py "مهمة" --autorun allow   # مهمة واحدة ثم خروج
    python jarvis_v2/cli.py --autorun ask            # جلسة حوارية"""
import os
import sys

try:
    from . import config, evidence, orchestrator
except ImportError:  # تشغيل مباشر بدون حزمة
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from jarvis_v2 import config, evidence, orchestrator


def _approver(name, args):
    """خط يشبه opencode: لكل أمر/كتابة يقرر المستخدم. read-only تنفذ تلقائياً."""
    if config.AUTORUN == "allow":
        return True
    if config.AUTORUN == "deny":
        return False
    prompt = "\n⚡ إذن مطلوب لـ %s\n   المعاملات: %s\n[ت] تنفيذ / [ن] رفض / [س] تخطي: " % (
        name, config.short_args(args, 100))
    while True:
        try:
            a = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        if a in ("ت", "y", "yes", "نعم"):
            return True
        if a in ("ن", "n", "no", "لا"):
            return False
        if a in ("س", ""):
            return False


def _banner():
    print("=" * 64)
    print("jarvis_v2 — نسخة مني الحقيقية (أدوات حقيقية + بوابة صدق)")
    print("الأوامر: /help  /evidence  /reset  /mode  /quit")
    print("الوضع الحالي: %s" % config.MODEL_MODE)
    print("=" * 64)


def _show_evidence(limit=12):
    rows = evidence.load()
    if not rows:
        print("لا سجل بعد.")
        return
    for r in rows[-limit:]:
        print("  [%s][%s] %s %s" % (r.get("ts", "?"), r.get("status"), r.get("tool"),
                                    (r.get("note") or "")[:70]))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # تحليل --autorun
    for flag in ("ask", "allow", "deny"):
        if ("--autorun=%s" % flag) in argv:
            config.AUTORUN = flag
            argv.remove("--autorun=%s" % flag)
    task = " ".join(a for a in argv if not a.startswith("--"))

    if task:
        config.AUTORUN = "ask" if config.AUTORUN == "ask" else config.AUTORUN
        oc = orchestrator.Orchestrator(approver=_approver)
        oc.run(task)
        return

    _banner()
    oc = orchestrator.Orchestrator(approver=_approver)
    while True:
        try:
            raw = input("\nأنت> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nوداعاً.")
            break
        if not raw:
            continue
        if raw in ("/quit", "/exit"):
            print("وصل.")
            break
        if raw == "/help":
            print("افعل ما يلي: اكتب مهمة بلغتك، وسيريها العمليات الحقيقية أولا بأول.")
            continue
        if raw == "/evidence":
            _show_evidence()
            continue
        if raw == "/reset":
            if oc.brain:
                oc.brain.reset()
                print("ذاكرة العقل أُفرغت.")
            continue
        if raw == "/mode":
            print("وضع العقل: %s" % config.MODEL_MODE)
            continue
        oc.run(raw)


if __name__ == "__main__":
    main()