"""conftest — عزل بيانات agent_os أثناء الاختبارات (عيب 14).

كل كتابات الأنظمة (فاينانس/أهداف/نواة/موافقات/إشعارات...) تذهب إلى مجلد منفصل
_data_isolated بدل بياناتك الحية في data/agent_os.
يُضبط قبل استيراد أي من agent_os (conftest يُحمّل أولاً)، فلا تلوّث الاختبارات
ذاكرتك أو ميزانيتك أو سجل الإنجازات الحقيقية.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_ISOLATED = os.path.join(ROOT, "tests", "_data_isolated")
os.environ["AGENT_OS_DATA_DIR"] = _ISOLATED
os.makedirs(_ISOLATED, exist_ok=True)

# سرعان: اختبارات الوحدات لا تتصل بمزوّدي الذكاء الحي — مفتاح تشغيل المفتاح الحقيقي
# هو SELFRUNNER_NETWORK_TESTS=1 (يستخدمه فحص smoke لا pytest). بدون ذلك نعطّل
# تحميل dotenv حتى لا تُلتقط مفاتيحك الحية أثناء الاختبارات (عادت الدورة من ~9 دقائق
# إلى ~90 ثانية مع بقاء كل الاختبارات خضراء كما كانت قبل إدخال المفاتيح).
if os.getenv("SELFRUNNER_NETWORK_TESTS") != "1":
    try:
        import dotenv
        dotenv.load_dotenv = lambda *a, **kw: False
    except Exception:
        pass


def pytest_sessionstart(session):
    """تصفير المجال المعزول بداية كل جلسة اختبار — يمنع تزاحم الإيجابيات المكررة
    والأرقام المتراكمة بين التشغيلات ويجعل الاختبارات حتمية (لا يمس بياناتك الحية)."""
    import shutil
    if os.path.isdir(_ISOLATED):
        shutil.rmtree(_ISOLATED, ignore_errors=True)
    os.makedirs(_ISOLATED, exist_ok=True)