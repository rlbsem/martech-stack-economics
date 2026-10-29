# Executed architecture assurance

Actual local HTTP processes and independent SQLite receiver journals, synthetic business records and prices. No native vendor integration, cloud deployment or commercial savings claim.

Execution source: [`e041863f416af3289e8dfa4a94956ae975aed164`](https://github.com/rlbsem/martech-stack-economics/tree/e041863f416af3289e8dfa4a94956ae975aed164). [Source fingerprints and environment](acceptance/verification.json). [59-test result](acceptance/mathematics/tests.xml). [Independent mathematical proof](acceptance/mathematics/report.md).

## Recorded decisions

The default profile maps 60 modeled minutes to 36 real seconds. Each original four-slot scenario was executed; the blocked decision launched no HTTP workload. An acceptable result applies only to this finite local business-constraint trial. It does not establish a route latency envelope, vendor SLA, residency guarantee or production throughput.

| Trial | Decision | On-time source operations | Predicted synthetic USD | Observed synthetic USD |
|---|---|---:|---:|---:|
| [normal](acceptance/execution/normal/result.json) | Acceptable | 5,400 / 5,400 | $5.18 | $5.18 |
| [launch-surge](acceptance/execution/launch-surge/result.json) | Revision required | 50,200 / 56,700 | $7.82 | $7.32 |
| [transient-recovery](acceptance/execution/transient-recovery/result.json) | Revision required | 50,450 / 56,700 | $7.82 | $7.35 |
| [delayed-source](acceptance/execution/delayed-source/result.json) | Revision required | 4,800 / 5,400 | $5.18 | $5.10 |
| [slow-destination](acceptance/execution/slow-destination/result.json) | Revision required | 4,900 / 5,400 | $5.18 | $5.23 |
| [shared-quota-pressure](acceptance/execution/shared-quota-pressure/result.json) | Revision required | 47,700 / 56,700 | $7.82 | $7.10 |
| [revoked-permission](acceptance/execution/revoked-permission/result.json) | Revision required | 0 / 5,400 | $5.18 | $4.70 |
| [capacity-revision](acceptance/execution/capacity-revision/result.json) | Acceptable | 56,700 / 56,700 | $12.36 | $12.36 |
| capacity-blocked | Blocked / infeasible | Not executed | — | — |

A lower charge for incomplete work is **not** an acceptable saving. Counts represent synthetic upsert/delete operations, not real customers or commercial outcomes. Unresolved state may include an already committed remote effect and can overlap late records; those categories must not be added as disjoint totals.

The 60-request capacity revision keeps all business requirements, demand, prices and freshness limits unchanged. It explicitly updates capacity assumptions, selects a different feasible architecture and uses fresh synthetic receiver state. The 30-request revision has no feasible selection. Earlier evidence remains intact.

## Inspect and reproduce

- [All decision documents, parent versions and transitions](acceptance/execution/summary.json)
- [Independent checker](../../../scripts/check_execution.py)
- [Execution contracts and limitations](../../execution-assurance.md)
- [Original mathematical evidence, preserved](../report.md)
- [Preserved development failures and source-binding limitations](development/README.md)

Each executed trial directory contains `observations.json.gz`: full source batch bodies, separate control attempts, independent receiver arrivals/receipts and final destination records. `python scripts/check_execution.py --evidence docs/evidence/execution/acceptance/execution` reopens every observation, checks hashes and recomputes the outcome.

The small protocol tests separately execute a real child-process crash after commit, exact receipt recovery, duplicate and changed-content retries, budget overrun, source isolation, late commits and altered measurements. A full transient-fault surge can correctly fail freshness even when acknowledgement recovery works.

The [browser verification record](browser/browser-verification.json) binds the execution summary, separate UI revision and actual UI file bytes. All **36 collapsed/expanded desktop/mobile states** passed the executed axe checks, with no page errors. Six genuine screenshots include the [accepted capacity revision](browser/capacity-revision-desktop.png), [rejected quota trial](browser/shared-quota-pressure-desktop.png) and [blocked mobile decision](browser/capacity-blocked-mobile.png). Automated accessibility checks are not a complete human accessibility audit.

The [separate financial audit](financial-audit.json) recomputes pricing and API arithmetic using only the standard library. [Independent local teardown](local-teardown.json) found all 24 receiver ports closed and no matching receiver processes remaining. This is local cleanup evidence, not cloud or billing clearance.

UI and execution revisions are deliberately separate. Historical records are never relabeled as execution of newer code. CI repeats actual execution on each proposed release head; its run records remain distinct from the committed local observations above.

## Host-dependent rejection and CI failure propagation

The local capacity revision above passed. The same profile on a slower Windows GitHub runner delivered **43,700 / 56,700 operations on time** and correctly remained `revision_required`. Its original [observations](ci-windows-rejection/observations.json.gz), [result](ci-windows-rejection/result.json) and [source/run context](ci-windows-rejection/context.json) are preserved. No freshness, quota, pricing or source constraint was relaxed.

Artifact inspection exposed a workflow defect: a later successful command masked the verifier's failed exit status in PowerShell, leaving no completion record. That job status is not accepted as completed verification. The workflow now uses a single acceptance command; checked child processes and the financial audit must finish before a completion record is written.

Evidence integrity and architecture acceptability are separate. The verifier accepts an accurately recorded rejection and rejects a fabricated success; a dedicated real-HTTP regression exercises both cases. This does not turn the Windows revision into an acceptable outcome or establish equivalent capacity across hosts.

The [subsequent local regression](regression-late-commit/tests.xml) executed 60 tests. Its late-effect probe isolates one real batch: admission precedes the five-second freshness deadline, six seconds of receiver processing cause a late commit, and observation waits for that committed effect. This avoids depending on all source setup finishing inside a one-second window. The original financial and freshness rules remain unchanged.
