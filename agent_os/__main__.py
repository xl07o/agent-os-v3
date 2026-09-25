"""
نقطة تشغيل الحزمة: `python -m agent_os` يُطلق واجهة JARVIS التفاعلية،
و`python -m agent_os "<مهمة>"` ينفّذها مباشرةً.
"""
import sys

from agent_os import jarvis

if __name__ == "__main__":
    if len(sys.argv) > 1:
        import json
        print(json.dumps(jarvis.handle(" ".join(sys.argv[1:])),
                         ensure_ascii=False, indent=2, default=str))
    else:
        jarvis.repl()
