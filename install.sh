#!/bin/bash
# install.sh — تثبيت Agent OS v3 بأمر واحد.
# الاستعمال:  bash install.sh
# آمن للتكرار (idempotent). لا يفشل إن غابت أداة اختيارية.
set -uo pipefail
cd "$(dirname "$0")"

echo "==================================================="
echo "  تثبيت Agent OS v3 (Ultra Agent / JARVIS)"
echo "==================================================="

PY=python3
command -v $PY >/dev/null 2>&1 || PY=python
echo "→ Python: $($PY --version 2>&1)"

echo "→ تثبيت الأساسي (نواة + اختبارات) …"
$PY -m pip install -q --disable-pip-version-check \
  pytest python-dotenv beautifulsoup4 lxml requests 2>&1 | tail -1 || true

echo "→ محاولة تثبيت الإضافات (تحكم الجهاز/الصوت — قد تفشل في بيئة بلا شاشة) …"
$PY -m pip install -q --disable-pip-version-check -r requirements.txt >/dev/null 2>&1 \
  && echo "   ✅ كل الاعتماديات" \
  || echo "   ⚠️ بعض اعتماديات الواجهة تُثبَّت على جهاز رسومي فقط — النواة تعمل بدونها"

# العقل (اختياري): إن وُجد Ollama نحمّل نموذجاً صغيراً مجانياً.
if command -v ollama >/dev/null 2>&1; then
  echo "→ Ollama موجود — تنزيل نموذج llama3.1 (قد يأخذ وقتاً) …"
  ollama pull llama3.1 >/dev/null 2>&1 && echo "   ✅ العقل المحلي جاهز" || echo "   ⚠️ تعذّر تنزيل النموذج"
else
  echo "→ (اختياري) لعقل أقوى: ثبّت Ollama من https://ollama.com ثم: ollama pull llama3.1"
  echo "  أو ضع مفتاح API مجاني في ملف .env"
fi

[ -f .env ] || { [ -f .env.example ] && cp .env.example .env && echo "→ أنشأت .env (عدّله لإضافة مفاتيح اختيارية)"; }

echo "→ فحص ذاتي شامل …"
PYTHONPATH=. $PY -m agent_os.selfcheck 2>/dev/null | tail -3 || true

echo ""
echo "✅ تم. جرّب الآن:"
echo "   $PY -m agent_os              # واجهة JARVIS التفاعلية"
echo "   $PY -m agent_os.demo         # عرض حيّ لكل القدرات"
echo "   $PY -m agent_os.ultra doctor # فحص شامل"
