#!/bin/bash
# SessionStart hook — يجهّز بيئة Agent OS v3 لتشغيل الاختبارات في جلسات الويب.
set -euo pipefail

# على الويب فقط (لا يعبث ببيئة المطوّر المحلية).
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# اجعل جذر المشروع على مسار الاستيراد لكل الجلسة.
echo 'export PYTHONPATH="."' >> "${CLAUDE_ENV_FILE:-/dev/null}"

# الأساسي الآمن للاختبارات (بلا اعتماديات واجهة رسومية تفشل في بيئة بلا شاشة).
python3 -m pip install -q --disable-pip-version-check \
  pytest python-dotenv beautifulsoup4 lxml requests 2>&1 | tail -2 || true

# محاولة تثبيت باقي الاعتماديات (أدوات الجهاز/الصوت) بلا إفشال الجلسة إن تعذّرت.
python3 -m pip install -q --disable-pip-version-check -r requirements.txt >/dev/null 2>&1 || \
  echo "ملاحظة: بعض اعتماديات الواجهة/الصوت تُثبَّت على جهازك لا في السحابة"

echo "Agent OS v3 جاهز — الاختبارات: python -m pytest tests/ -q"
