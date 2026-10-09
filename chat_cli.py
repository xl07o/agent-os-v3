"""
chat_cli.py - محادثة مباشرة مع موظف الليل (v2.0)
================================================
دردشة من الطرفية مع:
  - سجل كامل
  - أوامر بناء سريعة
  - واجهة نظيفة
"""

import os
import sys
import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import brain
import memory_bank
import priority_manager
import specialists

_LOG_DIR = os.path.join(_HERE, "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "chat_history.txt")


def _ensure_log():
    os.makedirs(_LOG_DIR, exist_ok=True)


def _log(role, text):
    _ensure_log()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {role.upper()}: {text}\n")
    except Exception:
        pass


def _build_dashboard(text):
    """يبني شاشة/لوحة مخصّصة من وصف حر — «سوِّ لي شاشة فيها تداول يسار ودخل يمين
    ودراسات» يترجم لأقسام حقيقية عبر العقل (مع افتراضي آمن لو تعذّر)."""
    import builders
    sections = None
    try:
        import json as _json
        classifier = brain.Brain(
            "استخرج من طلب المستخدم أقسام شاشة/لوحة يريد بناءها. ردّ بصيغة JSON فقط "
            "بلا أي شرح أو نص إضافي، بالشكل التالي بالضبط:\n"
            '[{"title": "اسم القسم", "items": ["سطر محتوى 1", "سطر محتوى 2"]}]\n'
            "كل قسم 2-4 عناصر نصية قصيرة واقعية (مو فارغة، مو placeholder عام)."
        )
        out, engine = classifier.ask(text, mode="smart")
        if engine not in (None, "none"):
            cleaned = out.strip().strip("`")
            if cleaned[:4].lower() == "json":
                cleaned = cleaned[4:].strip()
            parsed = _json.loads(cleaned)
            if isinstance(parsed, list) and parsed:
                sections = parsed
    except Exception:
        sections = None

    if not sections:
        sections = [{"title": "القسم الرئيسي", "items": ["وصّف لي الأقسام اللي تبيها بالتفصيل أكثر"]}]

    paths = builders.make_dashboard_project("شاشتي", sections)
    return "بنيتُ لك الشاشة ✅: " + paths.get("dashboard", "")


def _build(text):
    """بناء مشروع فوري."""
    import builders
    tl = text.lower()
    try:
        if any(k in tl for k in ("لوحة", "شاشة", "dashboard", "dash")):
            return _build_dashboard(text)
        if "roblox" in tl or "لوا" in tl or "لعبة" in tl or "game" in tl:
            paths = builders.make_roblox_place("MyPlace")
            return "بنيتُ لك خريطة Roblox جاهزة ✅: " + paths.get("server_script", "")
        if "بايثون" in tl or "python" in tl or "برنامج" in tl or "app" in tl:
            paths = builders.make_python_project("MyApp")
            return "بنيتُ لك مشروع بايثون جاهز ✅: " + paths.get("project", "")
        if "موقع" in tl or "هبوط" in tl or "landing" in tl or "ويب" in tl or "web" in tl:
            paths = builders.make_web_project("MyLanding")
            return "بنيتُ لك موقع هبوط كامل ✅: " + paths.get("site", "")
        return "اختر نوع: //بناء موقع | //بناء بايثون | //بناء روبلوكس | //بناء لوحة <وصف>"
    except Exception as e:
        return "خطأ أثناء البناء: " + str(e)


def _trading(sub):
    """وكيل التداول ذاتي التحسين — //تداول شغل [N] | //تداول حالة | //تداول حي تفعيل | //تداول حي ايقاف"""
    try:
        from trading import strategy_agent, kill_switch, alpaca_client
    except Exception as e:
        return f"تعذّر تحميل trading/: {e}"

    parts = sub.split()
    cmd = parts[0] if parts else "حالة"

    if cmd in ("شغل", "run"):
        n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
        result = strategy_agent.run_self_improvement_cycle(iterations=n)
        if "error" in result:
            return result["error"]
        best = result["best"]
        label = strategy_agent.FACTOR_LABELS.get(best["spec"]["factor"], best["spec"]["factor"])
        demo_note = " (بيانات تجريبية — لا اتصال ببيانات حقيقية)" if result.get("used_demo_data") else ""
        return (f"شغّلت {n} تكرار{demo_note}. أفضل عامل حتى الآن: {label} — "
                f"شارپ صادق {best['honest_sharpe']} (مو {best['biased_sharpe']}، ذاك متحيّز).")

    if cmd in ("حالة", "status"):
        snap = strategy_agent.pipeline_snapshot()
        if not snap["has_run"]:
            return "ما شغّلت دورة تحسين بعد — جرب //تداول شغل"
        ks = "🛑 مفعّل" if snap["kill_switch_tripped"] else "✅ سليم"
        return (f"العامل الحالي: {snap['current_factor_label']} — شارپ صادق {snap['honest_sharpe']} "
                f"(متحيّز {snap['biased_sharpe']}) — {snap['iterations_total']} تكرار إجمالي — "
                f"قاطع الأمان: {ks} — وضع Alpaca: {alpaca_client.mode()}")

    if cmd == "حي" and len(parts) > 1 and parts[1] in ("تفعيل", "enable"):
        res = alpaca_client.set_live_mode(True, requested_by="chat_cli")
        return f"طلب تفعيل الوضع الحي أُرسل لبوابة الموافقة — راجعه عبر agent_os/approval_center.py list (#{res.get('approval_request_id', '؟')})"

    if cmd == "حي" and len(parts) > 1 and parts[1] in ("ايقاف", "إيقاف", "disable"):
        alpaca_client.set_live_mode(False)
        return "رجّعت الوضع إلى paper فوراً."

    return "الصيغة: //تداول شغل [عدد التكرارات] | //تداول حالة | //تداول حي تفعيل | //تداول حي ايقاف"


def _run_hermes(sub_task):
    """يحوّل مهمة لـ hermes agent (jarvis_v2) — المسار المشترك بين //hermes والتحويل التلقائي."""
    try:
        from jarvis_v2 import cli as hermes_cli
        hermes_cli.main([sub_task])
        return "انتهت جلسة hermes لهذه المهمة."
    except Exception as e:
        return f"تعذّر تشغيل hermes: {str(e)[:150]}"


def _wants_action(raw):
    """يسأل العقل تصنيفاً سريعاً ومنفصلاً (بلا تاريخ محادثة): هل هذه رسالة تنفيذ فعلي
    (أمر/مهمة: بناء، بحث عميق، أتمتة) أم سؤال/دردشة عامة؟ أي غموض أو فشل → False
    (نفس السلوك الحالي: دردشة)، فلا يغيّر هذا شيئاً عند غياب العقل."""
    try:
        classifier = brain.Brain(
            "صنّف رسالة المستخدم التالية بكلمة واحدة فقط بلا أي شرح:\n"
            "ACTION — إن كانت طلب تنفيذ مهمة فعلية (ابنِ/نفّذ/أتمتة/بحث عميق وتنفيذ).\n"
            "CHAT — إن كانت سؤالاً عاماً أو دردشة أو طلب معلومة بسيطة."
        )
        out, engine = classifier.ask(raw, mode="fastest")
        if engine in (None, "none"):
            return False
        return out.strip().upper().startswith("ACTION")
    except Exception:
        return False


def _ask(raw, b):
    """رد عبر العقل المحسّن مع استرجاع الذاكرة — جلسة واحد متصلة عبر b."""
    try:
        # استرجاع الذاكرة ذات الصلة وحقنها في متن السؤال (تظل المحادثة متصلة)
        memory_context = memory_bank.recall_as_context(raw)
        content = raw
        if memory_context:
            content = (
                "[خلفية من الذاكرة - قد لا تكون ذات صلة بكل سؤال]\n"
                + memory_context
                + "\n\nسؤال المستخدم:\n"
                + raw
            )

        out, engine = b.ask(content)
        answer = str(out).strip()

        # تحديث الذاكرة
        if len(answer) > 20:
            memory_bank.remember(
                raw[:100], answer,
                importance=0.6,
                tags=["chat", raw.lower()[:50]],
            )
        return answer
    except Exception as e:
        return f"تعذّر الرد: {e}"


def main():
    import mastery
    mastery.mark_user_active()  # أخبر محرك الإتقان أن المستخدم موجود
    try:
        _main_loop()
    finally:
        mastery.mark_user_away()


def _main_loop():
    engines = brain.available_engines()
    _ensure_log()
    print("=" * 54)
    print("   🌙 موظف الليل - محادثة مباشرة")
    print("   العقول:", ", ".join(e["id"] for e in engines) or "لا شيء")
    print("   أوامر: //بناء <نوع> | //hermes <مهمة> | //خبير <مجال>::<سؤال> | //تداول شغل|حالة | /سجل | exit | /تذكر <معلومة> | /أولويات")
    print("=" * 54)

    # جلسة عقل واحدة متصلة عبر المحادثة كلها (نفس التاريخ — لا بداية جديدة كل رسالة)
    brain_session = brain.Brain(
        "أنت موظف الليل - مساعد ذكي ودّي، رد مختصر مفيد بالعربية."
    )

    while True:
        try:
            raw = input("\nأنت > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nوداعاً! 🌙")
            break
        if not raw:
            continue

        _log("user", raw)
        low = raw.lower()

        if low in {"exit", "quit", "خروج", "قف", "وداعاً", "باي"}:
            print("وداعاً! 🌙")
            break

        if raw.startswith("//hermes") or raw.startswith("//هيرمس"):
            prefix = "//hermes" if raw.startswith("//hermes") else "//هيرمس"
            sub_task = raw[len(prefix):].strip()
            if not sub_task:
                reply = "اكتب المهمة بعد //hermes — مثال: //hermes ابحث عن أفضل مكتبة ضغط صور"
                print("الموظف >", reply)
                _log("bot", reply)
                continue
            print("   (🤝 أحوّل هذه المهمة لـ hermes agent — سيسألك هو بنفسه قبل أي خطوة فعلية)")
            reply = _run_hermes(sub_task)
            print("الموظف >", reply)
            _log("bot", reply)
            continue

        if raw.startswith("//خبير") or raw.startswith("//specialist"):
            prefix = "//خبير" if raw.startswith("//خبير") else "//specialist"
            rest = raw[len(prefix):].strip()
            if "::" not in rest:
                reply = "الصيغة: //خبير <اسم أو مجال> :: <سؤالك> — مثال: //خبير frontend :: كيف أحسّن سرعة الموقع؟"
                print("الموظف >", reply)
                _log("bot", reply)
                continue
            who, _, question = rest.partition("::")
            who, question = who.strip(), question.strip()
            result = specialists.ask(who, question)
            if result.get("ok"):
                reply = f"[{result['specialist']}] {result['answer']}"
            else:
                sugg = "، ".join(result.get("suggestions", [])) or "لا يوجد اقتراح قريب"
                reply = f"{result['error']}. أقرب خبراء متاحين: {sugg}"
            print("الموظف >", reply[:1500])
            _log("bot", reply)
            continue

        if raw.startswith("//بناء"):
            req = raw[len("//بناء"):].strip()
            reply = _build(req) if req else "اكتب نوع: موقع / بايثون / روبلوكس"
            print("الموظف >", reply)
            _log("bot", reply)
            continue

        if raw.startswith("//تداول") or raw.startswith("//trading"):
            prefix = "//تداول" if raw.startswith("//تداول") else "//trading"
            sub = raw[len(prefix):].strip()
            reply = _trading(sub)
            print("الموظف >", reply)
            _log("bot", reply)
            continue

        if low.startswith("/تذكر"):
            content = raw[len("/تذكر"):].strip()
            if content:
                result = memory_bank.remember(
                    content[:50], content,
                    importance=0.8,
                    tags=["user_fact"],
                )
                reply = f"حفظت هذه المعلومة في ذاكرتي ✅"
            else:
                reply = "اكتب المعلومة بعد /تذكر"
            print("الموظف >", reply)
            _log("bot", reply)
            continue

        if low.startswith("/نو"):
            query = raw[len("/نو"):].strip()
            if query:
                results = memory_bank.recall(query)
                if results:
                    reply = "أقرب ما أتذكره:\n" + "\n".join(
                        f"- **{r['key']}** (تشابه {r['score']}): {r['content'][:150]}"
                        for r in results[:3]
                    )
                else:
                    reply = "لا أجد شيئاً متعلقاً بهذا."
            else:
                reply = "اكتب ما تريد البحث عنه بعد /نو"
            print("الموظف >", reply)
            _log("bot", reply)
            continue

        if low.strip() in {"/سجل", "سجل", "/log"}:
            print(f"الموظف > السجل هنا: {_LOG_FILE}")
            try:
                if sys.platform == "win32":
                    os.startfile(_LOG_FILE)
            except Exception:
                pass
            continue

        if low.strip() == "/ذ":
            stats = memory_bank.stats()
            reply = f"الذاكرة: {stats['total_items']} معلومة، {stats['unique_tags']} وسوم"
            print("الموظف >", reply)
            continue

        if low.strip() in {"/أولويات", "/اولويات"}:
            print("الموظف >", priority_manager.priority_brief())
            continue

        # استخراج أولوية محتملة من الرسالة (لا تنفيذ، فقط اقتراح يُراجَع لاحقاً بـ /أولويات)
        try:
            added_task = priority_manager.extract_from_message(raw)
            if added_task:
                print(f"   (📌 أضفتها لقائمة الأولويات — راجعها بـ /أولويات)")
        except Exception:
            pass

        # رسالة طبيعية بلا // — نكتشف إن كانت طلب تنفيذ فعلي، ونعرضها كاقتراح
        # يحتاج تأكيدك (نفس قاعدة النظام: لا تنفيذ فعلي بلا إذن)، بديل أسهل من
        # حفظ //hermes، لا بديل عن إذنك.
        if _wants_action(raw):
            confirm = input("   🤝 رسالتك تبدو مهمة تنفيذية — أشغّلها عبر hermes agent؟ (y/n) > ").strip().lower()
            if confirm in {"y", "yes", "نعم", "ايه", "اي"}:
                reply = _run_hermes(raw)
                print("الموظف >", reply)
                _log("bot", reply)
                continue
            # رفض أو أي رد آخر → نكمل برد محادثة عادي بالأسفل

        # رد مباشر
        reply = _ask(raw, brain_session)
        print("الموظف >", reply[:800])
        _log("bot", reply)


if __name__ == "__main__":
    main()