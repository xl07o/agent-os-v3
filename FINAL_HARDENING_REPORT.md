# Agent OS — Final Hardening Pass

## What changed

This pass keeps the original project and hardens the execution core rather than replacing it.

### Security / authority
- Added `agent_os/security_kernel.py` as a central policy surface for filesystem, command, URL and audit decisions.
- Added DNS-aware SSRF checks to detect hosts resolving to private/loopback/link-local/reserved addresses.
- Centralized command parsing and blocked shell chaining, inline interpreter execution, dangerous shells/downloaders and destructive force flags.
- Centralized filesystem checks with realpath resolution, secret-name protection, system-directory protection and symlink escape detection.
- Made GUI dependency probing fail closed without making the whole agent unimportable when no display exists.
- Browser backends now re-check the final URL after redirects.
- Fixed the robots.txt logic bug where a branch effectively always allowed navigation.
- Security-empire HTTP fetching now goes through the network policy.
- Verification URL/command checks now use the same policy.

### Execution / reliability
- Durable task queue now has an explicit transition matrix instead of allowing arbitrary state jumps.
- Queue selection claims tasks atomically to reduce duplicate execution by multiple workers.
- Self-healer no longer recursively runs the complete test suite from inside the suite itself. Full health tests are bounded and opt-in with `AGENT_HEALER_FULL_TESTS=1`.
- Added `agent_os/health_report.py` for a lightweight health snapshot.
- Added `agent_os/doctor.py` for preflight/CI-style diagnostics.

### Self-improvement
- Self-improvement can now target more of the Agent OS instead of being permanently blocked from the main brain/runtime modules.
- `security_kernel.py` remains protected from autonomous mutation.
- Critical/high-blast-radius changes still go through the existing approval path.
- Improvement branches run the full project test suite with a bounded timeout before promotion.
- Critical patch targets are validated to remain inside `agent_os/` and to be Python files.
- Approval payloads are bound to a SHA-256 hash at creation and checked again before approval.

### Tools / supply chain
- Tool installations now use a per-tool virtual environment instead of installing into the host Python environment.
- Tool installs require an explicit `package==version` pin.
- Tool metadata persistence was fixed.
- Tool health testing is virtualenv-aware.
- Active-tool discovery now recognizes successfully installed tools.
- Candidate code execution uses a restricted environment and rejects filesystem/network/eval-style primitives before execution.

### Product / learning
- Product Factory now validates generated Python function identifiers before inserting them into generated source.
- Added a public GitLab knowledge hunter (`agent_os/gitlab_hunter.py`) alongside the existing GitHub hunter.
- Daily autopilot now invokes the real `agent_os.self_improve_engine` instead of relying only on the older heuristic fixer.

### Authorized security research
- Bug-bounty programs now record an authorization source/status and lock the scope by default.
- Scope expansion requires an explicit authorization marker rather than silently expanding a target set.
- Active testing requires a recorded owner-confirmed authorization state and a locked scope.
- The intended security-research model remains authorized programs only; this is not an unrestricted offensive scanner.

## Verification

The complete repository test suite after the hardening pass:

- **244 passed**
- **1 skipped**
- Runtime: about **14 seconds** in the test environment.
- All Python files compile successfully.

## Important truth

This package is substantially safer and more coherent than the original, but it is not a mathematical guarantee of zero vulnerabilities, automatic profitability, or unrestricted real-world autonomy.

Production deployment still depends on the host OS, credentials, installed browsers/tools, provider availability, external service policies, and the permissions you explicitly grant.

The architecture deliberately keeps powerful capabilities behind policy, scope, evidence, tests, rollback/approval and audit boundaries so the agent can become more autonomous without turning every bug in an acquired tool or model response into unrestricted host access.
