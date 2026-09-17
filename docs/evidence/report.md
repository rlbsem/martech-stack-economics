# Executed integration economics proof

All demand, costs, capability declarations and service envelopes are synthetic. These are computed planning results, not observed vendor performance or business savings.

| Question | Executed result |
|---|---|
| Cheapest scenario-feasible modeled configuration | 782 cents per four-hour horizon |
| Feasible all-premium reference | 1340 cents per horizon |
| Difference against that reference | 558 cents (41.6%); hypothetical input-model difference |
| Independent optimum check | Enumerated all 3125 configurations; same optimum |
| Normal-only cheaper configuration under surge | Rejected for shared capacity violations |
| Cheapest lossy route | Rejected for freshness, missing capabilities and region |
| Budget of 781 cents | Infeasible; no recommendation |
| Saved recommendation after assumptions change | Refused as stale |

## Selected routes

| Workflow | Route |
|---|---|
| lead-handoff | stream |
| campaign-suppression | stream |
| attribution-refresh | bulk |
| web-personalization | stream |
| product-enrichment | bulk |

## Capacity tradeoffs

Each row is a new solve with the same demand and hourly CRM capacity changed in every scenario. These finite differences are not continuous shadow prices or purchase recommendations.

| CRM requests per hour | Status | Worst modeled cost, cents |
|---|---|---|
| 100 | optimal | 782 |
| 90 | optimal | 1236 |
| 60 | optimal | 1236 |
| 40 | optimal | 1236 |
| 30 | infeasible | no feasible plan |

[Full assumptions, rejected plans, charges, quotas, headroom and conflicts](planning-proof.json)

The optimizer chooses one fixed configuration for all supplied scenarios. It does not dynamically switch after observing a surge. The capacity model includes both per-hour and horizon quotas; it does not model within-hour queuing. Route latency bounds are declared inputs conditional on staying within capacity, not measured guarantees.
