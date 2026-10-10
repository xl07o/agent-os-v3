"""تشغيل: python -m agent_os4.cli"""

import os

from . import approval, bots, chatroom, decision, deploy, evidence, housekeeping, kernel, metrics, router, self_improve, skills

_HELP = """أوامر خاصة (غير مرسلة للعقل):
  انشر                                       ينشر شاتاً ويباً على Daytona ويعطيك رابطاً تفتحه بالمتصفح
  تحسين <ملف.py> <مسار_محتوى_جديد> <سبب>   يقترح تعديلاً، يختبره بساندبوكس، يفتح طلب موافقة
  اقتراحات                                  يعرض كل اقتراحات التطوير الذاتي المعلّقة/المحلولة
  طبّق <id>                                 يطبّق اقتراحاً مُوافَقاً عليه فعلياً على الملف
  نسخ <ملف.py>                              يعرض النسخ الاحتياطية المتوفرة لملف
  استرجاع <ملف.py>                          يقترح الرجوع لآخر نسخة احتياطية (يحتاج موافقة زي أي تعديل)
  وافق <id> / ارفض <id>                     يحسم طلب موافقة معلّق (تطوير ذاتي أو غيره)
  بوتات                                      يعرض كل البوتات المساعدة المتاحة
  بوت <اسم> <مهمة>                          يشغّل مهمة عبر بوت محدد (أدوات محصورة بدوره)
  نقاش <بوت1,بوت2,...> <موضوع>              يفتح نقاشاً جماعياً بين بوتات محددة، جولة واحدة
  احسم <بوت1,بوت2,...> <موضوع>              نقاش + توصية نهائية من كل بوت؛ توافق = طلب واحد، تعارض = طلب لكل خيار
  الغرفة                                     يعرض آخر محادثة غرفة النقاش الجماعي
  مهارات                                     يعرض كل المهارات المسجّلة ونسخها
  استخدم <اسم_مهارة> <نص>                   يستخدم آخر نسخة معتمدة من مهارة
  سجل                                       يعرض آخر قرارات decision.ledger()
  تدقيق                                      إحصاءات حقيقية: كم طلب، كم وافق، نسبة الموافقة لكل جهة
  مؤشرات                                     لقطة أرقام شاملة: قرارات، استخدام بوتات، ذاكرة، مهارات
  خروج                                       ينهي الجلسة ويرتب الذاكرة بـObsidian
"""


def _handle_propose(rest: str) -> None:
    parts = rest.split(" ", 2)
    if len(parts) < 3:
        print("الاستخدام: تحسين <ملف.py> <مسار_محتوى_جديد> <سبب التعديل>")
        return
    filename, content_path, why = parts
    if not os.path.isfile(content_path):
        print(f"ملف غير موجود: {content_path}")
        return
    with open(content_path, "r", encoding="utf-8") as f:
        new_content = f.read()

    print("يختبر التعديل بساندبوكس معزول قبل أي موافقة...")
    result = self_improve.propose(filename, new_content, why)
    if not result["ok"]:
        print(f"توقف عند مرحلة: {result['stage']}\n{result['error']}")
        return
    print(f"نجح الاختبار بالساندبوكس. طلب موافقة جديد: [{result['request_id']}]")
    print(result["diff"])
    print("اكتب: وافق " + result["request_id"] + "  ثم  طبّق " + result["request_id"])


def _handle_list_proposals() -> None:
    items = self_improve.list_proposals()
    if not items:
        print("لا اقتراحات تطوير ذاتي حالياً.")
        return
    for p in items:
        print(f"  [{p['request_id']}] {p['relative_filename']} — {p['status']} — {p['proposed_at']}")


def _handle_apply(request_id: str) -> None:
    result = self_improve.apply(request_id)
    if not result["ok"]:
        print(result["error"])
        return
    print(f"طُبِّق على: {result['applied_to']}")
    if result["backup"]:
        print(f"نسخة احتياطية من القديم: {result['backup']}")


def _handle_resolve(request_id: str, approved: bool) -> None:
    ok = (decision.approve if approved else decision.reject)(request_id, decided_by="owner")
    print("تم." if ok else "طلب غير موجود أو محسوم مسبقاً.")


def _handle_list_bots() -> None:
    for b in bots.list_bots():
        tools_str = "، ".join(b["allowed_tools"]) or "بلا أدوات تنفيذ (تحليل فقط)"
        print(f"  [{b['key']}] {b['title_ar']} ({b['directorate']}) — {tools_str}")


def _handle_run_bot(rest: str) -> None:
    parts = rest.split(" ", 1)
    if len(parts) < 2:
        print("الاستخدام: بوت <اسم_البوت> <المهمة>")
        return
    bot_key, task = parts
    try:
        result = bots.run(bot_key, task)
    except ValueError as e:
        print(e)
        return
    if result.get("reply"):
        print(result["reply"])
    else:
        print(f"\n{result['verdict']}")


def _handle_discuss(rest: str) -> None:
    parts = rest.split(" ", 1)
    if len(parts) < 2:
        print("الاستخدام: نقاش <بوت1,بوت2,...> <الموضوع>")
        return
    bot_keys = [k.strip() for k in parts[0].split(",") if k.strip()]
    topic = parts[1]
    try:
        messages = chatroom.discuss(bot_keys, topic)
    except ValueError as e:
        print(e)
        return
    for m in messages:
        print(f"  [{m['speaker']}] {m['text']}")


def _handle_resolve_discussion(rest: str) -> None:
    parts = rest.split(" ", 1)
    if len(parts) < 2:
        print("الاستخدام: احسم <بوت1,بوت2,...> <الموضوع>")
        return
    bot_keys = [k.strip() for k in parts[0].split(",") if k.strip()]
    topic = parts[1]
    try:
        result = chatroom.resolve(bot_keys, topic)
    except ValueError as e:
        print(e)
        return
    if result["outcome"] == "failed":
        print(f"فشل كل البوتات ({', '.join(result['failed_bots'])}) — لا قرار، لا طلب موافقة.")
        return
    if result["failed_bots"]:
        print(f"(تعذّر رد: {', '.join(result['failed_bots'])} — استُبعدوا من القرار)")
    if result["outcome"] == "consensus":
        print(f"توافق من {', '.join(result['supporters'])}: {result['recommendation']}")
        print(f"طلب موافقة: [{result['request_id']}]")
    else:
        print(f"تعارض — {len(result['proposals'])} خيارات متنافسة، كل واحد طلب موافقة منفصل:")
        for p in result["proposals"]:
            print(f"  [{p['request_id']}] {', '.join(p['supporters'])}: {p['recommendation']}")
        print("وافق على خيار واحد فقط بالأمر: وافق <id>")


def _handle_room() -> None:
    entries = chatroom.history(limit=30)
    if not entries:
        print("الغرفة فاضية حالياً.")
        return
    for e in entries:
        print(f"  [{e['at']}] [{e['speaker']}] {e['text']}")


def _handle_ledger() -> None:
    entries = decision.ledger(limit=20)
    if not entries:
        print("السجل فاضٍ حالياً.")
        return
    for e in entries:
        who = e.get("decided_by") or e.get("proposed_by", "?")
        print(f"  [{e['at']}] {e['stage']} — {e.get('request_id', '?')} — {who}")


def _handle_list_backups(filename: str) -> None:
    items = self_improve.list_backups(filename)
    if not items:
        print(f"لا نسخ احتياطية لـ{filename}.")
        return
    for b in items:
        print(f"  {b}")


def _handle_restore(filename: str) -> None:
    result = self_improve.restore(filename)
    if not result["ok"]:
        print(result["error"])
        return
    print(f"نجح الاقتراح، طلب موافقة جديد: [{result['request_id']}]")
    print(result["diff"])
    print("اكتب: وافق " + result["request_id"] + "  ثم  طبّق " + result["request_id"])


def _handle_list_skills() -> None:
    items = skills.list_skills()
    if not items:
        print("لا مهارات مسجّلة حالياً.")
        return
    for s in items:
        print(f"  {s['name']} — نسخة {s['latest_version']} — {s['examples_count']} أمثلة")


def _handle_use_skill(rest: str) -> None:
    parts = rest.split(" ", 1)
    if len(parts) < 2:
        print("الاستخدام: استخدم <اسم_مهارة> <نص>")
        return
    name, text = parts
    try:
        print(skills.use(name, text))
    except ValueError as e:
        print(e)
    except Exception as e:  # noqa: BLE001 — فشل استدعاء المخ، لا نخفيه
        print(f"فشل: {type(e).__name__}: {e}")


def _handle_audit() -> None:
    a = evidence.audit()
    print(f"  إجمالي السجلات: {a['total_entries']} — مُقترح: {a['proposed']} — موافَق: {a['approved']} — مرفوض: {a['rejected']}")
    print(f"  نسبة الموافقة: {a['approval_rate']}")
    for actor, counts in a["by_actor"].items():
        print(f"    {actor}: {counts}")


def _handle_metrics() -> None:
    m = metrics.snapshot()
    print(f"  القرارات: {m['decisions']}")
    print(f"  استخدام البوتات: {m['bot_usage'] or '(لا شيء بعد)'}")
    print(f"  عناصر الذاكرة: {m['memory_entries']}")
    print(f"  مهارات مسجّلة: {m['skills_registered']}")


def _handle_deploy() -> None:
    print("ينشر على Daytona... قد يأخذ دقيقة.")
    result = deploy.deploy()
    if not result["ok"]:
        print(f"فشل عند مرحلة {result['stage']}: {result['error']}")
        return
    print(f"جاهز! افتح هذا الرابط بالمتصفح (صالح {result['expires_in_seconds']} ثانية):")
    print(f"  {result['url']}")
    print(f"لإيقافه لاحقاً: python3 -c \"from agent_os4 import deploy; deploy.teardown('{result['sandbox_id']}')\"")


def main() -> None:
    pending = approval.pending()
    if pending:
        print(f"فيه {len(pending)} طلب معلّق من قبل:")
        for r in pending:
            print(f"  [{r['id']}] {r['what']} — {r['why'][:80]}")
        print()

    print("os4 جاهز. اكتب مهمتك، أو 'مساعدة' لعرض الأوامر الخاصة، أو 'خروج' للإنهاء.\n")
    while True:
        task = input("> ").strip()
        if task in ("خروج", "exit", "quit"):
            break
        if not task:
            continue
        if task in ("مساعدة", "help"):
            print(_HELP)
            continue
        if task.startswith("تحسين "):
            _handle_propose(task[len("تحسين "):])
            continue
        if task in ("اقتراحات",):
            _handle_list_proposals()
            continue
        if task.startswith("طبّق "):
            _handle_apply(task[len("طبّق "):].strip())
            continue
        if task.startswith("نسخ "):
            _handle_list_backups(task[len("نسخ "):].strip())
            continue
        if task.startswith("استرجاع "):
            _handle_restore(task[len("استرجاع "):].strip())
            continue
        if task in ("انشر",):
            _handle_deploy()
            continue
        if task.startswith("وافق "):
            _handle_resolve(task[len("وافق "):].strip(), approved=True)
            continue
        if task.startswith("ارفض "):
            _handle_resolve(task[len("ارفض "):].strip(), approved=False)
            continue
        if task in ("بوتات",):
            _handle_list_bots()
            continue
        if task.startswith("بوت "):
            _handle_run_bot(task[len("بوت "):])
            continue
        if task.startswith("نقاش "):
            _handle_discuss(task[len("نقاش "):])
            continue
        if task.startswith("احسم "):
            _handle_resolve_discussion(task[len("احسم "):])
            continue
        if task in ("الغرفة",):
            _handle_room()
            continue
        if task in ("مهارات",):
            _handle_list_skills()
            continue
        if task.startswith("استخدم "):
            _handle_use_skill(task[len("استخدم "):])
            continue
        if task in ("سجل",):
            _handle_ledger()
            continue
        if task in ("تدقيق",):
            _handle_audit()
            continue
        if task in ("مؤشرات",):
            _handle_metrics()
            continue

        # ما فيه أمر خاص مطابق — توجيه ذكي بدل افتراض دائماً المسار
        # العام: لو الطلب يطابق تخصص بوت معيّن بوضوح يتولاه هو، وإلا
        # عام كالمعتاد. فشل التصنيف نفسه = عام دائماً (فشل آمن).
        decided = router.classify(task)
        if decided["route"] == "bot":
            print(f"(تم التوجيه تلقائياً → {decided['bot_key']})")
            result = bots.run(decided["bot_key"], task)
        else:
            result = kernel.run_task(task)
        if result.get("reply"):
            print(result["reply"])
        else:
            print(f"\n{result['verdict']}")

    tidy_result = housekeeping.tidy()
    if tidy_result["archived"]:
        print(f"\nرُتِّبت الذاكرة: {tidy_result['archived']} عنصر أُرشف بـObsidian.")


if __name__ == "__main__":
    main()
