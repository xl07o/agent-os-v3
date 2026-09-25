# 🧠 البرومبت التام — تصميم موقع التحكم للوكيل (Agent OS · SelfRunner v3)

> هذا الملف هو المرجع الكامل. أرسله كاملًا إلى Claude (أو أي مساعد) لتصميم موقع تحكم يتواصل مع البوت.
> المعلومات أدناه **حقيقية ومستخرجة من كود التشغيل وبيانات حيّة فعلية** — ليست تخمينًا.
> كل ما يكتبه المُصمم يجب أن يبني عليه، لا أن يخترع أشكال بيانات جديدة.

---

## 0) المهمة الموكلة إلى المُصمّم (Instruction to the AI)

صمّم وبن NEXT: موقع ويب متكامل (لوحة تحكم + محادثة) يتواصل مع وكيل "Agent OS" الموصوف полностью في هذا الملف.
- البوت ثنائي اللغة، تفاعله بالعربية في الغالب — **الموقع يجب أن يكون RTL عربيًا أولًا** (واجهة عربية كاملة مع دعم إنجليزي اختياري).
- الهدف: المستخدم (شخص غير مبرمج) يفتح الموقع على جهازه وينجز كل شيء منه: يكلم الوكيل، يشوف أمواله وأهدافه ومشاريعه، ويدير نظام bug bounty (برامجه/خططه/تقاريره الجاهزة)، ويبيع الأداء طوال الوقت.
- الموقع **قارئ لبيانات حقيقية** وليس تجريبيًا: يقرأ ملفات JSON أسفلها "عقود البيانات" ويعرضها مباشرة، ويرسل الأوامر إلى توابع Python الموجودة فعلًا (سطر الأوامر أو دوال).
- **صفر كلمات مرور**، **صفر مفاتيح API مكشوفة في الواجهة**، **الرفع التلقائي للتقارير الأمنية ممنوع** (البشري يرفع بيده).
- التصميم: داكن هادئ، بطاقات، عصرية، بديهية لغير المبرمج.

---

## 1) من هو الوكيل؟

"Agent OS / SelfRunner" = وكيل ذاتي يتشغّل محليًا على Windows (Python 3.11+، كل المكتبات في `requirements.txt`)، يعمل بالأسطر والأوضاع الآلية. حاليًا 92 وحدة داخل `agent_os/` إضافة لـ 5 وحدات في `security_empire/`.

**دليل أنه يشتغل حقًا (نتائج مثبتة في المستودع):**
- pytest: **252 passed / 1 skipped** (~94 ثانية)
- `sandbox_test.py`: **76/76 PASS**
- `smoke_test.py`: **102/102 PASS**
- يوجد داخل الاختبارات اختبارات تلقائية التوليد (تولّدها وحدة `regression_writer` بنفسها).

**جدول الوصول (Entry Points):** كيف يتواصل المستخدم معه اليوم

| الواجهة | الأمر | ماذا تقدم |
|---|---|---|
| محادثة تفاعلية | `python selfrunner.py` | جلسة محادثة خطوة بخطوة مع العقل (حتى "DONE") |
| محادثة سريعة | `python chat_cli.py` | محادثة حية + أوامر سريعة `//بناء موقع` |
| تشغيل مهمة | `python agent_os/agent_os.py run "مهمتي"` | توجيه عبر ROUTER→PLANNER→EXECUTOR→CRITIC→VERIFIER |
| دورة الحياة | `python agent_os/kernel.py once` | نبضات قلب + أهداف + مالية + تحسين ذاتي كل 5 دورات |
| الوضع البعيد | `python mastery.py run` | 40 مسار تعلم حتى 24 دورة (قابل للإيقاف HARD_CAP) |
| الليلة بأمر واحد | `python employ.py night 120` | فحص → دورة → تحسين → تقرير صباحي |
| المال | `python agent_os/finance_intel.py report` | إيرادات/مصروف/ROI |
| قائمة أنظمة | `python agent_os/agent_os.py systems` | عرض كل دوائر العمل |
| لوحة فحص | `python agent_os/dashboard.py state` | نص حالة اللقطة |

**أوامر المحادثة داخل selfrunner (14):** `SEARCH: LEARN: READ: WRITE: RUN: CONTROL: SCREENSHOT: ATTACH: SKILLS: LIST: STATUS: SYSINFO: STRATEGY: SUGGEST:`
**صمامات أمان:** قائمة أوامر مسموحة/ممنوعة للتنفيذ، حجب `.env` وأسماء ملفات حساسة، طلب إذن قبل أي `RUN:` (`SELFRUNNER_AUTORUN=ask|allow|deny`)، حارس SSRF يمنع loopback/خاص، فاحص أسرار.

---

## 2) العقل (مزودو الذكاء — 8)

الاختيار تلقائي (`best_available`): مجاني أولًا ← الأرخص ← الأقوى. أنماط العقل: `hybrid` (افتراضي: سؤال مزودَين ومقارنة)، `smart`، `fastest`، `strongest`، `ollama`. سقف تكلفة يومي `SELFRUNNER_MAX_COST_USD` (افتراضي $2).

| مزود | يفضّل لـ | الحالة الحالية (نن 2026) |
|---|---|---|
| Gemini | عام مجاني | ✅ يعمل حي (نموذج gemini-3.6-flash) |
| NVIDIA NIM | نماذج أمنية قوية | ✅ يعمل حي (nemotron-3-ultra) |
| Ollama محلي | بلا إنترنت | يعمل فقط إذا الخادم الحي على 11434 |
| Groq | سرعة | **محجوب حاليًا** (خطأ 403/1010 من الطرف) |
| DeepSeek | أرخص مدفوع | يحتاج رصيد (ضبط cost_cap) |
| Anthropic/OpenAI/OpenRouter | قوة | متاح إن وُجد مفتاح له رصيد (نجح OpenRouter بدون رصيد فعلي) |

> للمصمّم: قم بإظهار في الموقع "المزود النشط الآن + تكلفة الرسالة + الرصيد المتاح"، وأنواع النشاط (live/failover). **لا تُظهر القيم السرية أبدًا** — اعرض "متاح/غير متاح" فقط.

---

## 3) دوائر العمل (14 — router في `agent_os/agent_os.py`)

| الخلية | ما تفعله (و dossier ملفاتها) |
|---|---|
| `news_intel` | أخبار HN/TechCrunch/SecurityWeek + CVE → `world_state.json` |
| `browser_agent` | متصفح حقيقي: فتح/نقر/كتابة/استخراج نص وروابط |
| `world_model` | لقطة كل شيء: مشاريع/منتجات/مال/أهداف/أدوات/طلبات → `world_state.json` |
| `goal_manager` | أهداف ذاتية التوليد: هدف→استراتيجية→مشاريع→مهام→تنفيذ→تحقق→نتيجة → `goals.json` |
| `tool_registry` | اكتشاف/مراجعة أمنية/تثبيت أدوات → `tool_registry.json` |
| `self_improve_engine` | قياس الضعف→توليد التعديل→فرع معزول→pytest→إيداع → `data/agent_os/_improve/*` |
| `product_factory` | 12 قالب منتج حقيقي → `products.json` + `output/products/` |
| `devops_agent` | git/github/docker/نشر/مراقبة/Rollback (argv فقط بلا قشرة) |
| `chief_staff` | تقرير الصباح المرتب → `morning_plan.json` |
| `approval_center` | قائمة طلبات موافقة بشرية → `requests.json` |
| `finance_intel` | الإيرادات/المصروف/أفضل مصدر → `finance.json` |
| `benchmark` | قياس ذكاء الوكيل 12 مجالًا + أضعف نقطة |
| `bounty_engine` | نظام المكافآت (بالأعلى) |
| `إنتاج مخرجات` | يسلّم ملف/تقرير في `output/` حسب القصد |

خريطة التوجيه (intent → خلايا): research→[news_intel,browser_agent,world_model] · code→[goal_manager,tool_registry,self_improve_engine] · build→[product_factory,devops_agent,browser_agent] · operate→[chief_staff,goal_manager,approval_center] · finance→[finance_intel,world_model] · report→[chief_staff,finance_intel,benchmark,world_model] · security→[bounty_engine,world_model] · improve→[self_improve_engine,benchmark]

**وحدات أفرع داخل agent_os/** (كلها قد تهم الموقع): `cognition/` (intent_engine, counterfactual, confidence, capability_gap, learning_engine, consensus, pattern_miner) · `recovery/` (self_healer, loop_guard, attention_budget) · `evolution/` (daily_evolution, hypothesis_lab, self_consultation, blast_radius, regression_writer) · `orchestration/` (durable_queue, idempotency, smart_scheduler) · `strategy/` (owner_model, mission_planner) · `business/` (reinvestment_wallet, auto_products) · `security/` (network_policy, prompt_injection, proactive_shield) · `verification/` (digital_twin, health_graph) · `models/` (router, consensus) · `interface/` (negotiator)

---

## 4) نظام المكافآت — Bounty (الأحدث، كامل)

### 4.1 سحب البرامج من 6 منصات (bounty_sync.py)
الشركات تعلن "نبغى مراجعة ونعطي فلوس" على منصات، والوكيل يسحب الأدلة الرسمية للمنصات الست:

| منصة | ~عدد برامج حي | مصدر التغذية (أدلة رسمية محدثة بمجتمع موثوق) |
|---|---|---|
| hackerone | 447 | arkadiyt/bounty-targets-data → hackerone_data.json |
| bugcrowd | 278 | arkadiyt → bugcrowd_data.json |
| intigriti | 137 | arkadiyt → intigriti_data.json |
| yeswehack | 58 | arkadiyt → yeswehack_data.json |
| federacy | 35 | arkadiyt → federacy_data.json |
| immunefi | 239 | infosec-us-team/Immunefi-Bug-Bounty-Programs-Unofficial → projects.json |

### 4.2 سير عمل متكامل
`fetch_public(platform)` ← `normalize_record(platform, raw)` (يستخرج: name/url/max_payout/targets في النطاق/out_of_scope/type) ← `candidates([platforms], cap)` ترتيب تنازلي بالمكافأة ← `adopt(platform, index, cap_targets)` يخلق برنامجًا في `bounty_engine.add_program` مع قفل scope ومصدر تفويض موثق `public-policy:<platform>`.
- `_target_type` للأنواع؛ `_target_id` يقرأ مفاتيح target/uri/asset_identifier/identifier/scope/data/url/**endpoint** (هذا ما جعل intigriti يشتغل).
- فلترة: يمنع `*.wild`، CIDR، وأصول ios/android (الماسح HTTP لا يصيد عليها).

### 4.3 محرك النطاق والنتائج (bounty_engine.py)
- `in_scope(program, host)`: يسمح بالمطابقة التامة أو النطاق الفرعي (`a.b.com` ✓ عندما `b.com` في النطاق)؛ `*.domain`/`.domain` يستثني الجذر نفسه.
- `add_finding(program_id, host, title, severity, evidence)`: يرفض خارج النطاق؛ كشف التكرار بالـ host+title (الوثيقة `duplicate`)؛ `validated` إذا أدلة غير فارغة، وإلا `pending`.
- `attack_plan(program_id)`: **خطة الصيد** — 5 مراحل ملموسة (استخبارات سلبية → خريطة سطح → صيد بالعائد IDOR/BOLA أولًا → تحقق وتفريز → تقرير) مستمدة من "وضع الخبير الأمني" في عقل الوكيل.
- `prepare_drafts()`: يحوّل الإيجابيات المؤكدة إلى تقرير نهائي جاهز للرفع لكل منصة مع دليل الرفع اليدوي (title/severity/impact/PoC/remediation/كشف-أمني) → `bounty_drafts.json`. `approve_draft(id)`/`reject_draft(id)`.
- `report_markdown(program_id)`: تقرير تجميعي.

### 4.4 الحسابات (bounty_accounts.py)
- يخزن **الاسم المستعار (handle) فقط** + التوكن اختياري. **كلمات المرور مرفوضة نهائيًا** (راجع "قواعد صارمة").
- `SUBMISSION_MODE`: كل المنصات = `manual` — الرفع بيد البشر؛ لا يوجد "رفع آلي معتمد".
- `submission_guide(platform)`: خطوات الرفع الآمن + رابط النموذج + ملاحظة KYC للدفع.

### 4.5 سورس فحص (security_empire)
`recon.py` (DNS/lookup subdomains/headers) + `scanner.py` (XSS/SQLi/redirect/hdrs/ملفات حساسة) + `empire.py full_pipeline(domain)` + `report_writer.py` (مقدار مكافأة تقديرية + تقارير عربي/إنجليزي) + `bounty_tracker.py` (سجل الرفع: pending/accepted/paid/rejected).
> **تحفّظ تقني على المصمّم:** بعض الفروع البرمجية الحية للماسح تعتمد https مكتوبًا وبعض الدوال المفتاحية لفحص معاملات (XSS/SQLi) لم تُستخدم بعد لأنها ستحتاج تثبيت _safe_get; لا تبني واجهة تَعِد "فحص XSS حي" الآن دون إعادة هذه الأدوات.

---

## 5) عقود البيانات (الشريان الأهم — يقرأها الموقع)

كل القيم تحت `data/agent_os/` (المسار الحقيقي: `C:\Users\hhdjj\ai-agent\ai-agent-main\data\agent_os\`). في الاختبارات يستبدل ب `tests\_data_isolated\`.

### 5.1 `bounty_programs.json` — البرامج والنتائج
```json
{
 "programs": [
  {
   "id": 1,
   "name": "Adobe Public",
   "scope": ["stock.adobe.com","firefly.adobe.com","photoshop.adobe.com",
             "account.magento.com","repo.magento.com","magento.com",
             "portfolio.ccpsx.com","fonts.adobe.com","account.adobe.com",
             "auth.services.adobe.com","adobeid-na1.services.adobe.com",
             "ims-na1.adobelogin.com","federatedid-na1.services.adobe.com"],
   "rules": "سياسية INTIGRITI العلنية لبرامج المكافآت هي التفويض. ممنوع: إجراءات تخريبية أو حذف أو DoS/Phish، تجاوز النطاق المعلن، بيانات مستخدمين حقيقية. ابدأ فحصاً سلبياً أولاً، ثم نشطاً منخفض الأثر داخل النطاق فقط. البرنامج: https://www.intigriti.com/programs/adobe/adobepublic/detail",
   "destructive_rules": ["dos","phish"],
   "authorization_source": "public-policy:intigriti",
   "authorization_status": "owner_confirmed",
   "scope_locked": true,
   "created": "2026-09-13T00:31:44.912098"
  }
 ],
 "findings": [
  {
   "id": 3, "program_id": 1,
   "host": "app.example.com", "title": "IDOR: تعديل معرّف الحساب",
   "severity": "high",
   "evidence": "GET /api/users/1001 -> 200 ...",
   "duplicate_of": null,
   "status": "validated",
   "date": "2026-09-13T..."
  }
 ],
 "next_id": 2
}
```
الحالات الممكنة: `validated` | `pending` | `duplicate`.

### 5.2 `bounty_drafts.json` — التقارير الجاهزة
```json
{
 "drafts": [
  {
   "id": 1, "finding_id": 3, "program_id": 1,
   "platform": "intigriti", "severity": "high",
   "title": "IDOR: ...", "host": "app.example.com",
   "status": "ready",             // ready | approved | rejected
   "body": "# العنوان\n...PoC...\n...المعالجة...\n...كشف مسؤول...",
   "guide": "منصة: intigriti\n...\nرابط الرفع: https://app.intigriti.com/...\nخطوات الرفع الآمن...KYC...",
   "created": "2026-...", "approved_at": null
  }
 ],
 "next_id": 1
}
```

### 5.3 `bounty_accounts.json`
```json
{ "accounts": { "immunefi": { "handle": "my_handle", "token": "",
                               "mode": "manual",
                               "submit_url": "https://bugs.immunefi.com/..." } } }
```
> عند إظهار `token` في الموقع: اعرض 🟢/المخفى فقط، لا القيمة.

### 5.4 `goals.json`
```json
{ "goals": [ { "id":1, "title":"اكتب ملف ملاحظات في output", "objective":"",
  "priority":"medium","category":"general","auto":true,"status":"active",
  "strategy":"...","projects":[],"tasks":[],"verification":{},"outcome":"",
  "created":"...","updated":"..." } ], "next_id":2 }
```

### 5.5 `finance.json` (يُنشأ أول استخدام، قد يكون مفقودًا = فارغًا)
```json
{ "txns": [ { "category":"revenue", "amount":50.0, "income":true,
              "source":"bounty", "note":"...", "date":"2026-09-13" } ],
  "next_id":1, "self_earned_usd": 0.0, "ledger": [ ... ] }
```

### 5.6 `notifications.json`
```json
{ "items": [ { "level":"warn|critical|info", "title":"...", "message":"...", "time":"ISO" } ] }
```

### 5.7 `world_state.json` — لقطة للوحة الرئيسية
```json
{ "built":"...", "day":"2026-09-12", "goals":{"total":0},
  "subsystems":{ "agent_os.product_factory":{"count":12},
                 "agent_os.approval_center":{"count":7},
                 "agent_os.goal_manager":{"count":21}, ... },
  "products":0, "deploys":0, "tools":0, "requests_pending":0,
  "findings":0, "txns":0, "intel":{"news":5,"hn":8} }
```

### 5.8 `products.json` (product_factory)
```json
{ "products": [ { "name":"TestSaaS","type":"web",
   "path":"C:\\(...)output\\products\\TestSaaS","spec":"{\"name\":\"TestSaaS\"}",
   "built":"...", "status":"built", "tests_passed":null } ] }
```

### 5.9 `events.jsonl` — سجل الأحداث (سطر-سطر JSON)
```json
{ "time": "...", "level": "info", "source": "...", "event": "..." }
```

### 5.10 `requests.json` (approvals) — طلبات موافقة بشرية
```json
{ "requests": [ { "id":1, "title":"...", "detail":"...", "status":"pending|approved|denied","created":"..." } ] }
```

### 5.11 ذاكرة skills/mastery (بأماكنها)
`skills/` (الحالية) + `data/agent_os/skills.json` و `data/agent_os/mastery.json` (إن وُجدت).

---

## 6) الواجهات الحالية وما ينقص

| موجود | البارنport | ملاحظة |
|---|---|---|
| `agent_os/dashboard.py` | FastAPI اختياري 8787 (GET / /state /finance /goals /approvals /notifications /heartbeat) | يشتغل فقط إذا fastapi+uvicorn مضمّنة؛ يبدأ يدويًا |
| `dashboard.py` (root) | HTML ساكن → output/dashboard.html | ملف لا خادم |
| `autopilot.py` | **عميل** يتصل بـ `SELFRUNNER_PLATFORM` (افتراضي http://127.0.0.1:8082) | الخادم المضيف **غير موجود** حاليًا |
| `agent_os/agent_os_api.py` | CLI/وحدة (status/checkpoints/events/run/run_goal) | فرع `run()` مكسور (يتطلب `A.AgentOS()` غير موجود) — لا تستخدمه كما هو |

**الفجوة للمصمّم:** لا يوجد خادم HTTP ثابت يعرض الوكيل. الموقع الجديد هو الذي يستبدل أو يكمل هذا: (أ) خادم JSON API رفيع يغلّف توابع Python الحية (bounty_sync/bounty_engine/finance_intel/goals/notifications...) عبر استدعاء `python -m ...` أو دوال مباشرة، و(ب) واجهة محادثة تُشغّل `selfrunner` على المهمة وتبثّ الخطوات حيًّا (SSE أو استطلاع increment).

---

## 7) اشتراطات الموقع (راجعها للمصمّم صراحة)

1. **صفحة محادثة** (شبيه واتساب، RTL): إرسال مهمة → تدفّق خطوات (مهما كانت) → عرض ناتج `DONE` + زر تحميل المخرج. إظهار: المزود النشط، التكلفة، عدد الخطوات، الزمن.
2. **لوحة المال**: إيرادات/مصروف/صافي/ROI اليوم والشهر (من finance.json) + "أفضل مصدر ربح" تلقائي.
3. **لوحة الأهداف**: قائمة + حالة + إيقاف أي هدف ("إيقاف") + إنشاء هدف سريع → نقله إلى goal_manager.
4. **لوحة الموافقات**: طلبات pending ⟶ أزرار "موافقة/رفض" تكتب الحالة للوكيل.
5. **لوحة المكافآت**: 
   - برامج (تعرض من platform feeds بـ name/url/max_payout/count targets) مع زر "اعتماد" ⟹ `adopt`
   - كل برنامج معتمد: نطاقه + زر "خطة الصيد" ⟹ `attack_plan` + زر "فحص سطحي".
   - التقارير الجاهزة ⟸ `prepare_drafts` مع زر "عرض كامل + دليل الرفع" + `approve`/`reject`.
   - **تحذير صارم:** صفحة البجتي لا تعرض ولا تخزّن كلمة مرور؛ زر "رفع" يفتح رابط المنصة اليدوي فقط.
6. **لوحة الأنشطة/السجل**: من events.jsonl + checkpoints؛ كل حدث بزمنه ومصدره ومستواه.
7. **لوحة العالم**: world_state.json بطاقة واحدة شاملة (منتجات/أهداف/إيرادات/موافقات/أخبار).
8. **لوحة المنتجات**: products.json مع فتح مسار الملف الناتج من الجهاز.
9. **إعدادات**: اختيار أنماط العقل (hybrid/smart/fastest/strongest)، سقف التكلفة، إيقاف الوكيل مؤقتًا، عرض حالة مزودي الذكاء (فقط متاح/غير متاح).
10. **غير المطلوب**: تسجيل دخول معقد. تشغيل محلي شخصي = شاشة قفل بسيطة (حتى لا يلمسه أحد على الشبكة)؛ لو لزم الخادم يُفتح على 127.0.0.1 فقط ما لم يضبط المستخدم خلاف ذلك.

### قواعد صارمة (Soft Constraints — وضع المصمم يلتزم بها)
- ❌ لا تُرسل، لا تُخزن، لا تطلب كلمات مرور منصات المكافآت.
- ❌ لا تعرض قيم مفاتيح API (اعرض حالة فقط).
- ❌ لا تبّن "رفع تقرير أمني تلقائي" — الرفع يدوي دائمًا (حماية سمعة المستخدم).
- ✅ كل كتابة في ملفات بيانات الوكيل تتم حصريًا عبر دوال الوكيل الرسمية (وهي ذرّية atomic_write) — لا كسر صيغ.
- ✅ حفظ نسخ بسيط (export) بحيث لا يتضرر شيء.

### بنية مقترحة (for the designer)
- **App**: Next.js + React بالعربية RTL (كما المتفق على استخدام Next.js في هذا المشروع).
- **API**: خادم Node spin يفصل القراءة/الكتابة: 
  - GETs: يقرأ ملفات JSON أعلاه تحت `data/agent_os/` بعد `path.join` آمن (لا عبور مسار).
  - POST «مهمة»: يستدعي `python selfrunner.py "المهمة"` أو `python agent_os/agent_os.py run "..."` عبر subprocess مع مهلة، ويرجع `steps[]` ثم `final` (SSE اختياري).
  - POST adopt/plan/approve: يستدعي `python agent_os/bounty_sync.py ...` / `bounty_engine.py ...`.
  - مسار نسبي: افرض `ALLOWED_ROOT` ولا تسمح بمسار خارج `data/agent_os`.
- **جمالي**: داكن، بطاقات، خط عربي واضح، شارة توثيق "يعمل على البيانات الحية" في كل كرت.

---

## 8) أشياء مكسورة/تحفّظات يجب أن يعرفها المصمّم (حتى لا يبني على رمال)
- `agent_os_api.run()` مكسور (stub) — **لا** تغلّفه إلا بعد إصلاحه أو استخدام kernel.run_task بدلًا عنه.
- لا يوجد خادم دايم؛ استناد الموقع إلى القراءة المباشرة للملفات + subprocess للتوابع أكبر استقرارًا.
- Groq محجوب بيئيًا حاليًا؛ تمرير "غير متاح".
- نظام `security_empire` مكتمل البنية لكن جزء الفحص الحي للمعاملات (check_xss/etc) قابل للتحسين — لا تَعِد الموقع بفحص XSS حي.
- ذاكرة الاحتفال (`_improve/*`) كثيرة؛ لا تلمسها من الموقع (مساحة أعمال الوكيل).

---

## 9) تكليف نهائي (Final Instructions للمصمّم)
1. اقرأ هذا الملف كاملًا قبل أي كتابة سطر.
2. صمّم الصفحات المرقمة في القسم 7 مع عقود البيانات الفعلية من القسم 5.
3. قدّم:
   - خارطة المشروع (مجلدات)
   - شيفرة Next.js كاملة (صفحات + API routes + مكوّنات)
   - سكربت تشغيل واحد على ويندوز (مثل site/run_site.bat)
   - قائمة الـ deps مع أدنى سطر (بلا تعقيد زائد)
4. تجنّب أي تخمين في أشكال البيانات — استعمل الأسماء الحقيقية للمفاتيح أعلاه كلمة-بكلمة.
5. اختبر أنه يقرأ `bounty_programs.json` المرفق بالعينات أعلاه ويظهر "Adobe Public · intigriti · 17 نطاقًا مصرحًا".

— نهاية البرومبت المرجعي —