from copy import deepcopy

import pytest

from stack_economics.fixtures import campaign_launch


@pytest.fixture
def tiny():
    spec = campaign_launch()
    spec["id"] = "tiny"
    spec["slots"] = 2
    spec["platforms"] = [{"id": "direct", "fixed_cost_cents": 0}, {"id": "batch-hub", "fixed_cost_cents": 10}]
    spec["resources"] = [{"id": "crm-api", "unit": "requests"}]
    spec["workloads"] = deepcopy(spec["workloads"][:2])
    for workload in spec["workloads"]:
        workload["max_lag_minutes"] = 60
        workload["options"] = deepcopy(workload["options"][:2])
        for option in workload["options"]:
            option["resources"] = {"crm-api": 1}
    spec["scenarios"] = [{"id": "normal", "demands": {w["id"]: [101, 0] for w in spec["workloads"]},
                          "capacities": {"crm-api": {"per_slot": [4, 4], "total": 8}}}]
    return spec
