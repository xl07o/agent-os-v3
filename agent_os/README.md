# Agent OS v3 — خريطة الأنظمة

النواة: **Router → Planner → Executor → Critic → Verifier** (ملف `agent_os.py`).

| # | النظام | الملف | الجزء | مدخل CLI |
|---|--------|-------|-------|----------|
| 1 | مدير الأهداف الذاتي | goal_manager.py | الأهداف والمهام الذاتية | add/list/breakdown/run/advance |
| 2 | محرك التحسين الذاتي | self_improve_engine.py | دورة قياس→تعديل→اختبار→التزام | cycle/history |
| 3 | قياس ذكاء الوكيل | benchmark.py | 12 مجالاً + أضعف المجالات + نصائح إصلاح | run/summary |
| 4 | السجل العام للأدوات | tool_registry.py | اكتشاف/مراجعة أمنية/تثبيت/صحة | discover/list/health |
| 5 | طبقة المتصفح | browser_agent.py | http (افتراضي) + selenium (اختياري) | url <رابط> |
| 6 | مشغّل الأعمال | business_autopilot.py | بحث سوق/فرص/خط أنابيب | opportunity/rank/pipeline |
| 7 | مصنع المنتجات | product_factory.py | قوالب قابلة للتشغيل لـ12 نوعاً | build <نوع> <اسم> <مسار> |
| 8 | وكيل النشر | devops_agent.py | git/docker + CI + نشر + مراقبة + تراجع | git/deploy/ci/monitor |
| 9 | محرك البجتي | bounty_engine.py | بوابة نطاق صارمة (wildcard) + تقارير | program/scan/report |
| 10 | الذكاء المالي | finance_intel.py | دخل/مصروف/أفضل مصدر/عائد | add/report/brief |
| 11 | مركز الموافقات البشرية | approval_center.py | طلبات + عودة تلقائية بعد القبول | create/list/resume |
| 12 | نموذج العالم + رئيس الأركان | world_model.py + chief_staff.py | بصمة/KPI/خطة اليوم | wake/plan/brief |

## أخلاقيات التشغيل (ثابتة — لا تتغير)

- لا تعديل ذاتي للملفات المحمية: `selfrunner.py, webtools.py, mastery.py, skills.py, memory_bank.py, brain.py, builders.py`.
- لا `shell=True` إطلاقاً — كل تنفيذ عبر `selfrunner.run_command` (argv + قائمة بيضاء).
- بوابة النطاق في البجتي **hard gate**: لا أصول خارج النطاق المصرح.
- الثغرة ≠ استغلال: الفحص سلبي/سطحي مصرح فقط، والاستغلال التخريبي مرفوض دائماً.
- الأسرار لا تُقرأ تلقائياً; أي credential يحتاج موافقة عبر مركز الموافقات.

## اختبارات

```powershell
python -m pytest tests/test_agent_os.py -q   # الحزمة وحدها (بلا شبكة وبلا دماغ)
python -m pytest tests/ -q                    # الكل
```