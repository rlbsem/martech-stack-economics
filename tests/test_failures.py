import json
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from stack_economics.accounting import assess, exhaustive
from stack_economics.cli import main, write_json
from stack_economics.contracts import Invalid, load, validate
from stack_economics.model import Model, diagnose
from stack_economics.planner import check_plan, solve


@pytest.mark.parametrize("status,expected", [(1, "unresolved"), (3, "solver_error"), (4, "solver_error")])
def test_solver_without_optimality_never_emits_a_recommendation(tiny, monkeypatch, status, expected):
    monkeypatch.setattr(Model, "run", lambda *a, **k: SimpleNamespace(status=status, message="injected failure", x=[1]))
    result = solve(tiny)
    assert result["status"] == expected and result["selection"] is None and result["assessment"] is None


def test_solver_exception_and_diagnostic_exception_have_explicit_outcomes(tiny, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("solver unavailable")
    monkeypatch.setattr(Model, "run", fail)
    assert solve(tiny)["status"] == "solver_error"
    diagnosis = diagnose(Model(tiny))
    assert not diagnosis["complete"] and diagnosis["kind"] == "unreduced_infeasible_business_set"


@pytest.mark.parametrize("fault", ["fractional", "nan", "wrong-cost", "missing-selection", "over-quota", "missing-bound"])
def test_independent_checker_refuses_bad_optimal_solver_output(tiny, monkeypatch, fault):
    model = Model(tiny)
    raw = model.run()
    assert raw.status == 0
    raw.x = raw.x.copy()
    if fault == "fractional":
        raw.x[0] = 0.5
    elif fault == "nan":
        raw.x[0] = np.nan
    elif fault == "wrong-cost":
        raw.fun += 1
    elif fault == "missing-selection":
        raw.x[:2] = 0
    elif fault == "missing-bound":
        raw.mip_dual_bound = None
    else:
        tiny["scenarios"][0]["capacities"]["crm-api"]["per_slot"][0] = 0
    monkeypatch.setattr(Model, "run", lambda *args, **kwargs: raw)
    result = solve(tiny)
    assert result["status"] == "verification_failed" and result["selection"] is None


def test_infeasibility_explanation_is_honest_when_its_budget_runs_out(tiny):
    tiny["budget_cents"] = 0
    model = Model(tiny)
    assert model.run().status == 2
    diagnostic = diagnose(model, max_solves=0)
    assert not diagnostic["complete"] and diagnostic["solves"] == 0
    assert model.run(set(diagnostic["constraints"])).status == 2


@pytest.mark.parametrize("change", ["demand", "price", "capacity", "freshness", "capability"])
def test_changed_assumptions_invalidate_a_saved_plan(tiny, change):
    plan = solve(tiny)
    assert check_plan(tiny, plan)["optimality"] == "not_reproved_by_check"
    if change == "demand":
        tiny["scenarios"][0]["demands"][tiny["workloads"][0]["id"]][0] += 1
    elif change == "price":
        tiny["platforms"][1]["fixed_cost_cents"] += 1
    elif change == "capacity":
        tiny["scenarios"][0]["capacities"]["crm-api"]["total"] += 1
    elif change == "freshness":
        tiny["workloads"][0]["max_lag_minutes"] -= 1
    else:
        tiny["workloads"][0]["required_capabilities"].append("history")
    with pytest.raises(Invalid, match="assumptions_changed"):
        check_plan(tiny, plan)


def test_corrupted_accounting_and_changed_implementation_are_rejected(tiny, monkeypatch):
    plan = solve(tiny)
    corrupt = deepcopy(plan)
    corrupt["assessment"]["fixed_cost_cents"] += 1
    with pytest.raises(Invalid, match="accounting_mismatch"):
        check_plan(tiny, corrupt)
    monkeypatch.setattr("stack_economics.planner.implementation", lambda: "changed")
    with pytest.raises(Invalid, match="implementation_changed"):
        check_plan(tiny, plan)


@pytest.mark.parametrize("field,value", [("batch_size", 0), ("batch_size", True), ("cost_per_batch_cents", -1),
                                       ("lag_minutes", 1.5), ("platform", "absent"), ("platform", []),
                                       ("resources", {}), ("resources", {"unknown": 1})])
def test_invalid_route_contracts_are_refused(tiny, field, value):
    tiny["workloads"][0]["options"][0][field] = value
    with pytest.raises(Invalid):
        solve(tiny)


def test_missing_scenario_coverage_and_duplicate_ids_fail_closed(tiny):
    missing = deepcopy(tiny)
    missing["scenarios"][0]["demands"].pop(missing["workloads"][0]["id"])
    with pytest.raises(Invalid, match="complete_workload_demands"):
        validate(missing)
    tiny["workloads"].append(deepcopy(tiny["workloads"][0]))
    with pytest.raises(Invalid, match="duplicate_identifier"):
        validate(tiny)


def test_duplicate_json_keys_and_nonfinite_numbers_are_rejected(tiny, tmp_path):
    path = tmp_path / "spec.json"
    path.write_text('{"schema":1,"schema":2}', encoding="utf-8")
    with pytest.raises(Invalid, match="duplicate_json_key"):
        load(path)
    tiny["budget_cents"] = float("nan")
    with pytest.raises(Invalid):
        validate(tiny)


def test_invalid_selection_and_unbounded_oracle_work_are_refused(tiny):
    with pytest.raises(Invalid, match="one_selection"):
        assess(tiny, {})
    with pytest.raises(Invalid, match="exhaustive_budget"):
        exhaustive(tiny, limit=1)


def test_cli_roundtrip_failure_exit_and_atomic_output(tiny, tmp_path, monkeypatch):
    spec, output, checked = [tmp_path / name for name in ("spec.json", "plan.json", "check.json")]
    write_json(spec, tiny)
    assert main(["solve", str(spec), "--output", str(output)]) == 0
    assert main(["check", str(spec), "--plan", str(output), "--output", str(checked)]) == 0
    saved = output.read_bytes()
    def failed_replace(*args):
        raise OSError("injected disk replacement failure")
    with monkeypatch.context() as context:
        context.setattr("stack_economics.cli.os.replace", failed_replace)
        with pytest.raises(OSError, match="injected"):
            write_json(output, {"incomplete": True})
    assert output.read_bytes() == saved and not list(tmp_path.glob("*.tmp"))
    tiny["budget_cents"] = 0
    write_json(spec, tiny)
    assert main(["check", str(spec), "--plan", str(output), "--output", str(checked)]) == 4
    assert main(["solve", str(spec), "--output", str(output)]) == 2
    assert json.loads(output.read_text())["selection"] is None


@pytest.mark.parametrize("seconds", [0, -1, True, float("nan"), 61])
def test_invalid_solver_budget_refused(tiny, seconds):
    with pytest.raises(Invalid, match="solver_time"):
        solve(tiny, seconds=seconds)
