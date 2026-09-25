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

# بعض التوزيعات (Python 3.12+ / PEP 668) تمنع pip على نظام الحزم. نتجاوزه بأمان
# داخل WSL/VM المخصّصة للمشروع عبر --break-system-packages إن لزم.
PIPFLAGS="-q --disable-pip-version-check"
if $PY -m pip install $PIPFLAGS pip >/dev/null 2>&1; then :; else PIPFLAGS="$PIPFLAGS --break-system-packages"; fi

echo "→ تثبيت الأساسي (نواة + اختبارات) …"
# لا نُدرج lxml في الأساسي (قد لا تتوفّر له عجلة على بايثون حديث جداً)؛ bs4 يعمل بدونه.
$PY -m pip install $PIPFLAGS pytest python-dotenv beautifulsoup4 requests 2>&1 | tail -1 \
  || echo "   ⚠️ تعذّر بعض الأساسي — النواة والجسر يعملان بمكتبات بايثون الأساسية"

echo "→ محاولة تثبيت الإضافات (تحكم الجهاز/الصوت/lxml — قد تفشل، غير حرجة) …"
$PY -m pip install $PIPFLAGS -r requirements.txt >/dev/null 2>&1 \
  && echo "   ✅ كل الاعتماديات" \
  || echo "   ⚠️ بعض الإضافات تُثبَّت على جهاز رسومي فقط — النواة تعمل بدونها"

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
