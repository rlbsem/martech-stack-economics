# Decision before implementation

The public portfolio inspection on 2026-09-17 identified four general-purpose architecture projects. A separate game-telemetry project was excluded from this MarTech portfolio comparison. Fresh commit IDs and observed current-commit workflow status are retained in the [inspection record](portfolio-inspection.json), alongside the [read-only profile snapshot](inspected-profile.md); existing suites were inspected, not rerun. Some existing README CI disclaimers lag the successful current-commit workflow statuses observed in this inspection.

## Capability gap

| Inspected implementation | Already convincing | Missing from this problem space |
|---|---|---|
| Control plane: `worker.py`, policy/service transactions, governance/execution tests, architecture and limits | Authority, durable execution, remote uncertainty, retries, idempotent effects | Retries and budgets do not decide the least-cost feasible allocation of shared capacity |
| Agent evaluation: evaluator, release model, failure/release tests, actual unfavorable live evaluation | Grounding, agent quality, release evidence and regression rejection | Model quality evaluation does not optimize an integration estate |
| Temporal audiences: feature SQL, incremental engine, coverage gate, oracle and boundary tests | Bitemporal audience semantics, cache invalidation, absence safety | Customer membership is a different computation from cost/capacity planning |
| Migration assurance: independent audit, snapshot/transfer/coordinator, crash/cutover tests | Semantic preservation, cutover and reverse transfer | Safe replacement does not establish whether a proposed operating configuration is economical or adequately sized |

These findings are grounded in current source snapshots, READMEs, architecture/validation documents, test implementations and generated reports. They are not repository-title assessments. The agent's unfavorable live outcomes remain important evidence, not a reason to duplicate its evaluator.

## Selected project

**MarTech Stack Economics** computes the cheapest integration configuration that meets finite, explicit business constraints across supplied demand/capacity scenarios. It chooses one semantically eligible route per workflow, accounts for shared subscription charges once, rounds real batch requests upward, and enforces both hourly and horizon-wide quotas. It retains the rejected cheaper plan, capacity violations, cost comparison and a diagnosable infeasible case.

The business decision is whether to consolidate or change integration execution modes without making launch-day work late, losing required fields/deletions, or exhausting a shared API budget. Costs and route service envelopes are synthetic inputs; no vendor quote, measured SLA or realized saving will be claimed.

## Alternatives rejected

- Another campaign agent: overlaps the current runtime, grounding and release evaluation; adding content generation would not prove the uncovered optimization responsibility.
- A general integration executor or migration tool: durable delivery and platform replacement already have substantial evidence.
- A causal marketing experiment platform: valuable but less directly related to the stated platform-architecture responsibilities and would require a different statistical/domain scope.
- A stack inventory dashboard or weighted vendor scorecard: easier, but would not demonstrate constrained feasibility or optimality.

## Architecture choice

Python compiles a closed JSON planning contract into a mixed-integer linear model. SciPy's HiGHS-backed MILP solver supplies established discrete optimization instead of an improvised production search algorithm. An independent integer accountant rechecks every chosen route against the original input, while exhaustive enumeration establishes optimum equivalence on bounded test cases. No AI is needed: the important decisions are explicit constraints and arithmetic.

This is an offline engineering decision tool. It does not dispatch campaigns, govern customer state, migrate data or claim a live integration. A database, broker, web service and cloud environment would not strengthen its central proof. The plan records exact input and implementation identity; changed assumptions require a new solve and assessment. Finite scenarios are stress cases, not probabilities or a guarantee against unmodeled incidents.
