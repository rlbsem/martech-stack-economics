from copy import deepcopy
from pathlib import Path

from .accounting import assess, exhaustive
from .cli import write_json
from .contracts import Invalid, digest, implementation
from .planner import check_plan, solve


def run(spec, output):
    output = Path(output)
    normal = deepcopy(spec)
    normal["scenarios"] = normal["scenarios"][:1]
    nominal = solve(normal)
    robust = solve(spec)
    assert robust["status"] == nominal["status"] == "optimal"
    independently_checked = check_plan(spec, robust)
    exhaustive_result = exhaustive(spec)
    assert exhaustive_result["best"]["cost_cents"] == robust["assessment"]["worst_cost_cents"]
    rejected = assess(spec, nominal["selection"])
    reference_selection = {w["id"]: "premium" for w in spec["workloads"]}
    reference = assess(spec, reference_selection)
    cheap = assess(spec, {w["id"]: "cheap-lossy" for w in spec["workloads"]})
    assert reference["feasible"] and not rejected["feasible"] and not cheap["feasible"]
    assert reference["worst_cost_cents"] > robust["assessment"]["worst_cost_cents"]
    frontier = []
    for capacity in (100, 90, 60, 40, 30):
        changed = deepcopy(spec)
        for scenario in changed["scenarios"]:
            scenario["capacities"]["crm-api"]["per_slot"] = [capacity] * spec["slots"]
        plan = solve(changed)
        frontier.append({"crm_requests_per_slot": capacity, "input": changed, "plan": plan})
        if plan["status"] == "optimal":
            assert plan["assessment"]["feasible"]
        else:
            assert plan["status"] == "infeasible"
    assert frontier[-1]["plan"]["status"] == "infeasible"
    tight = deepcopy(spec)
    tight["budget_cents"] = robust["assessment"]["worst_cost_cents"] - 1
    budget_failure = solve(tight)
    assert budget_failure["status"] == "infeasible" and budget_failure["selection"] is None
    stale = None
    try:
        check_plan(tight, robust)
    except Invalid as exc:
        stale = str(exc)
    assert stale == "planning_assumptions_changed"
    record = {"scope": "Synthetic four-hour integration planning; no real vendor prices, effects, load test or realized savings",
              "input": spec, "input_hash": digest(spec), "implementation_hash": implementation(),
              "normal_only_plan": nominal, "normal_plan_assessed_under_surge": rejected,
              "premium_reference": {"selection": reference_selection, "assessment": reference},
              "robust_plan": robust, "stored_plan_check": independently_checked,
              "independent_exhaustive_oracle": exhaustive_result, "cheap_lossy_rejection": cheap,
              "capacity_tradeoffs": frontier, "below_optimum_budget": {"input": tight, "result": budget_failure},
              "stale_plan_refusal": stale}
    write_json(output / "planning-proof.json", record)
    write_json(output / "recommended-plan.json", robust)
    write_json(output / "reference-selection.json", reference_selection)
    reference_cost, optimized_cost = reference["worst_cost_cents"], robust["assessment"]["worst_cost_cents"]
    report = ["# Executed integration economics proof", "",
              "All demand, costs, capability declarations and service envelopes are synthetic. These are computed planning results, not observed vendor performance or business savings.", "",
              "| Question | Executed result |", "|---|---|",
              f"| Cheapest scenario-feasible modeled configuration | {optimized_cost} cents per four-hour horizon |",
              f"| Feasible all-premium reference | {reference_cost} cents per horizon |",
              f"| Difference against that reference | {reference_cost - optimized_cost} cents ({(reference_cost - optimized_cost) / reference_cost:.1%}); hypothetical input-model difference |",
              f"| Independent optimum check | Enumerated all {exhaustive_result['configurations_checked']} configurations; same optimum |",
              "| Normal-only cheaper configuration under surge | Rejected for shared capacity violations |",
              "| Cheapest lossy route | Rejected for freshness, missing capabilities and region |",
              f"| Budget of {tight['budget_cents']} cents | Infeasible; no recommendation |",
              "| Saved recommendation after assumptions change | Refused as stale |", "",
              "## Selected routes", "", "| Workflow | Route |", "|---|---|"]
    report.extend(f"| {key} | {value} |" for key, value in robust["selection"].items())
    report += ["", "## Capacity tradeoffs", "",
               "Each row is a new solve with the same demand and hourly CRM capacity changed in every scenario. These finite differences are not continuous shadow prices or purchase recommendations.", "",
               "| CRM requests per hour | Status | Worst modeled cost, cents |", "|---|---|---|"]
    for item in frontier:
        plan = item["plan"]
        cost = plan["assessment"]["worst_cost_cents"] if plan["assessment"] else "no feasible plan"
        report.append(f"| {item['crm_requests_per_slot']} | {plan['status']} | {cost} |")
    report += ["", "[Full assumptions, rejected plans, charges, quotas, headroom and conflicts](planning-proof.json)", "",
               "The optimizer chooses one fixed configuration for all supplied scenarios. It does not dynamically switch after observing a surge. The capacity model includes both per-hour and horizon quotas; it does not model within-hour queuing. Route latency bounds are declared inputs conditional on staying within capacity, not measured guarantees.", ""]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    return record
