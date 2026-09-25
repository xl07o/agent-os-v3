# Agent OS v3 — Ultra Agent (حالة حقيقية، بلا تجميل)

هذه الوثيقة تصف ما بُني فعلاً وكيف تشغّله. المبدأ المعماري:
**الذاكرة أقوى من التوازي** — عقلٌ واحد يتذكّر ويتقنى مع الوقت > مليار وكيل ينسون.
لا يُعلَن نجاح بلا دليل، ولو عجز يقول «لا أعرف» أو يستشير أو يتعلّم.

## التشغيل السريع

```bash
python -m agent_os                            # يُطلق واجهة JARVIS التفاعلية
python -m agent_os "سجّل هدف بناء متجر"        # أو نفّذ أمراً واحداً
python -m agent_os.ultra status              # جاهزية النظام كاملاً (صدق تام)
python -m agent_os.ultra run   "سجّل هدف بناء متجر"   # نفّذ مهمة عبر النواة
python -m agent_os.ultra learn "تصميم واجهات REST"    # تعلّم من الويب واخزنه
python -m agent_os.ultra ingest owner/repo            # استوعب README مستودع
python -m agent_os.ultra ingest https://example.com   # استوعب صفحة
python -m agent_os.ultra idle  "هدفي الأول" "هدفي الثاني"  # تعلّم ذاتي وقت السكون
python -m agent_os.ultra ask   "كيف أبدأ أداة CLI؟"    # اسأل المساعد Hermes
python -m agent_os.ultra say   "افتح لي تقرير الحالة"  # المسار الصوتي (نصياً)
python -m agent_os.ultra memory                        # لمحة الذاكرة المتراكمة
```

## ما يلزم لتشغيله كاملاً على جهازك (لا يمكن فعله من السحابة)

1. **عقل** (يرفع جودة المحتوى؛ النواة تعمل بدونه لكن المخرجات تبقى سقالات صادقة):
   - مجاناً محلياً: ثبّت [Ollama](https://ollama.com) ثم `ollama pull llama3.1`
   - أو ضع مفتاحاً مجانياً في `.env` (Gemini/Groq/OpenRouter…)
2. **الصوت (جارفيس)** على جهازك:
   ```bash
   pip install faster-whisper piper-tts openwakeword sounddevice
   # ونزّل صوت Piper (.onnx) واضبط PIPER_VOICE=/path/voice.onnx
   ```
   ثم: `python -c "from agent_os.voice import assistant; assistant.run_loop()"`

## حالة البنود الـ18

| # | البند | الحالة | أين |
|---|------|--------|-----|
| 1 | يتعلم من كل مكان (ويب/GitHub/YouTube) | ✅ مبني ومُختبَر | `agent_os/learn/ingest.py` |
| 2 | تعلّم ذاتي وقت السكون (مجاناً عبر الويب) | ✅ مبني ومُختبَر | `agent_os/learn/idle_learner.py` |
| 3 | الذاكرة (مركز الثقل) + مربوطة بالحلقة | ✅ مبني ومُختبَر | `agent_os/memory/` + `run_task` |
| 4 | كود حقيقي لا سطحي | ✅ توليد حقيقي بالعقل + بوابات صدق + احتياط صادق | `_brain_deliverable` |
| 5 | ممنوع الاستجابات الوهمية | ✅ كل مسارات النجاح الكاذب قُتلت ومُختبَرة | `test_honesty_fixes.py` |
| 6 | قوة بمستوى الشركات | ◻️ الأساس أقوى الآن؛ طموح مستمر | — |
| 7 | فكر مالي + تقني | ✅ تحليل جدوى (ROI/استرداد/go-no-go) مبني ومُختبَر | `agent_os/finance_brain.py` |
| 8 | تحكم مباشر بالجهاز (بموافقة) | ✅ قائم وحقيقي | `computer_control.py` |
| 9 | ولوج لكوده + sandbox تجارب | ✅ قائم وحقيقي (فرع + بوابة اختبارات) | `self_improve_engine.py` |
| 10 | يطوّر عقله | ✅ عبر دورة التحسين (committed فقط = نجاح) | `self_improve_engine.improve_once` |
| 11 | أولويات من محادثاتنا | ✅ تعدين أولويات موزون بالحداثة من كل حوار | `agent_os/memory/conversation.py` |
| 12 | يخزّن كل شيء كمرجع | ✅ مبني ومُختبَر | `agent_os/memory/provenance` |
| 13 | صوت كامل (whisper/wake/piper) | ✅ تكامل حقيقي؛ يحتاج تثبيت الأدوات على جهازك | `agent_os/voice/` |
| 14 | مساعد Hermes | ✅ مبني ومُختبَر | `agent_os/hermes.py` |
| 15 | راوتر API مجاني + تدوير | ✅ قائم ومُتحقَّق منه | `brain.py` |
| 16 | Checkpoint + Resume | ✅ قائم وحقيقي | `checkpoint_system.py` |
| 17 | يسأل Claude/DeepSeek/Gemini عند العجز | ✅ مبني ومُختبَر | `agent_os.py._consult_brain` |
| 18 | HackerOne ضمن النطاق فقط (خط أحمر) | ✅ بوابة نطاق صارمة ومُختبَرة | `bounty_engine.in_scope` |

### خطوط حمراء دائمة (بموافقتك المسبقة)
- **الاختراق ضمن النطاق المصرّح فقط**، والرفع يدوي، والتوسيع يحتاج تفويضاً — مفروض في `bounty_engine`.
- **لا أدوات تعرّف على الأشخاص / مراقبة جماعية** (مثل «god eyes») — استهداف أفراد، مرفوض.
- تثبيت Kali وأدوات الهجوم: خطوة يقودها المالك على جهازه، لا تُنفَّذ آلياً من هنا.

## واجهة JARVIS التفاعلية (نظام تشغيل مصغّر)
```
python -m agent_os
# ثم: حالة | ذاكرة | أولويات | تعلّم <موضوع> | اسأل <سؤال> | سكون | صوت on|off | خروج
# وأي جملة أخرى تُنفَّذ كمهمة، ويُسجَّل كل حوار لاستخلاص أولوياتك.
```

## الاختبارات
```bash
python -m pytest tests/ -q      # 307 ناجح (وقت كتابة هذه الوثيقة)
```
