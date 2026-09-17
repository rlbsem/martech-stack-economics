# Architecture and mathematical contract

## The decision boundary

Input describes a bounded planning horizon, alternative execution routes and a finite set of demand/capacity scenarios. The system chooses exactly one route per workflow and minimizes the **maximum scenario cost** while satisfying every scenario's constraints. It does not average away a bad launch scenario or assume a configuration can be chosen after the scenario is known.

All quantities are declared inputs. The four-slot example is four hours; fixed fees and usage prices must use that same horizon. A fixed fee is the allocated enablement charge for that horizon, not a real vendor's monthly subscription. Each workload's records are independent units of required integration work. Two workflows are not assumed to share the same source records, so their traffic is not silently deduplicated. Sharing a platform shares its fixed charge, not its data semantics or request allowance.

Route `resources` specifies requests consumed on each named shared quota per emitted batch. The example models shared CRM, destination and bulk-job budgets. The batch size is a maximum, not an assumption that every batch is full. Demand in slot t must be handled in slot t; the model cannot move work into spare capacity later. This is a planning constraint, not an implemented scheduler.

Freshness is a declared upper latency envelope for a route operating within the supplied capacity budget. It must be no worse than the workload requirement. The code does not infer that envelope from hourly capacity. Real deployment decisions need measured profiles and vendor semantics; without them, mathematical feasibility is only conditional feasibility.

## Variables and constraints

For workflow w and route o, binary `x[w,o]` indicates selection. Binary `y[p]` indicates a platform is enabled. Integer z bounds worst-scenario cost. For supplied demand `d[s,w,t]` and route batch size b:

```text
batches[s,w,o,t] = ceil(d[s,w,t] / b[w,o])
sum_o x[w,o] = 1
x[w,o] <= y[platform(w,o)]
y[p] <= sum_{w,o using p} x[w,o]

for each scenario s, resource r, slot t:
    sum_{w,o} batches[s,w,o,t] * requests_per_batch[w,o,r] * x[w,o]
        <= capacity[s,r,t]

for each scenario s, resource r:
    sum_{w,o,t} batches[s,w,o,t] * requests_per_batch[w,o,r] * x[w,o]
        <= total_capacity[s,r]

for each scenario s:
    sum_p fixed_cost[p] * y[p]
      + sum_{w,o,t} batches[s,w,o,t] * batch_cost[w,o] * x[w,o] <= z
z <= budget
minimize z
```

Ineligible routes have x fixed to zero by named business constraints. Eligibility requires all declared capabilities, an allowed region and acceptable latency. A deletion-capable route is a declared semantic property; the planner does not manufacture or test deletion support itself. The allowed-region test is not a privacy or residency certification.

`model.py` creates named constraint rows, compiles a numeric matrix and calls SciPy `milp`. Monetary inputs are integer cents; demand, batch sizes and quota units are integers. Contract bounds keep arithmetic well below binary64's exact integer range. The solver still uses floating-point numerical methods internally. The planner requires optimal status, zero reported relative gap, agreement between the objective and lower bound, integral choices within tolerance, and exact integer accounting of the chosen plan. A tolerance is never used to excuse a real one-request quota violation or one-cent budget excess.

SciPy documents `milp` as a wrapper around HiGHS, with separate statuses for optimal, limit reached, infeasible and errors. The implementation uses a tested pinned release rather than claiming the newest version. [Official SciPy MILP reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html).

## Independent verification

`accounting.py` selects routes directly from the original input. It recomputes batches using quotient/remainder arithmetic, checks semantic eligibility, sums requests by resource/slot and horizon, charges each enabled platform once and checks every scenario's cost. It imports neither `model.py` nor solver state.

The planner discards a claimed optimal vector if it is fractional, non-finite, incomplete, over quota, over budget, has mismatched platform charges, or disagrees with independent cost accounting. A separate exhaustive Cartesian-product oracle proves the same optimum or infeasibility on bounded cases. It checks all 3,125 choices in the main fixture, plus seeded randomized small models. This validates the compiler against a different algorithm, not just the solver's returned matrix.

The independent accountant proves feasibility of a configuration conditional on the input contract. It does not itself prove optimality. Solver optimum/infeasibility claims rely on the established solver; exhaustive enumeration provides an independent optimum proof only for the executed bounded cases. Shared mistakes in the written business contract remain possible.

## Explain infeasibility without inventing a recommendation

Structural route-choice, platform-linkage and cost-definition rows always remain. Starting from an infeasible model, the diagnostic removes a business row only when another solve proves the remainder infeasible. At completion, every retained row is needed relative to that remainder. This is an **irreducible business conflict**, not necessarily the smallest conflict and not a unique business remedy.

Every row has an inspectable name: budget, workflow/route eligibility, or scenario/resource/slot quota. If a diagnostic reaches its solve budget, errors or receives an unresolved answer, it labels the result an unreduced infeasible set. It never calls a partial reduction minimal. The initial infeasibility conclusion remains the original solve's result. A fully reduced conflict can be checked by proving it infeasible and showing that removing any one retained row makes it feasible; an automated test does so.

Diagnostics have up to 100 solver calls, each capped at two seconds. Main solves default to ten seconds, capped at sixty. The process and dependency import time are outside those solver limits; this is not a hard wall-clock service SLA. Large finite models may return unresolved rather than a useful recommendation.

## Artifacts and operation

Each result binds the complete input hash and current package implementation hash. The stored-plan checker recomputes the assessment and refuses changed demand, prices, capacity, semantic requirements or implementation. It verifies feasibility/accounting, not the truth of input observations or an adversarially forged optimum. Files are ordinary local artifacts, not signed attestations.

The CLI writes complete JSON to a sibling temporary file, flushes it and atomically replaces the target. A failed replacement preserves the previous file and returns a failure exit code; consumers must honor exit codes and input identity. This is protection against partial output, not a power-loss or malicious-administrator guarantee. No existing repository or external application is modified.

## Deliberate architectural choices

- An established MILP solver handles shared fixed costs and competing quotas. Sorting each workflow's route prices independently misses those couplings. Exhaustive enumeration stays a bounded test oracle.
- A closed catalogue avoids a general rule language, executable user expressions or an agent whose recommendations would require a second correctness system.
- An offline CLI and JSON artifacts are enough to make architecture decisions reproducible. A database, event broker, cloud stack or live campaign executor would shift the project into already demonstrated portfolio territory.
- Finite scenario robustness is understandable and auditable. It is not a probability model, chance constraint or promise about all future loads.
