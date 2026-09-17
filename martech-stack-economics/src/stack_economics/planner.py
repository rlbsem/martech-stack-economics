import math

import numpy as np
import scipy

from .accounting import assess
from .contracts import Invalid, digest, implementation, validate
from .model import Model, diagnose


def solve(spec, *, seconds=10.0, explain_infeasible=True):
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 60:
        raise Invalid("solver_time_must_be_between_zero_and_60_seconds")
    spec = validate(spec)
    model = Model(spec)
    result = {"contract": 1, "input_hash": digest(spec), "implementation_hash": implementation(),
              "solver": {"backend": "SciPy milp / HiGHS", "scipy": scipy.__version__, "numpy": np.__version__,
                         "time_limit_seconds": seconds}, "selection": None, "assessment": None}
    try:
        raw = model.run(seconds=seconds)
    except Exception as exc:
        return {**result, "status": "solver_error", "reason": type(exc).__name__}
    result["solver"].update({"status": int(raw.status), "message": str(raw.message)})
    if raw.status == 2:
        result["status"] = "infeasible"
        if explain_infeasible:
            result["conflict"] = diagnose(model)
        return result
    if raw.status != 0:
        return {**result, "status": "unresolved" if raw.status == 1 else "solver_error",
                "reason": "No recommendation: solver did not establish an optimum."}
    # Never accept rounded fractional, malformed or non-finite decisions as a valid plan.
    vector = getattr(raw, "x", None)
    if (vector is None or len(vector) != model.z + 1 or not np.all(np.isfinite(vector))
            or np.any(np.abs(vector - np.rint(vector)) > 1e-6)
            or np.any(vector[:model.z] < -1e-6) or np.any(vector[:model.z] > 1 + 1e-6)):
        return {**result, "status": "verification_failed", "reason": "invalid_solver_decisions"}
    selection = {}
    for i, (workload, option) in enumerate(model.options):
        if round(vector[i]) == 1:
            if workload["id"] in selection:
                return {**result, "status": "verification_failed", "reason": "multiple_routes_selected"}
            selection[workload["id"]] = option["id"]
    try:
        assessment = assess(spec, selection)
    except Invalid as exc:
        return {**result, "status": "verification_failed", "reason": str(exc)}
    fixed = {p for p, index in model.platforms.items() if round(vector[index]) == 1}
    cost = assessment["worst_cost_cents"]
    lower = getattr(raw, "mip_dual_bound", None)
    gap = getattr(raw, "mip_gap", None)
    objective = getattr(raw, "fun", None)
    certified = all(v is not None and math.isfinite(v) for v in (lower, gap, objective))
    if (not assessment["feasible"] or fixed != set(assessment["enabled_platforms"])
            or abs(vector[model.z] - cost) > 1e-6 or not certified
            or abs(objective - cost) > 1e-6 or abs(lower - cost) > 1e-6 or gap > 1e-8):
        return {**result, "status": "verification_failed", "reason": "independent_accounting_or_optimum_mismatch",
                "rejected_assessment": assessment}
    result["solver"].update({"objective_cents": cost, "lower_bound_cents": float(lower), "relative_gap": float(gap)})
    return {**result, "status": "optimal", "selection": selection, "assessment": assessment}


def check_plan(spec, plan):
    spec = validate(spec)
    if (not isinstance(plan, dict) or plan.get("status") != "optimal"
            or type(plan.get("contract")) is not int or plan.get("contract") != 1):
        raise Invalid("optimal_plan_required")
    if plan.get("input_hash") != digest(spec):
        raise Invalid("planning_assumptions_changed")
    if plan.get("implementation_hash") != implementation():
        raise Invalid("planning_implementation_changed")
    checked = assess(spec, plan.get("selection"))
    if not checked["feasible"] or checked != plan.get("assessment"):
        raise Invalid("plan_accounting_mismatch")
    # This checks feasibility/accounting of a stored artifact, not an independent optimality proof.
    return {"feasible": True, "accounting_matches": True, "optimality": "not_reproved_by_check", "assessment": checked}
