' jarvis-brain.vbs — يشغّل عقل الوكيل (Hermes-compat) مخفياً في الخلفية على ويندوز.
' ضعه في مجلد بدء التشغيل: اضغط Win+R واكتب shell:startup ثم انسخه هناك.
' عدّل REPO ليشير إلى مجلد المشروع.
Set sh = CreateObject("WScript.Shell")
REPO = "C:\path\to\agent-os-v3"      ' ← عدّل هذا
sh.CurrentDirectory = REPO
' 0 = نافذة مخفية تماماً، False = لا تنتظر
sh.Run "pythonw -m agent_os.hermes_server", 0, False
