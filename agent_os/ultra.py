"""
ultra.py - نقطة الدخول الموحّدة لـ Agent OS v3 (Ultra Agent)
============================================================
واجهة واحدة تجمع كل قدرات النظام في أوامر واضحة:

  python -m agent_os.ultra run   "<مهمة>"      # نفّذ مهمة عبر النواة
  python -m agent_os.ultra learn "<موضوع>"     # تعلّم من الويب واخزنه
  python -m agent_os.ultra ingest <url|owner/repo>  # استوعب مصدراً
  python -m agent_os.ultra idle  ["هدف" ...]   # تعلّم ذاتي وقت السكون
  python -m agent_os.ultra ask   "<سؤال>"      # اسأل المساعد Hermes
  python -m agent_os.ultra say   "<جملة>"      # نفّذ جملة عبر المسار الصوتي (نصياً)
  python -m agent_os.ultra memory                # لمحة الذاكرة
  python -m agent_os.ultra status                # جاهزية كل النظام (صدق تام)

كل أمر يرجع JSON، ويخبر بصدق بما ينقص (مزوّد عقل، شبكة، أدوات صوت) بلا تلفيق.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C


def cmd_run(args):
    from agent_os import agent_os as A
    return A.run_task(" ".join(args))


def cmd_learn(args):
    from agent_os.learn import ingest
    return ingest.learn_query(" ".join(args))


def cmd_ingest(args):
    from agent_os.learn import ingest
    src = args[0] if args else ""
    if src.startswith("http") and "youtube" not in src and "youtu.be" not in src:
        return ingest.ingest_url(src)
    if "youtube" in src or "youtu.be" in src:
        return ingest.ingest_youtube(src)
    if "/" in src and "." not in src.split("/")[0]:
        return ingest.ingest_github(src)
    return ingest.ingest_url(src)


def cmd_idle(args):
    from agent_os.learn import idle_learner
    return idle_learner.idle_learn_cycle(owner_goals=args or None)


def cmd_ask(args):
    from agent_os import hermes
    return hermes.get().ask(" ".join(args))


def cmd_say(args):
    from agent_os.voice import assistant
    return assistant.handle_utterance(" ".join(args))


def cmd_finance(args):
    """تحليل جدوى فرصة: finance "<الفكرة>" <إيراد شهري> [تكلفة] [أيام جهد]."""
    from agent_os import finance_brain
    nums, words = [], []
    for a in args:
        try:
            nums.append(float(a))
        except ValueError:
            words.append(a)
    idea = " ".join(words) or "فرصة"
    rev = nums[0] if len(nums) > 0 else 0
    cost = nums[1] if len(nums) > 1 else 0
    effort = nums[2] if len(nums) > 2 else 1
    return finance_brain.evaluate(idea, cost_usd=cost, monthly_revenue_usd=rev, effort_days=effort)


def cmd_memory(_args):
    out = {}
    try:
        from agent_os.memory import provenance, contextual_memory, strategy_memory, conflict_resolver
        out["knowledge_items"] = len(provenance._load().get("items", {}))
        out["experiences"] = len(contextual_memory._load().get("experiences", []))
        out["strategy"] = strategy_memory.stats()
        out["disputes_pending"] = len(conflict_resolver.disputed_items())
    except Exception as e:
        out["error"] = str(e)[:150]
    return out


def cmd_status(_args):
    """جاهزية شاملة صادقة: عقل، ذاكرة، تعلّم، صوت، مساعد."""
    st = {"data_dir": C.AGENT_OS_DIR}
    try:
        import brain
        st["brain_providers_available"] = [e["id"] for e in brain.available_engines()]
    except Exception as e:
        st["brain_providers_available"] = f"خطأ: {str(e)[:80]}"
    try:
        from agent_os.voice import assistant
        st["voice"] = assistant.status()
    except Exception as e:
        st["voice"] = f"خطأ: {str(e)[:80]}"
    st["memory"] = cmd_memory(None)
    st["notes"] = {
        "no_brain_provider": "شغّل Ollama محلياً أو ضع مفتاحاً في .env — النواة تعمل بلا عقل لكن جودة المحتوى تعتمد عليه",
        "voice": "ثبّت faster-whisper + piper + openwakeword على جهازك لتشغيل الصوت الحي",
    }
    return st


COMMANDS = {
    "run": cmd_run, "learn": cmd_learn, "ingest": cmd_ingest, "idle": cmd_idle,
    "ask": cmd_ask, "say": cmd_say, "memory": cmd_memory, "status": cmd_status,
    "finance": cmd_finance,
}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 0
    result = COMMANDS[argv[0]](argv[1:])
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
