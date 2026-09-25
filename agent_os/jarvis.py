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

    # حارس الضجيج: أمر قصير/غير مفهوم (مثل «ش») لا يُنفَّذ كمهمة — نطلب التوضيح
    # بدل تصنيفه خطأً (البند 5: لا نتظاهر بتنفيذ ما لم نفهمه).
    if cmd is None:
        import re as _re
        letters = _re.findall(r"[A-Za-z؀-ۿ]", text)
        # نحجب فقط ما لا يحمل حروفاً إطلاقاً (رموز/ضجيج)؛ التحيات القصيرة مثل
        # «hi» و«مرحبا» تذهب للدردشة الطبيعية لا لرسالة «ما فهمت».
        if len(letters) == 0:
            reply = "ما فهمت — اكتب أمراً أو سؤالاً واضحاً، مثل «حالة» أو «سجّل هدف بناء متجر»."
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

    # تحاوري أم مهمة؟ لو ما فيه فعل تنفيذي واضح → دردشة طبيعية (شات + وكيل).
    if not _is_task(text):
        return _chat(text), {"chat": True}

    # مهمة عامة عبر النواة — بردّ صادق يعكس ما حصل فعلاً (لا «أنجزت» عامة).
    from agent_os import agent_os as A
    res = A.run_task(text)
    return _task_reply(res), res


# وصف صادق ومختصر لكل قصد (ماذا فعل فعلاً، لا «أنجزت المهمة»).
_INTENT_DONE = {
    "operate": "سجّلت الهدف في قائمة المهام",
    "finance": "حسبت الجدوى المالية",
    "research": "جمعت النتائج",
    "report": "جهّزت التقرير",
    "security": "فحصت النطاق المصرّح",
    "learn": "تعلّمت وخزّنت المعرفة",
    "improve": "شغّلت دورة تحسين ذاتي",
}


def _task_reply(res):
    """جملة قصيرة صادقة: دليل ملموس إن وُجد، وإلا سبب صريح لعدم الاكتمال."""
    result = res.get("result", {})
    st = result.get("status", "?")
    intent = res.get("intent", "?")
    artifact = res.get("artifact")

    if artifact:
        import os as _os
        return f"جاهز ✅ — حفظت الملف: {_os.path.basename(str(artifact))}"
    if st == "verified":
        return (_INTENT_DONE.get(intent, "نفّذت الطلب")) + " ✅"
    if st == "needs_human":
        return "يحتاج موافقتك قبل المتابعة."
    # لم يكتمل: نُظهر السبب الحقيقي بدل «لم تكتمل» المبهمة (البند 5).
    issues = result.get("issues") or []
    why = issues[0] if issues else "ما قدرت أنتج مخرجاً حقيقياً — وضّح الطلب أكثر أو شغّل العقل."
    return f"ما أكملت ⚠️ — {why[:120]}"


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
    persona = ("أنت جارفيس. جاوب بإيجاز شديد: جملة إلى جملتين كحد أقصى، مباشرة، "
               "بلغة المستخدم (عربي/إنجليزي). ممنوع المقدمات والحشو والتكرار وسرد ما لم يُطلب. "
               "لو لا تعرف، قل «لا أعرف». لو طُلبت مهمة تنفيذية، اقترح الأمر المناسب بسطر واحد.")
    prompt = (f"سياق:\n{ctx}\n\n" if ctx else "") + f"المستخدم: {text}\nجارفيس (بإيجاز):"
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
    return ("أنا معك — لكن للدردشة أحتاج تشغيل العقل (Ollama). "
            "أو جرّب «حالة» أو «سجّل هدف بناء متجر».")


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
