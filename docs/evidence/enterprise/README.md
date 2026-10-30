# Enterprise economics evidence

This directory adds an annual modeled decision to the preserved [bounded HTTP execution evidence](../execution/README.md). It does not replace or rescale that historical experiment.

- [Complete deterministic decision and input snapshot](acceptance/decision.json): monthly source records/counts, fan-out, batches, retry overhead, costs, allocation, selected routes, capacity headroom, independent oracle results, 22 sensitivities and one-cent budget rejection.
- [Executed source/environment record](acceptance/verification.json): exact source revision and file hashes, execution time and decision digest.
- [Actual desktop console](browser/optimized-operating-desktop.png), [mobile](browser/optimized-operating-mobile.png), [resilient disruption](browser/resilient-campaign-disruption-desktop.png) and [browser provenance](browser/browser-verification.json).
- [Original implementation and evidence preservation](preserved-files.json), verified against merged PR #3.
- [Assumptions, billing units, mathematics and reproduction](../../enterprise-economics.md).

## Interpretation

The model computes an average 100M monthly source-event scenario; no 100M-event HTTP workload was executed. Its annual costs are **synthetic USD assumptions**, not native vendor pricing or demonstrated client savings. The three alternatives are assessed against identical monthly demand and prices. Disruption is an alternative year, not an extra charge added to normal operations.

The operating optimum is USD $187,453.59 annually. The mixed reference is USD $281,919.28. The resilient minimax choice costs USD $196,748.14 during normal operations and USD $200,608.52 under disruption. All three satisfy the original declared envelopes. More severe constrained-quota/throughput inputs produce different tiers; budget and route-requirement violations can produce infeasibility. We do not invent a failed base scenario to make the resilient choice look mandatory.

Hourly capacity, emission intervals and route latency are input assumptions. The worker reserve and balanced-arrival model do not prove burst queue latency, residency or strict receiver-arrival rate guarantees. No measured extrapolation joins these values to the separate local HTTP timings.

The original 60-test baseline, 3,125-choice fixture, prices, all historical receiver observations and slower Windows rejection remain unchanged. Current test results are recorded by each verification run and by GitHub Actions; archived counts remain historical.
