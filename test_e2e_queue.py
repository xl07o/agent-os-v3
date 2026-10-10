"""اختبار نهاية-لنهاية للطابور: تنفيذ فعلي عبر kernel.AgentOS.run_goal()"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from agent_os import task_queue as tq

print('[RUN_PENDING max=3] بدأ...')
results = tq.run_pending(max_tasks=3)
print('[RESULTS]')
for r in results:
    print(' -', json.dumps(r, ensure_ascii=False))

after = tq.summary()
print('[SUMMARY AFTER]', json.dumps(after, ensure_ascii=False))

states = tq._load_states()
print('[STATES LAST 6]')
items = list(states.items())
for tid, st in items[-6:]:
    err = str(st.get('last_error', '') or '')[:70]
    print(f'  #{tid}: {st.get("status")} attempts={st.get("attempts")} err={err}')
