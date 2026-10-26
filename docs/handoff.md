# MarTech Stack Economics: technical verification and release

An offline integration-cost and capacity planner with a closed planning contract, mixed-integer solver, independent integer accountant, generated evidence and automated verification.

## Verified results

- The synthetic four-hour launch scenario produces a modeled optimum of **782 cents** against a feasible **1,340-cent** all-premium reference. These are artificial input prices, not vendor quotes or realized savings.
- Independent enumeration of **3,125 possible configurations** agrees with the chosen optimum.
- The normal-only plan violates launch demand; a cheaper lossy route fails capability requirements.
- A 781-cent budget is infeasible. Reducing CRM capacity to 30 requests/hour leaves no feasible plan.
- Packaged-install verification recorded **51 passing tests** with lint, dependency checking and an actual CLI round-trip. [Hosted GitHub Actions verification](https://github.com/rlbsem/martech-stack-economics/actions/runs/38501653389) passed on Ubuntu and Windows.

[Business result](evidence/report.md) · [Detailed proof](evidence/planning-proof.json) · [Validation boundaries](validation.md) · [Operating instructions](operations.md)

## Engineering boundary

Python compiles the scenario contract into a constrained optimizer with shared fees, rounded batch calls, time-specific API budgets, required functionality, geography and latency restrictions. SciPy/HiGHS solves the problem. The independent accounting path recomputes every chosen route; a finite enumeration oracle checks the optimum in small cases.

This project **informs** architecture choices. It does not dispatch data, govern customer truth, implement a production integration, establish real-world vendor performance, or prove savings. Scenarios and costs are synthetic.

## Operational pilot requirements

1. Replace fictional costs, capabilities, capacity and latency assumptions with measured, reviewed evidence from platform owners and contracts.
2. Verify field/deletion semantics, rate limits and demand peaks against real vendors before accepting a plan.
3. Test held-out incidents and solving time at the intended operating scale.

These are separate acceptance steps, not unfinished features represented as complete.
