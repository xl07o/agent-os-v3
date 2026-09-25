# موظف الليل - SelfRunner v3.0 (Autonomous AI Employee)

> **⭐ Ultra Agent (JARVIS):** الواجهة الموحّدة الجديدة والحالة الحقيقية الصادقة
> لكل القدرات موثّقة في **[`ULTRA_AGENT_V3.md`](ULTRA_AGENT_V3.md)**.
> التشغيل السريع: `python -m agent_os` (واجهة تفاعلية) ·
> `python -m agent_os.ultra status` (جاهزية النظام).
> المعمارية: **الذاكرة أقوى من التوازي** — عقلٌ يتذكّر ويتقنى مع الوقت.


وكيل ذاتي (AI agent) **عام تماماً وبلا حدود**. أي مهمة تطلبه إياها ينفذها بنفسه:
يبني، يحل، يصلح، يفتح مشاريع، يدير ملفات، يبحث، يتعلم, ويشغّل أوامر —
ثم يسلّمك تقريراً كاملاً ولوحة عرض لكل ما أنجزه.

## ✨ المزايا الجديدة في v3.0

- **Checkpoint System**: لو طفى الجهاز يكمل من نفس الخطوة بالضبط
- **Failure Learning**: كل فشل يتحول لقاعدة وقائية واختبار دائم
- **Dream Mode**: وأنت نايم يستكشف ويجرب ويترك لك تقرير الصباح
- **ROI Brain**: يرتب المهام حسب القيمة الحقيقية مو مجرد FIFO
- **Self-Evolving**: يراقب نفسه ويحسن أداءه تلقائياً
- **Agent Constitution**: دستور داخلي مع Validator
- **Why Engine**: يسجل سبب كل قرار - تسأله بعد شهر ويجاوبك
- **Morning Brief**: تقرير صباحي ذكي بكل ما حدث
- **Knowledge DNA**: كل معلومة لها مصدر + ثقة + دليل + تاريخ
- **Opportunity Radar**: يبحث دورياً عن فرص ويقيّمها

## ✨ المزايا السابقة في v2.0

- **الأوركسترا**: يقسم المهمة الكبيرة لخطوات صغيرة وينفذها بترتيب منطقي
- **الذاكرة الخارقة**: يتذكر كل ما تعلمه ويربطه بالسياق تلقائياً
- **هجين حقيقي**: يسأل عقلين ويقارن فعلياً ويأخذ الأفضل
- **أمان محسّن**: قائمة أوامر بيضاء + منع الكتابة للمسارات الحساسة
- **Retry logic**: لا يفشل بسبب مشاكل الشبكة
- **Rate limiting**: لا يتغدى حدود الـ API
- **بصمة المهارات**: كشف التكرار قبل حفظ مهارة جديدة
- **تقييم جودة المصادر**: ترتيب الروابط حسب الموثوقية

## ما يقدّمه

- **تنفيذ أي طلب**: موقع، تطبيق، سكربت، لعبة, مهمة نظام, أي شيء.
- **بحث ذاتي**: يبحث في محركات البحث (DuckDuckGo/Groq) عن أي أداة/حزمة/مهارة.
- **تعلم ذاتي**: يجهل شيئاً → يتعلمه بنفسه، يخزنه كمهارة، ويستخدمه لاحقاً.
- **ذاكرة متراكمة**: يزداد خبرة مع كل جلسة.
- **لوحة عرض**: صفحة واحدة تجمع تقاريرك ومشاريعك وأبحاثك ومهاراتك.
- **عقل لا محدود**: نظام متعدد المزودين يختار تلقائياً الأنسب لكل مهمة.

## نظام العقل المتعدد

| المزود | مجاني؟ | الدور |
|--------|--------|-------|
| Ollama (محلي) | نعم 100% | الأساسي المجاني - لا يحتاج مفتاحاً |
| Google Gemini | نعم (free tier) | سريع وقوي |
| Groq | نعم (free tier) | فائق السرعة |
| NVIDIA NIM | نعم | نماذج مفتوحة |
| OpenRouter | فيه نماذج مجانية | بوابة لنماذج كثيرة |
| DeepSeek | رخيص جداً | قوي بالمنطق والبرمجة |
| Mistral | نعم (free tier) | مجاني إضافي |
| Claude/Anthropic | لا | الأقوى للمهام الصعبة |
| OpenAI | لا | بديل ووسائط |

**كيف أضيف مفتاحاً؟** افتح `.env` وضع مفتاحك. المزود يدخل تلقائياً.
تحقق بـ `python selfrunner.py --status`.

## التثبيت

1. ثبّت **Python 3** من python.org.
2. ثبّت **Ollama** من https://ollama.com ثم:
   ```
   ollama pull llama3.1
   ```
3. ثبّت الاعتماديات:
   ```
   pip install -r requirements.txt
   ```
4. اختياري: انسخ `.env.example` إلى `.env` وأضف مفاتيحك.
5. شغّل الاختبارات للتأكد:
   ```
   pip install pytest
   python -m pytest tests/ -v
   ```

## التشغيل

```bash
python selfrunner.py "ابنِ لي موقعاً متكاملاً"   # تنفيذ مهمة
python selfrunner.py                             # تفاعلي
python selfrunner.py --status                    # جاهزية العقول
python selfrunner.py --dashboard                 # لوحة العرض
python selfrunner.py --skills                    # قائمة المهارات

# الأوركسترا (المهام الكبيرة)
python orchestrator.py "ابنِ نظاماً كاملاً لإدارة المحتوى"

# محادثة مباشرة
python chat_cli.py

# تحقق من Ollama
python ollama_manager.py status
python ollama_manager.py pull llama3.1

# إدارة الذاكرة
python memory_bank.py stats          # إحصائيات الذاكرة
python memory_bank.py search "كيف أصلح"   # بحث في الذاكرة
python memory_bank.py prune          # تنظيف الذاكرة القديمة
```

أو ضغطة واحدة على `start.bat` (فيه 11 خياراً).

## التشغيل التلقائي كل ليلة

```bash
python schedule.py --time 02:00 --task "مهمتك الليلية"
python schedule.py --list
python schedule.py --delete
```

## محرك الإتقان (أثناء غيابك)

خلال غيابك يتعلم وحدك مهارات متقدمة، يبني برمجيات لنفسه، ويختبرها ذاتياً:
فقط المكتبات التي تنجح اختباراتها تُقبل ويترقّى مستواها.

```bash
python mastery.py run        # حلقة الإتقان المستمرة (تتعرف على عودتك وتتوقف)
python mastery.py status     # حالة المستويات والمناهج
python mastery.py report     # تقرير كامل بالمكتبات المولّدة
python mastery.py stop       # إيقاف يدوي
python mastery.py resume     # استئناف
```

**توقف ذكي:** ما إن تعود وتفتح المحادثة (`chat_cli`) أو وضع المهام (`selfrunner`) —
حتى يكتشف وجودك خلال ثوانٍ ويوقف التعلم ليعود لك. وستكمل من حيث وقفت أول ما تغيب.

**مناهج إتقان متعددة:** البرمجة الآمنة، التحصين الدفاعي للويب، أسس التشفير،
نمذجة التهديدات، الخوارزميات المتقدمة، الذكاء الاصطناعي، النظم الموزعة، تحصين الأنظمة.
كل مسار يتدرج من مستوى (1) إلى خبير (5) مع بناء مكتبة عملية تُختبر تلقائياً.

**التطوير الذاتي:** كل دورة ناجحة تضيف مكتبة بايثون جديدة مولّدة ومُختبَرة
إلى `projects/mastery/_library/` — مكتبة ترتقي نفسها بنفسها.

## أوامر الوكيل

`SEARCH:` / `LEARN:` / `SKILLS` / `READ:` / `WRITE:` / `ATTACH:` / `LIST` / `RUN:` / `STATUS` / `DONE`

## نظام الأوركسترا (الجديد)

يقسم المهمة الكبيرة إلى خطوات، ينفذ كل خطوة كقــلة منفصلة، ثم يجمع النتائج في تقرير شامل.

```
المهمة: "ابنِ نظام إدارة محتوى كامل"
  ├─ الخطوة 1: تخطيط البنية
  ├─ الخطوة 2: بناء الواجهة
  ├─ الخطوة 3: بناء الخادم
  └─ الخطوة 4: ربط وتكامل
```

## نظام الذاكرة الخارق (الجديد)

- **الذاكرة المتجهة**: يخزن معلومات ويسترجعها حسب الأهمية
- **البحث الذكي**: يجد المعلومة المناسبة للسياق الحالي
- **التنظيف التلقائي**: يحذف المعلومات القديمة غير المهمة

## المجلدات

- `projects/` — المشاريع
- `reports/` — تقارير المهام
- `output/` — لوحة العرض + نتائج الأبحاث
- `skills/` — المهارات المتعلمة
- `memory/` — الذاكرة
- `logs/` — السجلات
- `tests/` — الاختبارات

## الأمان في v2.0

- ✅ قائمة أوامر بيضاء (لا ينفذ أي أمر عشوائي)
- ✅ منع ربط الأوامر (`&&`, `;`, `|`)
- ✅ منع الكتابة في المسارات الحساسة (Windows, System, etc)
- ✅ لا `shell=True`
- ✅ `.gitignore` يحمي `/.env` و `__pycache__`

## طبقة أمان v2.1 (بعد مراجعة خارجية سطراً بسطر)

- ✅ **عزل الكود المولَّد ذاتياً** (mastery): حارس AST يرفض أي `import`/استدعاء خطير
  (`os, subprocess, socket, eval, exec, __import__...`) قبل الوصول للقرص، + حد 400 سطر،
  + تشغيل بـ `python -B -p no:cacheprovider` ومهلة 60 ثانية فقط.
- ✅ **إغلاق DNS rebinding** (webtools): حلّ DNS **مرة واحدة** وتثبيت الـ IP الناتج
  — الاتصال نفسه (http و https) يذهب للـ IP المثبَّت مع SNI/Host الأصلي،
  وأي تحويل (redirect) يعاد فحصه وتثبيته من جديد.
- ✅ **فحص أوامر منطقي** بدل regex هش: تباينات "القوة" (`-r -f` / `--recursive`
  / `/s /q` ...) تُرصد منطقياً على وسائط مقسّمة بأي صياغة.
- ✅ **realpath** في فحص المسارات — تحل الروابط الرمزية قبل المقارنة (لا `..` يُلتفّ).
- ✅ **تنقية أسرار** من السجلات: أنماط `sk-`, `AIza`, `gsk_`, Bearer/key=value تُستر
  قبل أي طباعة أو حفظ.
- ✅ **قفل** على cache الويب (أمان خيوط التشغيل المتوازي).
- ✅ اختبارات انحدار تلقائية تغطي كل ما سبق (42 اختباراً).

## طبقة أمان v2.2 (المرور الثالث — تعميق المراجعة)

- ✅ **تحصين المهارات** (skills): كل دوال تعديل/قراءة المهارات
  (`delete_skill`, `update_skill`, `get_skill`, `get_skill_info`) تمر الآن عبر فحص
  `_safe_skill_dir` — تعقيم صارم + realpath مع الرفض القاطع لأي خروج عن `SKILLS_DIR`
  (منع path traversal / `rmtree` عشوائي).
- ✅ **كتابة ذرية لكل JSON**: `brain_perf.json`, فهرس المهارات, الذاكرة,
  و `mastery_state.json` — تُكتب لملف مؤقت ثم `os.replace`؛ لا ملف مكسور
  ولا فقدان تراكمي لميزانية التكلفة عند انقطاع مفاجئ.
- ✅ **موديل Anthropic محدَّث** افتراضياً (`claude-sonnet-4-5`) ويبقى قابلاً
  للتغيير عبر `ANTHROPIC_MODEL` في `.env`.
- ✅ **لوحة العرض بلا تسريب مسار**: روابط نسبية بدل `file:///` — تتشارك لوحة
  `dashboard.html` بأمان دون كشف اسم المستخدم ومسار الجهاز.
- ➕ **حكم دلالي اختياري للهجين**: عند `SELFRUNNER_HYBRID_JUDGE=1`، مزود ثالث
  خفيف يقرر «أيّ الردّين أدق» بدل نقاط الشكل — ويعود تلقائياً للتقييم الشكلي
  عند أي فشل. (معطّل افتراضياً لتجنّب تكلفة إضافية)
- ✅ اختبارات الانحدار غطت الجولة الثالثة أيضاً (46 اختباراً).

## طبقة أمان v2.3 (المراجعة الشاملة — 40 ملاحظة)

- ✅ **حقن أوامر الـ batch** (`start.bat`): اقتباسات المدخل تُجرد، ثم تُمرَّر القيمة
  بالتمديد المؤجل `!var!` — أُغلق خطأ الاقتباس الذي كان يفتح أمراً ثانياً،
  وعولج خطأ خفي كان يُفرّغ المهمة قبل قراءتها.
- ✅ **حقن كود Lua** (`builders.py`): اسم خريطة Roblox يُعقَّم ضد الاقتباسات
  والفواصل والميلات — لا `os.execute` ولا كسر للسلسلة النصية.
- ✅ **استبدال أوامر bash** (`$((`, `$[`, `<(`) مرفوضة + الاقتباسات غير المتوازنة
  = أمر غير آمن (لا fallback ساذج يُخفي فلاق -c).
- ✅ **مجلدات النظام على كل الأقراص** محظورة (لا `C:\Windows` فقط)، وقيود
  `list_project_files` تمنع كشف أي ملف يفلت عبر رابط رمزي.
- ✅ **ذاكرة بنك** (`memory_bank`): كتابة ذرية وفهرسها أيضاً.
- ✅ **Rate-limiter وقفل Cache** للويب (خيوط آمنة).
- ✅ **قراءة استجابة مضبوطة الحجم** (لا إهلاك ذاكرة) + **فحص Content-Type**
  (لا تنزيل ملفات ثنائية كنص) + محلِّل HTML أقوى عند توفر lxml.
- ✅ **محادثة متصلة فعلاً** (`chat_cli`): جلسة عقل واحدة عبر المحادثة كاملة.
- ✅ **ميزانية التكلفة يومية**: تُصفّر تلقائياً بعد منتصف الليل (لا توقف مزوداً
  للأبد) + مهلة `as_completed` مُوافقة للإعدادات + تجاوز الـ hashes بأقدمها لا عشوائياً.
- ✅ **تقرير الإتقان** بمسارات نسبية (لا كشف لحرف المستخدم) + زخم XP يعمل فعلاً.
- ✅ **متنوعة**: روابط اللوحة `rel="noopener noreferrer"`، بصمة SHA-256، بحث ثانٍ
  مشروط، حد مهمة سخي مضبوط، تعقيم أسماء نماذج Ollama، `--user` كاحتياط للـ pip،
  مهلة API، و`.gitignore` يسمح بمصادر اختبارات JSON.
- ➡️ **تجاهل متعمد حسب رغبتك**: السجلات تنمو بلا حدّ (`#10/#14`) — نمو لا محدود.
- ✅ اختبارات: **55 نجحت + 1 شبكي يُتخطى افتراضياً** (فعّله بـ `SELFRUNNER_NETWORK_TESTS=1`)
  مع تغطية جديدة لأوتوبايلوت والملخص والمجدول والمنسّق والمهمات.

## ملاحظة

الوكيل يجهّز وينفّذ كل شيء تقنياً. لكن الأمور اللي تتطلب هوية/حسابات/مسؤولية نهائية
(حسابات مالية، شراء، التزام) تبقى بيدك — لا يمكن لأي وكيل تنفيذها نيابة عنك.
=======
# ai agent



## Getting started

To make it easy for you to get started with GitLab, here's a list of recommended next steps.

Already a pro? Just edit this README.md and make it your own. Want to make it easy? [Use the template at the bottom](#editing-this-readme)!

## Add your files

* [Create](https://docs.gitlab.com/user/project/repository/web_editor/#create-a-file) or [upload](https://docs.gitlab.com/user/project/repository/web_editor/#upload-a-file) files
* [Add files using the command line](https://docs.gitlab.com/topics/git/add_files/#add-files-to-a-git-repository) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://gitlab.com/idkgroupproject/ai-agent.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

* [Set up project integrations](https://gitlab.com/idkgroupproject/ai-agent/-/settings/integrations)

## Collaborate with your team

* [Invite team members and collaborators](https://docs.gitlab.com/user/project/members/)
* [Create a new merge request](https://docs.gitlab.com/user/project/merge_requests/creating_merge_requests/)
* [Automatically close issues from merge requests](https://docs.gitlab.com/user/project/issues/managing_issues/#closing-issues-automatically)
* [Enable merge request approvals](https://docs.gitlab.com/user/project/merge_requests/approvals/)
* [Set auto-merge](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)

## Test and Deploy

Use the built-in continuous integration in GitLab.

* [Get started with GitLab CI/CD](https://docs.gitlab.com/ci/quick_start/)
* [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/user/application_security/sast/)
* [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/topics/autodevops/requirements/)
* [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/user/clusters/agent/)
* [Set up protected environments](https://docs.gitlab.com/ci/environments/protected_environments/)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.
>>>>>>> c6bfd144533b6f56c0214829bd0b06ac625f4e46
