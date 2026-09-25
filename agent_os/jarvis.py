"""
jarvis.py - واجهة Agent OS التفاعلية على نمط نظام تشغيل (البنود 3/11/13/14/17)
=============================================================================
سطح تحكّم واحد تتكلّم معه بالعربية أو الإنجليزية: يوجّه أوامرك للنواة، يتذكّر
محادثتنا، يستخلص أولوياتك، يتعلّم، يستشير Hermes، وينطق ردّه اختيارياً.

تشغيل تفاعلي:   python -m agent_os.jarvis
سطر واحد:       python -m agent_os.jarvis "سجّل هدف بناء متجر"

أوامر النظام (بالعربية أو الإنجليزية):
  حالة/status · ذاكرة/memory · أولويات/priorities · تعلّم/learn <س>
  اسأل/ask <س> · سكون/idle · صوت/voice on|off · مساعدة/help · خروج/exit
كل ما عدا ذلك = مهمة تُنفَّذ عبر النواة. يُسجَّل كل دور في ذاكرة المحادثة.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

HELP = (
    "أوامر JARVIS: حالة | ذاكرة | أولويات | تعلّم <موضوع> | اسأل <سؤال> | "
    "سكون | صوت on|off | مساعدة | خروج — وأي جملة أخرى تُنفَّذ كمهمة."
)

_STATE = {"voice": False}

# مرادفات الأوامر (عربي/إنجليزي) → مفتاح موحّد.
_CMD = {
    "حالة": "status", "status": "status",
    "ذاكرة": "memory", "memory": "memory",
    "أولويات": "priorities", "اولويات": "priorities", "priorities": "priorities",
    "مساعدة": "help", "help": "help", "؟": "help",
    "خروج": "exit", "خروج!": "exit", "exit": "exit", "quit": "exit",
    "سكون": "idle", "idle": "idle",
}


def _first_word(text):
    return (text or "").strip().split(maxsplit=1)


def handle(text):
    """يعالج جملة واحدة ويعيد {kind, reply, data}. قابل للاختبار بلا تفاعل."""
    text = (text or "").strip()
    if not text:
        return {"kind": "noop", "reply": "…", "data": None}

    parts = _first_word(text)
    head = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    cmd = _CMD.get(head)
    if head in ("تعلّم", "تعلم", "learn") and rest:
        cmd = "learn"
    elif head in ("اسأل", "اسال", "ask") and rest:
        cmd = "ask"
    elif head in ("صوت", "voice"):
        cmd = "voice"

    reply, data = _dispatch(cmd, text, rest)

    # سجّل الدور في ذاكرة المحادثة (يغذّي الأولويات — البند 11).
    try:
        from agent_os.memory import conversation
        conversation.record_turn(text, reply, intent=cmd or "task")
    except Exception:
        pass

    # نُطق اختياري.
    if _STATE["voice"] and cmd not in ("exit", "help"):
        try:
            from agent_os.voice import tts
            tts.speak(reply)
        except Exception:
            pass

    return {"kind": cmd or "task", "reply": reply, "data": data}


def _dispatch(cmd, text, rest):
    if cmd == "help":
        return HELP, None
    if cmd == "exit":
        return "إلى اللقاء.", None
    if cmd == "status":
        from agent_os import ultra
        d = ultra.cmd_status(None)
        prov = d.get("brain_providers_available")
        ready_voice = d.get("voice", {}).get("ready")
        return (f"العقل: {prov or 'لا مزوّد'} · الصوت جاهز: {ready_voice} · "
                f"معرفة مخزّنة: {d.get('memory', {}).get('knowledge_items')}"), d
    if cmd == "memory":
        from agent_os import ultra
        d = ultra.cmd_memory(None)
        return (f"معرفة: {d.get('knowledge_items')} · تجارب: {d.get('experiences')} · "
                f"تعارضات معلّقة: {d.get('disputes_pending')}"), d
    if cmd == "priorities":
        from agent_os.memory import conversation
        pr = conversation.priorities(5)
        if not pr:
            return "لا أولويات بعد — تحدّث معي أكثر لأتعلّم ما يهمّك.", pr
        return "أولوياتك الحالية: " + "، ".join(p["topic"] for p in pr), pr
    if cmd == "learn":
        from agent_os.learn import ingest
        d = ingest.learn_query(rest)
        return (f"تعلّمت من {len(d.get('ingested', []))} مصدر عن «{rest}»." if d.get("ok")
                else f"تعذّر التعلّم عن «{rest}» ({'لا شبكة/نتائج'})."), d
    if cmd == "ask":
        from agent_os import hermes
        d = hermes.get().ask(rest)
        return (d.get("text") if d.get("ok") else f"لا أعرف الآن ({d.get('reason')})."), d
    if cmd == "idle":
        from agent_os.learn import idle_learner
        from agent_os.memory import conversation
        goals = [p["topic"] for p in conversation.priorities(3)] or None
        d = idle_learner.idle_learn_cycle(owner_goals=goals)
        return f"دورة سكون: تعلّمت {d.get('learned_count')} موضوعاً.", d
    if cmd == "voice":
        want = "on" if "on" in text.lower() or "شغّل" in text or "شغل" in text else "off"
        _STATE["voice"] = (want == "on")
        return f"الصوت الآن: {'مُفعّل' if _STATE['voice'] else 'مُطفأ'}.", {"voice": _STATE["voice"]}

    # مهمة عامة عبر النواة.
    from agent_os import agent_os as A
    res = A.run_task(text)
    st = res.get("result", {}).get("status", "?")
    verb = {"verified": "أُنجزت", "needs_human": "تحتاج موافقتك", }.get(st, "لم تكتمل بعد")
    return f"المهمة ({res.get('intent')}) {verb}.", res


def repl():
    """حلقة تفاعلية حيّة."""
    from agent_os import ultra
    print("🤖 JARVIS — Agent OS v3. اكتب «مساعدة» للأوامر، «خروج» للإنهاء.")
    print(handle("status")["reply"])
    while True:
        try:
            line = input("\nأنت › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nإلى اللقاء.")
            break
        if not line:
            continue
        out = handle(line)
        print(f"JARVIS › {out['reply']}")
        if out["kind"] == "exit":
            break


if __name__ == "__main__":
    if len(sys.argv) > 1:
        import json
        print(json.dumps(handle(" ".join(sys.argv[1:])), ensure_ascii=False, indent=2, default=str))
    else:
        repl()
