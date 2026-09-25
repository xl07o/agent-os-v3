"""
self_consultation.py - محرك الاستشارة الذاتية
=============================================
فكرة المالك: "يسأل مواقع الـAI مثل ChatGPT أو كلاودي أو جيميناي عن اقتراحات
              وأدوات يضيفها في نفسه مع أكواد"
التوسيع: الوكيل يسأل عقوله المتعددة (المتاحة في brain.py) عن:
  - نقاط ضعف في كوده
  - أدوات/APIs جديدة مفيدة
  - أفكار مشاريع مربحة
  - تحسينات معمارية
  ثم يفلتر الاقتراحات ويسجّلها كفرضيات قابلة للاختبار.
"""

import os
import sys

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

CONSULT_LOG = os.path.join(C.AGENT_OS_DIR, "self_consultation_log.json")

# أنواع الاستشارة المتاحة
CONSULT_TYPES = {
    "code_improvement": "أنت مراجع كود خبير. حلّل هذا الكود واقترح 3 تحسينات عملية مع الأولوية:",
    "tool_discovery": "أنت خبير أدوات برمجية. اقترح 3 أدوات/APIs مجانية مفيدة لوكيل AI مستقل يعمل بـPython:",
    "revenue_ideas": "أنت خبير ريادة أعمال رقمية. اقترح 3 أفكار مشاريع رقمية يستطيع وكيل AI بناؤها وتحقيق دخل منها:",
    "architecture": "أنت مهندس برمجيات خبير. حلّل هذه المعمارية واقترح 3 تحسينات:",
    "security_audit": "أنت خبير أمن معلومات. اكتشف 3 ثغرات محتملة في هذا النظام:",
}


def consult(consult_type, context="", mode="smart"):
    """يستشير العقل عن موضوع ويعيد الاقتراحات.

    يعمل بلا مزوّد حيّ (يعيد نتيجة فارغة مهذّبة بدل أن يكسر).
    """
    if consult_type not in CONSULT_TYPES:
        return {"suggestions": [], "error": f"نوع استشارة غير معروف: {consult_type}"}

    prompt_prefix = CONSULT_TYPES[consult_type]
    full_prompt = f"{prompt_prefix}\n\n{context[:2000]}" if context else prompt_prefix

    try:
        text, engine = C.call_brain(
            "أنت مستشار خبير. أجب بإيجاز وعملية. رقّم اقتراحاتك.",
            full_prompt, mode=mode,
        )
    except Exception as e:
        return {"suggestions": [], "engine": None,
                "note": f"لا مزوّد متاح: {e}"}

    if not text or text.startswith("("):
        return {"suggestions": [], "engine": None,
                "note": "لا مزوّد متاح — أضف مفتاحاً أو شغّل Ollama"}

    record = {
        "type": consult_type,
        "response": text[:1500],
        "engine": engine,
        "at": C.now_iso(),
    }
    _log_consultation(record)
    return {"suggestions": text[:1500], "engine": engine, "type": consult_type}


def consult_about_code(file_path):
    """يقرأ ملف ويستشير العقل عن تحسينات."""
    if not os.path.exists(file_path):
        return {"error": "ملف غير موجود"}
    try:
        code = open(file_path, "r", encoding="utf-8", errors="replace").read()[:3000]
    except Exception as e:
        return {"error": str(e)}
    return consult("code_improvement", context=code)


def consult_for_revenue():
    """يطلب أفكار مشاريع مربحة."""
    return consult("revenue_ideas", context="الوكيل يعمل بـPython ويستطيع: "
                   "بناء مواقع، أدوات CLI، APIs، أتمتة، تحليل بيانات، أمن معلومات.")


def consult_for_tools():
    """يطلب اقتراحات أدوات/APIs جديدة."""
    return consult("tool_discovery")


def recent(n=5):
    """آخر N استشارات."""
    log = C.load_json(CONSULT_LOG, {"consultations": []})
    return log["consultations"][-n:]


def _log_consultation(record):
    log = C.load_json(CONSULT_LOG, {"consultations": []})
    log["consultations"].append(record)
    log["consultations"] = log["consultations"][-200:]
    C.atomic_write(CONSULT_LOG, log)


if __name__ == "__main__":
    r = consult_for_tools()
    if r.get("suggestions"):
        print(f"اقتراحات من {r['engine']}:\n{r['suggestions'][:300]}")
    else:
        print(f"ملاحظة: {r.get('note', 'لا نتيجة')}")
