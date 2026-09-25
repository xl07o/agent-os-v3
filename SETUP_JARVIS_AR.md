# دليل تشغيل JARVIS كاملاً من الصفر (الطريق ②) — بالتفصيل

هذا الدليل يفترض أنك **لم تُثبّت أي شيء**. اتبعه سطراً سطراً.

---

## 🧩 كيف تتركّب القطع (افهم هذا أولاً)

```
[ تطبيق JARVIS ]  ──SSH──▶  [ جهاز Linux ]  ──▶  [ عقل وكيلك: hermes_server ]
   (ويندوز، الوجه               (WSL2 مجاناً        (بروتوكول Hermes على 8642)
    + الصوت)                     أو VPS)
```

- **تطبيق JARVIS**: تطبيق ويندوز (Flutter) = الوجه + الصوت + كلمة الإيقاظ.
- **جهاز Linux**: JARVIS يتصل به عبر SSH. المجاني = **WSL2** (لينكس داخل ويندوز).
- **عقل وكيلك**: `hermes_server` يعمل على Linux ويتكلّم بروتوكول Hermes، فتظنّه JARVIS خادمها.

> إن أردت الأسهل بلا كل هذا: الطريق ① (وجه بالمتصفح) — `python -m agent_os.server`.

---

# القسم أ — تجهيز جهاز Linux (WSL2 داخل ويندوز، مجاناً)

### أ-1) ثبّت WSL2
افتح **PowerShell كمسؤول** (Run as administrator) واكتب:
```powershell
wsl --install
```
أعِد تشغيل الجهاز إن طلب. سيُثبّت Ubuntu تلقائياً.

### أ-2) افتح Ubuntu لأول مرة
من قائمة ابدأ افتح **Ubuntu**. سيطلب إنشاء **اسم مستخدم** و**كلمة مرور** —
اكتبهما واحفظهما (ستحتاجهما في JARVIS لاحقاً). مثال: المستخدم `jarvis`.

### أ-3) حدّث النظام وثبّت الأدوات
داخل نافذة Ubuntu:
```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git openssh-server
```

### أ-4) نزّل مشروع وكيلك وشغّل الإعداد
```bash
git clone https://github.com/xl07o/agent-os-v3
cd agent-os-v3
git checkout claude/amazing-hypatia-4ylk9f
bash install.sh
```

### أ-5) أنشئ ملف مفتاح Hermes (ليمرّ فحص JARVIS)
```bash
mkdir -p ~/.hermes
printf 'API_SERVER_ENABLED=true\nAPI_SERVER_HOST=127.0.0.1\nAPI_SERVER_PORT=8642\nAPI_SERVER_KEY=jarvis-local-key\n' > ~/.hermes/.env
```

### أ-6) شغّل SSH داخل WSL (حتى تتصل به JARVIS)
```bash
sudo ssh-keygen -A
sudo service ssh start
```
> إن قال "port 22 in use" أو رفض، عدّل المنفذ:
> `sudo sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config && sudo service ssh restart`
> واستخدم المنفذ 2222 في JARVIS.

### أ-7) اعرف عنوان WSL (IP) والمستخدم
```bash
hostname -I        # مثال: 172.23.45.67  ← هذا عنوان الاتصال في JARVIS
whoami             # اسم مستخدم SSH
```
احفظ الرقم واسم المستخدم.

### أ-8) شغّل عقل وكيلك (اتركه يعمل)
```bash
cd ~/agent-os-v3
export HERMES_MENTOR=1      # يفعّل التطوّر المزدوج (Hermes يصحّح ويحدّث الذاكرة)
python3 -m agent_os.hermes_server
```
يجب أن ترى: `🧠 Hermes-compat ... على http://127.0.0.1:8642`.
**اترك هذه النافذة مفتوحة.** (لاحقاً نجعله يعمل تلقائياً.)

---

# القسم ب — تجهيز تطبيق JARVIS على ويندوز

### ب-1) ثبّت المتطلبات (ثلاثة أشياء)
1. **Git for Windows**: https://git-scm.com/download/win
2. **Flutter SDK**: https://docs.flutter.dev/get-started/install/windows
   (فُكّ الضغط، وأضِف مجلد `flutter\bin` إلى متغيّر البيئة PATH)
3. **Visual Studio 2022** (Community مجاني): أثناء التثبيت اختر حزمة
   **"Desktop development with C++"** (ضرورية لبناء تطبيق ويندوز).

### ب-2) تأكّد أن Flutter جاهز
افتح **PowerShell** جديدة:
```powershell
flutter doctor
```
يجب أن ترى ✓ عند Flutter و Windows و Visual Studio. أصلح أي ✗ يذكره.

### ب-3) نزّل تطبيق JARVIS
```powershell
git clone https://github.com/MultiX0/jarvis
cd jarvis
flutter pub get
```

### ب-4) جهّز الصوت (sidecar)
```powershell
python -m venv sidecar/.venv
sidecar\.venv\Scripts\python.exe -m pip install -r sidecar/requirements.txt
sidecar\.venv\Scripts\python.exe -c "import openwakeword.utils as u; u.download_models(model_names=['hey_jarvis'])"
```

### ب-5) نزّل أصوات Piper (عربي + إنجليزي) إلى `sidecar/models/piper/`
حمّل هذه الملفات وضعها في مجلد `sidecar\models\piper\`:
- `ar_JO-kareem-medium.onnx` و `.onnx.json`
- `en_GB-alan-medium.onnx` و `.onnx.json`

الروابط في `sidecar/README.md` بالمستودع (من huggingface piper-voices).

### ب-6) اختبر أن الجهاز جاهز
```powershell
sidecar\.venv\Scripts\python.exe sidecar/jarvis_voice.py --selftest
```
يخبرك بما يعمل وما ينقص. أصلح ما يذكره (غالباً الميكروفون أو صوت مفقود).

### ب-7) شغّل التطبيق
```powershell
flutter run -d windows
```

---

# القسم ج — الربط (شاشة الاتصال في JARVIS)

عند أول تشغيل تظهر شاشة اتصال، املأها:
- **Host / العنوان**: عنوان WSL من خطوة أ-7 (مثل `172.23.45.67`)، أو جرّب `127.0.0.1`.
- **Port (SSH)**: `22` (أو `2222` لو غيّرته في أ-6).
- **Username**: مستخدم Ubuntu من خطوة أ-2.
- **Password**: كلمة مرور Ubuntu.
- **Hermes port**: `8642` (اتركه كما هو).

سيمرّ الفحص صفّاً صفّاً:
```
SSH REACHABLE ✓   AUTHENTICATED ✓   HOST IDENTIFIED ✓
HERMES DETECTED ✓ (عقل وكيلك)   API KEY ACCEPTED ✓   TELEMETRY READING ✓
```
إذا صارت كلها خضراء → **وكيلك صار العقل خلف JARVIS**. قل «جارفيس» وجرّب أمراً.

---

# القسم د — التطوّر المزدوج + التشغيل التلقائي

- **التطوّر المزدوج**: فعّلته في خطوة أ-8 (`HERMES_MENTOR=1`). بعد كل أمر،
  يراجع النظام العمل ويحوّل التصحيح إلى **درس دائم** في ذاكرة وكيلك.
- **تشغيل العقل تلقائياً في WSL** (بدل تركه بنافذة): داخل Ubuntu:
  ```bash
  cp ~/agent-os-v3/tools/jarvis-brain.service ~/.config/systemd/user/ 2>/dev/null || true
  systemctl --user enable --now jarvis-brain 2>/dev/null || \
    echo 'HERMES_MENTOR=1 nohup python3 -m agent_os.hermes_server >~/jarvis-brain.log 2>&1 &' >> ~/.bashrc
  ```

---

# 🛠️ حلّ المشاكل الشائعة

| المشكلة | الحل |
|--------|------|
| `wsl --install` لا يعمل | فعّل «Virtual Machine Platform» و«WSL» من "تشغيل ميزات Windows"، ثم أعِد التشغيل |
| JARVIS: SSH REACHABLE أحمر | تأكّد `sudo service ssh start` في WSL، وجرّب IP من `hostname -I` |
| IP الـ WSL يتغيّر بعد إعادة التشغيل | أعِد تشغيل `sudo service ssh start` وحدّث العنوان في JARVIS |
| `flutter doctor` يشكو من C++ | ثبّت "Desktop development with C++" في Visual Studio |
| لا صوت خرج | تأكّد من وجود ملفات Piper في `sidecar/models/piper/` |
| HERMES DETECTED أحمر | تأكّد أن `python3 -m agent_os.hermes_server` يعمل في WSL على 8642 |

---

**تذكير:** الطريق ① (`python -m agent_os.server` + المتصفح) يعمل فوراً بلا أي من
هذا التعقيد — استخدمه لتجرّب الآن بينما تجهّز الطريق ②.
