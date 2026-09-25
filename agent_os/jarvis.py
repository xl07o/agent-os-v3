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

# لغة الردود: en (افتراضي) أو ar — تُضبط بـ JARVIS_LANG.
LANG = os.getenv("JARVIS_LANG", "en").lower()


def _L(en, ar):
    """يختار نص الرد حسب اللغة المضبوطة."""
    return en if LANG.startswith("en") else ar


HELP = _L(
    "JARVIS commands: status | memory | priorities | learn <topic> | ask <q> | "
    "idle | voice on|off | help | exit — anything else is chat or a task.",
    "أوامر JARVIS: حالة | ذاكرة | أولويات | تعلّم <موضوع> | اسأل <سؤال> | "
    "سكون | صوت on|off | مساعدة | خروج — وأي جملة أخرى دردشة أو مهمة.",
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

    # حارس الضجيج: أمر قصير/غير مفهوم (مثل «ش») لا يُنفَّذ كمهمة — نطلب التوضيح
    # بدل تصنيفه خطأً (البند 5: لا نتظاهر بتنفيذ ما لم نفهمه).
    if cmd is None:
        import re as _re
        letters = _re.findall(r"[A-Za-z؀-ۿ]", text)
        # نحجب فقط ما لا يحمل حروفاً إطلاقاً (رموز/ضجيج)؛ التحيات القصيرة مثل
        # «hi» و«مرحبا» تذهب للدردشة الطبيعية لا لرسالة «ما فهمت».
        if len(letters) == 0:
            reply = _L("I didn't catch that — type a clear question or command, e.g. 'status'.",
                       "ما فهمت — اكتب أمراً أو سؤالاً واضحاً، مثل «حالة».")
            try:
                from agent_os.memory import conversation
                conversation.record_turn(text, reply, intent="unclear")
            except Exception:
                pass
            if _STATE["voice"]:
                try:
                    from agent_os.voice import tts
                    tts.speak(reply)
                except Exception:
                    pass
            return {"kind": "unclear", "reply": reply, "data": None}

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
        prov = d.get("brain_providers_available") or _L("none", "لا مزوّد")
        rv = d.get("voice", {}).get("ready")
        km = d.get("memory", {}).get("knowledge_items")
        return _L(f"Brain: {prov} · voice ready: {rv} · knowledge: {km}",
                  f"العقل: {prov} · الصوت جاهز: {rv} · معرفة: {km}"), d
    if cmd == "memory":
        from agent_os import ultra
        d = ultra.cmd_memory(None)
        return _L(f"Knowledge: {d.get('knowledge_items')} · experiences: {d.get('experiences')} "
                  f"· open conflicts: {d.get('disputes_pending')}",
                  f"معرفة: {d.get('knowledge_items')} · تجارب: {d.get('experiences')} "
                  f"· تعارضات: {d.get('disputes_pending')}"), d
    if cmd == "priorities":
        from agent_os.memory import conversation
        pr = conversation.priorities(5)
        if not pr:
            return _L("No priorities yet — talk to me more so I learn what matters.",
                      "لا أولويات بعد — تحدّث معي أكثر."), pr
        return _L("Your priorities: ", "أولوياتك: ") + ", ".join(p["topic"] for p in pr), pr
    if cmd == "learn":
        from agent_os.learn import ingest
        d = ingest.learn_query(rest)
        return (_L(f"Learned from {len(d.get('ingested', []))} sources about '{rest}'.",
                   f"تعلّمت من {len(d.get('ingested', []))} مصدر عن «{rest}».") if d.get("ok")
                else _L(f"Couldn't learn about '{rest}' (no network/results).",
                        f"تعذّر التعلّم عن «{rest}».")), d
    if cmd == "ask":
        from agent_os import hermes
        d = hermes.get().ask(rest)
        return (_trim(d.get("text")) if d.get("ok")
                else _L(f"I don't know right now ({d.get('reason')}).",
                        f"لا أعرف الآن ({d.get('reason')}).")), d
    if cmd == "idle":
        from agent_os.learn import idle_learner
        from agent_os.memory import conversation
        goals = [p["topic"] for p in conversation.priorities(3)] or None
        d = idle_learner.idle_learn_cycle(owner_goals=goals)
        return _L(f"Idle cycle: learned {d.get('learned_count')} topics.",
                  f"دورة سكون: تعلّمت {d.get('learned_count')} موضوعاً."), d
    if cmd == "voice":
        want = "on" if "on" in text.lower() or "شغّل" in text or "شغل" in text else "off"
        _STATE["voice"] = (want == "on")
        return _L(f"Voice is now {'on' if _STATE['voice'] else 'off'}.",
                  f"الصوت الآن: {'مُفعّل' if _STATE['voice'] else 'مُطفأ'}."), {"voice": _STATE["voice"]}

    # تحاوري أم مهمة؟ لو ما فيه فعل تنفيذي واضح → دردشة طبيعية (شات + وكيل).
    if not _is_task(text):
        return _chat(text), {"chat": True}

    # مهمة عامة عبر النواة — بردّ صادق يعكس ما حصل فعلاً (لا «أنجزت» عامة).
    from agent_os import agent_os as A
    res = A.run_task(text)
    return _task_reply(res), res


# وصف صادق ومختصر لكل قصد (ماذا فعل فعلاً، لا «أنجزت المهمة»).
_INTENT_DONE = {
    "operate": _L("saved the goal to your task list", "سجّلت الهدف في قائمة المهام"),
    "finance": _L("computed the financial feasibility", "حسبت الجدوى المالية"),
    "research": _L("gathered the results", "جمعت النتائج"),
    "report": _L("prepared the report", "جهّزت التقرير"),
    "security": _L("checked the authorized scope", "فحصت النطاق المصرّح"),
    "learn": _L("learned and stored the knowledge", "تعلّمت وخزّنت المعرفة"),
    "improve": _L("ran one self-improvement cycle", "شغّلت دورة تحسين ذاتي"),
}


def _task_reply(res):
    """جملة قصيرة صادقة: دليل ملموس إن وُجد، وإلا سبب صريح لعدم الاكتمال."""
    result = res.get("result", {})
    st = result.get("status", "?")
    intent = res.get("intent", "?")
    artifact = res.get("artifact")

    if artifact:
        import os as _os
        return _L(f"Done ✅ — saved file: {_os.path.basename(str(artifact))}",
                  f"جاهز ✅ — حفظت الملف: {_os.path.basename(str(artifact))}")
    if st == "verified":
        return _INTENT_DONE.get(intent, _L("did it", "نفّذت الطلب")) + " ✅"
    if st == "needs_human":
        return _L("Needs your approval before continuing.", "يحتاج موافقتك قبل المتابعة.")
    issues = result.get("issues") or []
    why = issues[0] if issues else _L("couldn't produce a real output — be more specific or start the brain.",
                                      "ما قدرت أنتج مخرجاً حقيقياً — وضّح الطلب أو شغّل العقل.")
    return _L(f"Not done ⚠️ — {why[:120]}", f"ما أكملت ⚠️ — {why[:120]}")


# أفعال تنفيذية واضحة → مهمة؛ ما عداها → دردشة.
_ACTION_HINTS = (
    "سجّل", "سجل", "ابن", "ابنِ", "اكتب", "نفّذ", "نفذ", "افتح", "شغّل", "شغل",
    "حمّل", "حمل", "ثبّت", "ثبت", "ابحث", "سوّ", "سو ", "سوي", "اعمل", "أنشئ", "انشئ",
    "طوّر", "طور", "حسّن", "حسن", "قيّم", "قيم", "افحص", "راقب",
    "build", "make", "create", "open", "run", "write", "install", "search",
    "deploy", "fix", "generate", "بونتي", "ثغرة", "bounty",
)


def _is_task(text):
    """فعل تنفيذي واضح = مهمة. مطابقة على مستوى الكلمة حتى لا يُخلط «تسوي»
    (سؤال) بـ «سوّ» (أمر)."""
    low = (text or "").lower()
    words = low.replace("،", " ").replace("؟", " ").split()
    for h in (x.strip() for x in _ACTION_HINTS if x.strip()):
        if h in words:                                   # كلمة مطابقة تماماً
            return True
        if len(h) >= 4 and any(w.startswith(h) for w in words):  # بادئة فعل
            return True
        if len(h) >= 5 and h in low:                     # كلمة إنجليزية مميّزة
            return True
    return False


def _chat(text):
    """دردشة طبيعية عبر العقل (Hermes الحقيقي أولاً ثم brain/Ollama) مع سياق
    من المحادثة — شات حقيقي، لا «أنجزت المهمة». بلا عقل: يخبر بصدق."""
    ctx = ""
    try:
        from agent_os.memory import conversation
        recent = [t for t in conversation.recent(6) if t.get("user")]
        ctx = "\n".join(f"المستخدم: {t['user']}\nجارفيس: {t.get('reply', '')}" for t in recent[-4:])
    except Exception:
        pass
    persona = _L(
        "You are JARVIS, a sharp assistant. Reply in English, very concisely: "
        "one or two sentences max, direct, no preamble or filler or repetition. "
        "If you don't know, say 'I don't know'. If an actionable task is asked, "
        "suggest the exact command in one line.",
        "أنت جارفيس، مساعد ذكي. جاوب بإيجاز شديد: جملة إلى جملتين، بلا حشو. "
        "لو لا تعرف قل «لا أعرف». لو طُلبت مهمة، اقترح الأمر المناسب بسطر.")
    prompt = (f"Context:\n{ctx}\n\n" if ctx else "") + f"User: {text}\nJARVIS (brief):"
    # Hermes حقيقي أولاً
    try:
        from agent_os import hermes_client
        if hermes_client.available():
            r = hermes_client.ask(f"{persona}\n\n{prompt}")
            if r.get("ok"):
                return _trim(r["text"])
    except Exception:
        pass
    # ثم العقل متعدد المزودين (Ollama إن كان مشغّلاً)
    raw, engine = C.call_brain(persona, prompt, mode="smart")
    if raw and engine not in (None, "", "none") and not raw.strip().startswith("("):
        return _trim(raw.strip())
    return _L("I'm here, but I need the brain running (Ollama) to chat. "
              "Try 'status' or 'set a goal to build a store'.",
              "أنا معك — لكن للدردشة أحتاج تشغيل العقل (Ollama). جرّب «حالة».")


def _trim(text, max_sentences=3, max_chars=400):
    """يقصّ ثرثرة العقل: أول جملتين-ثلاث، وبحدّ أقصى للطول (صوت-ودود)."""
    t = " ".join(str(text).split())
    import re as _re
    parts = _re.split(r"(?<=[.!؟?])\s+", t)
    out = " ".join(parts[:max_sentences]).strip()
    if len(out) > max_chars:
        out = out[:max_chars].rsplit(" ", 1)[0] + "…"
    return out or t[:max_chars]


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
