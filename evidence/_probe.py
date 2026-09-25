import inspect, importlib, sys, os, json
sys.path.insert(0, os.getcwd())


def probe(modname, attrs):
    out = {}
    try:
        m = importlib.import_module(modname)
        for a in attrs:
            try:
                o = getattr(m, a)
                try:
                    sig = str(inspect.signature(o))
                except Exception:
                    sig = type(o).__name__
                out[a] = sig
            except AttributeError:
                out[a] = "MISSING"
    except Exception as e:
        out["__import__"] = f"{type(e).__name__}: {e}"
    return out


R = [
    ("brain", ["Brain", "ask", "Brain.__init__"]),
    ("memory_bank", ["MemoryBank", "add_memory", "get_memory", "query_memory", "create", "add", "query"]),
    ("schedule", ["Scheduler", "add_job", "list_jobs", "create_schedule", "ScheduleManager"]),
    ("webtools", ["url_guard", "is_safe_url", "check_url", "fetch_page", "search"]),
    ("failure_learning", ["FailureLearner", "record", "report", "add_failure"]),
    ("roi_brain", ["compute_roi", "calculate_roi", "evaluate_header", "measure_roi", "RoiBrain"]),
    ("agent_os.agent_os", ["run_task", "router", "execute_task", "process_task"]),
    ("agent_os.checkpoint", ["snap", "restore", "create_checkpoint"]),
    ("agent_os.security.network_policy", ["allow_url", "is_allowed", "check", "verify_url", "ALLOWED_SCHEMES"]),
    ("agent_os.security.prompt_injection", ["detect", "is_injection", "check", "scan"]),
    ("agent_os.verification.reality", ["check", "verify", "assess", "validate"]),
    ("agent_os.interface.human_requests", ["request", "submit", "HumanRequest"]),
    ("agent_os.product_factory", ["build", "build_web", "create", "produce", "types_list", "make_product"]),
    ("agent_os.opportunity_brain", ["lookup", "find_opportunity", "scan", "get_opportunity"]),
    ("agent_os.kernel_guard", ["check", "snapshot", "verify", "monitor", "audit"]),
    ("agent_os.dashboard", ["render", "state", "serve"]),
    ("agent_os.cognition.intent_engine", ["classify", "detect_intent"]),
    ("agent_os.bounty_engine", ["record_bounty", "report", "BountyEngine"]),
    ("agent_os.api_hunter", ["recent", "check", "scan"]),
    ("agent_os.github_hunter", ["recent", "check", "scan"]),
    ("agent_os.mission_generator", ["compose", "generate"]),
    ("agent_os.registry_center", ["snapshot", "audit", "list"]),
    ("agent_os.self_improve_engine", ["history", "improve_once", "train"]),
    ("agent_os.event_bus", ["post", "recent", "get_events"]),
    ("agent_os.goal_manager", ["add_goal", "list_goals"]),
    ("agent_os.approval_center", ["request", "list_requests", "deny"]),
    ("agent_os.skill_memory", ["snapshot", "summarize"]),
]
out = {}
for mod, attrs in R:
    out[mod] = probe(mod, attrs)
print(json.dumps(out, ensure_ascii=False, indent=1))