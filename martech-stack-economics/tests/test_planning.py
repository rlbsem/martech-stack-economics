from copy import deepcopy
import random

import pytest

from stack_economics.accounting import assess, exhaustive
from stack_economics.fixtures import campaign_launch
from stack_economics.model import Model
from stack_economics.planner import solve


def test_campaign_plan_matches_independent_global_optimum():
    spec = campaign_launch()
    actual = solve(spec)
    oracle = exhaustive(spec)
    assert actual["status"] == oracle["status"] == "optimal"
    assert actual["assessment"]["worst_cost_cents"] == oracle["best"]["cost_cents"] == 782
    assert oracle["configurations_checked"] == 3125
    assert actual["selection"] == {"lead-handoff": "stream", "campaign-suppression": "stream",
                                   "attribution-refresh": "bulk", "web-personalization": "stream", "product-enrichment": "bulk"}


def test_normal_cheap_plan_fails_surge_and_reference_is_more_expensive():
    spec = campaign_launch()
    normal = deepcopy(spec)
    normal["scenarios"] = normal["scenarios"][:1]
    nominal = solve(normal)
    rejected = assess(spec, nominal["selection"])
    assert nominal["status"] == "optimal" and not rejected["feasible"]
    assert any(v["kind"] == "capacity" and v["scenario"] == "launch-surge" for v in rejected["violations"])
    reference = assess(spec, {w["id"]: "premium" for w in spec["workloads"]})
    optimized = solve(spec)
    assert reference["feasible"] and reference["worst_cost_cents"] > optimized["assessment"]["worst_cost_cents"]


def test_shared_fee_is_charged_once_and_partial_batches_round_up(tiny):
    result = solve(tiny)
    assert result["status"] == "optimal"
    assert set(result["selection"].values()) == {"bulk"}
    assert result["assessment"]["fixed_cost_cents"] == 10
    assert result["assessment"]["worst_cost_cents"] == 14
    direct = assess(tiny, {w["id"]: "rest" for w in tiny["workloads"]})
    assert direct["worst_cost_cents"] == 24
    assert all(c["batches_by_slot"] == [2, 0] for c in direct["scenarios"][0]["charges"])


def test_horizon_quota_cannot_replace_burst_quota(tiny):
    for workload in tiny["workloads"]:
        workload["options"] = workload["options"][:1]
    tiny["scenarios"][0]["capacities"]["crm-api"] = {"per_slot": [3, 100], "total": 100}
    rejected = assess(tiny, {w["id"]: "rest" for w in tiny["workloads"]})
    assert not rejected["feasible"] and len(rejected["violations"]) == 1
    assert rejected["violations"][0]["slot"] == 0
    plan = solve(tiny)
    assert plan["status"] == "infeasible" and plan["selection"] is None
    assert plan["conflict"]["constraints"] == ["quota/normal/crm-api/slot-0"]


def test_horizon_quota_enforced_even_if_every_slot_fits(tiny):
    tiny["scenarios"][0]["capacities"]["crm-api"]["total"] = 1
    plan = solve(tiny)
    assert plan["status"] == "infeasible"
    assert plan["conflict"]["constraints"] == ["quota/normal/crm-api/total"]


def test_exact_budget_boundary_and_irreducible_conflict(tiny):
    tiny["budget_cents"] = 14
    assert solve(tiny)["status"] == "optimal"
    tiny["budget_cents"] = 13
    plan = solve(tiny)
    assert plan["status"] == "infeasible" and plan["conflict"]["complete"]
    conflict = set(plan["conflict"]["constraints"])
    model = Model(tiny)
    assert model.run(conflict).status == 2
    for name in conflict:
        assert model.run(conflict - {name}).status == 0
    assert exhaustive(tiny)["status"] == "infeasible"


@pytest.mark.parametrize("field,value,kind", [("lag_minutes", 61, "freshness"),
                                            ("capabilities", ["upserts"], "missing_capabilities"),
                                            ("region", "us", "region")])
def test_low_price_cannot_buy_its_way_out_of_business_constraints(tiny, field, value, kind):
    for workload in tiny["workloads"]:
        workload["options"][1][field] = value
        workload["options"][1]["cost_per_batch_cents"] = 0
    rejected = assess(tiny, {w["id"]: "bulk" for w in tiny["workloads"]})
    assert any(v["kind"] == kind for v in rejected["violations"])
    actual = solve(tiny)
    assert set(actual["selection"].values()) == {"rest"}
    assert actual["assessment"]["worst_cost_cents"] == exhaustive(tiny)["best"]["cost_cents"]


def test_zero_demand_does_not_create_requests_but_keeps_enabled_fixed_cost(tiny):
    for values in tiny["scenarios"][0]["demands"].values():
        values[:] = [0, 0]
    assessment = assess(tiny, {w["id"]: "bulk" for w in tiny["workloads"]})
    assert assessment["worst_cost_cents"] == 10
    assert all(row["used"] == 0 for row in assessment["scenarios"][0]["capacity"])
    assert solve(tiny)["assessment"]["worst_cost_cents"] == 0


def test_scenarios_cannot_choose_different_configurations(tiny):
    # Each scenario alone fits direct, but robust cost must cover the worst supplied demand.
    surge = deepcopy(tiny["scenarios"][0])
    surge["id"] = "surge"
    surge["demands"] = {w["id"]: [201, 201] for w in tiny["workloads"]}
    tiny["scenarios"].append(surge)
    result = solve(tiny)
    assert result["status"] == "optimal" and result["assessment"]["worst_cost_cents"] == 18
    assert len(result["selection"]) == 2
    assert all(row["cost_cents"] <= result["assessment"]["worst_cost_cents"] for row in result["assessment"]["scenarios"])


def test_crossing_scenarios_require_nonanticipating_shared_platform_cost(tiny):
    first, second = [w["id"] for w in tiny["workloads"]]
    tiny["scenarios"][0]["demands"] = {first: [100, 0], second: [0, 0]}
    isolated = solve(tiny)
    assert isolated["assessment"]["worst_cost_cents"] == 6
    other = deepcopy(tiny["scenarios"][0])
    other["id"] = "other-peak"
    other["demands"] = {first: [0, 0], second: [1001, 0]}
    tiny["scenarios"].append(other)
    robust = solve(tiny)
    assert robust["assessment"]["worst_cost_cents"] == exhaustive(tiny)["best"]["cost_cents"] == 14
    assert set(robust["selection"].values()) == {"bulk"}
    # Mixing the individually cheap routes costs 16: the shared fee remains in the first scenario too.
    mixed = assess(tiny, {first: "rest", second: "bulk"})
    assert mixed["worst_cost_cents"] == 16


@pytest.mark.parametrize("seed", [3, 19, 73, 211])
def test_randomized_models_match_exhaustive_feasibility_and_optimum(tiny, seed):
    rng = random.Random(seed)
    for _ in range(16):
        spec = deepcopy(tiny)
        for platform in spec["platforms"]:
            platform["fixed_cost_cents"] = rng.randrange(0, 30)
        for workload in spec["workloads"]:
            workload["max_lag_minutes"] = rng.choice([5, 30, 60])
            for option in workload["options"]:
                option["batch_size"] = rng.choice([1, 10, 100, 1000])
                option["cost_per_batch_cents"] = rng.randrange(0, 10)
                option["resources"]["crm-api"] = rng.randrange(1, 4)
        spec["budget_cents"] = rng.randrange(0, 300)
        for scenario in spec["scenarios"]:
            for workload in spec["workloads"]:
                scenario["demands"][workload["id"]] = [rng.randrange(0, 201), rng.randrange(0, 201)]
            scenario["capacities"]["crm-api"] = {"per_slot": [rng.randrange(1, 35), rng.randrange(1, 35)],
                                                   "total": rng.randrange(1, 50)}
        actual, expected = solve(spec, explain_infeasible=False), exhaustive(spec)
        assert actual["status"] == expected["status"]
        if actual["status"] == "optimal":
            assert actual["assessment"]["worst_cost_cents"] == expected["best"]["cost_cents"]


def test_reordering_inputs_does_not_change_optimum(tiny):
    cost = solve(tiny)["assessment"]["worst_cost_cents"]
    tiny["workloads"].reverse()
    tiny["platforms"].reverse()
    for workload in tiny["workloads"]:
        workload["options"].reverse()
    assert solve(tiny)["assessment"]["worst_cost_cents"] == cost
