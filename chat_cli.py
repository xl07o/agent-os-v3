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


def _build(text):
    """بناء مشروع فوري."""
    import builders
    tl = text.lower()
    try:
        if "roblox" in tl or "لوا" in tl or "لعبة" in tl or "game" in tl:
            paths = builders.make_roblox_place("MyPlace")
            return "بنيتُ لك خريطة Roblox جاهزة ✅: " + paths.get("server_script", "")
        if "بايثون" in tl or "python" in tl or "برنامج" in tl or "app" in tl:
            paths = builders.make_python_project("MyApp")
            return "بنيتُ لك مشروع بايثون جاهز ✅: " + paths.get("project", "")
        if "موقع" in tl or "هبوط" in tl or "landing" in tl or "ويب" in tl or "web" in tl:
            paths = builders.make_web_project("MyLanding")
            return "بنيتُ لك موقع هبوط كامل ✅: " + paths.get("site", "")
        return "اختر نوع: //بناء موقع | //بناء بايثون | //بناء روبلوكس"
    except Exception as e:
        return "خطأ أثناء البناء: " + str(e)


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
    print("   أوامر: //بناء <نوع> | /سجل | exit | /تذكر <معلومة>")
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

        if raw.startswith("//بناء"):
            req = raw[len("//بناء"):].strip()
            reply = _build(req) if req else "اكتب نوع: موقع / بايثون / روبلوكس"
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

        # رد مباشر
        reply = _ask(raw, brain_session)
        print("الموظف >", reply[:800])
        _log("bot", reply)


if __name__ == "__main__":
    main()