"""
suggest.py - نظام الاقتراح الذكي الشامل (v1.0)
================================================
يراجع كل ما تعلمه الوكيل ويقترح أفكاراً قوية ومربحة يومياً.

الاستخدام:
  python suggest.py              - توليد اقتراحات جديدة وعرضها
  python suggest.py --today      - اقتراحات اليوم فقط
  python suggest.py --history    - كل الاقتراحات السابقة
  python suggest.py --execute 1  - تنفيذ الاقتراح رقم 1 مباشرة
"""

import datetime
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SUGGEST_JSON = os.path.join(OUTPUT_DIR, "suggestions.json")
SUGGEST_MD = os.path.join(OUTPUT_DIR, "suggestions.md")
SKILLS_DIR = os.path.join(BASE_DIR, "skills")
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
MEMORY_FILE = os.path.join(MEMORY_DIR, "memory.json")
STATE_FILE = os.path.join(BASE_DIR, "data", "mastery_state.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ===== قراءة ما تعلمه الوكيل =====

def _load_skills():
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills
    for name in os.listdir(SKILLS_DIR):
        if name.startswith("_"):
            continue
        skill_file = os.path.join(SKILLS_DIR, name, "SKILL.md")
        if os.path.exists(skill_file):
            skills.append(name.replace("-", " "))
    return skills


def _load_memory_topics():
    topics = []
    if not os.path.exists(MEMORY_FILE):
        return topics
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            mem = json.load(f)
        for item in mem.get("learned", []):
            t = item.get("topic", "")
            if t:
                topics.append(t)
    except Exception:
        pass
    return topics


def _load_mastery_tracks():
    tracks = []
    if not os.path.exists(STATE_FILE):
        return tracks
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        for track_id, data in state.get("tracks", {}).items():
            if data.get("level", 1) >= 3:
                tracks.append(track_id.replace("-", " "))
    except Exception:
        pass
    return tracks


def _gather_knowledge():
    skills = _load_skills()
    memory_topics = _load_memory_topics()
    mastery_tracks = _load_mastery_tracks()
    all_knowledge = list(set(skills + memory_topics + mastery_tracks))
    return {
        "skills": skills,
        "memory_topics": memory_topics[:20],
        "mastery_tracks": mastery_tracks,
        "all": all_knowledge[:30],
        "total": len(all_knowledge),
    }


# ===== توليد الاقتراحات =====

def _build_intel_summary(intel):
    """يلخص الاستخبارات الحية من news_intel ليتغذى عليها توليد الاقتراحات."""
    if not intel or not isinstance(intel, dict):
        return "لا توجد استخبارات محدثة"
    parts = []
    titles = []
    for key in ("hacker_news", "tech_news", "security_news"):
        for item in intel.get(key, [])[:3]:
            t = item.get("title", "") if isinstance(item, dict) else ""
            if t:
                titles.append(t)
    if titles:
        parts.append("مواضيع رائجة: " + " | ".join(titles[:6]))
    if intel.get("cve_recent"):
        cves = [f"{c.get('id', '')}({c.get('score', '?')})" for c in intel["cve_recent"] if isinstance(c, dict)]
        if cves:
            parts.append("ثغرات جديدة: " + ", ".join(cves))
    if intel.get("github_trending"):
        repos = [r.get("repo", "") for r in intel["github_trending"] if isinstance(r, dict)][:5]
        if repos:
            parts.append("مشاريع رائجة: " + ", ".join(repos))
    if intel.get("freelance"):
        jobs = [j.get("title", "") for j in intel["freelance"] if isinstance(j, dict)][:3]
        if jobs:
            parts.append("فرص عمل حر: " + " | ".join(jobs))
    if intel.get("extracted_skills"):
        parts.append("تقنيات ناشئة: " + ", ".join(intel["extracted_skills"][:8]))
    return "; ".join(parts) if parts else "لا توجد استخبارات محدثة"


def _atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_history():
    if os.path.exists(SUGGEST_JSON):
        try:
            with open(SUGGEST_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"sessions": [], "total": 0}


def generate_suggestions(count=5, intel=None):
    import brain

    knowledge = _gather_knowledge()
    history = _load_history()

    knowledge_summary = ", ".join(knowledge["all"][:15]) if knowledge["all"] else "برمجة عامة"
    skills_summary = ", ".join(knowledge["skills"][:10]) if knowledge["skills"] else "لا توجد مهارات بعد"
    mastery_summary = ", ".join(knowledge["mastery_tracks"]) if knowledge["mastery_tracks"] else "لا يوجد"
    intel_summary = _build_intel_summary(intel)

    prompt = f"""أنت مستشار أعمال وتقنية خبير. بناءً على ما يعرفه الوكيل الذكي:

المهارات المتعلمة: {skills_summary}
مسارات الإتقان المكتملة: {mastery_summary}
المعرفة الشاملة: {knowledge_summary}
الاستخبارات الحية اليوم: {intel_summary}

اقترح {count} أفكار مشاريع قوية ومربحة يمكن تنفيذها الآن.
استخدم خبر الأخبار والاستخبارات في التوجيه: أي فرصة ناشئة، تقنية رائجة،
ثغرة أمنية جديدة (CVE) تُفتح حاجة، أو فرصة عمل حر متاحة.
لكل فكرة اكتب بالضبط بهذا الشكل:

FIELD: [المجال]
IDEA: [وصف الفكرة بجملة واحدة قوية]
WHY: [لماذا هي مربحة - جملتان]
HOW: [كيف ينفذها الوكيل - خطوات مختصرة]
PROFIT: [التقدير المالي المحتمل]
TIME: [وقت التنفيذ]
DIFFICULTY: [سهل/متوسط/صعب]
---

اجعل الأفكار متنوعة: تقنية، تجارية، إبداعية، علمية، صحية، تعليمية. ركز على الأفكار التي تجمع بين ما يعرفه الوكيل."""

    b = brain.Brain("أنت مستشار أعمال وتقنية خبير يقترح أفكاراً مربحة وقابلة للتنفيذ.")
    try:
        raw, engine = b.ask(prompt)
    except Exception as e:
        return None, f"فشل التوليد: {e}"

    suggestions = _parse_suggestions(raw)
    if not suggestions:
        suggestions = _default_suggestions(knowledge)

    session = {
        "date": datetime.datetime.now().isoformat(),
        "knowledge_snapshot": knowledge_summary,
        "intel_snapshot": intel_summary,
        "suggestions": suggestions,
        "engine": engine,
    }
    history["sessions"].append(session)
    history["total"] = sum(len(s["suggestions"]) for s in history["sessions"])
    _atomic_write(SUGGEST_JSON, history)
    _save_markdown(history)

    return suggestions, engine


def _parse_suggestions(raw):
    suggestions = []
    blocks = raw.split("---")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        s = {}
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("FIELD:"):
                s["field"] = line.replace("FIELD:", "").strip()
            elif line.startswith("IDEA:"):
                s["idea"] = line.replace("IDEA:", "").strip()
            elif line.startswith("WHY:"):
                s["why"] = line.replace("WHY:", "").strip()
            elif line.startswith("HOW:"):
                s["how"] = line.replace("HOW:", "").strip()
            elif line.startswith("PROFIT:"):
                s["profit"] = line.replace("PROFIT:", "").strip()
            elif line.startswith("TIME:"):
                s["time"] = line.replace("TIME:", "").strip()
            elif line.startswith("DIFFICULTY:"):
                s["difficulty"] = line.replace("DIFFICULTY:", "").strip()
        if s.get("idea"):
            s.setdefault("field", "تقنية")
            s.setdefault("why", "فكرة واعدة")
            s.setdefault("how", "استخدم selfrunner لتنفيذها")
            s.setdefault("profit", "غير محدد")
            s.setdefault("time", "أسبوع")
            s.setdefault("difficulty", "متوسط")
            suggestions.append(s)
    return suggestions


def _default_suggestions(knowledge):
    domains = knowledge["all"][:3] if knowledge["all"] else ["برمجة", "ذكاء اصطناعي", "تجارة"]
    templates = [
        ("أداة SaaS", "بناء أداة {d} كخدمة اشتراك شهري", "عالية ⭐⭐⭐⭐⭐", "شهر"),
        ("مساعد ذكي", "مساعد ذكاء اصطناعي متخصص في {d}", "عالية جداً ⭐⭐⭐⭐⭐", "أسبوعين"),
        ("منصة تعليمية", "منصة تعليم {d} بالذكاء الاصطناعي", "متوسطة ⭐⭐⭐", "شهر"),
    ]
    suggestions = []
    for i, domain in enumerate(domains):
        t = templates[i % len(templates)]
        suggestions.append({
            "field": domain,
            "idea": t[1].format(d=domain),
            "why": f"مجال {domain} في نمو مستمر والطلب عليه عالٍ",
            "how": "ابحث عن المنافسين ثم صمم الحل ثم نفذه بالوكيل",
            "profit": t[2],
            "time": t[3],
            "difficulty": "متوسط",
        })
    return suggestions


def _save_markdown(history):
    lines = [
        "# 💡 نظام الاقتراح الذكي - موظف الليل",
        f"آخر تحديث: {datetime.datetime.now():%Y-%m-%d %H:%M}",
        f"إجمالي الاقتراحات: {history['total']}",
        "",
    ]
    for session in reversed(history["sessions"][-5:]):
        date = session["date"][:10]
        lines.append(f"## 📅 جلسة {date}")
        lines.append(f"المعرفة: {session.get('knowledge_snapshot', '-')}")
        lines.append("")
        for i, s in enumerate(session["suggestions"], 1):
            lines += [
                f"### 💡 اقتراح #{i}: {s.get('idea', '-')}",
                f"**المجال:** {s.get('field', '-')}",
                f"**لماذا مربح:** {s.get('why', '-')}",
                f"**كيف تنفذه:** {s.get('how', '-')}",
                f"**الربحية:** {s.get('profit', '-')}",
                f"**الوقت:** {s.get('time', '-')}",
                f"**الصعوبة:** {s.get('difficulty', '-')}",
                f"**للتنفيذ:** `python suggest.py --execute {i}`",
                "",
            ]
        lines.append("---")
    tmp = SUGGEST_MD + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(tmp, SUGGEST_MD)


# ===== تنفيذ اقتراح =====

def execute_suggestion(index):
    history = _load_history()
    if not history["sessions"]:
        print("لا توجد اقتراحات بعد. شغّل: python suggest.py")
        return
    last_session = history["sessions"][-1]
    suggestions = last_session["suggestions"]
    if index < 1 or index > len(suggestions):
        print(f"رقم غير صحيح. المتاح: 1 إلى {len(suggestions)}")
        return
    s = suggestions[index - 1]
    print(f"\n🚀 تنفيذ الاقتراح #{index}: {s['idea']}")
    print(f"المجال: {s['field']} | الوقت: {s['time']}")
    print("جارٍ التنفيذ...\n")
    try:
        import selfrunner
        prompt = f"نفّذ هذا المشروع كاملاً:\nالفكرة: {s['idea']}\nالمجال: {s['field']}\nالخطوات: {s['how']}\nابنِ المشروع في مجلد projects/ مع كل الملفات اللازمة."
        report = selfrunner.run_task(prompt)
        print(f"\n✅ اكتمل!")
        print(f"التقرير: {report[:500] if report else 'تم الحفظ في reports/'}")
    except Exception as e:
        print(f"خطأ: {e}")
        print(f"يمكنك تنفيذه يدوياً: python selfrunner.py \"{s['idea']}\"")


# ===== عرض =====

def display_suggestions(suggestions, engine=""):
    print("\n" + "=" * 60)
    print("💡 اقتراحات موظف الليل الذكية")
    print(f"العقل: {engine}")
    print("=" * 60)
    for i, s in enumerate(suggestions, 1):
        print(f"\n{'-' * 50}")
        print(f"💡 اقتراح #{i}: {s.get('idea', '-')}")
        print(f"   📂 المجال: {s.get('field', '-')}")
        print(f"   💰 الربحية: {s.get('profit', '-')}")
        print(f"   ⏱️  الوقت: {s.get('time', '-')}")
        print(f"   🎯 الصعوبة: {s.get('difficulty', '-')}")
        print(f"   ✅ لماذا: {s.get('why', '-')}")
        print(f"   🔧 كيف: {s.get('how', '-')}")
        print(f"   ▶️  للتنفيذ: python suggest.py --execute {i}")
    print(f"\n{'=' * 60}")
    print(f"📄 محفوظ في: {SUGGEST_MD}")


def show_today():
    history = _load_history()
    if not history["sessions"]:
        print("لا توجد اقتراحات. شغّل: python suggest.py")
        return
    today = datetime.date.today().isoformat()
    today_sessions = [s for s in history["sessions"] if s["date"].startswith(today)]
    if not today_sessions:
        print("لا توجد اقتراحات اليوم. شغّل: python suggest.py")
        return
    last = today_sessions[-1]
    display_suggestions(last["suggestions"], last.get("engine", ""))


def show_history():
    history = _load_history()
    if not history["sessions"]:
        print("لا يوجد سجل بعد.")
        return
    print(f"\n📚 سجل الاقتراحات - إجمالي: {history['total']}")
    print("=" * 60)
    for session in reversed(history["sessions"]):
        date = session["date"][:16].replace("T", " ")
        count = len(session["suggestions"])
        print(f"\n📅 {date} - {count} اقتراحات")
        for i, s in enumerate(session["suggestions"], 1):
            print(f"   {i}. {s.get('idea', '-')} [{s.get('field', '-')}]")
    print(f"\n📄 التفاصيل: {SUGGEST_MD}")


# ===== الواجهة الرئيسية =====

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--today" in args:
        show_today()
    elif "--history" in args:
        show_history()
    elif "--execute" in args:
        idx = args.index("--execute")
        try:
            num = int(args[idx + 1])
            execute_suggestion(num)
        except (IndexError, ValueError):
            print("استخدام: python suggest.py --execute <رقم>")
    else:
        print("🧠 جارٍ تحليل ما تعلمته وتوليد اقتراحات ذكية...")
        knowledge = _gather_knowledge()
        print(f"📊 المعرفة المتاحة: {knowledge['total']} موضوع")
        print(f"   المهارات: {len(knowledge['skills'])}")
        print(f"   الذاكرة: {len(knowledge['memory_topics'])}")
        print(f"   الإتقان: {len(knowledge['mastery_tracks'])}")
        print("\n⏳ جارٍ التوليد...")
        suggestions, engine = generate_suggestions(count=5)
        if suggestions:
            display_suggestions(suggestions, engine)
        else:
            print(f"فشل: {engine}")
            print("تأكد من وجود مفتاح API في .env")
