# Agent OS v3 — Evaluation Brief for Claude Code

> Read this file first, then evaluate the codebase in this repository.
> This is an **offensive evaluation**: find real defects, not style nits.
> Every finding must cite `file_path:line_number` and prove it with code you actually read.

---

## 1. What this project is

**Agent OS v3** ("نظام تشغيل الوكيل v3") — a self-hosted autonomous agent operating system.
It is a layer of systems built on top of **SelfRunner v3.0** ("موظف الليل"), the parent agent in this repo.

Core loop (in `agent_os/agent_os.py`):

```
Router → Planner → Executor → Critic → Verifier
```

Entry point: `agent_os.AgentOS()` (lazy import in `agent_os/__init__.py`) → `agent_os/kernel.py`.

The 12 registered systems and their CLI verbs are documented in `agent_os/README.md`. Read that file
first — it is the authoritative map of the architecture.

## 2. Scope of the evaluation

| Priority | Area | Where |
|---|---|---|
| P0 | **Security** — command execution, secret handling, scope gates, prompt injection, network policy | `agent_os/_common.py`, `agent_os/security/`, `agent_os/security_kernel.py`, `agent_os/bounty_engine.py`, `agent_os/full_access.py` |
| P0 | **Correctness of the core loop** — does Router→Planner→Executor→Critic→Verifier actually gate, or does it just narrate? | `agent_os/agent_os.py`, `agent_os/kernel.py` |
| P1 | **Concurrency & state** — races, non-atomic writes, checkpoint corruption, lock correctness | `agent_os/checkpoint.py`, `agent_os/orchestration/durable_queue.py`, `agent_os/orchestration/idempotency.py`, `agent_os/event_bus.py` |
| P1 | **Self-modification safety** — can `self_improve_engine.py` escalate its own permissions? | `agent_os/self_improve_engine.py`, `agent_os/evolution/` |
| P2 | **Test quality** — do tests assert real behavior, or do they assert mocks re-call themselves? | `tests/` |
| P3 | **Dead code / duplication** — unused modules, copy-paste forks, unreachable branches | whole repo |

## 3. Non-negotiable operating rules (declared by the project)

These are invariants. **Verify they actually hold. A violation here is a P0 finding.**

1. No self-modification of protected files:
   `selfrunner.py, webtools.py, mastery.py, skills.py, memory_bank.py, brain.py, builders.py`
2. **Never** `shell=True`. All execution must go through `selfrunner.run_command` (argv list + allowlist).
3. The bounty scope gate is a **hard gate** — no assets outside the authorized scope.
4. Recon is passive/surface-level only. Exploitation is always rejected.
5. Secrets are never auto-read. Any credential requires human approval via `agent_os/approval_center.py`.

For each of the 5 rules: state whether it is enforced in code, enforced only nominally, or not enforced.
Cite the enforcing function.

## 4. How to run it

```bash
python -m pytest tests/test_agent_os.py -q   # the package alone (no network, no brain)
python -m pytest tests/ -q                   # everything
```

Do not run anything that touches the network, real credentials, or a real LLM endpoint.
Copy `.env.example` to `.env` and leave every key blank if you must.

## 5. Output format

Report in this exact structure:

### VERDICT
One of: `SHIP` / `SHIP WITH FIXES` / `DO NOT SHIP` — plus one sentence of justification.

### P0 — Blocking defects
For each: `path:line` · what breaks · the exact input/condition that triggers it · minimal repro · fix.
If there are none, say so explicitly. Do not pad.

### P1 — Serious issues
Same format, ordered by blast radius.

### P2 / P3 — Cleanup
One line each, grouped by file.

### THE FIVE RULES
A table: `Rule | Enforced? | Enforcing code | Evidence`.

### WHAT IS ACTUALLY GOOD
Name it honestly. If the architecture is sound in a place, say so and say why.
Do not sandbag a good design just to look rigorous.

## 6. Calibration

- Prefer **3 proven findings** over 20 speculative ones.
- "This could be a problem if X" is not a finding unless you traced X.
- If you cannot run the tests, say so — do not guess at results.
- If a module is a stub, note it as a stub; do not evaluate it as if it were real.
