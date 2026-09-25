import os

os.chdir(r"C:\Users\hhdjj\OneDrive\سطح المكتب\ai-agent-master\ai-agent-master")
import sys

sys.path.insert(0, ".")
from agent_os import agent_os_api as API  # الدفعة 4: الواجهة الموحّدة

s = API.status()
print("واجهة موحّدة status(): ok =", s["ok"], "| الأنظمة =", len(s.get("systems", [])),
      "| أهداف =", s.get("goals"), "| قيد الموافقة =", s.get("pending_approvals"))

from agent_os import registry_center as RC  # الدفعة 4: السجل المركزي

print("سجل مركزي snapshot():", {k: (len(v) if hasattr(v, "__len__") else v)
                                 for k, v in RC.snapshot().items()})

from agent_os import checkpoint as CH  # الدفعة 4: نقاط الحماية

ch = CH.snap("تحقق إغلاق الدفعة 4")
print("لقطة: id =", ch["id"], "| ملفات =", len(ch["files"]))
print("تحقق اللقطة سليم:", CH.verify(ch["id"])["ok"])

from agent_os import kernel_guard as KG  # الدفعة 4: حارس النواة + مفتاح الأمان

g = KG.current_state()
print("حارس النواة: mode =", g["mode"], "| مدارّعاً؟", g.get("armed", ""))

from agent_os import incident_commander as IC  # الدفعة 4: قائد الحوادث

print("حوادث مفتوحة:", IC.report()["open"], "| درسٌ مُسجَّل:", IC.learned_lessons() is not None)
print()
print("== السجلّ الحي (ذاكرة المهارات) — آخر 3 دروس ==")
from agent_os import skill_memory as SM

for e in SM.recall("درس دفعة 4", top=3):
    print(" •", e["context"][:54])
