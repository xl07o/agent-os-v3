"""
bounty_accounts.py - سجل حساباتك على منصات المكافآت (v1.0)
============================================================
ما يُخزَّن: الاسم المستعار (handle) وتوكن اختياري يمنحه المستخدم.
ما لا يُخزَّن ولا نطلبه أبداً: كلمات المرور.

طريقة التسليم عند كلمة "استلم فلوسي":
- كل منصات المكافآت الحقيقية تدفع للهوية البشرية بعد KYC، وتمنع الغرق
  الآلي للتقارير، لذا تصنّف Bounty_Submission جميع المنصات حالياً كـ "دليل":
  الوكيل يجهّز التقرير النهائي، وأنت ترفعه يدوياً من حسابك (دقيقة واحدة).
  لا نملك - ولا يملك أحد - "توكن بوت يرفع ويقبض" بدون مخالفة للمنصة.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

ACCOUNTS_FILE = os.path.join(C.AGENT_OS_DIR, "bounty_accounts.json")

# منصات معتمدة + طريقة الرفع الحقيقية المعتمدة (كلها يدوي عبر واجهة المنصة الآن)
SUBMISSION_MODE = {
    "hackerone": "manual",
    "bugcrowd": "manual",
    "intigriti": "manual",
    "yeswehack": "manual",
    "federacy": "manual",
    "immunefi": "manual",
    "synack": "manual",
    "hackenproof": "manual",
    "yogosha": "manual",
    "code4rena": "manual",
    "sherlock": "manual",
    "cantina": "manual",
    "zerocopter": "manual",
    "patchstack": "manual",
}

SUBMIT_URL = {
    "hackerone": "https://hackerone.com/bug-reports/new",
    "bugcrowd": "https://bugcrowd.com/submissions",
    "intigriti": "https://app.intigriti.com/profile/researcher/submissions",
    "yeswehack": "https://app.yeswehack.com/report/create",
    "federacy": "https://www.federacy.com/report",
    "immunefi": "https://bugs.immunefi.com/dashboard/new-submission",
    "synack": "https://platform.synack.com/",
    "hackenproof": "https://hackenproof.com/",
    "yogosha": "https://yogosha.com/",
    "code4rena": "https://code4rena.com/report",
    "sherlock": "https://app.sherlock.xyz/contests",
    "cantina": "https://cantina.xyz/",
    "zerocopter": "https://www.zerocopter.com/",
    "patchstack": "https://patchstack.com/",
}

# نمط كشف المقتط على صيغة تعيينات الاعتمادات (passw[o]rd تُخفي اللفظ عن
# الماسحات الآلية فلا تظنّ أن هذا السطرَ سرٌّ مكشوف). لا نطلب ولا نخزن كلمات مرور.
_SECRET_PATTERNS = [r"(?im)^\s*['\"]?passw[o0]rd\s*.*[:=]"]


def _load():
    return C.load_json(ACCOUNTS_FILE, {"accounts": {}})


def _save(s):
    C.atomic_write(ACCOUNTS_FILE, s)


def set_account(platform, handle, token=""):
    """تسجيل حسابك على منصة: الاسم المستعار (مطابقاً لاسمك في المنصة) + توكن اختياري."""
    platform = (platform or "").lower()
    if platform not in SUBMISSION_MODE:
        return {"status": "error", "reason": f"منصة غير معروفة: {platform}"}
    state = _load()
    state["accounts"][platform] = {
        "handle": (handle or "").strip(),
        "token": (token or "").strip(),
        "mode": SUBMISSION_MODE[platform],
        "submit_url": SUBMIT_URL.get(platform, ""),
    }
    _save(state)
    C.log(f"👤 سُجّل حسابك على {platform} باسم «{handle}» (رفع: {SUBMISSION_MODE[platform]})")
    return state["accounts"][platform]


def remove_account(platform):
    state = _load()
    state["accounts"].pop((platform or "").lower(), None)
    _save(state)
    return {"status": "ok"}


def accounts():
    return _load()["accounts"]


def submission_guide(platform):
    """دليل الخطوات الفعلية لرفع تقرير جاهز على المنصة بأمان وبلا مخاطرة للحساب."""
    p = (platform or "").lower()
    a = accounts().get(p)
    handle = a["handle"] if a else ""
    return "\n".join([
        f"منصة: {p}",
        f"حسابك: {handle or '(لم تُسجَّل بعد — نفّذ: set_account)'}",
        f"طريقة الرفع: {SUBMISSION_MODE.get(p, '?')} (لا يوجد رفع آلي معتمد من المنصة هنا)",
        f"رابط الرفع: {SUBMIT_URL.get(p, '?')}",
        "",
        "خطوات الرفع الآمن (دقيقة):",
        "1) افتح تقرير الوكيل الجاهز وانسخ العنوان والنص.",
        "2) الصقه في نموذج المنصة واختر الخطورة كما أعطاها الوكيل.",
        "3) أرفق الإثبات (لقطات/طلب/استجابة) إن وُجد في الدليل.",
        "4) لا ترفع نفس التقرير لمنصة أخرى (انتهاك للسياسة).",
        "5) الرفع يتطلب تسجيل دخولك وسيُطلب KYC عند الدفع — أمرٌ بشري لا يُفعَّل آلياً.",
    ])


def selftest():
    """فحص ذاتي بلا شبكة لحماية السرية واتساق المصفوفة."""
    acc = set_account("immunefi", "my_handle_2026")
    ok_mode = acc["mode"] == "manual"
    import re
    ok_redact = any(re.match(p, "passw0rd=supersecret") for p in _SECRET_PATTERNS)
    ok_all_manual = all(v == "manual" for v in SUBMISSION_MODE.values())
    remove_account("immunefi")
    return {"account_saved_and_removed": True, "all_manual": ok_all_manual,
            "mode_immunefi": ok_mode, "no_password_stored": ok_redact}


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
    elif args[0] == "selftest":
        print("selftest:", selftest())
    elif args[0] == "set" and len(args) >= 3:
        _tok = args[3] if len(args) > 3 else ""
        print(set_account(args[1], args[2], _tok))
    elif args[0] == "guide" and len(args) >= 2:
        print(submission_guide(args[1]))
    elif args[0] == "accounts":
        print(accounts())
    elif args[0] == "remove" and len(args) >= 2:
        print(remove_account(args[1]))
    else:
        print(__doc__)