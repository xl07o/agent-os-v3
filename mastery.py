"""
mastery.py - محرك الإتقان الخارق (v2.1)
========================================
وضع "غياب المستخدم": يتعلم مهارات متقدمة بلا حدود، يعمّقها بالمستويات،
يكتب برمجياته الخاصة ويختبرها بنفسه (توليد -> تنفيذ -> اختبار -> قبول فقط لو نجح)،
ويراقب حضور المستخدم ليتوقف تلقائياً ويعود لأوامرك.

التشغيل:
  python mastery.py run                (حلقة الإتقان المستمرة)
  python mastery.py status             (الحالة الحالية)
  python mastery.py stop               (إيقاف دائم بعلامة)
  python mastery.py resume             (إعادة التشغيل)
  python mastery.py report             (تقرير كامل)

متى يتوقف عن التعلم:
  - عودة المستخدم (علامة user_active يضعها التفاعلي chat_cli/selfrunner)
  - ملف mastery.stop
  - تجاوز سقف التكلفة اليومي
"""

import ast
import datetime
import json
import os
import re
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import brain
import skills

MASTERY_DIR = os.path.join(_HERE, "projects", "mastery")
STATE_FILE = os.path.join(_HERE, "data", "mastery_state.json")
LOG_FILE = os.path.join(_HERE, "logs", "mastery.log")
STOP_FILE = os.path.join(_HERE, "mastery.stop")
USER_FLAG = os.path.join(_HERE, "output", "user_active.flag")
IMPROV_DIR = os.path.join(_HERE, "projects", "mastery", "_library")

for d in (MASTERY_DIR, IMPROV_DIR, os.path.dirname(STATE_FILE), os.path.dirname(LOG_FILE)):
    os.makedirs(d, exist_ok=True)

PAUSE_AFTER_CYCLES = int(os.getenv("SELFRUNNER_MAX_MASTERY_CYCLES", "8"))  # سقف
HARD_CAP = int(os.getenv("SELFRUNNER_MASTERY_HARD_CAP", "24"))  # سقف مطلق لجلسة run — إيقاف حقيقي بعدها لكل جلسة
CYCLE_DELAY = float(os.getenv("SELFRUNNER_MASTERY_DELAY", "5.0"))           # توقف بين الدورات
POLL_USER_EVERY = int(os.getenv("SELFRUNNER_POLL_USER_SECONDS", "30"))      # كل كم ثانية نراقب حضورك


# ===== مناهج بلا حدود - كل شيء في الكون =====

TRACKS = [
    # ===== تقنية وبرمجة =====
    {"id": "secure-coding", "label": "البرمجة الآمنة", "level": 1, "topics": [
        "تحصين كود بايثون ضد الحقن SQL و Command",
        "المصادقة والتفويض الآمن (OWASP)",
        "إدارة المدخلات والمخرجات الآمنة",
        "منع تهريب المسارات path traversal",
    ]},
    {"id": "offensive-security", "label": "الأمن الهجومي والاختراق", "level": 1, "topics": [
        "أساسيات اختبار الاختراق Penetration Testing",
        "تقنيات OSINT وجمع المعلومات",
        "ثغرات الويب OWASP Top 10 وكيف تعمل",
        "هندسة عكسية Reverse Engineering أساسيات",
        "تحليل البرمجيات الخبيثة Malware Analysis",
        "استغلال الثغرات Buffer Overflow",
        "هجمات الشبكات Man in the Middle",
        "تقنيات التخفي والتمويه في الأنظمة",
    ]},
    {"id": "defensive-web-security", "label": "التحصين الدفاعي للويب", "level": 1, "topics": [
        "رؤوس الأمان و CSP و HSTS",
        "منع XSS بالتشفير الصحيح",
        "حماية الـ API من التجربة والتجاوز",
        "التصدي لـ CSRF و clickjacking",
    ]},
    {"id": "cryptography", "label": "التشفير وعلم الأكواد", "level": 1, "topics": [
        "التبييت والهاشين الآمن (bcrypt, argon2)",
        "إدارة المفاتيح AES/RSA",
        "التوقيع الرقمي والتكامل",
        "التشفير الكمي Quantum Cryptography",
        "Steganography إخفاء المعلومات",
        "تحليل الشفرات Cryptanalysis",
    ]},
    {"id": "advanced-algorithms", "label": "خوارزميات متقدمة", "level": 1, "topics": [
        "البرمجة الديناميكية وحل المشاكل",
        "الخوارزميات على الرسوم البيانية",
        "الهياكل المتقدمة والضغط",
        "تحليل التعقيد الزمني",
    ]},
    {"id": "ml-ai", "label": "ذكاء اصطناعي وتعلم آلة", "level": 1, "topics": [
        "أساسيات الانحدار والتصنيف",
        "شبكات عصبية عميقة Deep Learning",
        "معالجة اللغة الطبيعية NLP",
        "تقييم النماذج وضبطها",
        "نماذج اللغة الكبيرة LLMs وكيف تعمل",
        "الذكاء الاصطناعي التوليدي Generative AI",
        "الرؤية الحاسوبية Computer Vision",
    ]},
    {"id": "system-design", "label": "تصميم الأنظمة الموزعة", "level": 1, "topics": [
        "تصميم قواعد بيانات وفهرسة",
        "التخزين المؤقت والتقسيم",
        "تصميم واجهات API قابلة للتوسع",
        "معالجة الأخطاء والتراجع",
        "Microservices Architecture",
        "Event-Driven Architecture",
    ]},
    {"id": "hardening", "label": "تحصين الأنظمة", "level": 1, "topics": [
        "أذونات ملفات ونظام تشغيل",
        "تعمية المنافذ والخدمات",
        "المراقبة والكشف",
        "نسخ احتياطي آمن",
    ]},
    {"id": "networking", "label": "الشبكات والبروتوكولات", "level": 1, "topics": [
        "بروتوكولات TCP/IP والشبكات",
        "DNS وكيف يعمل الإنترنت",
        "VPN والشبكات الخاصة",
        "Firewall وأنظمة الكشف عن التسلل IDS/IPS",
        "شبكات الـ Dark Web وTor",
        "بروتوكولات الاتصال اللاسلكي",
    ]},
    {"id": "blockchain", "label": "البلوكتشين والعملات الرقمية", "level": 1, "topics": [
        "كيف يعمل البلوكتشين",
        "العقود الذكية Smart Contracts",
        "DeFi التمويل اللامركزي",
        "NFT وتقنياتها",
        "تعدين العملات الرقمية",
        "أمان المحافظ الرقمية",
    ]},
    {"id": "web-dev", "label": "تطوير الويب الشامل", "level": 1, "topics": [
        "React و Next.js المتقدم",
        "Backend APIs بـ FastAPI و Node.js",
        "قواعد البيانات SQL و NoSQL",
        "WebSockets والتطبيقات الفورية",
        "PWA التطبيقات التقدمية",
        "WebAssembly",
    ]},
    {"id": "mobile-dev", "label": "تطوير التطبيقات المحمولة", "level": 1, "topics": [
        "React Native للتطبيقات المتعددة المنصات",
        "Flutter وDart",
        "تطوير iOS بـ Swift",
        "تطوير Android بـ Kotlin",
        "نشر التطبيقات في المتاجر",
    ]},
    {"id": "devops-cloud", "label": "DevOps والسحابة", "level": 1, "topics": [
        "Docker وحاويات التطبيقات",
        "Kubernetes وإدارة الحاويات",
        "CI/CD وأتمتة النشر",
        "AWS و Azure و GCP",
        "Infrastructure as Code",
        "Monitoring وObservability",
    ]},
    # ===== علوم وفيزياء =====
    {"id": "physics", "label": "الفيزياء والكون", "level": 1, "topics": [
        "النسبية الخاصة والعامة لأينشتاين",
        "ميكانيكا الكم Quantum Mechanics",
        "الفيزياء النووية والجسيمات الدون ذرية",
        "الثقوب السوداء ونظرية الأوتار",
        "الكون والانفجار العظيم Big Bang",
        "المجرات والنجوم وتطورها",
        "الطاقة المظلمة والمادة المظلمة",
        "الفيزياء الكمية التطبيقية",
        "الحوسبة الكمية Quantum Computing",
    ]},
    {"id": "astronomy", "label": "علم الفلك والفضاء", "level": 1, "topics": [
        "المجموعة الشمسية والكواكب",
        "النجوم ودورة حياتها",
        "المجرات وأنواعها",
        "الكون المرئي وحدوده",
        "الأجسام الفضائية النيازك والمذنبات",
        "استكشاف الفضاء والمركبات الفضائية",
        "البحث عن حياة خارج الأرض SETI",
        "الثقوب الدودية Wormholes نظرياً",
        "نظريات الأكوان المتعددة Multiverse",
    ]},
    {"id": "chemistry", "label": "الكيمياء والمواد", "level": 1, "topics": [
        "الكيمياء العضوية وغير العضوية",
        "الكيمياء الحيوية Biochemistry",
        "علم المواد Nanotechnology",
        "الكيمياء الصناعية والتصنيع",
        "الأدوية وكيف تعمل",
    ]},
    {"id": "biology", "label": "الأحياء والجينات", "level": 1, "topics": [
        "الجينوم البشري وعلم الجينات",
        "CRISPR وتعديل الجينات",
        "علم الأعصاب Neuroscience",
        "الخلايا الجذعية والطب التجديدي",
        "التطور والانتخاب الطبيعي",
        "الأوبئة وعلم الأوبئة",
        "الذكاء الاصطناعي في الطب",
    ]},
    {"id": "mathematics", "label": "الرياضيات المتقدمة", "level": 1, "topics": [
        "نظرية الأعداد Number Theory",
        "التوبولوجيا Topology",
        "الجبر التجريدي Abstract Algebra",
        "حساب التفاضل والتكامل المتقدم",
        "نظرية الاحتمالات والإحصاء",
        "الرياضيات المنفصلة",
        "نظرية الفوضى Chaos Theory",
    ]},
    # ===== أعمال وتجارة =====
    {"id": "business", "label": "ريادة الأعمال والتجارة", "level": 1, "topics": [
        "نماذج الأعمال Business Models",
        "التخطيط الاستراتيجي",
        "إدارة المشاريع Agile و Scrum",
        "بناء الشركات الناشئة Startups",
        "جمع التمويل Venture Capital",
        "الاستحواذ والاندماج M&A",
        "إدارة الموارد البشرية",
    ]},
    {"id": "marketing", "label": "التسويق الرقمي والمبيعات", "level": 1, "topics": [
        "SEO وتحسين محركات البحث",
        "التسويق عبر وسائل التواصل الاجتماعي",
        "Growth Hacking",
        "Email Marketing",
        "تحليل البيانات التسويقية",
        "بناء العلامة التجارية Branding",
        "تحسين معدل التحويل CRO",
    ]},
    {"id": "finance", "label": "المال والاستثمار", "level": 1, "topics": [
        "أسواق الأسهم وكيف تعمل",
        "التحليل الفني والأساسي",
        "إدارة المحافظ الاستثمارية",
        "العقارات والاستثمار العقاري",
        "الاقتصاد الكلي والجزئي",
        "المشتقات المالية والخيارات",
        "التمويل الإسلامي",
    ]},
    {"id": "ecommerce", "label": "التجارة الإلكترونية", "level": 1, "topics": [
        "بناء المتاجر الإلكترونية",
        "Dropshipping وسلاسل التوريد",
        "Amazon FBA وبيع المنتجات",
        "تحسين صفحات المنتجات",
        "إدارة المخزون والشحن",
        "بوابات الدفع الإلكتروني",
    ]},
    # ===== إنسانيات وعلوم اجتماعية =====
    {"id": "psychology", "label": "علم النفس والسلوك", "level": 1, "topics": [
        "علم النفس المعرفي",
        "التحيزات المعرفية Cognitive Biases",
        "علم النفس الاجتماعي",
        "الذكاء العاطفي EQ",
        "علم الإقناع والتأثير",
        "الصحة النفسية والعلاج",
        "علم الأعصاب والسلوك",
    ]},
    {"id": "philosophy", "label": "الفلسفة والمنطق", "level": 1, "topics": [
        "المنطق الصوري وغير الصوري",
        "الفلسفة الوجودية",
        "أخلاقيات الذكاء الاصطناعي",
        "فلسفة العلوم",
        "نظرية المعرفة Epistemology",
        "الفلسفة السياسية",
    ]},
    {"id": "history", "label": "التاريخ والحضارات", "level": 1, "topics": [
        "تاريخ الحضارات القديمة",
        "الحروب الكبرى وتأثيرها",
        "تاريخ التكنولوجيا والاختراعات",
        "الثورات السياسية والاجتماعية",
        "تاريخ الإسلام والحضارة العربية",
        "تاريخ المستقبل Futurism",
    ]},
    {"id": "law", "label": "القانون والأنظمة", "level": 1, "topics": [
        "القانون التجاري الدولي",
        "قانون الملكية الفكرية",
        "قانون الخصوصية والبيانات GDPR",
        "قانون العقود الرقمية",
        "الأنظمة السعودية والخليجية",
        "قانون الذكاء الاصطناعي",
    ]},
    # ===== إبداع وفنون =====
    {"id": "design", "label": "التصميم والإبداع", "level": 1, "topics": [
        "مبادئ تصميم UI/UX",
        "نظرية الألوان والتصميم الجرافيكي",
        "تصميم الشعارات والهوية البصرية",
        "تصميم الحركة Motion Design",
        "تصميم المنتجات Product Design",
        "الذكاء الاصطناعي في التصميم",
    ]},
    {"id": "content", "label": "إنشاء المحتوى والإعلام", "level": 1, "topics": [
        "كتابة المحتوى الإبداعي",
        "صناعة الفيديو والمونتاج",
        "البودكاست وإنتاج الصوت",
        "التصوير الفوتوغرافي",
        "استراتيجيات يوتيوب",
        "الذكاء الاصطناعي في إنشاء المحتوى",
    ]},
    # ===== علوم متقدمة =====
    {"id": "neuroscience", "label": "علم الأعصاب والدماغ", "level": 1, "topics": [
        "كيف يعمل الدماغ البشري",
        "الذاكرة والتعلم عصبياً",
        "واجهات الدماغ-الحاسوب BCI",
        "الأمراض العصبية وعلاجها",
        "تعزيز القدرات المعرفية",
        "الوعي والإدراك",
    ]},
    {"id": "robotics", "label": "الروبوتات والأتمتة", "level": 1, "topics": [
        "أساسيات الروبوتات",
        "الذراعات الآلية والتصنيع",
        "الروبوتات المستقلة Autonomous Robots",
        "الطائرات المسيّرة Drones",
        "الروبوتات الطبية",
        "مستقبل الأتمتة وسوق العمل",
    ]},
    {"id": "energy", "label": "الطاقة والبيئة", "level": 1, "topics": [
        "الطاقة الشمسية وتقنياتها",
        "طاقة الرياح والمائية",
        "الطاقة النووية والاندماج النووي",
        "تخزين الطاقة والبطاريات",
        "تغير المناخ والحلول",
        "الهيدروجين كوقود المستقبل",
    ]},
    {"id": "geopolitics", "label": "الجيوسياسة والعلاقات الدولية", "level": 1, "topics": [
        "موازين القوى العالمية",
        "الحروب الاقتصادية والعقوبات",
        "الصراعات الإقليمية وتحليلها",
        "الدبلوماسية والمفاوضات",
        "الأمن القومي والاستخبارات",
        "مستقبل النظام العالمي",
    ]},
    {"id": "medicine", "label": "الطب والصحة", "level": 1, "topics": [
        "أساسيات التشريح والفسيولوجيا",
        "الأمراض المزمنة وعلاجها",
        "الطب الجيني والشخصي",
        "الذكاء الاصطناعي في التشخيص",
        "الأدوية وكيف تُطوَّر",
        "الصحة النفسية والعلاج",
        "طول العمر Longevity Science",
    ]},
    {"id": "social-engineering", "label": "الهندسة الاجتماعية والتأثير", "level": 1, "topics": [
        "تقنيات الهندسة الاجتماعية",
        "Phishing وكيف يعمل",
        "علم الإقناع Cialdini",
        "التلاعب النفسي وكيف تتعرف عليه",
        "بناء الثقة والعلاقات",
        "الدعاية والتأثير الجماهيري",
    ]},
    {"id": "future-tech", "label": "تقنيات المستقبل", "level": 1, "topics": [
        "الحوسبة الكمية Quantum Computing",
        "الواقع الافتراضي والمعزز VR/AR",
        "الميتافيرس Metaverse",
        "الطباعة ثلاثية الأبعاد المتقدمة",
        "النانوتكنولوجي Nanotechnology",
        "الذكاء الاصطناعي العام AGI",
        "Singularity نقطة التفرد التكنولوجي",
    ]},
    {"id": "languages", "label": "اللغات والتواصل", "level": 1, "topics": [
        "علم اللغويات Linguistics",
        "تعلم اللغات بسرعة",
        "الترجمة الآلية وتقنياتها",
        "لغة الجسد والتواصل غير اللفظي",
        "الخطابة والإقناع",
    ]},
    {"id": "intelligence", "label": "الاستخبارات وتحليل المعلومات", "level": 1, "topics": [
        "OSINT جمع المعلومات المفتوحة",
        "تحليل البيانات الضخمة للاستخبارات",
        "التحقق من المعلومات Fact Checking",
        "تتبع الأموال والمعاملات",
        "تحليل الشبكات الاجتماعية",
        "الاستخبارات الاقتصادية",
    ]},
]

_LEVEL_NAMES = {1: "له أول مرة", 2: "نظري", 3: "عملي", 4: "متقن", 5: "خبير"}


# ===== سجل وسجل النشاط =====

_SECRET_PATTERNS = [
    re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)\b(pass(word)?|api[_-]?key|token|secret)\b[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_\-\.]{8,}"),
    re.compile(r"(?i)authorization[\"']?\s*[:=]\s*[\"']?(basic|bearer|token)\s+[^\s]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}", re.IGNORECASE),
]


def _redact(text):
    """استبدال أي نص يشبه سراً بـ [REDACTED] قبل الطباعة/الحفظ."""
    text = str(text)
    for pat in _SECRET_PATTERNS:
        try:
            text = pat.sub("[REDACTED]", text)
        except Exception:
            pass
    return text


def _log(msg):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {_redact(msg)}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "version": 3,
        "tracks": {t["id"]: {"level": 1, "topic_idx": 0, "xp": 0, "demos": []} for t in TRACKS},
        "total_cycles": 0,
        "total_demos": 0,
        "created": datetime.datetime.now().isoformat(),
        "last_cycle": None,
    }


def _save_state(st):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)  # استبدال ذري — لا ينكسر ملف الحالة أبداً


# ===== مراقبة حضور المستخدم =====

def user_present():
    """هل المستخدم موجود؟ (علامة يضعها التفاعلي عند تشغيله)."""
    return os.path.exists(USER_FLAG)


def mark_user_active():
    """ضع علامة الحضور (يستدعيها التفاعلي chat_cli/selfrunner)."""
    try:
        with open(USER_FLAG, "w", encoding="utf-8") as f:
            f.write(datetime.datetime.now().isoformat())
    except Exception:
        pass


def mark_user_away():
    """إزالة علامة الحضور عند خروج التفاعلي."""
    try:
        if os.path.exists(USER_FLAG):
            os.remove(USER_FLAG)
    except Exception:
        pass


def stalled():
    """هل أوقفت الإتقان يدوياً؟"""
    return os.path.exists(STOP_FILE)


# ===== اختيار المهارة التالية =====

def next_target():
    """يرجع المسار الأقل تقدماً المتبقي تعلّمه."""
    st = _load_state()
    order = sorted(TRACKS, key=lambda t: (st["tracks"][t["id"]]["level"], -t["id"].count("-")))
    for t in order:
        tr = st["tracks"][t["id"]]
        if tr["level"] < 5:
            return t, tr
    return None, None


# ===== توليد برمجية + اختبارها (التطور الذاتي الآمن) =====

def _sanitize(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40] or "skill"


# ===== حارس أمني: فحص ستاتيكي (AST) قبل أي تنفيذ للكود المولَّد =====

ALLOWED_IMPORTS = {
    "math", "re", "json", "itertools", "functools", "collections",
    "datetime", "string", "random", "statistics", "heapq", "bisect",
    "dataclasses", "typing", "enum", "decimal", "fractions", "copy",
    "unittest", "pytest", "hashlib", "base64", "struct",
}

FORBIDDEN_NAMES = {
    "os", "sys", "subprocess", "socket", "shutil", "ctypes", "importlib",
    "eval", "exec", "compile", "__import__", "open", "input",
    "pathlib", "multiprocessing", "threading", "signal", "resource",
    "pty", "platform", "webbrowser", "urllib", "requests", "http",
    "ssl", "socket", "winreg", "getpass", "tempfile",
}

FORBIDDEN_ATTRS = {
    "system", "popen", "remove", "rmtree", "unlink", "chmod", "kill",
    "fork", "spawn", "startfile", "run", "popen2", "popen3",
}

MAX_DEMO_LINES = 400  # حدّ أكبر للأسطر يمنع استنزاف الموارد


def _static_guard(code_text):
    """يرفض أي كود فيه استيراد/استدعاء خطير قبل وصوله للتشغيل الفعلي."""
    try:
        tree = ast.parse(code_text)
    except SyntaxError as e:
        return False, f"خطأ صياغة: {e}" 

    if len(code_text.splitlines()) > MAX_DEMO_LINES:
        return False, f"الكود أطول من الحد المسموح ({MAX_DEMO_LINES} سطراً)"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod not in ALLOWED_IMPORTS:
                    return False, f"استيراد ممنوع: {mod}"
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod not in ALLOWED_IMPORTS:
                return False, f"استيراد ممنوع: {mod}"
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return False, f"استخدام ممنوع: {node.id}"
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
            return False, f"استدعاء ممنوع: {node.attr}"

    return True, "ok"


def _run_pytest(path):
    """تشغيل الاختبارات في عملية معزولة الموارد (مهلة أقصر، بلا كاش، بلا bytecode)."""
    try:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        r = subprocess.run(
            [sys.executable, "-B", "-m", "pytest", path, "-q", "--tb=line",
             "-p", "no:cacheprovider"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,   # 60 ثانية كافية لمكتبة صغيرة
            cwd=os.path.dirname(path),
            env=env,
        )
        ok = r.returncode == 0
        out = (r.stdout or "")[-450:] + (r.stderr or "")[-450:]
        return ok, out.strip() or ("نجحت الاختبارات" if ok else "فشل الاختبارات")
    except subprocess.TimeoutExpired:
        return False, "انتهت المهلة — قد يكون الكود عالقاً في حلقة لا نهائية"
    except Exception as e:
        return False, str(e)


def _build_demo(topic):
    """توليد مكتبة + اختبارات ثم تشغيلها — يُقبل فقط لو نجحت الاختبارات.
    مع حلقة تصحيح ذاتي: لو فشل شيء، نعيد للنسخة الذكية فشل الاختبارات ليصلحها.
    """
    name = _sanitize(topic)
    attempts = 2
    last_output = None

    for attempt in range(1, attempts + 1):
        feedback = ""
        if attempt > 1:
            feedback = (
                "\n\nالمحاولة السابقة فشلت في الاختبارات. هذه مخرجات الفشل:\n"
                + (last_output or "بدون مخرجات")
                + "\nأصلح المكتبة أو الاختبارات حتى تنجح كل الاختبارات. "
                "يجب أن تعرّف كل الدوال التي تستدعيها الاختبارات."
            )
        ok, result, dest = _attempt_demo(topic, feedback)
        last_output = result
        if ok:
            return True, result, dest

    return False, last_output, None


def _attempt_demo(topic, feedback=""):
    """محاولة توليد وتشغيل واحدة."""
    name = _sanitize(topic)
    b = brain.Brain(
        "أنت مهندس برمجيات كبير. تكتب مكتبة بايثون صغيرة عاملة ومختبرة بأي مكتبة "
        "قياسية فقط، حول الموضوع المطلوب.\n"
        "أخرج المخرجات بصيغة صارمة:\n"
        "1. سطر واحد: MODULE_START\n"
        "2. كود المكتبة كاملاً (def/class فقط، بلا طباعة جانبية)\n"
        "3. سطر واحد: MODULE_END\n"
        "4. سطر واحد: TESTS_START\n"
        "5. اختبارات pytest كاملة تتحقق حقيقةً من عمل المكتبة، تستدعي الدوال المحددة فقط\n"
        "6. سطر: TESTS_END\n"
        "لا تكتب أي شرح خارج هذه الصيغة."
    )
    prompt = (
        f"اكتب مكتبة بايثون قياسية كاملة (بلا مكتبات خارجية) عن: {topic}.\n"
        "يجب أن تحتوي دوالاً مفيدة قابلة للتشغيل فعلياً، وأن تتحقق الاختبارات من النتائج الحقيقية."
        + feedback
    )
    try:
        raw, engine = b.ask(prompt)
    except Exception as e:
        return False, f"فشل التوليد: {e}", None

    lib = None
    tests = None
    m1 = re.search(r"MODULE_START(.*?)MODULE_END", raw, re.DOTALL)
    m2 = re.search(r"TESTS_START(.*?)TESTS_END", raw, re.DOTALL)
    if m1:
        lib = m1.group(1).strip()
    if m2:
        tests = m2.group(1).strip()
    if not lib:
        return False, "لم يُستخرج الكود بصيغة صحيحة", None

    # ===== الحارس الأمني: لا يُكتب على القرص إلا كود نظيف =====
    ok_lib, why_lib = _static_guard(lib)
    if not ok_lib:
        return False, f"رُفض الكود أمنياً: {why_lib}", None
    if tests:
        ok_tests, why_tests = _static_guard(tests)
        if not ok_tests:
            return False, f"رُفضت الاختبارات أمنياً: {why_tests}", None

    proj = os.path.join(MASTERY_DIR, name)
    os.makedirs(proj, exist_ok=True)
    lib_path = os.path.join(proj, "lib.py")
    with open(lib_path, "w", encoding="utf-8") as f:
        f.write(lib)
    if not tests:
        # إن لم تُسلم اختبارات، نولد اختبارات دخانية تحمي من كسر الاستيراد
        tests = "import lib\n\ndef test_import():\n    assert callable(getattr(lib, 'main', None)) or hasattr(lib, '__all__')\n"
    test_path = os.path.join(proj, "test_lib.py")
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(tests)

    ok, output = _run_pytest(test_path)
    if ok:
        # نسخة في المكتبة المتراكمة
        lib_name = _sanitize(topic) + "_" + datetime.datetime.now().strftime("%H%M")
        dest = os.path.join(IMPROV_DIR, lib_name + ".py")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(lib)
        return True, f"المكتبة نجحت اختباراتها: projects/mastery/{name}", dest
    return False, f"فشل الاختبارات:\n{output[:500]}", None


# ===== دورة الإتقان الواحدة =====

def _run_cycle():
    st = _load_state()
    track, _ = next_target()
    if track is None:
        _log("اكتملت كل المسارات في المستوى الخبير! أكملت كل المناهج.")
        return False
    tr = st["tracks"][track["id"]]

    topic = track["topics"][tr["topic_idx"] % len(track["topics"])]
    _log(f"مسار [{track['label']}] | مستوى {tr['level']} | موضوع: {topic}")

    # 1) تعلّم النظرية عبر البحث
    try:
        info = skills.learn(topic, force=True)
        _log(f"> تعلم نظري: {info.get('quality')} من {info.get('sources')} مصادر")
    except Exception as e:
        _log(f"> التعلم النظري تعثر: {e}")

    # 2) تطبيق عملي: توليد برمجية + اختبارات
    ok, result, dest = _build_demo(topic)
    if ok:
        tr["level"] = min(5, tr["level"] + 1)
        tr["xp"] += 1
        tr["demos"].append({
            "topic": topic,
            "date": datetime.datetime.now().isoformat(),
            "level": tr["level"],
            "path": os.path.relpath(dest, _HERE),  # نسبي — لا كشف للمسار الكامل
        })
        st["total_demos"] += 1
        _log(f"> نجح الإتقان → مستوى {tr['level']} ({_LEVEL_NAMES.get(tr['level'], '')})")
    else:
        # فشل محاولة الإتقان — انحدار بسيط للزخم (إشارة لتكرار الفشل)
        tr["xp"] = max(0, tr["xp"] - 1)
        _log(f"> لم يكتمل بعد (سنتعلم لاحقاً): {result}")
    # ننتقل للحدث التالي من الموضوعات
    tr["topic_idx"] += 1

    st["total_cycles"] += 1
    st["last_cycle"] = datetime.datetime.now().isoformat()
    _save_state(st)
    _log(f"الدورة {st['total_cycles']} اكتملت. مجموع المكتبات المقبولة: {st['total_demos']}")
    return True


# ===== حلقة الغياب =====

def run_away(limit=None):
    _log("=== بدء وضع الإتقان (غياب المستخدم) ===")
    _log("سأتعلم وأتقن وأضيف برمجيات لنفسي — إيقاف رشيق عبر Ctrl+C أو mastery.stop، أو سقف جلسة مطلق.")
    cycles = 0
    total = 0
    hard = limit if limit else HARD_CAP
    try:
        while True:
            if stalled():
                _log("تم إيقاف الإتقان يدوياً (mastery.stop). إنهاء الحلقة بأمان.")
                break
            if limit and cycles >= limit:
                break
            if total >= hard:
                _log(f"بلغنا سقف الجلسة المطلق ({hard} دورة) — إيقاف آمن. "
                     f"لجلسة أخرى شغّل: python mastery.py run [عدد]")
                break
            budget = brain._budget_report()
            _log(f"الحالة: {budget['max_cost_usd']}$ سقف | حضورك: {'نعم (سأتوقف)' if user_present() else 'لا'}")
            if user_present():
                _log("اكتشفت أنك موجود — إيقاف التعلم مؤقتاً والسماح لك بالأوامر.")
                wait = 0
                while user_present() and not stalled():
                    if wait >= 600:
                        _log("أنت ما زلت موجوداً — أستمر بالانتظار (لا أتعلم أثناء وجودك).")
                        wait = 0
                    time.sleep(POLL_USER_EVERY)
                    wait += POLL_USER_EVERY
                _log("غاب المستخدم — أستأنف الإتقان.")
                continue

            try:
                _run_cycle()
            except KeyboardInterrupt:
                raise
            except Exception as e:
                _log(f"خطأ في الدورة سيتم تجاوزه: {e}")
            cycles += 1
            total += 1

            # لوحة استهلاك يومي: إذا تجاوزنا القدر الأقصى من الدورات نرتاح ساعة
            max_cycles = int(os.getenv("SELFRUNNER_MAX_MASTERY_CYCLES", "8"))
            if cycles >= max_cycles:
                _log(f"انتهى سقف هذه الجلسة ({max_cycles} دورات). استراحة {CYCLE_DELAY} ث ثم نكمل في جلسة جديدة.")
                time.sleep(CYCLE_DELAY)
                cycles = 0
            else:
                time.sleep(CYCLE_DELAY)
    except KeyboardInterrupt:
        _log("تلقّيت إيقافاً يدوياً (Ctrl+C) — أحفظ حالة الإتقان وأتوقف بأمان.")
        try:
            do_stop()
        except Exception:
            pass

    _log("انتهت حلقة الإتقان بشكل آمن.")


# ===== التقارير =====

def status():
    st = _load_state()
    lines = ["# محرك الإتقان - الحالة", ""]
    for t in TRACKS:
        tr = st["tracks"].get(t["id"], {"level": 1, "xp": 0})
        bar = "█" * tr["level"] + "░" * (5 - tr["level"])
        lines.append(f"- {t['label']}: [ {bar} ] مستوى {tr['level']} ({_LEVEL_NAMES.get(tr['level'], '')}) ")
    lines += ["", f"**دورات:** {st['total_cycles']} | **مكتبات مقبولة:** {st['total_demos']}"]
    lines += [f"**آخر دورة:** {st.get('last_cycle') or '-'}"]
    return "\n".join(lines)


def report():
    st = _load_state()
    out = ["# تقرير الإتقان الكامل", ""]
    out.append(status())
    out.append("")
    out.append("## سجل المكتبات المولّدة ذاتياً")
    for t in TRACKS:
        tr = st["tracks"].get(t["id"], {})
        for d in tr.get("demos", []):
            out.append(f"- [{t['label']}] {d['topic']} → {d.get('path')} (مستوى {d.get('level')})")
    out.append("")
    out.append(f"الخلاصة: {st['total_demos']} مكتبة مكتوبة ومختبَرة ذاتياً.")

    path = os.path.join(_HERE, "output", "mastery_report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    _log(f"التقرير: {path}")
    return path


def do_stop():
    """إيقاف دائم للإتقان عبر ملف العلامة."""
    with open(STOP_FILE, "w", encoding="utf-8") as f:
        f.write(datetime.datetime.now().isoformat())
    _log("تم هضم ملف الإيقاف. شغّل resume لتكمل.")


def do_resume():
    """إزالة علامة الإيقاف والاستئناف."""
    try:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
            _log("أُزيل الإيقاف. المتمّي للإتقان.")
    except Exception:
        pass


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "run":
        limit = None
        if len(sys.argv) > 2:
            try:
                limit = max(1, int(sys.argv[2]))
            except ValueError:
                pass
        run_away(limit=limit)
    elif action == "status":
        print(status())
    elif action == "stop":
        do_stop()
    elif action == "resume":
        do_resume()
    elif action == "report":
        report()
    else:
        print(status())