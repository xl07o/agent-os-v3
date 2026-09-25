#!/usr/bin/env python3
"""Smoke-test harness: runs every CLI entry point with a strict timeout.
Exit 0 if all PASS; exit 1 if any FAIL/TIMEOUT/ERROR.

Run:  python smoke_test.py
"""
import os, sys, subprocess, time, json, textwrap

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
os.environ["PYTHONIOENCODING"] = "utf-8"
# Prevent any autonomous loop from spinning during smoke tests
os.environ["SELFRUNNER_AUTORUN"] = "deny"
os.environ["SELFRUNNER_NETWORK_TESTS"] = "0"
os.environ["SELFRUNNER_STEPS"] = "5"

WIN = sys.platform == "win32"
PY = sys.executable


def _run(name, argv, timeout=30, stdin_text=None):
    t0 = time.time()
    try:
        stdin = None
        if stdin_text is not None:
            stdin = subprocess.PIPE
        r = subprocess.run(
            [PY] + argv,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            stdin=stdin,
        )
        elapsed = round(time.time() - t0, 1)
        out = (r.stdout or "") + (r.stderr or "")
        if stdin_text is not None:
            # Send text then close to simulate EOF after desired input
            pass  # text already sent via stdin_text in Popen below
        no_traceback = "Traceback" not in out and "Traceback (most recent call last)" not in out
        # Some tools return non-zero for usage; that's fine if no traceback
        ok = no_traceback
        return {"cmd": name, "status": "PASS" if ok else "FAIL", "exit": r.returncode,
                "elapsed": elapsed, "out": out[:400], "err": (r.stderr or "")[:400]}
    except subprocess.TimeoutExpired:
        return {"cmd": name, "status": "TIMEOUT", "exit": -1, "elapsed": timeout, "out": "", "err": ""}
    except Exception as e:
        return {"cmd": name, "status": "ERROR", "exit": -2, "elapsed": round(time.time() - t0, 1),
                "out": "", "err": str(e)[:300]}


def _run_stdin(name, argv, text, timeout=30):
    t0 = time.time()
    try:
        proc = subprocess.Popen(
            [PY] + argv, cwd=ROOT, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        try:
            stdout, stderr = proc.communicate(input=text, timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return {"cmd": name, "status": "TIMEOUT", "exit": -1, "elapsed": timeout, "out": "", "err": ""}
        elapsed = round(time.time() - t0, 1)
        out = (stdout or "") + (stderr or "")
        no_tb = "Traceback (most recent call last)" not in out
        return {"cmd": name, "status": "PASS" if no_tb else "FAIL", "exit": proc.returncode,
                "elapsed": elapsed, "out": out[:400], "err": (stderr or "")[:400]}
    except Exception as e:
        return {"cmd": name, "status": "ERROR", "exit": -2, "elapsed": round(time.time() - t0, 1),
                "out": "", "err": str(e)[:300]}


# ── command list: (name, argv, timeout_sec, optional_stdin_text) ──
CMDS = [
    # Root tools (start.bat options)
    ("selfrunner-status",       ["selfrunner.py", "--status"], 20),
    ("selfrunner-skills",       ["selfrunner.py", "--skills"], 20),
    ("brain-status",            ["brain.py"], 20),
    ("mastery-status",          ["mastery.py", "status"], 20),
    ("mastery-report",          ["mastery.py", "report"], 20),
    ("chat-cli",                ["chat_cli.py"], 20, "باي\n"),
    ("orchestrator",            ["orchestrator.py", "describe the weather"], 300),
    ("builders-py",             ["builders.py", "py", "SmokeApp"], 15),
    ("suggest-today",           ["suggest.py", "--today"], 30),
    ("daily-quick",             ["daily_autopilot.py", "--quick"], 90),
    ("daily-summary",           ["daily_summary.py", "--hours", "1"], 30),
    ("morning-brief",           ["morning_brief.py"], 30),
    ("schedule-list",           ["schedule.py", "--list"], 15),
    ("memory-stats",            ["memory_bank.py", "stats"], 15),
    ("skills-learn",            ["skills.py", "web security basics"], 60),
    ("webtools-search",         ["webtools.py", "test query"], 30),
    ("employ-state",            ["employ.py", "state"], 20),
    ("dream-status",            ["dream_mode.py", "status"], 20),
    ("strategic-mind",          ["strategic_mind.py"], 60),
    ("knowledge-stats",         ["knowledge_dna.py", "stats"], 15),
    ("failure-report",          ["failure_learning.py", "report"], 15),
    ("roi-report",              ["roi_brain.py", "report"], 20),
    ("opp-top",                 ["opportunity_radar.py", "top"], 20),
    ("watchdog-once",           ["watchdog.py", "once"], 15),
    ("ollama-status",           ["ollama_manager.py", "status"], 15),
    ("code-review",             ["code_reviewer.py", "brain.py"], 60),
    ("constitution-show",       ["agent_constitution.py", "show"], 15),
    ("checkpoint-list",         ["checkpoint_system.py", "list"], 15),
    ("autoproviders-report",    ["autoproviders.py", "report"], 20),
    ("self-evolving-report",    ["self_evolving.py", "report"], 15),
    ("why-ask",                 ["why_engine.py", "ask", "لماذا نتعلم البرمجة"], 20),
    ("self-improver-lessons",   ["self_improver.py", "--lessons"], 20),

    # agent_os systems (12+) + subsystems
    ("agent-os-systems",        ["agent_os/agent_os.py", "systems"], 15),
    ("agent-os-status",         ["agent_os/agent_os.py", "status"], 15),
    ("agent-os-run",            ["agent_os/agent_os.py", "run", "اكتب ملف ملاحظات اختبار في output"], 90),
    ("kernel-once",             ["agent_os/kernel.py", "once"], 90),
    ("benchmark-summary",       ["agent_os/benchmark.py", "summary"], 30),
    ("chief-wake",              ["agent_os/chief_staff.py", "wake"], 20),
    ("chief-brief",             ["agent_os/chief_staff.py", "brief"], 20),
    ("goal-list",               ["agent_os/goal_manager.py", "list"], 15),
    ("approval-list",           ["agent_os/approval_center.py", "list"], 15),
    ("finance-report",          ["agent_os/finance_intel.py", "report"], 15),
    ("finance-brief",           ["agent_os/finance_intel.py", "brief"], 15),
    ("world-build",             ["agent_os/world_model.py"], 15),
    ("tool-list",               ["agent_os/tool_registry.py", "list"], 15),
    ("bounty-report",           ["agent_os/bounty_engine.py", "report"], 15),
    ("devops-monitor",          ["agent_os/devops_agent.py", "monitor"], 30),
    ("biz-autopilot",           ["agent_os/business_autopilot.py", "opportunity"], 90),
    ("product-types",           ["agent_os/product_factory.py", "types"], 15),
    ("self-improve-history",    ["agent_os/self_improve_engine.py", "history"], 15),
    ("eventbus-recent",         ["agent_os/event_bus.py", "recent"], 15),
    ("mission-compose",         ["agent_os/mission_generator.py"], 20),
    ("checkpoint-snap",         ["agent_os/checkpoint.py", "snap", "smoke"], 20),
    ("incident-report",         ["agent_os/incident_commander.py"], 15),
    ("recovery-list",           ["agent_os/recovery/recovery_engine.py", "list"], 15),
    ("skill-memory-sum",        ["agent_os/skill_memory.py", "summarize"], 15),
    ("netpolicy",               ["agent_os/security/network_policy.py"], 20),
    ("prompt-inject",           ["agent_os/security/prompt_injection.py"], 15),
    ("reality-verify",          ["agent_os/verification/reality.py"], 15),
    ("golden-loop-demo",        ["agent_os/golden_loop.py"], 20),
    ("api-hunter-recent",       ["agent_os/api_hunter.py", "recent"], 15),
    ("github-recent",           ["agent_os/github_hunter.py", "recent"], 15),
    ("evaluator-usage",         ["agent_os/evaluator_agent.py"], 15),
    ("kernel-guard",            ["agent_os/kernel_guard.py"], 15),
    ("registry-snapshot",       ["agent_os/registry_center.py"], 20),
    ("agent-os-dashboard-state",["agent_os/dashboard.py", "state"], 15),
    ("supervisor-state",        ["agent_os/supervisor.py"], 15),
    ("intent-engine",           ["agent_os/cognition/intent_engine.py"], 15),
    ("counterfactual",          ["agent_os/cognition/counterfactual.py"], 15),
    ("confidence",              ["agent_os/cognition/confidence.py"], 15),
    ("chain-of-thought",        ["agent_os/cognition/chain_of_thought.py", "ما هي فائدة الذكاء الاصطناعي"], 20),
    ("cap-gap",                 ["agent_os/cognition/capability_gap.py"], 15),
    ("learning-engine",         ["agent_os/cognition/learning_engine.py"], 15),
    ("conflict-resolver",       ["agent_os/memory/conflict_resolver.py"], 15),
    ("provenance",              ["agent_os/memory/provenance.py"], 15),
    ("strategy-memory",         ["agent_os/memory/strategy_memory.py"], 15),
    ("consensus",               ["agent_os/models/consensus.py"], 15),
    ("model-router",            ["agent_os/models/router.py"], 15),
    ("health-graph",            ["agent_os/verification/health_graph.py"], 15),
    ("digital-twin",            ["agent_os/verification/digital_twin.py"], 15),
    ("loop-guard",              ["agent_os/recovery/loop_guard.py"], 15),
    ("attention-budget",        ["agent_os/recovery/attention_budget.py"], 15),
    ("self-healer",             ["agent_os/recovery/self_healer.py"], 15),
    ("brief-extension",         ["agent_os/brief_extension.py"], 15),
    ("durable-queue",           ["agent_os/orchestration/durable_queue.py"], 15),
    ("idempotency",             ["agent_os/orchestration/idempotency.py"], 15),
    ("blast-radius",            ["agent_os/evolution/blast_radius.py"], 15),
    ("regression-writer",       ["agent_os/evolution/regression_writer.py"], 15),
    ("daily-evolution",         ["agent_os/evolution/daily_evolution.py"], 15),
    ("self-consultation",       ["agent_os/evolution/self_consultation.py"], 60),
    ("hypothesis-lab",          ["agent_os/evolution/hypothesis_lab.py"], 15),
    ("mission-planner",         ["agent_os/strategy/mission_planner.py"], 15),
    ("proactive-shield",        ["agent_os/security/proactive_shield.py"], 15),

    # security_empire
    ("se-bounty",               ["security_empire/bounty_tracker.py"], 20),
    ("se-report",               ["security_empire/report_writer.py"], 20),
    ("se-recon",                ["security_empire/recon.py", "example.com"], 30),
    ("se-scanner",              ["security_empire/scanner.py", "example.com"], 60),
    ("se-empire",               ["security_empire/empire.py", "programs"], 20),

    # core_v2
    ("corev2-core",             ["core_v2/agent_core_v2.py"], 90),
    ("corev2-agent",            ["core_v2/agent_os_v2_final.py"], 90),
    ("corev2-biz",              ["core_v2/business_production_v2.py"], 90),
    ("corev2-cog",              ["core_v2/advanced_cognition_v2.py"], 90),
]


def main():
    results = []
    totals = {"PASS": 0, "FAIL": 0, "TIMEOUT": 0, "ERROR": 0}
    print("=" * 80)
    print("SMOKE TEST — SelfRunner / Agent OS")
    print("=" * 80)
    for entry in CMDS:
        name = entry[0]
        argv = entry[1]
        timeout = entry[2]
        stdin_text = entry[3] if len(entry) > 3 else None
        if stdin_text is not None:
            res = _run_stdin(name, argv, stdin_text, timeout=timeout)
        else:
            res = _run(name, argv, timeout=timeout)
        results.append(res)
        totals[res["status"]] += 1
        icon = {"PASS": "✅", "FAIL": "❌", "TIMEOUT": "⏰", "ERROR": "💥"}[res["status"]]
        print(f"{icon} {name:<28s} {res['status']:<7s} exit={res['exit']:<4d} {res['elapsed']:5.1f}s")
        if res["status"] != "PASS":
            snippet = (res.get("err") or res.get("out") or "")[:200].replace("\n", " ")
            if snippet:
                print(f"   └─ {snippet}")

    print("-" * 80)
    print(f"TOTAL: {len(results)}  |  PASS: {totals['PASS']}  FAIL: {totals['FAIL']}  TIMEOUT: {totals['TIMEOUT']}  ERROR: {totals['ERROR']}")
    print("=" * 80)

    report = {"totals": totals, "results": results}
    with open(os.path.join(ROOT, "smoke_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    sys.exit(0 if totals["FAIL"] == 0 and totals["TIMEOUT"] == 0 and totals["ERROR"] == 0 else 1)


if __name__ == "__main__":
    main()
