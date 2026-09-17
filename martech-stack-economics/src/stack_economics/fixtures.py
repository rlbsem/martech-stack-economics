"""Declared synthetic workloads and service envelopes; no vendor prices or measured SLAs."""
from copy import deepcopy


def campaign_launch():
    capabilities = ["upserts", "deletes", "custom-fields"]
    routes = [
        {"id": "rest", "platform": "direct", "region": "ca", "capabilities": capabilities,
         "lag_minutes": 5, "batch_size": 100, "cost_per_batch_cents": 6,
         "resources": {"crm-api": 1, "destination-api": 1}},
        {"id": "bulk", "platform": "batch-hub", "region": "ca", "capabilities": capabilities,
         "lag_minutes": 30, "batch_size": 1000, "cost_per_batch_cents": 2,
         "resources": {"crm-api": 1, "destination-api": 1, "bulk-jobs": 1}},
        {"id": "stream", "platform": "stream-hub", "region": "ca", "capabilities": capabilities,
         "lag_minutes": 2, "batch_size": 250, "cost_per_batch_cents": 2,
         "resources": {"crm-api": 1, "destination-api": 1}},
        {"id": "premium", "platform": "premium-hub", "region": "ca", "capabilities": capabilities,
         "lag_minutes": 2, "batch_size": 1000, "cost_per_batch_cents": 10,
         "resources": {"crm-api": 1, "destination-api": 1}},
        {"id": "cheap-lossy", "platform": "direct", "region": "us", "capabilities": ["upserts"],
         "lag_minutes": 90, "batch_size": 1000, "cost_per_batch_cents": 0,
         "resources": {"crm-api": 1}},
    ]
    definitions = [("lead-handoff", "revenue-operations", 10, 1),
                   ("campaign-suppression", "integrated-campaigns", 10, 2),
                   ("attribution-refresh", "marketing-analytics", 60, 3),
                   ("web-personalization", "web", 10, 2),
                   ("product-enrichment", "product-marketing", 60, 1)]
    workloads = [{"id": name, "owner": owner, "max_lag_minutes": lag,
                  "required_capabilities": capabilities, "allowed_regions": ["ca"], "options": deepcopy(routes)}
                 for name, owner, lag, _ in definitions]
    scenarios = []
    for name, profile in [("normal", [100, 200, 200, 100]), ("launch-surge", [100, 2000, 4000, 200])]:
        scenarios.append({"id": name, "demands": {w: [v * scale for v in profile] for w, _, _, scale in definitions},
                          "capacities": {"crm-api": {"per_slot": [100] * 4, "total": 250},
                                         "destination-api": {"per_slot": [180] * 4, "total": 450},
                                         "bulk-jobs": {"per_slot": [20] * 4, "total": 60}}})
    return {"schema": 1, "id": "campaign-launch", "currency": "USD", "slot_minutes": 60, "slots": 4,
            "budget_cents": 2000,
            "platforms": [{"id": name, "fixed_cost_cents": cost} for name, cost in
                          [("direct", 0), ("batch-hub", 120), ("stream-hub", 350), ("premium-hub", 700)]],
            "resources": [{"id": name, "unit": "requests"} for name in ["crm-api", "destination-api", "bulk-jobs"]],
            "workloads": workloads, "scenarios": scenarios}
