"""Compile finite route choices, shared fixed charges and scenario quota rows."""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


@dataclass
class Row:
    name: str
    coefficients: dict
    low: float
    high: float
    business: bool = False


class Model:
    def __init__(self, spec):
        self.spec = spec
        self.options = [(w, o) for w in spec["workloads"] for o in w["options"]]
        self.platforms = {p["id"]: len(self.options) + i for i, p in enumerate(spec["platforms"])}
        self.z = len(self.options) + len(self.platforms)
        self.rows = []
        self.costs = {}
        for workload in spec["workloads"]:
            indexes = {i: 1 for i, (w, _) in enumerate(self.options) if w["id"] == workload["id"]}
            self.add("choose/" + workload["id"], indexes, 1, 1)
        for i, (w, o) in enumerate(self.options):
            prefix = "eligible/" + w["id"] + "/" + o["id"]
            if o["lag_minutes"] > w["max_lag_minutes"]:
                self.add(prefix + "/freshness", {i: 1}, 0, 0, True)
            if not set(w["required_capabilities"]) <= set(o["capabilities"]):
                self.add(prefix + "/capabilities", {i: 1}, 0, 0, True)
            if o["region"] not in w["allowed_regions"]:
                self.add(prefix + "/region", {i: 1}, 0, 0, True)
            self.add("enable/" + w["id"] + "/" + o["id"], {i: 1, self.platforms[o["platform"]]: -1}, -np.inf, 0)
        for platform, j in self.platforms.items():
            use = {i: -1 for i, (_, o) in enumerate(self.options) if o["platform"] == platform}
            self.add("used/" + platform, {**use, j: 1}, -np.inf, 0)
        for scenario in spec["scenarios"]:
            batches = {i: [(d + o["batch_size"] - 1) // o["batch_size"] for d in scenario["demands"][w["id"]]]
                       for i, (w, o) in enumerate(self.options)}
            costs = {i: sum(batches[i]) * o["cost_per_batch_cents"] for i, (_, o) in enumerate(self.options)}
            costs.update({self.platforms[p["id"]]: p["fixed_cost_cents"] for p in spec["platforms"]})
            self.costs[scenario["id"]] = costs
            self.add("cost/" + scenario["id"], {**costs, self.z: -1}, -np.inf, 0)
            for resource, capacity in scenario["capacities"].items():
                for slot in range(spec["slots"]):
                    use = {i: batches[i][slot] * o["resources"].get(resource, 0)
                           for i, (_, o) in enumerate(self.options)}
                    self.add(f"quota/{scenario['id']}/{resource}/slot-{slot}", use, -np.inf, capacity["per_slot"][slot], True)
                total = {i: sum(batches[i]) * o["resources"].get(resource, 0) for i, (_, o) in enumerate(self.options)}
                self.add(f"quota/{scenario['id']}/{resource}/total", total, -np.inf, capacity["total"], True)
        self.add("budget", {self.z: 1}, -np.inf, spec["budget_cents"], True)

    def add(self, name, coefficients, low, high, business=False):
        self.rows.append(Row(name, coefficients, low, high, business))

    def run(self, active=None, seconds=10.0):
        rows = [r for r in self.rows if not r.business or active is None or r.name in active]
        matrix = np.zeros((len(rows), self.z + 1))
        for i, row in enumerate(rows):
            for j, coefficient in row.coefficients.items():
                matrix[i, j] = coefficient
        objective = np.zeros(self.z + 1)
        objective[self.z] = 1
        return milp(objective, integrality=np.ones(self.z + 1),
                    bounds=Bounds(np.zeros(self.z + 1), np.array([1] * self.z + [1_000_000_000_000])),
                    constraints=LinearConstraint(matrix, [r.low for r in rows], [r.high for r in rows]),
                    options={"time_limit": seconds, "mip_rel_gap": 0.0, "presolve": True})


def diagnose(model, max_solves=100, seconds=2.0):
    """Deletion-minimal business conflict relative to fixed structural constraints; not minimum cardinality."""
    active = {r.name for r in model.rows if r.business}
    calls = 0
    complete = True
    for name in sorted(active):
        if calls >= max_solves:
            complete = False
            break
        trial = active - {name}
        try:
            outcome = model.run(trial, seconds=seconds)
        except Exception:
            complete = False
            break
        calls += 1
        if outcome.status == 2:
            active = trial
        elif outcome.status != 0:
            complete = False
    return {"kind": "irreducible_business_conflict" if complete else "unreduced_infeasible_business_set",
            "constraints": sorted(active), "solves": calls, "complete": complete,
            "qualification": "Relative to mandatory route-choice and platform/cost definitions; not a minimum-size conflict."}
