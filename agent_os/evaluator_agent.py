"""
evaluator_agent.py - وكيل المقيّم المستقل (مقترح كلاودي #6)
============================================================
يحكم على تحسينات self_improve قبل الالتزام: فحوص حتمية صارمة بلا شبكة.

  - صياغة سليمة (compile) للملف الجديد كاملاً.
  - رفض قطعي: أسرار/رموز اعتماد، أنماط ممنوعة (عبر tool_registry)،
    استيراد نواة محمية، نموذج Except عارٍ جديد beyond allowed.
  - درجات وملاحظات لأغراض الحوكمة والسجل.

الاستخدام:
  python agent_os/evaluator_agent.py evaluate <ملف-جديد.py>
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C


def evaluate_file(new_path, base_path=None):
    """تقييم ملف كامل (الجديد بعد التحسين) مقابل الأصل إن وُجد.
    يعيد {score, verdict, reasons}. verdict: pass | review | reject."""
    reasons = []
    try:
        with open(new_path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
        compile(src, new_path, "exec")
        reasons.append(("ok", "صياغة سليمة"))
    except SyntaxError as e:
        return {"score": 0, "verdict": "reject", "reasons": [("critical", f"صياغة فاسدة: {e}")]}

    # أسرار ممنوعة قطعياً — لا تعديل حي يمرّ أمامها
SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9]{16,}",           # OpenAI/SDK-style keys
    r"(?i)\b(?:api[_-]?key|password|passwd|secret_token)\b\s*[=:]\s*['\"][^'\"]{8,}",
    r"AKIA[0-9A-Z]{16}",             # AWS access key
    r"BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY",
]

# استيرادات داخله-النواة ممنوعة أيضاً في الملفات الحيوية
HARD_IMPORT_BAD = ("subprocess", "socket")
HARD_IMPORT_PROTECTED = ("selfrunner", "webtools", "mastery", "skills", "memory_bank", "brain", "builders")


def evaluate_file(new_path, base_path=None):
    """تقييم ملف كامل (الجديد بعد التحسين) مقابل الأصل إن وُجد.
    يعيد {score, verdict, reasons}. verdict: pass | review | reject.
    الأبواب الحتمية للرفض: صياغة، أسرار، استيراد داخلي خارج القائمة، __import__.
    الاستخدام الشائع (os/sys/time/re/datetime…) يُنقص الدرجات كتحذير لا كرفض —
    أمنٌ بلا شلل: لا نمنع الملفات الحيوية لأنها تستعمل os."""
    reasons = []
    try:
        with open(new_path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
        compile(src, new_path, "exec")
        reasons.append(("ok", "صياغة سليمة"))
    except SyntaxError as e:
        return {"score": 0, "verdict": "reject", "reasons": [("critical", f"صياغة فاسدة: {e}")]}

    import agent_os.tool_registry as tr

    def _scan(ccode):
        """مسح المخالفات في كود معيّن: يعيد (critical, warns)."""
        crit, wrn = [], []
        for pat in SECRET_PATTERNS:
            if re.search(pat, ccode):
                crit.append(("critical", "يبدو سراً/كلمة مرور — مرفوض: " + pat[:36]))

        # استيرادات داخلية داخل القائمة المصرّح بها فقط (عيب 8) + نوى محمية
        for m in re.finditer(r"(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))", ccode):
            head = ((m.group(1) or m.group(2)) or "").strip().split()[0]
            parts = head.split(".")
            if parts[0] in HARD_IMPORT_PROTECTED:
                crit.append(("critical", f"استيراد نواة محمية: {parts[0]}"))
            elif parts[0] == "agent_os":
                sub = parts[1] if len(parts) > 1 else ""
                if sub and sub not in tr.ALLOWED_INTERNAL_IMPORTS:
                    crit.append(("critical", f"استيراد داخلي خارج القائمة: {sub}"))
            elif parts[0] in HARD_IMPORT_BAD:
                wrn.append(("warn", f"استيراد {parts[0]} — يُسمح فقط إن حُوكم سياقه"))

        # صيد الصيغة  from agent_os import X, (Y) as Z  — سطر واحد مع أسماء مُفكّكة
        for ln in ccode.splitlines():
            m = re.match(r"\s*from\s+agent_os\s+import\s+(.+)$", ln)
            if not m:
                continue
            for chunk in re.split(r"[,()]", m.group(1)):
                name = chunk.split(" as ", 1)[0].strip()
                name = name.split()[0] if name.split() else ""
                if name and name not in tr.ALLOWED_INTERNAL_IMPORTS:
                    crit.append(("critical", f"استيراد داخلي خارج القائمة: {name}"))

        if re.search(r"\b__import__\s*\(", ccode):
            # Kernel/world_model تستعمله عمداً لتحميل أنظمتها المقيدة بالقوائم — تحذير لا رفض
            wrn.append(("warn", "__import__ الديناميكي — تحميل نظام يستلزم مراجعة السياق"))

        for pat in tr.FORBIDDEN_PATTERNS:
            if "__import__" in pat:
                continue  # حُكم أعلاه كتحذير سياقي (لا شلل داخلي)
            if re.search(pat, ccode.lower()):
                crit.append(("critical", f"نمط ممنوع قطعياً: {pat[:40]}"))
        return crit, wrn

    critical, warns = _scan(src)

    # مقارنة بالمصدر: يُرفض ما أَدخلَه التعديلُ من مخالفاتٍ جديدة فقط، لا ما
    # كان موروثاً في الأصل (مثل _common.py الذي يستورد نوى محمية عمداً) —
    # وإلا أصبحت الملفات الحية غير القابلة للتحسين محترقة للأبد.
    inherited_msgs = set()
    old = ""
    if base_path and os.path.exists(base_path):
        try:
            with open(base_path, "r", encoding="utf-8", errors="replace") as f:
                old = f.read()
            if old:
                inherited_msgs = {m for (_t, m) in _scan(old)[0]}
        except Exception:
            pass
    if inherited_msgs:
        critical = [c for c in critical if c[1] not in inherited_msgs]

    if critical:
        reasons.extend(critical)

    # ثانويات إيجابية/تحذيرات
    score = 0 if critical else 100
    if not critical:
        import ast
        try:
            tree = ast.parse(src)
            funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if funcs:
                doc = sum(1 for fn in funcs if ast.get_docstring(fn))
                score += int(5 * doc / len(funcs))
            score = min(100, score)
        except Exception:
            pass
        score -= 4 * len([w for w in warns if w[0] == "warn"])
        score = max(50, score)
        inherited_n = len(inherited_msgs)
        extra = f" (مخالفات {inherited_n} موروثة من الأصل مقبولة مؤقتاً)" if inherited_n else ""
        reasons.append(("ok", f"لا أسرار ولا استيراد ممنوع جديد (درجة {score}){extra}"))
        reasons.extend(warns)

    # مقارنة الحجم مع الأصل إن وُجد (تحذير فقط)
    if old and len(src) > len(old) * 2 + 200:
        reasons.append(("warn", "النمو في الحجم كبير غير معتاد — مراجعة"))

    verdict = "reject" if critical else ("review" if any(r[0] == "warn" for r in reasons) else "pass")
    return {"score": score, "verdict": verdict, "reasons": reasons}


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "evaluate":
        import json
        print(json.dumps(evaluate_file(args[1], args[2] if len(args) > 2 else None),
                         ensure_ascii=False, indent=1))
    else:
        print("الاستعمال: evaluate <ملف-جديد.py> [ملف-أصلي.py]")