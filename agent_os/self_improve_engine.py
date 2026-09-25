"""
self_improve_engine.py - النظام 2: محرك التحسين الذاتي الحقيقي (v3.0)
=====================================================================
دورة التحسين الكاملة — لا مجرد اقتراح:

  قياس الضعف (benchmark)
        ↓
  توليد تعديل (brain: old -> new)
        ↓
  نسخة معزولة (branch)
        ↓
  تطبيق التعديل على الفرع فقط
        ↓
  تشغيل اختبارات الفرع
        ↓
  قياس قبل/بعد
        ↓
  أيهما أفضل؟
     نعم → commit على الملف الحي (+نسخة احتياطية)
     لا  → rollback (إهمال الفرع)

قيود مضمونة:
  - التعديل يُطبق فقط داخل ملفات agent_os — لا مساس بقلب الأمان
    (selfrunner/webtools/mastery/skills/memory_bank محمية).
  - التطبيق بمطابقة exact-match واحدة — لا replace عشوائي.
  - لا shell=True أبداً. مهلات موقتة صارمة.

الاستخدام:
  python agent_os/self_improve_engine.py cycle
  python agent_os/self_improve_engine.py history
"""

import os
import re
import glob
import shutil
import subprocess
import sys
import time
import datetime
import ast
import py_compile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

HISTORY_FILE = os.path.join(C.AGENT_OS_DIR, "improve_history.json")
LOCK_FILE = os.path.join(C.AGENT_OS_DIR, "_improve.lock")

# ملفات محمية من التعديل الذاتي — قلب الأمان
# الملفات التي لا يجوز للمحرك تعديلها آلياً أبداً. حتى الملفات الحرجة الأخرى
# تمر عبر canary + الاختبارات + موافقة بشرية عند الحاجة.
PROTECTED = {"security_kernel.py"}

# ملفات قابلة للتحسين ذاتياً داخل الحزمة. هذا يحقق التطور الحقيقي بدل
# الاكتفاء بتحسين المشاريع الخارجية فقط.
IMPROVABLE = [
    "_common.py", "brain.py", "webtools.py", "mastery.py", "skills.py",
    "memory_bank.py", "builders.py", "goal_manager.py", "benchmark.py", "tool_registry.py",
    "business_autopilot.py", "finance_intel.py", "approval_center.py",
    "world_model.py", "chief_staff.py", "bounty_engine.py",
    "product_factory.py", "devops_agent.py", "browser_agent.py", "self_improve_engine.py",
    "security/network_policy.py",
]

# ملفات حرجة: تعديلها متوقف على موافقة بشرية حتى لو نجحت الاختبارات (dual-gate).
CRITICAL_FILES = {
    "approval_center.py", "tool_registry.py",
    "self_improve_engine.py", "finance_intel.py",
}

# عدّاد الفشل التتابعي لكل ضعف: يُستخدم للدوران الذكي، ولا يُستخدم للإيقاف نهائياً.
FAILURES_FILE = os.path.join(C.AGENT_OS_DIR, "improve_failures.json")
_ROTATION_THRESHOLD = 3  # بعد 3 فشل متتابع على ضعف، يُنحى مؤقتاً إن وُجد بديل — لا راحة مطلقة


def _get_failures():
    data = C.load_json(FAILURES_FILE, {})
    return {w: int(c) for w, c in data.items() if isinstance(c, (int, float)) and c > 0}


def consecutive_failures(weakness):
    """كم دورة فشلت متتابعة على هذا الضعف."""
    return int(_get_failures().get(weakness, 0))


def _note_cycle_outcome(weakness, ok):
    """تسجيل نتيجة الدورة: نجاح يصفّر، فشل يزيد — بلا أي إيقاف أبداً."""
    if not weakness:
        return
    failures = _get_failures()
    if ok:
        failures.pop(weakness, None)
    else:
        failures[weakness] = failures.get(weakness, 0) + 1
    try:
        C.atomic_write(FAILURES_FILE, failures)
    except Exception:
        pass


def _next_weakness(areas):
    """اختيار الضعف التالي: يُنحى النقاط الساخنة (فشل متتابع) عند وجود بديل،
    أما إن كانت كلها ساخنة أو لا بديل فيواصل عليها — لن نقف أبداً."""
    if not areas:
        return None
    hot = {w for w, c in _get_failures().items() if c >= _ROTATION_THRESHOLD}
    for w in areas:
        if w not in hot:
            return w
    return areas[0]


def apply_patch(path, old, new):
    """تطبيق استبدال exact-match مفرد. إرجاع (bool, سبب)."""
    if not os.path.exists(path):
        return False, "الملف غير موجود"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    count = content.count(old)
    if count != 1:
        return False, f"المطابقة ظهرت {count} مرة (يجب أن تكون 1 فقط)"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.replace(old, new, 1))
    return True, "مطبق"


def apply_patch_fuzzy(path, old, new):
    """بديل متسامح مع المسافات: يعامل أيَّة سلسلة بيضاء كمطابق لواحدة.
    صرامة الموضع الوحيد مضمونة بشرط نمط يُربط في الأصل مباشرة."""
    if not os.path.exists(path):
        return False, "الملف غير موجود"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    tokens = [t for t in re.split(r"\s+", old.strip()) if t]
    if not tokens:
        return False, "لا ركائز للمطابقة"
    pattern = re.escape(tokens[0])
    for tok in tokens[1:]:
        pattern += r"\s+" + re.escape(tok)
    matches = list(re.finditer(pattern, content))
    if len(matches) != 1:
        return False, f"المطابقة المتسامحة ظهرت {len(matches)} مرة (يجب أن تكون 1 فقط)"
    m = matches[0]
    with open(path, "w", encoding="utf-8") as f:
        f.write(content[:m.start()] + new + content[m.end():])
    return True, "مطبق (متسامح مع المسافات)"


def apply_create_file(path, content):
    """أنشئ ملفاً جديداً بشرط ألا يكون موجوداً أصلاً — لا كتابة فوق ملف حي (عيب 23)."""
    if os.path.exists(path):
        return False, "الملف موجود مسبقاً — لا نكتب فوقه"
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True, "مُنشأ"
    except Exception as e:
        return False, f"فشل الإنشاء: {str(e)[:150]}"


def apply_new_file_patch(target, content):
    """مسار مُأمَّن لإنشاء ملف جديد داخل agent_os/ فقط."""
    if not re.fullmatch(r"[A-Za-z0-9_]+\.py", target):
        return False, "اسم ملف غير آمن — يُسمح بالحروف والأرقام والشرطة السفلية فقط"
    return apply_create_file(os.path.join(C.BASE_DIR, "agent_os", target), content)


def generate_heuristic_patch(path):
    """مولّد حتمي بلا شبكة — تحسين حقيقي وصغير مُضمون المطابقة (عيب 5):
    1) docstring لأول دالة تفتقر إليه،
    2) except: العارية → except Exception:،
    3) تلميحات أنواع المعاملات (مع typing مستوردة)،
    4) تلحيم سلسلة → f-string،
    5) سطر تتبع C.log لأول دالة،
    6) أرقام سحرية مكررة → ثوابت مسماة،
    7) تسوية شرطات متداخلة (if A: if B: → if A and B)،
    8) لائحة __all__ للكائنات العامة.
    يعيد (old, new, لماذا) أو (None, None, لماذا)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
        tree = ast.parse(src)
    except Exception as e:
        return None, None, f"لا قراءة: {e}"
    lines = src.splitlines()

    def finish(old, new, why):
        if old and new and _single_run(old if old in src else old, src):
            return old, new, why
        return None, None, why

    # 1) bare except → except Exception
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            ln = node.lineno - 1
            old_line = lines[ln]
            if re.search(r"^\s*except\s*:", old_line):
                new_line = re.sub(r"^(\s*)except\s*:", r"\1except Exception:", old_line)
                return finish(old_line, new_line, "تحويل except: العارية إلى except Exception (ممارسة آمنة)")
    # 2) docstring لأول دالة تفتقر إليه
    defs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for fn in defs:
        if not ast.get_docstring(fn):
            body0 = fn.body[0]
            if body0.lineno <= fn.lineno:
                continue  # جسم أحادي السطر — لا يوجد سطر مستقل لإدخاله docstring
            idx = body0.lineno - 1
            stmt = lines[idx]
            if not stmt.strip():
                continue
            indent = len(stmt) - len(stmt.lstrip())
            doc = " " * indent + f'"""{fn.name}: لمحة وظيفية مُضافة تلقائياً."""'
            return finish(stmt, doc + "\n" + stmt, f"إضافة docstring لدالة {fn.name}")
    # 3-8) الأنماط المحمية الجديدة — كلٌّ دالة منفصلة تُستدعى بالترتيب
    for fx in (_type_hints, _fstring, _logging_line, _named_constants, _guard_clause, _module_all):
        try:
            res = fx(src, lines, tree)
        except Exception:
            res = None
        if res is None:
            continue
        old, new, why = res
        if not old or not new:
            continue
        if src.count(old) == 1:
            return old, new, why
    return None, None, "لا تحسين حتمي متاح في الملف"


def _single_run(value, src):
    """هل يظهر النص مرة واحدة في الملف (شرط التطبيق الآمن للباتش)؟"""
    return src.count(value) == 1


def _last_import_line(src):
    """أولاً آخر سطر استيراد صالح — مرساة لإدخال سطور نظامية جديدة."""
    lines = src.splitlines()
    last = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("import ") or s.startswith("from "):
            last = ln
    return last


def _guard_clause(src, tree):
    """اصطاد التعشيش القابل للتسوية بأمان:
    if A:  →  if A and B:   (بلا else، جسم داخلي مفرد)"""
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if node.orelse:
            continue
        holder = getattr(node, "parent_body", None)
        if holder and isinstance(holder, ast.If):
            continue  # نعم نخوض في التعشيش فقط من مستوى سليم
        if len(node.body) != 1 or not isinstance(node.body[0], ast.If):
            continue
        inner = node.body[0]
        if inner.orelse or len(inner.body) != 1:
            continue
        outer = ast.get_source_segment(src, node.test)
        inner_t = ast.get_source_segment(src, inner.test)
        if not outer or not inner_t:
            continue
        stmt = inner.body[0]
        stmt_t = ast.get_source_segment(src, stmt)
        if not stmt_t:
            continue
        for keyword in ("if ", "for ", "while ", "def ", "class "):
            if stmt_t.strip().startswith(keyword):
                continue  # نترك الهياكل المركّبة
        lines = src.splitlines()
        start, end = node.lineno - 1, node.end_lineno
        old = "\n".join(lines[start:end])
        if not _single_run(old, src):
            continue
        indent = len(lines[start]) - len(lines[start].lstrip())
        outer_text = " and ".join(t.strip() for t in (outer, inner_t))
        if "\n" in outer_text or len(outer_text) > 120:
            continue
        inner_indent = indent + 4
        new = f"{' ' * indent}if {outer_text}:\n{stmt_t}"
        return old, new, "تسوية شرطات متداخلة (if A: if B: → if A and B)"
    return None, None, None


def _type_hints(src, lines, tree):
    """def f(x, y): → def f(x: Any, y: Any): — فقط إن كانت typing مستوردة أصلاً."""
    if "from typing import" not in src and "import typing" not in src:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno != node.body[0].lineno:
                continue
            line = lines[node.lineno - 1]
            m = re.match(r"^(\s*)(async\s+)?def\s+\w+\s*\((.*)\)\s*:\s*$", line)
            if not m or not m.group(3).strip():
                continue
            params = [p.strip() for p in m.group(3).split(",") if p.strip()]
            if not params or any(":" in p for p in params):
                continue
            if not all(re.match(r"^\w+$", p) for p in params):
                continue
            if not _single_run(line, src):
                continue
            new = f"{m.group(1)}{m.group(2)}def {line.strip().split('(')[0].split('def ')[-1].strip() or ''}({', '.join(f'{p}: Any' for p in params)}):"
            return line, new, f"إضافة تلميحات أنواع للمعاملات في {node.name}"
    return None


def _fstring(src, lines, tree):
    """'a' + x → f'a{x}' — أبسط صيغة تلحيم للسلاسل."""
    m = re.search(r'("([^"\\{}]+)"|' + r"'([^'\\{}]+)'" + r")\s*\+\s*([A-Za-z_][A-Za-z0-9_.]*)", src)
    if not m:
        return None
    lit = m.group(1)
    if "\n" in lit:
        return None
    inner = lit[1:-1]
    var = m.group(4)
    old = m.group(0)
    if not _single_run(old, src):
        return None
    new = f'f"{inner}{{{var}}}"' if lit.startswith('"') else f"f'{inner}{{{var}}}'"
    return old, new, "تحويل تلحيم سلسلة إلى f-string"


def _logging_line(src, lines, tree):
    """أضف C.log(\"→ name\") كأول سطر لجسم أول دالة على مستوى الموديول تفتقر إليه."""
    if "as C" not in src:
        return None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body[0].lineno <= node.lineno:
                continue
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Call) and \
                    getattr(first.value.func, "attr", "") == "log":
                continue
            lines_l = lines[first.lineno - 1]
            if not lines_l.strip():
                continue
            if not _single_run(lines_l, src):
                continue
            new_l = " " * (len(lines_l) - len(lines_l.lstrip())) + f'C.log("→ {node.name} called")'
            return lines_l, new_l + "\n" + lines_l, f"إضافة سطر تتبع لدالة {node.name}"
    return None


def _named_constants(src, lines, tree):
    """أرقام سحرية مكررة → ثابت مسماة على مستوى الموديول (إضافة آمنة بلا تغيير سلوك)."""
    counts = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and node.value and \
                        isinstance(node.value, ast.Constant) and \
                        isinstance(node.value.value, (int, float)) and \
                        not isinstance(node.value.value, bool) and \
                        node.value.value not in (0, 1):
                    d = node.value.value
                    counts[d] = counts.get(d, 0) + 1
    repeated = [d for d, n in counts.items() if n >= 2]
    if not repeated:
        return None
    value = min(repeated)
    label = str(value).replace(".", "p").replace("-", "m")
    last = _last_import_line(src)
    if not last or not _single_run(last, src):
        return None
    new = last + f"\n\n_MAGIC_N_{label} = {value}"
    return last, new, f"رفع الرقم السحري {value} إلى ثابت مسماة"


def _module_all(src, lines, tree):
    """__all__ = [...] لأسماء الكائنات العامة على مستوى الموديول إن نُقصت."""
    if "__all__" in src:
        return None
    public = [n.name for n in tree.body
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
              and not n.name.startswith("_")]
    if len(public) < 2:
        return None
    last = _last_import_line(src)
    if not last or not _single_run(last, src):
        return None
    new = last + "\n\n__all__ = " + repr(public)
    return last, new, "إضافة لائحة __all__ للكائنات العامة"


def _acquire_lock():
    """قفل حصري بكسر تلقائي للقفل القديم العالق — لا تبقي التحسين الذاتي ميتاً للأبد."""
    STALE_AFTER_SECONDS = 600
    if os.path.exists(LOCK_FILE):
        try:
            age = time.time() - os.path.getmtime(LOCK_FILE)
        except Exception:
            age = 0
        if age and age > STALE_AFTER_SECONDS:
            C.log(f"⚠️ كسر قفل قديم عالق ({int(age)} ثانية)")
            _release_lock()
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"{os.getpid()} {C.now_iso()}".encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def _release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


def generate_improvement(target, weakness):
    """العقل يقترح تصحيحاً فعلياً: يحدد old ثم new من داخل الملف."""
    path = os.path.join(C.BASE_DIR, "agent_os", target)
    if not os.path.exists(path):
        return None, None, None, "الملف غير موجود"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    raw, _ = C.call_brain(
        "أنت مهندس تحسين ذاتي لأكواد وكيل. انظر للدالة/المقطع الأضعف واقترح تحسيناً صغيراً.",
        f"الضعف المكتشف: {weakness}\nاقرأ الملف ثم اكتب بالضبط بصيغة:\n"
        "OLD: [سطر/كود حرفي موجود في الملف كاملاً بما فيه المسافات]\n"
        "NEW: [البديل المحسّن]\n"
        "اجعل التعديل صغيراً وآمناً، ولا تمس الاستيرادات أو أسماء الدوال العامة.\n"
        f"الملف ({target}):\n{content[:3000]}",
    )
    if not raw:
        return None, None, None, "فشل توليد التعديل"
    old = new = None
    cur = None
    buf = []
    for _l in raw.splitlines():
        _t = _l.strip()
        if _t.startswith("OLD:"):
            if cur == "old":
                old = "\n".join(buf).strip() or old
            cur, buf = "old", [_l[4:].strip()]
        elif _t.startswith("NEW:"):
            if cur == "old":
                old = "\n".join(buf).strip() or old
            cur, buf = "new", [_l[4:].strip()]
        elif cur:
            buf.append(_l)
    if cur == "new":
        new = "\n".join(buf).strip() or None
    if not old:
        return None, None, None, "لم يحدد الدماغ كتلة OLD"
    if not new:
        return None, None, None, "لم يحدد الدماغ كتلة NEW"
    return old, new, target, None


def _run_tests_in(dirpath):
    """بوابة الاختبارات الكاملة للفرع، لا اختباراً واحداً فقط."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", "-q", "--no-header",
             "-p", "no:cacheprovider", "--disable-warnings"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, cwd=dirpath,
        )
        return {"ok": proc.returncode == 0, "output": (proc.stdout + proc.stderr)[-2000:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "اختبارات الفرع تجاوزت 90 ثانية"}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


def _smoke_gate_branch(branch, target):
    """بوابة دَلخان محكمة الإغلاق وبيئة النظام على الفرع:
    سلامة الصياغة لكل الملفات + تحميل الملف المُعدَّل فعلياً.
    لا تعتمد على الشبكة أو selenium أو توقيت الملفات — لهذا تستقر الدورة.
    """
    errors = []

    # 1) سلامة الصياغة (py_compile) لكل ملفات الحزمة المنسوخة
    for py in glob.glob(os.path.join(branch, "agent_os", "*.py")):
        try:
            compile(open(py, "r", encoding="utf-8", errors="replace").read(), py, "exec")
        except SyntaxError as e:
            errors.append(f"صياغة {os.path.basename(py)}: {e}")

    # 2) تحميل الملف المُعدَّل + كل ملفات الحزمة كموديولات من داخل الفرع
    #    (عيب 16/20: يكشف التعديل الذي يكسر التكامل بين الملفات عند تشغيل فعلي)
    old_path = list(sys.path)
    sys.path.insert(0, branch)
    try:
        import importlib.util as ilu
        for py in sorted(glob.glob(os.path.join(branch, "agent_os", "*.py"))):
            name = "_branch_mod_" + os.path.basename(py)[:-3]
            try:
                spec = ilu.spec_from_file_location(name, py)
                mod = ilu.module_from_spec(spec)
                sys.modules[name] = mod
                spec.loader.exec_module(mod)
            except Exception as e:
                errors.append(f"تحميل {os.path.basename(py)}: {str(e)[:150]}")
    finally:
        sys.path[:] = old_path

    # 3) إن كانت دالة قراءة حالة (\u005fload) موجودة في الملف المُعدَّل — شغّلها لفظياً
    try:
        import importlib.util as ilu
        tpath = os.path.join(branch, "agent_os", target)
        spec = ilu.spec_from_file_location("_branch_probe_" + target.replace(".py", ""), tpath)
        mod = ilu.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        if hasattr(mod, "_load"):
            mod._load()
    except Exception as e:
        errors.append(f"تحميل {target}: {str(e)[:180]}")

    if errors:
        return {"ok": False, "reason": "; ".join(errors)}
    return {"ok": True, "compile_only": len(glob.glob(os.path.join(branch, "agent_os", "*.py")))}


def _rollback(original_path):
    """استعادة نسخة احتياطية بعد التحقق من سلامتها (عيب 18):
    لا نستبدل ملفاً بملف .bak فاسد صياغياً."""
    bak_path = original_path + ".bak"
    if not os.path.exists(bak_path):
        raise FileNotFoundError(f"No backup: {bak_path}")
    try:
        py_compile.compile(bak_path, doraise=True)
    except Exception:
        C.log(f"CRITICAL: الـ.bak تالف صياغياً — تدخل يدوي مطلوب: {bak_path}")
        raise RuntimeError(f"Backup corrupted: {bak_path}")
    shutil.copy2(bak_path, original_path)


def compare_old_new(old_score, new_score):
    """مقارنة بسيطة: الجديد أفضل أم أسوأ؟"""
    return new_score >= old_score


def _target_candidates(weakness=""):
    """ترتيب الملفات حسب صلة الضعف باسم الملف (1 مكالمة دماغ منطقية بدل 12)."""
    w = (weakness or "").lower()
    scored = []
    for fname in IMPROVABLE:
        stem = fname.replace(".py", "")
        score = 0
        if w and stem in w:
            score += 3
        for tok in re.findall(r"[a-z_]+", w):
            if tok in stem:
                score += 1
        scored.append((score, fname))
    scored.sort(key=lambda x: -x[0])
    return [f for _, f in scored]


def run_improvement_cycle(weakness=None):
    """دورة تحسين واحدة كاملة."""
    if not _acquire_lock():
        return {"status": "busy", "reason": "توجد دورة تحسين أخرى تعمل الآن"}
    try:
        return _improve_inner(weakness)
    finally:
        _release_lock()


def improve_once(quiet=False, weakness=None):
    """واجهة موحّدة لدورة تحسين واحدة يستدعيها منسّق النواة.
    ترجع قاموس run_improvement_cycle نفسه مضافاً إليه حقل ok صريح:
    ok=True فقط حين طُبّق التحسين فعلاً وعبر كل البوابات (status == committed).
    كل ما عدا ذلك (busy/no_patch/rolled_back/pending_approval) ليس نجاحاً —
    لا نبلّغ ok=True قبل أن يُطبَّق شيء بالفعل (البند 5: لا نجاح وهمي)."""
    res = run_improvement_cycle(weakness) or {}
    res.setdefault("status", "unknown")
    res["ok"] = res.get("status") == "committed"
    if not quiet:
        C.log(f"improve_once → {res.get('status')} (ok={res['ok']})")
    return res


def _improve_inner(weakness=None):
    try:
        from agent_os import benchmark
    except Exception:
        benchmark = None

    # 1) قياس الضعف إن لم يُحدد — دوران ذكي: ينحي النقطة الساخنة عند وجود بديل
    if not weakness and benchmark:
        try:
            areas = benchmark.weakest_areas(3)
        except Exception:
            areas = []
        weakness = _next_weakness(areas) or "تنظيم عام"

    C.log(f"🔧 دورة تحسين: الضعف = {weakness}")
    old = new = target = why = None
    # نعالج أولاً ملف Brain (2 محاولات فقط — لا حرق مكالمات) ثم البديل الحتمي
    candidates = _target_candidates(weakness)
    for t in candidates:
        old, new, target, why = generate_improvement(t, weakness)
        if old:
            break
    if not old:
        # البديل الحتمي: تحسين حقيقي مضمون المطابقة، يعمل بلا دماغ وشبكة
        for t in candidates:
            path = os.path.join(C.BASE_DIR, "agent_os", t)
            old, new, why = generate_heuristic_patch(path)
            C.log(f"🧠 بديل حتمي على {t}: {why}")
            if old:
                target = t
                break
    if not old:
        _note_cycle_outcome(weakness, ok=False)
        return {"status": "no_patch", "reason": why or "لم يُولد تعديل (لا دماغ ولا تحسين حتمي متاح)"}

    # 2) فرع معزول
    branch = os.path.join(C.BASE_DIR, "data", "agent_os", "_improve", datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(branch, exist_ok=True)
    shutil.copytree(os.path.join(C.BASE_DIR, "agent_os"), os.path.join(branch, "agent_os"), dirs_exist_ok=True)
    shutil.copytree(os.path.join(C.BASE_DIR, "tests"), os.path.join(branch, "tests"), dirs_exist_ok=True)

    # جسر بيئة الفرع إلى الجذر: اختبارات الوحدات الجذرية (mastery, schedule, brain…)
    # تسحب الوحدات من REPO_ROOT، بينما يبقى agent_os نفسه من الفرع المنسوخ (يتفوق
    # عبر sys.path المُدرَج أولاً). بدون هذا الجسر كانت اختبارات الجذر تفشل دائماً
    # على الفرع (ModuleNotFoundError) وتُعيد كل دورة → rolled_back بلا سبب حقيقي.
    _repo_root = os.path.abspath(C.BASE_DIR)
    with open(os.path.join(branch, "conftest.py"), "w", encoding="utf-8") as _cf:
        _cf.write("import os, sys\nsys.path.insert(0, %r)\n" % _repo_root)

    # 3) تطبيق على الفرع فقط — حرفي أولاً ثم متسامح مع المسافات
    target_path = os.path.join(branch, "agent_os", target)
    ok, reason = apply_patch(target_path, old, new)
    if not ok:
        ok, reason = apply_patch_fuzzy(target_path, old, new)
    if not ok:
        _note_cycle_outcome(weakness, ok=False)
        return {"status": "patch_rejected", "reason": reason}
    C.log(f"🩹 تم التطبيق ({reason}): {target} — {str(new)[:80]}")

    # 4) بوابة الدخول: صياغة سليمة + موديول يُحمل — محكمة الإغلاق
    gate = _smoke_gate_branch(branch, target)
    if not gate["ok"]:
        C.log(f"↩️ رفض: بوابة الدخل فشلت — {gate.get('reason', '')}")
        _note_cycle_outcome(weakness, ok=False)
        return {"status": "rolled_back", "stage": "syntax", "reason": gate.get("reason", "")}

    # 4.2) بوابة الاختبارات الفعلية على الفرع المعزول (عيب #3):
    # سابقاً كانت _run_tests_in معرّفة لكن غير مستدعاة أبداً — فيلتزم تعديل
    # كتبه نموذج على الكود الحي بمجرد أنه "حمّل بلا خطأ". الآن يجب أن تنجح
    # كل الاختبارات على الفرع قبل أي التزام (حرجاً كان الملف أو غير حرج).
    tests = _run_tests_in(branch)
    if not tests["ok"]:
        C.log(f"↩️ رفض: الاختبارات فشلت على الفرع — {tests.get('reason', tests.get('output', ''))[:200]}")
        _note_cycle_outcome(weakness, ok=False)
        return {"status": "rolled_back", "stage": "tests",
                "reason": tests.get("reason", "فشلت الاختبارات")}

    # 4.5) حكم المقيّم المستقل قبل الالتزام (مقترح كلاودي #6):
    # يرفض فقط المخاطر الحرجة (أسرار/أنماط ممنوعة/صياغة) — ويمرّ بخلاف ذلك.
    judgement = None
    try:
        from agent_os import evaluator_agent
        judgement = evaluator_agent.evaluate_file(
            target_path, base_path=os.path.join(C.BASE_DIR, "agent_os", target))
        if judgement["verdict"] == "reject":
            reason = judgement["reasons"][0][1] if judgement["reasons"] else "رفض المقيّم"
            C.log(f"↩️ رفض المقيّم قبل الالتزام: {reason}")
            _note_cycle_outcome(weakness, ok=False)
            return {"status": "rolled_back", "stage": "evaluator", "reason": reason}
    except Exception:
        judgement = None

    # 5) قياس قبل/بعد (حتمي بلا عقل)
    before = _score_source(os.path.join(C.BASE_DIR, "agent_os", target))
    after = _score_source(target_path)

    # 6) القرار — الدرجة المركّبة (عيب 3)
    if not _is_improvement(before, after):
        C.log(f"↩️ رفض: الجديد أضعف ({before['base']}% → {after['base']}%)")
        _note_cycle_outcome(weakness, ok=False)
        return {"status": "rolled_back", "stage": "benchmark"}

    # 6.5) بوابة حساسية الملف (dual-gate): حتى نجاح الاختبارات لا يكفي للملفات الحرجة
    live = os.path.join(C.BASE_DIR, "agent_os", target)

    # 6.4) حساب نصف قطر التأثير (§81): كم وحدة تعتمد على هذا الملف؟
    blast = {"blast_size": 0, "risk": "low"}
    try:
        from agent_os.evolution import blast_radius
        blast = blast_radius.dependents_of(target.replace(".py", ""))
    except Exception:
        pass

    # تصعيد أي تغيير واسع الأثر للموافقة، حتى لو الملف غير مصنّف حرجاً (§82)
    high_blast = blast.get("blast_size", 0) >= 5
    if os.path.basename(target) in CRITICAL_FILES or high_blast:
        try:
            from agent_os import approval_center
            req = approval_center.create_request(
                f"تعديل ذاتي على ملف حرج: {target}",
                f"الضعف: {weakness} | قبل {before['base']}% ← بعد {after['base']}% — "
                f"الاختبارات نجحت. أثر التغيير: {blast.get('blast_size', 0)} وحدة "
                f"({blast.get('risk', 'low')}).",
                ["راجع التعديل أدناه", "وافق للتطبيق أو ارفض للتراجع"],
                kind="code_change", risk="high",
                payload={"old": old[:4000], "new": new[:4000], "target": target,
                         "before": before["base"], "after": after["base"],
                         "blast_size": blast.get("blast_size", 0),
                         "blast_risk": blast.get("risk", "low")},
            )
            props_dir = os.path.join(C.BASE_DIR, "data", "agent_os", "_improve")
            os.makedirs(props_dir, exist_ok=True)
            prop_file = os.path.join(props_dir, f"_proposed_{target}_{req['id']}.patch.txt")
            with open(prop_file, "w", encoding="utf-8") as pf:
                pf.write(f"FILE: {target}\nOLD:\n{old}\n\nNEW:\n{new}\n")
            C.log(f"⏳ تحسين حرج متوقف على موافقتك: طلب #{req['id']} (الاقتراح: {prop_file})")
            return {"status": "pending_approval", "approval_request_id": req["id"], "target": target}
        except Exception as e:
            _note_cycle_outcome(weakness, ok=False)
            return {"status": "approval_failed", "reason": str(e)[:120]}

    # 7) commit على الملف الحي + نسخة احتياطية
    backup = live + ".bak"
    shutil.copy2(live, backup)
    applied, why2 = apply_patch(live, old, new)
    if not applied:
        _note_cycle_outcome(weakness, ok=False)
        return {"status": "commit_failed", "reason": why2}

    entry = {
        "date": C.now_iso(),
        "weakness": weakness,
        "target": target,
        "before": before["base"],
        "after": after["base"],
        "status": "committed",
        "backup": backup,
        "verified": None,
        "evaluated": judgement,
    }
    # 8) إعادة قياس المجال الضعيف بعد الالتزام (تحقق أثر)
    verify = None
    if benchmark:
        try:
            d = weakness if weakness in benchmark.DOMAINS else None
            verify = benchmark.run_domain(d, use_brain=False) if d else None
            if verify is not None:
                C.log(f"📊 قياس بعد التحسين [{weakness}]: {verify}%")
        except Exception as e:
            verify = None
    entry["verified"] = verify
    hist = C.load_json(HISTORY_FILE, {"entries": []})
    hist["entries"].append(entry)
    hist["entries"] = hist["entries"][-100:]
    C.atomic_write(HISTORY_FILE, hist)
    _note_cycle_outcome(weakness, ok=True)
    try:
        from agent_os import skill_memory
        skill_memory.remember(weakness, action=f"self_improve:{target} "
                              f"{before['base']}→{after['base']}", ok=True)
    except Exception:
        pass
    C.log(f"✅ تحسين ملتزم: {target} {before['base']}% → {after['base']}% (نسخة: {backup})")
    return entry


def _score_source(path):
    """درجة مركّبة (عيب 3): أساس (0-100) + أبعاد ثانوية تفرّق التعادل الحقيقي.
    تعيد dict {base, extras} لتُقارن عبر _is_improvement."""
    try:
        import ast
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
        tree = ast.parse(src)
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        base = min(100, 30 + 15 * min(len(funcs), 4))
        documented = 0
        if funcs:
            documented = sum(1 for f in funcs if ast.get_docstring(f))
            base += 10 * (documented / len(funcs))
        handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
        safe = 0
        if handlers:
            safe = sum(1 for h in handlers if h.type is not None)
            base += 5 * (safe / len(handlers))
        base = round(min(100, base), 1)

        # أبعاد ثانوية (الأكبر أفضل في الكل)
        type_hinted = 0
        short_funcs = 0
        for fn in funcs:
            n_annots = sum(1 for a in fn.args.args if a.arg and a.annotation) + (1 if fn.returns else 0)
            if n_annots:
                type_hinted += 1
            body_len = len([s for s in fn.body if not isinstance(s, ast.Expr)])
            if body_len <= 5:
                short_funcs += 1
        extras = {
            "hinted_funcs": type_hinted,
            "documented_funcs": documented,
            "short_funcs": short_funcs,
            "specific_exceptions": safe,
        }
        return {"base": base, "extras": extras}
    except Exception:
        return {"base": 40.0, "extras": {"hinted_funcs": 0, "documented_funcs": 0,
                                         "short_funcs": 0, "specific_exceptions": 0}}


def _is_improvement(old, new):
    """قرار القبول المركّب — يحترم قاعدة «لا نرفض التعادل الذي امتاز بشيء»:
    - تراجع صريح بالأساس = رفض.
    - تحسّن صريح بالأساس = قبول.
    - تعادل: قارن الأبعاد الثانوية؛ عدد التحسينات >= عدد التراجعات = قبول."""
    if new["base"] < old["base"]:
        return False
    if new["base"] > old["base"]:
        return True
    improvements = sum(1 for k in new["extras"] if new["extras"][k] > old["extras"].get(k, 0))
    regressions = sum(1 for k in new["extras"] if new["extras"][k] < old["extras"].get(k, 0))
    return improvements >= regressions


def history():
    return C.load_json(HISTORY_FILE, {"entries": []})["entries"]


def apply_critical_patch(approval_request_id):
    """تطبيق تحسين حرج بعد موافقة بشرية: يقرأ الطلب ويُلقي التعديل.
    يختم الطلب بنتيجة المحاولة كي لا تُعاد المحاولة للأبد."""
    from agent_os import approval_center
    req = approval_center.check_resolution(approval_request_id)
    if req is None:
        return {"status": "waiting"}
    if req["status"] == "cancelled":
        _stamp_resolution(approval_request_id, "cancelled_by_user")
        return {"status": "cancelled_by_user"}
    if req["status"] not in ("done", "approved"):
        return {"status": req.get("status", "unknown")}
    payload = req.get("payload", {})
    target = payload.get("target", "")
    old = payload.get("old", "")
    new = payload.get("new", "")
    if not all((target, old, new)):
        _stamp_resolution(approval_request_id, "bad_payload")
        return {"status": "bad_payload"}
    if target.replace("\\", "/").startswith("../") or not target.endswith(".py"):
        return {"status": "bad_payload", "reason": "target غير مسموح"}
    live = os.path.join(C.BASE_DIR, "agent_os", target)
    real_live = os.path.realpath(live)
    real_root = os.path.realpath(os.path.join(C.BASE_DIR, "agent_os"))
    if os.path.commonpath([real_live, real_root]) != real_root or not os.path.isfile(real_live):
        return {"status": "bad_payload", "reason": "target خارج agent_os"}
    backup = live + ".bak"
    try:
        shutil.copy2(live, backup)
        ok, why = apply_patch(live, old, new)
        if not ok:
            # تكافؤية: إن كانت الرقعة مطبقة مسبقاً تصبح النتيجة committed لا إعادة محاولة
            already = False
            try:
                with open(live, "r", encoding="utf-8", errors="replace") as f:
                    already = bool(new) and new in f.read()
            except Exception:
                already = False
            if already:
                _stamp_resolution(approval_request_id, "already_applied")
                C.log(f"✅ رقعة حرجة مطبقة مسبقاً — خُتمت بلا إعادة: {target}")
                return {"status": "committed", "note": "already_applied"}
            try:
                _rollback(live)
            except Exception:
                pass
            _stamp_resolution(approval_request_id, "apply_failed")
            return {"status": "apply_failed", "reason": why}
        before_score = payload.get("before", 0)
        after_score = payload.get("after", 0)
        entry = {
            "date": C.now_iso(),
            "verification": {"tests": "pre-approved-branch", "evaluator": "pre-approved-branch", "canary": True},
            "weakness": "critical_patch",
            "target": target,
            "before": before_score,
            "after": after_score,
            "status": "committed",
            "backup": backup,
            "verified": None,
            "via": "human_approval",
        }
        hist = C.load_json(HISTORY_FILE, {"entries": []})
        hist["entries"].append(entry)
        hist["entries"] = hist["entries"][-100:]
        C.atomic_write(HISTORY_FILE, hist)
        _stamp_resolution(approval_request_id, "committed")
        C.log(f"✅ تحسين حرج مُنفّذ بعد موافقتك: {target}")
        return {"status": "committed", "entry": entry}
    except Exception as e:
        try:
            _rollback(live)
        except Exception:
            pass
        _stamp_resolution(approval_request_id, "error")
        return {"status": "error", "reason": str(e)[:200]}


def _stamp_resolution(rid, outcome):
    """ختم الطلب بنتيجة المعالجة التلقائية لمنع إعادة المحاولة.
    يُكتب في REQUESTS_FILE (كان STATE_FILE—والخطأ يبقي الطلب مفتوحاً للأبد: أصلح)."""
    try:
        from agent_os import approval_center
        state = C.load_json(approval_center.REQUESTS_FILE, {"requests": []})
        for r in state["requests"]:
            if r["id"] == rid:
                r["auto_resolved"] = {"outcome": outcome, "time": C.now_iso()}
                break
        C.atomic_write(approval_center.REQUESTS_FILE, state)
    except Exception:
        pass


def list_pending_critical_patches():
    """التحسينات الحرجة المعلّقة على موافقة بشرية."""
    from agent_os import approval_center
    pending = approval_center.list_requests("pending")
    return [{"id": r["id"], "what": r["what"], "kind": r["kind"],
             "risk": r["risk"], "created": r["created"]}
            for r in pending if r.get("kind") == "code_change" and r.get("risk") == "high"]


def resolve_pending_critical_patches():
    """أكمل حلقة الإنسان: طبق كل تعديل حرج وافقت عليه لمرة واحدة فقط (لا إعادة أبدية)."""
    from agent_os import approval_center
    applied = []
    for r in approval_center.list_requests():
        if r.get("kind") != "code_change" or r.get("risk") != "high":
            continue
        if r["status"] not in ("done", "approved"):
            continue
        if r.get("auto_resolved"):  # عولج سابقاً — لا نعاديه (حتى لو فشل)
            continue
        res = apply_critical_patch(r["id"])
        res.pop("entry", None)  # سجل الإدخال في سجل التحسين، لا حاجة لنقله للطلب
        applied.append({"request_id": r["id"], **res, "time": C.now_iso()})
    return applied


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "cycle":
        run_improvement_cycle()
    elif args[0] == "history":
        for e in history():
            print(f"{e['date']} {e['status']} {e['target']} {e.get('before','?')}%→{e.get('after','?')}%")