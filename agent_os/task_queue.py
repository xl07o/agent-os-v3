"""
task_queue.py - طابور مهام خلفية موثوق (v1.0)
===============================================
مهام تنفّذ بالخلفية، تنجو من إعادة تشغيل، وفيها إعادة محاولة (حتى MAX_RETRY)
عند الفشل — بدون اعتماد على أي خدمة خارجية.

يمدّ inbox_worker.py: استخدمه للمهام المؤجلة/الطويلة بدل الفورية.
  - append-only queue file (task_queue.jsonl)
  - states file لتتبع حالة كل مهمة (task_states.json)
  - تلقائياً يعيد المحاولة حتى MAX_RETRY قبل التخلي
  - يبقى pending عند إعادة التشغيل — لا مهمة تُنسى

الاستخدام:
  from agent_os import task_queue as tq
  tq.enqueue("اكتب ملخص اليوم")
  tq.run_pending()          # أو من daemon في الخلفية
  tq.list_tasks(status="pending")
  tq.summary()              # {'pending': 1, 'done': 3, ...}
"""

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

QUEUE_FILE  = os.path.join(C.AGENT_OS_DIR, "task_queue.jsonl")
STATES_FILE = os.path.join(C.AGENT_OS_DIR, "task_states.json")

MAX_RETRY = 3


def _load_states():
    return C.load_json(STATES_FILE, {})


def _save_states(s):
    C.atomic_write(STATES_FILE, s)


def _set_state(task_id, **kwargs):
    states = _load_states()
    if task_id not in states:
        states[task_id] = {}
    states[task_id].update(kwargs)
    _save_states(states)


# ------------------------------------------------------------------
def enqueue(text, source="api", metadata=None):
    """أضف مهمة للطابور. يرجع task_id."""
    task_id = str(uuid.uuid4())[:8]
    entry = {
        "id": task_id,
        "text": str(text)[:1000],
        "source": str(source)[:50],
        "created": C.now_iso(),
        "metadata": metadata or {},
    }
    with open(QUEUE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _set_state(task_id, status="pending", attempts=0,
               last_error=None, created=entry["created"], done_at=None)
    C.log(f"📥 مهمة #{task_id} في الطابور: {text[:60]}")
    return task_id


def _read_queue_map():
    """يقرأ الملف كاملاً ويرجع dict من id -> entry."""
    tasks = {}
    if not os.path.exists(QUEUE_FILE):
        return tasks
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    tasks[e["id"]] = e
                except Exception:
                    pass
    except Exception:
        pass
    return tasks


def _execute(text):
    """تنفيذ مهمة عبر kernel. يرفع استثناءً عند الفشل."""
    from agent_os import kernel
    agent = kernel.AgentOS(use_brain=True)
    res = agent.run_goal(text)
    return res.get("summary") or res.get("result") or str(res)[:200]


def run_pending(max_tasks=5):
    """نفّذ حتى max_tasks من المهام المعلّقة. يرجع قائمة النتائج."""
    states = _load_states()
    candidates = [
        tid for tid, st in states.items()
        if st.get("status") == "pending" and st.get("attempts", 0) < MAX_RETRY
    ][:max_tasks]
    if not candidates:
        return []

    tasks_map = _read_queue_map()
    results = []
    for tid in candidates:
        entry = tasks_map.get(tid)
        if not entry:
            _set_state(tid, status="failed", last_error="task not found in queue file")
            continue
        text = entry.get("text", "")
        attempts = _load_states().get(tid, {}).get("attempts", 0) + 1
        _set_state(tid, status="running", attempts=attempts)
        try:
            result = _execute(text)
            _set_state(tid, status="done", done_at=C.now_iso(), last_error=None)
            C.log(f"✅ مهمة #{tid} تمّت: {str(result)[:80]}")
            results.append({"id": tid, "ok": True, "result": str(result)[:200]})
        except Exception as e:
            err = str(e)[:200]
            new_status = "failed" if attempts >= MAX_RETRY else "pending"
            _set_state(tid, status=new_status, last_error=err)
            C.log(f"❌ مهمة #{tid} فشلت (محاولة {attempts}/{MAX_RETRY}): {err}")
            try:
                from agent_os import error_tracker
                error_tracker.capture(e, source=f"task_queue:{tid}",
                                      ctx={"text": text[:100], "attempt": attempts})
            except Exception:
                pass
            results.append({"id": tid, "ok": False, "error": err})
    return results


def list_tasks(status=None, last=50):
    """قائمة المهام مع النص. status=None يرجع الكل. الأحدث أولاً."""
    states = _load_states()
    tasks_map = _read_queue_map()
    items = []
    for tid, st in states.items():
        entry = tasks_map.get(tid, {})
        items.append({"id": tid, "text": entry.get("text", ""), "source": entry.get("source", ""), **st})
    items.sort(key=lambda x: x.get("created", ""), reverse=True)
    if status:
        items = [i for i in items if i.get("status") == status]
    return items[:last]


def summary():
    """ملخص أرقام الطابور — للواجهة والمشرف."""
    states = _load_states()
    counts = {}
    for st in states.values():
        s = st.get("status", "?")
        counts[s] = counts.get(s, 0) + 1
    return counts


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(json.dumps(summary(), ensure_ascii=False, indent=2))
    elif args[0] == "run":
        print(json.dumps(run_pending(), ensure_ascii=False, indent=2))
    elif args[0] == "enqueue" and len(args) > 1:
        print(enqueue(" ".join(args[1:]), source="cli"))
    elif args[0] == "list":
        st = args[1] if len(args) > 1 else None
        for t in list_tasks(status=st):
            print(f"#{t['id']} [{t['status']}] {t.get('text','')[:60]}")
    else:
        print("الاستخدام: [run | enqueue <نص> | list [status] | (بلا: ملخص)]")
