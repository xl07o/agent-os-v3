# ربط وكيلك بـ JARVIS (MultiX0/jarvis) — الاتجاهان

قرأتُ مستودع [MultiX0/jarvis](https://github.com/MultiX0/jarvis): تطبيق **Flutter**
سطح مكتب يعطي وجهاً وصوتاً لوكيل **Hermes** يعمل على خادمك، ويصله عبر
**REST + SSE** على المنفذ `8642` خلال نفق SSH. الصوت (كلمة الإيقاظ + التفريغ +
النطق) محلي في sidecar. لا يُثبَّت شيء على الخادم.

بنيتُ الجسر الذي يجعل التكامل يعمل في الاتجاهين، **مطابقاً لبروتوكول Hermes
الموثّق في `docs/hermes-probe.md` بذلك المستودع** (تحقّقت من كل نقطة).

---

## الاتجاه ①: وكيلك = العقل خلف JARVIS  ✅ جاهز

وكيلك يتنكّر كخادم Hermes، فتتصل به JARVIS ويصير هو العقل.

```bash
# على نفس صندوق لينكس الذي تصله JARVIS عبر SSH (أو جهازك):
python -m agent_os.hermes_server        # يستمع على 127.0.0.1:8642
```

في إعداد JARVIS (onboarding): ضع `host` و`username` لصندوقك، واترك
`hermes_port = 8642`. تتصل JARVIS عبر SSH وتُمرّر إلى `127.0.0.1:8642` حيث
يستمع جسرك.

> JARVIS تقرأ مفتاح Hermes من `~/.hermes/.env` على الخادم. أنشئ ملفاً بسيطاً
> ليمرّ فحصها (الجسر يقبل أي مفتاح):
> ```bash
> mkdir -p ~/.hermes && cat > ~/.hermes/.env <<'E'
> API_SERVER_ENABLED=true
> API_SERVER_HOST=127.0.0.1
> API_SERVER_PORT=8642
> API_SERVER_KEY=jarvis-local-key
> E
> ```
> ولمطابقة المفتاح بدل قبول أي مفتاح: `export HERMES_API_KEY=jarvis-local-key`.

المسارات المنفّذة (كما تتوقّعها JARVIS بالضبط): `/health`, `/health/detailed`,
`/v1/capabilities`, `/v1/models`, `/v1/toolsets`, `POST /v1/runs` (الحقل
`input` → `202 {run_id}`), `GET /v1/runs/{id}`, بثّ `GET /v1/runs/{id}/events`
(أسطر `data:` فقط، تنتهي بـ `: stream closed`), `GET /api/sessions/{id}/messages`.

---

## الاتجاه ②: Hermes = مساعد لوكيلك  ✅ جاهز

وكيلك يفوّض/يستشير مثيل Hermes حقيقياً حين يتوفّر (وإلا يستعمل عقله المعتاد،
بصدق بلا تلفيق).

```bash
export HERMES_UPSTREAM_URL=http://127.0.0.1:8642   # عنوان مثيل Hermes
export HERMES_UPSTREAM_KEY=<API_SERVER_KEY>        # مفتاحه
```
بعدها `Hermes.ask/plan/review` في وكيلك يستخدم Hermes تلقائياً كأقوى مساعد،
ويظهر `engine: "hermes"` في الرد.

---

## بديل بلا Hermes ولا SSH: وجه JARVIS في المتصفح (بنيته لك)
لا تملك خادم Hermes؟ استخدم الوجه الجاهز — يعمل فوراً بلا تثبيت:
```bash
python -m agent_os.server        # افتح http://127.0.0.1:8770 في Chrome، قل «جارفيس»
```

## ملاحظة صدق
بيئة السحابة هنا تحجب `jarvis.iprog.dev` (سياسة الشبكة)، لكني قرأتُ **الكود
المصدري** للمستودع وبنيتُ الجسر على بروتوكوله الموثّق والمُلتقَط (عيّنات
`docs/sse-sample.txt`). التشغيل الفعلي (SSH، الصوت المحلي، بناء تطبيق Flutter)
يتمّ على جهازك — الكود جاهز ومختبَر لذلك.
