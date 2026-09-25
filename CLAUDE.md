# CLAUDE.md — دليل مشروع Agent OS v3 (Ultra Agent)

## المعمارية الجوهرية
**الذاكرة أقوى من التوازي.** عقلٌ واحد يتذكّر ويتقنى مع الوقت > مليار وكيل ينسى.
كل فشل يُخزَّن كدرس ويُقرأ قبل المحاولة التالية. لا يُعلَن نجاح بلا دليل حقيقي.

## القاعدة الذهبية (البند 5 — غير قابلة للتفاوض)
ممنوع النجاح الوهمي: لا `ok=True` قبل تنفيذ فعلي، لا درجة A لمخرج فارغ، لا أرقام
مُلفّقة، لا "تم" دون عمل. إن لم يُعرف الجواب → "لا أعرف" أو استشارة أو تعلّم.
حين يغيب مزوّد العقل أو أدوات الصوت، تُعيد الدوال سبباً صريحاً — لا تلفيقاً.

## نقاط الدخول
- `python -m agent_os` — واجهة JARVIS التفاعلية.
- `python -m agent_os.ultra <cmd>` — run/learn/ingest/idle/ask/say/finance/tick/daemon/doctor/memory/status.
- `python -m agent_os.selfcheck` — فحص تكامل شامل (Doctor).
- `python agent_os/daemon.py run` — الحلقة الدائمة (تعلّم + تحسين ذاتي + checkpoint).

## الخريطة
| المجال | المسار |
|--------|--------|
| النواة (Router→Planner→Executor→Critic→Verifier) | `agent_os/agent_os.py` |
| الذاكرة طويلة الأمد | `agent_os/memory/` (provenance, contextual, strategy, conflict_resolver, conversation) |
| التعلّم من أي مصدر | `agent_os/learn/` (ingest, idle_learner) |
| الصوت (JARVIS) | `agent_os/voice/` (stt/tts/wake/assistant) |
| العقل متعدد المزودين | `brain.py` |
| التحسين الذاتي (sandbox + بوابة اختبارات) | `agent_os/self_improve_engine.py` |
| المساعد الثاني | `agent_os/hermes.py` |
| الفكر المالي | `agent_os/finance_brain.py` |
| بوابة نطاق الأمن (خط أحمر) | `agent_os/bounty_engine.py` |
| الواجهة الموحّدة + الحلقة الدائمة | `agent_os/ultra.py`, `agent_os/daemon.py` |

## قواعد التطوير
- كل ميزة جديدة = كود حقيقي + اختبار في `tests/` يثبتها قبل الالتزام.
- الوحدات تعمل بلا شبكة وبلا مفاتيح؛ ما يحتاج خارجياً يتدهور بصدق.
- الكتابة الذرّية عبر `agent_os._common` (`load_json`/`atomic_write`)؛ السجلّات إلى stderr.
- بيانات وقت التشغيل في `AGENT_OS_DATA_DIR` (افتراضاً `data/agent_os`)؛ الاختبارات تعزلها في tmp.

## الاختبارات
```bash
python -m pytest tests/ -q     # يجب أن يبقى أخضر بالكامل
```

## الخطوط الحمراء الدائمة
- الاختراق ضمن النطاق المصرّح فقط + رفع يدوي + التوسيع يحتاج تفويضاً (مفروض في `bounty_engine`، مُختبَر).
- لا أدوات تعرّف على أشخاص / مراقبة جماعية.
- الأفعال الحساسة على الجهاز تتطلب موافقة المالك.

## ما يحتاجه المالك على جهازه (لا يُبنى من السحابة)
- عقل: Ollama (`ollama pull llama3.1`) أو مفتاح مجاني في `.env`.
- صوت حي: `pip install faster-whisper piper-tts openwakeword sounddevice` + `PIPER_VOICE`.
