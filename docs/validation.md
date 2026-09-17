# Validation, failure evidence and limits

## What was executed

The complete verification ran locally on Windows with Python 3.12, actual SciPy/HiGHS mixed-integer solves, a separate integer accountant, an exhaustive configuration enumerator, filesystem output, and real CLI subprocesses. The final installed-wheel run passed **51 tests with zero failures, errors or skips**. Lint, dependency checks, the asserted demonstration and CLI solve/check round-trip also passed. Exact package versions, timestamps, installation mode and source/fixture hashes are in [verification.json](evidence/verification.json); individual cases are in [tests.xml](evidence/tests.xml).

The production compiler does not validate itself. The independent accountant reads the original workload contract rather than compiler coefficients. The exhaustive oracle evaluates every combination directly: all 3,125 options combinations in the launch fixture and 64 seeded randomized small models. Other targeted cases address exact arithmetic and failure boundaries. Enumeration is explicitly capped to prevent its use as an unbounded production search.

## Claim-to-counterexample mapping

| Claim | Falsification exercised |
|---|---|
| Feasible global cost optimum | MILP and complete enumeration agree on feasibility and objective, including randomized infeasible cases |
| Shared platform economics | Two workflows share one fixed fee; a per-workflow fee mistake would choose or price the plan incorrectly |
| Correct batching | 101 records with a 100-record batch size consume two requests; zero demand consumes zero requests but does not cancel a selected platform fee |
| Bursts and total use both matter | A plan fits the horizon allowance yet exceeds one slot; another fits every slot but exceeds the total |
| Robustness uses one configuration | Crossing demand scenarios expose fixed fees even in a scenario where the enabled platform has zero traffic; independently choosing after seeing each scenario would report a falsely cheaper answer |
| Cheapest is not automatically eligible | Missing deletion/field support, wrong region and excessive latency each independently exclude a zero-priced alternative |
| One cent is meaningful | Budget at the exact optimum succeeds; one cent below is infeasible |
| Conflict diagnosis is qualified | A complete reduced conflict is infeasible; dropping any retained row makes it feasible. A zero diagnostic budget is explicitly incomplete |
| Solver failure cannot become a recommendation | Injected limit/error statuses and solver exceptions return no selection; fractional/nonfinite/missing choices, missing bounds, incorrect costs and actual quota violations are rejected |
| Assumptions cannot drift silently | Changes to demand, price, capacity, freshness, capability or implementation invalidate saved plans |
| Contracts are strict | Unknown references, missing scenario inputs, duplicate keys/IDs, invalid numeric types and zero batch sizes are refused |
| Artifact output is complete | Injected replacement failure preserves previous bytes, removes the temporary file and reports failure; real CLI argument/exit handling is exercised |

The solver-limit/error tests inject backend outcomes to verify application handling; they are not claims of a killed native solver or a measured timeout SLA. File replacement failure is injected; sudden host power loss is not tested.

## Unfavorable results are retained

The [executed report](evidence/report.md) and [full proof](evidence/planning-proof.json) include the normal-only plan's surge violations, the cheap lossy plan's semantic failures, the infeasible budget, and the infeasible 30-request/hour capacity case. These are expected adverse planning outcomes, not test-suite failures hidden from the report. No failing automated test remains in the delivered scope.

The reference is a declared all-premium synthetic configuration that is feasible under the same inputs. The modeled 558-cent difference is relative to that reference, not proof of achievable customer savings or a vendor price comparison. Normal-only optimization is shown to fail under the full scenario set rather than used as a flattering baseline.

## Skeptical review and changes

Review focused on whether numerical success could mislead a hiring-panel reader. It added a crossing-scenario regression to prove that platform costs remain nonanticipating, independent checks of solver objective/lower bound and route accounting, exact budget/batch edges, incomplete-conflict labeling, and stale-artifact checks. Input validation explicitly rejects an unhashable platform reference rather than letting it escape as an unrelated runtime error. Diagnostic backend failures retain an incomplete diagnosis instead of destroying an already established infeasibility result.

The claims were narrowed where software cannot supply the missing evidence: latency is declared rather than measured; semantic capability is declared rather than integration-tested; the stored-plan checker verifies feasibility but does not reprove optimality; and conflict minimality is relative and irreducible, not minimum cardinality. The result is an optimization proof conditional on inspectable assumptions.

## Known limitations

- **Input calibration is the main production gap.** There are no real vendor measurements, prices, source accounts or field-preservation experiments. False route declarations can make a mathematically valid plan operationally wrong.
- **Finite scenario protection only.** No probabilistic SLA, chance-constrained forecast, seasonality model or protection against an omitted outage is claimed. Correlated risks must be represented deliberately in scenarios.
- **Coarse capacity envelope.** Work stays in its declared slot. Within-slot concurrency, queues, retry storms, paging consistency, backpressure and deadline distributions are not simulated. The model does not establish latency from quota arithmetic.
- **Bounded economics.** One integer per-batch price and one fixed per-platform horizon charge; no contract tiers, discounts, migration expense, termination fees, minimum commitments or shared-record caching. The comparison is one modeled operating decision, not total cost of ownership.
- **Solver trust and numeric methods.** Feasibility is rechecked with integer arithmetic. Optimality/infeasibility beyond the enumerated cases relies on HiGHS and the compiler tests. This is not a formally certified optimizer or a proof against malicious solver/code substitution.
- **Bounded size and runtime.** Up to 12 workloads, six routes each, eight platforms, six resources, six scenarios and 24 slots. These are input limits, not a demonstrated maximum throughput. No sustained optimization benchmark, distributed scale or service SLA is claimed.
- **Local artifacts.** Hashes and atomic replacement prevent ordinary stale/partial use. They are not signatures, access control or independent attestation; local operators own their files. Consumers must honor nonzero exit codes.
- **No execution authority.** No vendor configuration, migration, approval, customer membership or campaign action is changed. A production adapter would need separate validated contracts and the existing portfolio's execution safeguards where appropriate.
- **Hosted CI remains unobserved.** The new workflow is configured for Windows and Ubuntu; only local Windows execution is claimed. Current successful runs of the four inspected existing repositories are retained separately and do not establish this new project's CI success.
