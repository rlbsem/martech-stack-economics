# Reproduce and operate the local planner

Use Python 3.12. Activate a new environment with `.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` in bash. From the repository root:

```bash
python -m pip install -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e .
python scripts/verify.py
```

NumPy and SciPy are runtime dependencies. Other pinned packages support testing, lint and packaging. The lock records tested versions, not currency. Installation needs package-download access; execution and verification use no network.

## Commands

```bash
stack-economics solve fixtures/campaign-launch.json --output work/plan.json
stack-economics check fixtures/campaign-launch.json --plan work/plan.json --output work/check.json
stack-economics assess fixtures/campaign-launch.json --selection docs/evidence/reference-selection.json --output work/reference.json
python scripts/demo.py --output work/demo-evidence
```

Selections map every workflow ID to exactly one of its option IDs. `assess` can deliberately evaluate a bad plan under new assumptions and preserve exact violations. `check` is stricter: an existing recommendation is bound to its original input and implementation. A changed input must be explicitly solved again. There is no automatic deployment.

| Exit code | Meaning | Operator response |
|---|---|---|
| 0 | Optimal checked solve, successful stored-plan check, or feasible assessment | Read the input assumptions and report before using the decision |
| 2 | Infeasible solve or infeasible supplied selection | Inspect named conflicts or exact violations; do not interpret an empty selection as a zero-cost plan |
| 3 | Solver limit/error or failed independent verification | No recommendation; inspect the status, reduce the model or investigate the solver/contract discrepancy |
| 4 | Invalid input, stale/corrupt artifact, or file failure | Correct the input/path; a prior output file may remain and must not be treated as this run's success |

`solve --seconds 20` changes the main solver budget. It does not authorize a suboptimal incumbent. Diagnostic reduction has its own bounded calls, documented in architecture. You may repeat a solve, but equal-cost route ties are not a business preference ranking; compare objective and feasibility, not necessarily identical route identity across library versions.

## Input discipline

The sample JSON is complete and editable. `schema` is 1, currency is USD, and every scenario must provide every workflow and every resource for every slot. Partial scenario input is refused rather than treated as zero. Duplicate JSON keys/IDs, booleans in integer fields, zero batch sizes, unknown references, negative costs and unsupported shapes fail validation.

Use one economic horizon consistently. Include capacity consumed by external workloads by reducing the available quota before supplying it. Keep burst/slot limits separate from the total allowance. Do not smooth a launch spike into the daily average. Capability and latency declarations require evidence outside this synthetic system; the planner cannot discover whether a real API drops deletes or loses custom fields.

Fixed fees are incurred for enabled routes even if a scenario has zero traffic. Requests/usage cost are zero for zero demand. Requests for a partial batch round up. There is no cancellation credit, vendor tiered pricing, cache-hit inference, shared-record deduplication or unmodeled retry allowance. Include operational headroom explicitly in scenario capacities and demand.

## Evidence

`planning-proof.json` retains all assumptions, the robust plan, the overloaded nominal plan, the feasible premium reference, the lossy route rejection, capacity tradeoffs and below-optimum budget failure. `recommended-plan.json` is suitable for the check command. `verification.json` binds the executed source, fixture, environment and test counts; `tests.xml` lists the individual tests.

The supplied GitHub Actions workflow runs the same verification on Windows and Ubuntu. It is configuration, not an observed hosted pass for this new repository. Publish the ZIP contents as a new repository when ready, then observe both jobs. Existing portfolio repositories were only inspected and remain untouched.
