# Annual enterprise economics contract

## Workload and time horizon

The separately versioned `enterprise-economics/v1` contract extends planning without changing the original four-hour compiler, accountant or 3,125-choice fixture. The full input is [multibrand-2026.json](../fixtures/enterprise/multibrand-2026.json). Every monetary value is integer **USD cents**. All prices are synthetic allocated assumptions, not vendor quotes, actual procurement or client expenditure.

Eight mutually exclusive **source event families** total 100 million per baseline month: web 65M, product 18M, profile changes 6M, identity links 4M, consent 1M, CRM handoffs 2M, activation 3M and attribution 1M. A profile change is not a unique customer. Twelve million customers is a separate population assumption, not inferred from events.

Explicit downstream multipliers of 1, 1, 2, 1, 3, 1, 2 and 1 produce 111 million downstream records per baseline month. Categories do not double-count input events; downstream fan-out is deliberately counted separately. The same logical customer may appear in many changes. These are aggregate planning inputs, not materialized records claiming executed ingestion.

The calendar is 2026: actual days per month and volume weights **80, 82, 90, 95, 98, 100, 96, 100, 105, 115, 130, 109%**. The weights sum to 1,200%, yielding 1.2B annual source events / 1.332B downstream records. A separate alternative disruption year uses 125% volume, 180% peak concentration, 10% retries and 70% normal CRM quota. The normal year uses 2% retries. These retry fractions are explicit deterministic planning allowances, not inferred failure probabilities.

## Route and dependency decisions

| Route | Emission interval / declared lag | Maximum records / request | Platform role |
|---|---:|---:|---|
| Stream | 1 minute | 250 | Shared event fabric |
| Microbatch | 5 minutes | 1,000 | Integration hub |
| Bulk | 60 minutes | 5,000 | Governed warehouse |

CRM, CDP, journey orchestration, warehouse, identity and consent are representative enterprise roles. Salesforce, Adobe Experience Platform / Journey Optimizer and Snowflake are examples of those roles, not live connectors in this repository. `purpose` links every workload to a source/destination dependency. Profile and consent workloads require deletion support; the bulk route only supports event/analytics capabilities. Consent requires a one-minute route. European processing is a declared eligibility requirement, not a certification.

Requests are rounded **per emission window**, not once per month. The monthly downstream record count is distributed as evenly as possible across `days × 1,440 / interval_minutes` windows, with remaining records assigned one per window. Each non-empty partial batch consumes a full request. Retries are `ceil(original_requests × retry_percent / 100)`, separate from logical downstream records. Zero records produce zero requests.

This model assumes balanced traffic within each hour. Peak hour demand is 0.4% of monthly records, or 0.7% for activation, multiplied by the disruption peak factor. Peak requests are independently rounded across the hour’s emission windows, including retries. For 60-minute and slower routes, the route emits at most once within the selected peak hour. Peak workers consume one unit per microbatch/bulk attempt or three per stream attempt. CRM prerequisites consume the per-route declared additional call count; these are **not** identical to destination requests. Non-CRM source/event routes consume no CRM calls.

Hourly demand must fit **80% of shared worker capacity** and the condition-adjusted CRM quota. This is a peak-envelope check with headroom, not a discrete-event queue simulation. It implies no growing fluid backlog under balanced arrivals, but does not prove arbitrary intra-hour burst latency, queue tails or a provider's rolling arrival limit. Freshness is enforced through the route's declared lag, not derived from a measured enterprise scheduler. The bounded execution suite separately tests real queues and deadlines; it does not calibrate these enterprise service assumptions.

## Synthetic price book and allocation

| Component | Assumption | Billing treatment |
|---|---|---|
| Event fabric subscription | USD $3,500 / month | Once if any route uses it |
| Integration hub subscription | USD $6,000 / month | Once if any route uses it |
| Warehouse allocated fixed share | USD $1,800 / month | Integration workload share, not entire warehouse bill |
| Worker capacity | USD $1,100 / worker-month | 4 / 8 / 16 workers, fixed annual tier |
| Operational support | USD $150 / hour | 8 / 14 / 22 allocated hours per month by tier |
| Shared request allowance | 400K / 900K / 1.8M per month | Tier allowance; USD $0.01 per excess attempt, no carryover |
| Logical record processing | USD cents 3 / 1 / 1 per thousand | Stream / microbatch / bulk; fan-out records billed once |
| Request overhead | USD cents 30 / 15 / 5 per thousand attempts | Includes original attempts and retries |
| Egress | USD cents 80 / 40 / 0 per GiB | Logical payload bytes, no cross-region transfer assumption |
| Warehouse processing | USD cents 0 / 0 / 700 per TiB | Bulk input bytes; unrelated warehouse queries excluded |

The allowance is a shared broker/dispatch charge; the route request fee is a separate destination-adapter overhead, so both are explicit components. Worker allocation includes reserved compute capacity. Request overhead includes retry processing; record/egress/warehouse billing is based on logical delivered volume, not rebilled on a retry. The bounded trial accountant has its own unchanged price book; neither converts to a real cloud invoice.

Component charges are rounded upward to cents per workload/month, then summed. Fixed charges are paid every month of the selected annual configuration; no switching routes or tiers to exploit one month. Shared fixed costs and overage are allocated by each workload’s downstream records, floor-rounded with residual cents assigned to the first workload. This affects attribution only, never the total or solver decision. Every month's allocated workload lines reconcile exactly to its bill; annual totals are the sum of twelve actual monthly bills.

Capacity tiers have different throughput, CRM quotas and monthly allowances. Their costs are not linear event multipliers. Subscriptions, unused allowances and burst overage can make doubling demand much cheaper or more expensive than doubling annual cost. Taxes, enterprise discounts, procurement, migration/change costs, license entitlements, independent security certifications and real commercial outcomes are excluded.

## Optimization and independent verification

The annual MILP chooses one route per workload, one shared capacity tier and exactly the used platforms. Monthly nonnegative integer overage variables represent `max(0, aggregate_attempts − selected_allowance)`. A minimax variable bounds every selected condition’s annual bill. The operating optimum uses only the operating condition; the resilient optimum minimizes the worst annual bill over both conditions. Both retain every business constraint and the USD $800,000 synthetic annual budget.

The reference is a plausible separately declared design: microbatch routes for most integrations, streaming consent, bulk attribution and an eight-worker tier. It is not the optimizer’s incumbent and is not an all-premium strawman. It retains capacity for a broader integration footprint; the comparison explicitly includes the cost of reducing that allocation. Its optional bulk platform is a reference design choice, not a claim that every enterprise would buy a warehouse solely for one workload.

Independent `enterprise/accounting.py` imports no compiler or solver. It recalculates all record, request, retry, peak, cost and allocation lines using separate integer arithmetic. It enumerates this bounded fixture: **19,683 raw route/tier combinations**, pruned by capability/region/freshness to **576 eligible combinations actually assessed** per condition set. The MILP optimum, solver dual bound and independent minimum agree. No claim of exhaustive verification for unbounded enterprise designs is made; the oracle refuses spaces above 100,000. The original 3,125-case oracle is untouched.

Twenty-two one-variable sensitivities cover demand, processing prices, CRM quota, worker throughput and tightened freshness. All are solved and independently enumerated. The package also retains a one-cent-below-optimum infeasibility result. Tests cover partial and zero batches, rounding, allocation, monthly/annual consistency, source-unit separation, invalid currency/inputs, unknown routes, lost capabilities, region/freshness exclusion, quota infeasibility, unavailable solver results and tier behavior.

## Reproduction and evidence

```bash
python scripts/enterprise_verify.py --check docs/evidence/enterprise/acceptance
python scripts/enterprise_verify.py --output .local/enterprise-new
python -m stack_economics.enterprise.console --enterprise .local/enterprise-new
```

The source scenario, deterministic decision package and source-bound verification are preserved separately from [historical HTTP evidence](evidence/execution/README.md). The console checks decision integrity and serves only explicit read-only routes on loopback, with Host/Origin checks, no write endpoints and a strict content policy. It remains a local inspection tool, not an authenticated multi-user service. `/execution` preserves the previous console and its independent journal downloads.

## Browser verification

```bash
python -m pip install -r requirements-browser.lock
python -m playwright install chromium
python scripts/fetch_browser_tools.py
python scripts/enterprise_browser.py --enterprise docs/evidence/enterprise/acceptance --execution docs/evidence/execution/acceptance/execution --output .local/enterprise-browser-new
```

Actual Chromium screenshots and pinned axe checks cover desktop/mobile, all three architectures, both conditions, January/November, collapsed/expanded evidence, five sensitivity controls, exact JSON downloads and the preserved execution view. Browser source hashes and the enterprise decision hash are recorded independently. CI also executes the original regression and actual HTTP suite on Linux, Windows and an isolated container. A passing software/evidence check does not turn a rejected timing result into architecture acceptance.
