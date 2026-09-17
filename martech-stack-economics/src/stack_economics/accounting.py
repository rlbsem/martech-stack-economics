"""Independent integer accountant: never imports the model compiler or solver."""
import itertools
import math

from .contracts import Invalid, validate


def assess(spec, selection):
    spec = validate(spec)
    if not isinstance(selection, dict) or set(selection) != {w["id"] for w in spec["workloads"]}:
        raise Invalid("one_selection_per_workload_required")
    violations, chosen = [], {}
    for workload in spec["workloads"]:
        matches = [o for o in workload["options"] if o["id"] == selection[workload["id"]]]
        if len(matches) != 1:
            raise Invalid("unknown_option")
        option = matches[0]
        chosen[workload["id"]] = option
        missing = sorted(set(workload["required_capabilities"]) - set(option["capabilities"]))
        if missing:
            violations.append({"kind": "missing_capabilities", "workload": workload["id"], "missing": missing})
        if option["region"] not in workload["allowed_regions"]:
            violations.append({"kind": "region", "workload": workload["id"], "actual": option["region"]})
        if option["lag_minutes"] > workload["max_lag_minutes"]:
            violations.append({"kind": "freshness", "workload": workload["id"],
                               "actual": option["lag_minutes"], "limit": workload["max_lag_minutes"]})
    enabled = {o["platform"] for o in chosen.values()}
    fixed = sum(p["fixed_cost_cents"] for p in spec["platforms"] if p["id"] in enabled)
    scenarios = []
    for scenario in spec["scenarios"]:
        usage = {r["id"]: [0] * spec["slots"] for r in spec["resources"]}
        charges = []
        for person, option in chosen.items():
            batches = []
            for records in scenario["demands"][person]:
                whole, remainder = divmod(records, option["batch_size"])
                batches.append(whole + bool(remainder))
            charge = sum(batches) * option["cost_per_batch_cents"]
            charges.append({"workload": person, "option": option["id"], "batches_by_slot": batches,
                            "records_by_slot": scenario["demands"][person], "variable_cost_cents": charge})
            for resource, per_batch in option["resources"].items():
                for slot, count in enumerate(batches):
                    usage[resource][slot] += count * per_batch
        limits = []
        for resource, slots in usage.items():
            cap = scenario["capacities"][resource]
            for slot, count in enumerate(slots):
                limits.append({"resource": resource, "slot": slot, "used": count, "limit": cap["per_slot"][slot],
                               "headroom": cap["per_slot"][slot] - count})
            limits.append({"resource": resource, "slot": "total", "used": sum(slots), "limit": cap["total"],
                           "headroom": cap["total"] - sum(slots)})
        violations.extend({"kind": "capacity", "scenario": scenario["id"], **row} for row in limits if row["headroom"] < 0)
        cost = fixed + sum(c["variable_cost_cents"] for c in charges)
        if cost > spec["budget_cents"]:
            violations.append({"kind": "budget", "scenario": scenario["id"], "actual": cost, "limit": spec["budget_cents"]})
        scenarios.append({"id": scenario["id"], "cost_cents": cost, "charges": charges, "capacity": limits})
    return {"feasible": not violations, "violations": violations, "enabled_platforms": sorted(enabled),
            "fixed_cost_cents": fixed, "worst_cost_cents": max(s["cost_cents"] for s in scenarios), "scenarios": scenarios}


def exhaustive(spec, limit=100_000):
    """Small-case optimum oracle, including infeasibility. Not the production algorithm."""
    spec = validate(spec)
    count = math.prod(len(w["options"]) for w in spec["workloads"])
    if count > limit:
        raise Invalid("exhaustive_budget_exceeded")
    best, checked = None, 0
    for choices in itertools.product(*(w["options"] for w in spec["workloads"])):
        selection = {w["id"]: o["id"] for w, o in zip(spec["workloads"], choices)}
        result = assess(spec, selection)
        checked += 1
        if result["feasible"] and (best is None or result["worst_cost_cents"] < best["cost_cents"]):
            best = {"selection": selection, "cost_cents": result["worst_cost_cents"]}
    return {"status": "optimal" if best else "infeasible", "best": best, "configurations_checked": checked}
