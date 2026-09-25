# ملاحظات المراجعة — موظف الليل (SelfRunner) v2.3

هذه نسخة محدثة للعرض على Claude Code للمراجعة الأمنية والوظيفية.

## ما أُصلح منذ المراجعة السابقة (Claude Code #4 — المراجعة الشاملة 40 ملاحظة)
1. **حقن أوامر الـ batch** (`start.bat`): اقتباسات المدخل تُجرد
   (`set "task=!task:"=!"`) وتُمرَّر القيمة بالتمديد المؤجل `!var!`؛ أُصلح خطأ
   خفي كان يُفرّغ المهمة داخل الكتل الشرطية، وأُغلق ثغرة فتح أمر ثانٍ. وُثّق
   باختبار حي (مدخل بعلامات اقتباس وعوامل لا ينتج عنه أمراً ثانياً).
2. **حقن كود Lua** (`builders.py`): اسم خريطة Roblox يُعقَّم (`name_lua`): يُجرد
   من `'`, `"`, `\`, وأسطر جديدة قبل وضعه في تعليق وسطر الطباعة — لا كسر
   للسلسلة ولا استدعاء `os.execute`.
3. **استبدالات أوامر bash إضافية** مرفوضة في `selfrunner`: `$[`, `<(`, و`$((` —
   مع الاقتباسات غير المتوازنة: `_split_args` يعيد قائمة فارغة (أمر غير آمن) بدل
   تقسيم ساذج يكشف فلاق `-c`.
4. **مجلدات النظام على كل الأقراص**: `_ALL_BLOCKED` يضيف `Windows`،
   `System Volume Information`، و`$RECYCLE.BIN` لكل قرص موجود (إلى جانب
   `SystemRoot`)؛ و`list_project_files` يفلتر الروابط الرمزية التي تخرج عن
   `PROJECTS_DIR`.
5. **كتابة ذرية لبنك الذاكرة**: `memory_bank._save_bank` و`_save_index` عبر
   `_atomic_write_json` (tmp + os.replace) — لا بقايا `.tmp`.
6. **قفل الـ Rate-limiter وCache** لـ `webtools` (`_rate_lock`, `_cache_lock`) —
   الوصول من عدة خيوط آمن الآن.
7. **قراءة استجابة محدودة الحجم** (`_read_limited`, 5MB بقطع 64KB) + **فحص
   Content-Type** قبل قراءة الجسم (نصوص فقط: text/json/xml/js/xhtml/rss/atom/
   csv/markdown/yaml) + محلِّل HTML الأقوى عند توفر lxml.
8. **محادثة متصلة فعلاً** (`chat_cli`): جلسة عقل واحدة تُبنى مرة واحدة
   (`_main_loop`) وتستمر لكل الرسائل — الذاكرة الآن تتحدث (تُحقن بسياق المستخدم).
9. **ميزانية التكلفة يومية**: `brain._perf_total` تتصفَّر تلقائياً عندما يتغير
   التاريخ المخزّن (`_date`) — لا يعلّق مزوّد مدفوع إلى الأبد بعد منتصف الليل؛
   و`_response_hashes` تُقتطع بأقدمها لا عشوائياً؛ ومهلة الهجين
   `as_completed(timeout=REQUEST_TIMEOUT + 5)`.
10. **تقرير الإتقان بلا كشف مسار**: `mastery` يخزن مسار الديمو نسبياً
    (`os.path.relpath`) — لا اسم مستخدم في التقرير — وXP الدورة الفاشلة ينقص
    فعلًا (`max(0, xp-1)`).
11. **متفرقات**: روابط اللوحة `rel="noopener noreferrer"`؛ بصمة المهارة SHA-256
    بدل MD5؛ بحث ثانٍ في `learn()` فقط عند غيض نتائج (أقل من 3)؛ حد المهمة
    `{LIMIT}` يُملأ من البيئة (افتراضي PT71H)؛ أسماء نماذج Ollama تُعقَّم
    بـ regex؛ `pip install` تُعاد مع `--user` عند الفشل؛ مهلة واجهة المنصة قابلة
    للضبط؛ و`.gitignore` يسمح بمصادر اختبارات JSON.
12. **إصلاح عابر في الاختبارات**: محاكي `_FakeResp.read` دعم القراءة بالقطع
    (توافق مع `_read_limited`)؛ واختبار البحث الشبكي يُتخطى افتراضياً
    (`SELFRUNNER_NETWORK_TESTS=1` ليُفعَّل).

### تجاهل متعمد (بطلب المستخدم)
- السجلات تنمو بلا حدّ (ملاحظتا الحجم/التدوير) — **نمو لا محدود** كما أراد.
- قياس `access_count` لمفتاح الإرفاق — لا توجد ميزة بهذا الاسم في `selfrunner`.

## ما أُصلح منذ المراجعة السابقة (Claude Code #3 — تعميق المراجعة)
1. **تحصين المهارات ضد path traversal (خطير)** — `skills.py`: كل من
   `delete_skill`, `update_skill`, `get_skill`, `get_skill_info` تمر عبر
   `_safe_skill_dir` الذي يبني المسار بتنظيف صارم (`[^a-z0-9-]`) داخل `SKILLS_DIR`
   مع `realpath` ورفض قاطع لأي خروج عن الجذر — لا `rmtree` عشوائي أبداً حتى لو
   أُضيف لاحقاً أمر `DELETE_SKILL:<name>` بمدخل خارجي.
2. **كتابة ذرية لـ JSON (منع كسر الملفات)** — `brain._save_perf`, `skills._save_index`
   و`_save_memory`, و`mastery._save_state`: تُكتب لملف `.tmp` ثم `os.replace`.
   لو أُطفئت الطاقة ليلةً، لا ينكسر `brain_perf.json` ولا تُلحى ميزانية
   `MAX_COST_USD` تراكمياً. `skills` و`mastery` عبر دالة `_atomic_write_json` موحّدة.
3. **موديل Anthropic محدَّث** — الافتراضي صار `claude-sonnet-4-5-20250929`
   (يُغيّر عبر `ANTHROPIC_MODEL` في `.env`).
4. **حكم دلالي اختياري للهجين** — `_judge_response`: عند `SELFRUNNER_HYBRID_JUDGE=1`
   يسأل مزوداً ثالثاً خفيفاً «أيّ الردّين أدق؟ (A أو B)» ويأخذ قراره فعلًيا؛ مع
   `fallback` تلقائي للتقييم الشكلي عند أي فشل. معطّل افتراضياً (صفبر تكلفة إضافية).
5. **لوحة العرض بلا تسريب مسار** — `dashboard.card_links` تولّد روابط **نسبية**
   بدل `file:///C:/Users/...` — تُشارك `dashboard.html` دون كشف اسم المستخدم
   والمسار الكامل على القرص.
6. **اختبارات انحدار جديدة** (مسار عابر لا يخرج عن الجذر، ذرّية JSON بلا بقايا
   `.tmp`، الحكم معطّل دون أي استدعاء شبكة، اللوحة بلا `file:///`) —
   **55 اختباراً نجحت + اختبار شبكي يُتخطى افتراضياً (أُعيد التشغيل مرتين)**.

## ما أُصلح منذ المراجعة السابقة (Claude Code #2 — جولة التثبيت)
1. **عزل الكود المولَّد ذاتياً في mastery.py** — `_static_guard` (فحص AST) يفحص
   أي `lib.py`/`test_lib.py` قبل الكتابة على القرص: قائمة بيضاء للاستيرادات
   (`math, re, json, collections, datetime, pytest...`)، وقائمة أسماء/صفات ممنوعة
   (`os, sys, subprocess, socket, shutil, ctypes, eval, exec, __import__,
   open, input, pathlib, urllib, requests...` و`system, popen, remove, rmtree,
   unlink, chmod, kill...`)، وحد 400 سطر. `_run_pytest` صار `python -B
   -p no:cacheprovider` بمهلة 60 ثانية وبدون bytecode.
2. **إغلاق DNS rebinding في webtools.py** — `_resolve_safe_ip` يحل DNS مرة واحدة
   ويتحقق أن الـ IP عام؛ `_fetch` يثبّت الـ IP ويبني اتصالات مخصصة
   (`_PinnedHTTPConnection`/`_PinnedHTTPSConnection`) تتصل فعلياً بالـ IP المثبَّت
   مع الإبقاء على Host/SNI الأصلية (http و https معاً)، وأي redirect يُعاد فحصه
   وتثبيته. قفل (`threading.Lock`) على الـ cache.
3. **فحص أوامر منطقي بدل regex** — `selfrunner._is_safe_command` يحلل وسائط
   مقسّمة ويُقيّم تباينات "القوة" (`-r -f`, `--recursive`, `/s /q`...) بالمعنى
   لا بالنص؛ فلا يفلت `rmdir -r -f` أو `rmdir --recursive`.
4. **realpath في `_validate_path`** — تحليل الروابط الرمزية قبل مقارنة المسارات
   الممنوعة (منع `..`/symlink traversal).
5. **تنقية الأسرار في السجلات** — `_redact()` في `selfrunner.log` و`mastery._log`
   يستبدل `sk-`, `AIza`, `gsk_`, `Bearer`, و`key=value` بـ [REDACTED] قبل الطباعة/الحفظ.
6. **اختبارات انحدار جديدة** تغطي: AST guard (رفض الأشرار/قبول الآمن)، DNS rebinding
   (محاكاةٍ للتحويل الضار + عزل بدون شبكة)، تباينات فلاقات القوة، realpath/symlink،
   وتنقية السجلات — **46 اختباراً كلها خضراء**.

## ما تبقى كمقترحات للمراجعة القادمة (حسب الجولة #2)
- الـ `_static_guard` دفاع قوي لكن ليس sandbox كامل — العزل النهائي يتطلب تشغيل
  pytest داخل حاوية Docker خفيفة بلا شبكة، لو توفرت البيئة.
- `brain._estimate_tokens` تقدير تقريبي — يمكن ترقية إلى عدّاد أدق (tiktoken) أو
  عدّاد مبنى على مسافات/ترقيم.
- مراجعة سطراً بسطر لـ `schedule.py` / `builders.py` (تم إصلاح XML/HTML injection
  سابقاً، لكن لم تُراجع كلياً بعد).

## المحتوى المرفق
- الكود المصدر كاملاً + اختبارات 55 + `README` v2.3.
- `projects/mastery/_library/*.py` — أمثلة فعلية لبرمجيات مكتوبة ومُختبَرة ذاتياً.
- `output/mastery_report.md` — تقرير حالة المحرك.
- **مستثنى عمداً**: `.env` (مفاتيح حية)، `logs/`، `memory/`، `data/`، `reports/`,
  `__pycache__`، `.pytest_cache`.

## ما هذا المشروع؟
وكيل ذكاء اصطناعي ذاتي يعمل على ويندوز بـ Python 3.14، مزوّد "بأدمغة" متعددة
(Gemini + Groq عبر واجهات HTTP، وأساس للـ Ollama). يبحث، يقرأ، يكتب ملفات،
ينفّذ أوامر آمنة، ويركض مهام ليلية. كل التواصل بالعربية.

## بنية الكود (الملفات الأساسية للفحص)
- `selfrunner.py` — حلقة الوكيل الرئيسية: تنفيذ أوامر، أدوات، تقارير. **الأهم أمنياً.**
- `brain.py` — إدارة المزودين (hybrid، ميزانية تكلفة يومية، تراجع).
- `webtools.py` — بحث وحجب URLs (SSRF-safe) وجلب صفحات.
- `skills.py` — تعلّم مهارات جديدة عبر بحث + تكوين نظام بحثي.
- `autopilot.py` — تحسين ذاتي مستقل (مقيّد على مجلد projects/ فقط).
- `schedule.py` — جدولة مهام ليلية (بناء XML مُهرَّب ضد الـ injection).
- `builders.py` — توليد مشاريع ويب/بايثون (ترميز HTML وآمن ضد injection).
- `chat_cli.py` — محادثة تفاعلية (تستخدم الذاكرة وترصد حضور المستخدم).
- `memory_bank.py` — ذاكرة بنك معرفي مع تقليم.
- `orchestrator.py` — تقسيم المهام الكبيرة وتنفيذ موازٍ.
- `daily_summary.py` — ملخص صباحي.
- `ollama_manager.py` — إدارة Ollama محلياً.
- `mastery.py` — **جديد**: محرك إتقان يعمل أثناء غياب المستخدم (انظر أدناه).
- `tests/test_selfrunner.py` — 55 اختباراً (Core + أمني + master) + 1 شبكي اختياري.

## ما أُصلح بناءً على المراجعة السابقة (Claude Code)
1. **تجاوز القائمة البيضاء رفض** — `_is_safe_command` يمنع الآن `-c/-e/-m/-p` لأي
   مترجم معرّف في `EVAL_FLAGS`، ويمنع `curl/wget/sh/bash/cmd/powershell/telnet/nc`
   في `FORBIDDEN_COMMANDS`. التنفيذ عبر `_run_argv` (قائمة argv، لا سلسلة).
2. **`RUN:` في غير التفاعلي** — سلو `SELFRUNNER_AUTORUN=ask` يرفض الآن صراحة
   (يكتب رسالةً أن الوضع غير تفاعلي ولا يوجَّه إلا بـ `allow`).
3. **SSRF/file://** — `_is_safe_url` يسمح فقط بـ http/https، ويحسم DNS
   (`ipaddress.is_global`)، ويرفض localhost/خاص/ميتاداتا AWS.
4. **حقن عبر نتائج الأدوات** — مخرجات أدوات الويب تُغلّف بـ `TOOL_OUTPUT_MARKER`
   وتُمرَّر كنص غير موثوق عبر `_as_tool_result` لتمييزها عن الأوامر.
5. **قراءة `.env*` ممنوعة** — `BLOCKED_FILENAMES` تمنع الوكيل من قراءة/إرفاق
   أي ملف `.env` أو `*.pem` أو `eval/dev_quote` إلخ.
6. **XML injection** — `_build_xml` يستخدم `xml.sax.saxutils.escape` لكل القيم.
7. **مفتاح Gemini لا يمر في URL** — عبر header `x-goog-api-key` فقط.
8. **Hybrid timeout** — `as_completed` داخل try/except يدير انقضاء المهلة.
9. **ميزانية تكلفة يومية** — `brains` يحسب التكلفة فعلية بـ `_perf_total()`
   ومتغيّر `MAX_COST_USD` (افتراضي 2.0$) كأثر على تعليق عندما في البيانات؟
   — غير مرتبط: يعطل المزودات المدفوعة عند تجاوز السقف.

## الجديد في هذه النسخة: محرك الإتقان (mastery.py)
- يعمل أثناء غياب المستخدم: يتعلم نظرية بدل "موضوع اليوم" من 8 مسارات
  (secure-coding, defensive-web-security, cryptography, threat-modeling,
  advanced-algorithms, ml-ai, system-design, hardening)، كل مسار 4 مواضيع،
  من مستوى 1 إلى خبير 5.
- **توليد وتطوير ذاتي آمن:** يطلب من العقل توليد مكتبة بايثون + اختبارات
  بصيغة `MODULE_START/END` و`TESTS_START/END`، يكتبها في `projects/mastery/`
  ثم يشغّل `pytest` عليها — **ولا يُقبل أي شيء إلا إذا نجحت الاختبارات**.
- **حلقة تصحيح ذاتي:** لو فشلت الاختبارات، تُمرَّر مخرجات الفشل للنموذج لتصحيحها
  (محاولتان). كل مكتبة نجحت تُضاف إلى `projects/mastery/_library/`.
- **توقف ذكي عند حضورك:** `chat_cli` و`selfrunner` (التفاعلي) يستدعيان
  `mark_user_active/away`؛ والحلقة تفحص علامة الحضور كل 30 ثانية
  (`POLL_USER_EVERY`) فتتوقف وتنتظر حتى تغيب. `mastery.stop` إيقاف يدوي.
- ميزانية: `SELFRUNNER_MAX_MASTERY_CYCLES` (افتراضي 8) و سقف التكلفة اليومي.
- CLI: `run | status | report | stop | resume`.

## ملاحظات أمنية مهمة للمراجعة
- **القرار الهندسي المتعمد:** مفاتيح API الحقيقية باقية في `.env` الحي (ليشتغل
  النظام فعلياً) — وتُحمى من الوكيل ومن القراءة، وتُستثنى من هذ الدفعة.
  افحصوا إن كان للأفضل فصلها أو تقييدها أكثر.
- منهج الإتقان **دفاعي/قانوني** حصراً — لا يحتوي أي هجوم فعلي على أنظمة الغير.
- `webtools._fetch` تسمح بجلب أي http(s) عام؛ لاحظوا أوقات الـ timeout وحدود.
- المراجعة السابقة لاحظت `best_headers` في `builders.py` — أُصلح بالـ escaping.
- الشحن ثنائي UTF-8: `webtools.py` و`schedule.py` وغيرها؛ `duckduckgo_search`
  أعيدت تسميتها `ddgs` — المتشغّل يحاول الجديد ثم القديم ثم HTML fallback.

## المتغيرات البيئية المدعومة
- `GEMINI_API_KEY`, `GROQ_API_KEY` (أحياء)، `OLLAMA_HOST` (اختياري).
- `SELFRUNNER_MODE` (ask/allow), `SELFRUNNER_MAX_COST_USD`,
  `SELFRUNNER_MAX_MASTERY_CYCLES`, `SELFRUNNER_AGENT_NAME`.

## تشغيل الفحوصات
```bash
python -m pytest tests/ -v        # 55 اختباراً (+ شبكي اختياري بـ SELFRUNNER_NETWORK_TESTS=1)
python mastery.py status          # حالة الإتقان
python mastery.py report          # تقرير المكتبات المولّدة ذاتياً
```

## استثناءات هذه الحزمة (غير مضمّنة عمداً — خصوصية/إعادة توليد)
`.env` (مفاتيح حية)، `logs/`، `memory/`، `data/` (حالة الإتقان والبحث)،
`reports/`، `__pycache__/`, `.pytest_cache/`. تضمّنت `output/mastery_report.md`
و`projects/mastery/_library/*.py` كأدلة عمل فعلية.