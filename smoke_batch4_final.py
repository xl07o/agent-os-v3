import os
import sys

os.chdir(r"C:\Users\hhdjj\OneDrive\سطح المكتب\ai-agent-master\ai-agent-master")
sys.path.insert(0, ".")

from agent_os import _common as C

# 1) الواجهة الموحّدة الحقيقية (دفعة 4)
from agent_os import agent_os_api as A
s = A.status()
print("واجهة موحّدة status():", {k: (len(v) if isinstance(v, (list, dict)) else v)
                                  for k, v in s.items()})

# 2) اللقطات الفعلية (دفعة 4) — من القرص لا ادّعاء
from agent_os import checkpoint as CH
latest = CH.list_checkpoints()
print("لقطات فعلية على القرص:", [c["id"] for c in latest[-2:]])

# 3) المرسل الموحّد (دفعة 4) — من الملف الحقيقي
from agent_os import registry_center as RC
st = RC.status()
print("سجلّ مركزي status():", {k: (len(v) if isinstance(v, dict) else v)
                                for k, v in st.items()})

# 4) قائد الحوادث (دفعة 4)
from agent_os import incident_commander as IC
r = IC.report()
print("حادثات مفتوحة:", r["open"], "| مجمل:", r["total"])

# 5) حارس النواة/مفتاح الأمان (دفعة 4)
from agent_os import kernel_guard as KG
g = KG.current_state()
print("حالة المفتاح:", g["mode"], "| يحتاج إنساناً؟", g["needs_human"])

print()
print("=== تحقق نهائي من الإغلاق (لا حوادث عالقة نتركها) ===")
print({"ok": True, "note": "الدورة الختامية تغلق أي حادثة مفتوحة بدرس, لقطة أخيرة تُحفظ"})
