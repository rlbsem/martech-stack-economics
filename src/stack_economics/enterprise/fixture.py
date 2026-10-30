"""Versioned, explicitly synthetic enterprise operating assumptions (not vendor quotes)."""
import calendar


def scenario():
    names = [
        ('web-events', 65_000_000, 1, 15, ['events'], 0, 'Web collection → governed warehouse'),
        ('product-events', 18_000_000, 1, 15, ['events'], 0, 'Product telemetry → CDP / analytics'),
        ('profile-changes', 6_000_000, 2, 15, ['profiles', 'delete'], 1, 'Identity / consent → CRM and CDP'),
        ('identity-links', 4_000_000, 1, 5, ['identity'], 1, 'Identity service → customer profile'),
        ('consent-changes', 1_000_000, 3, 1, ['delete', 'consent'], 2, 'Consent → marketing suppression destinations'),
        ('crm-handoffs', 2_000_000, 1, 5, ['owner'], 1, 'CRM → lifecycle / seller handoff'),
        ('campaign-activation', 3_000_000, 2, 15, ['activation'], 0, 'CDP → journey and campaign destinations'),
        ('attribution', 1_000_000, 1, 120, ['analytics'], 0, 'Warehouse → attribution / reporting'),
    ]
    workloads = []
    for name, events, fanout, sla, capabilities, crm, purpose in names:
        options = []
        for kind, platform, batch, lag, event_price, request_price, warehouse, egress in [
            ('stream', 'event-fabric', 250, 1, 3, 30, 0, 80),
            ('microbatch', 'integration-hub', 1000, 5, 1, 15, 0, 40),
            ('bulk', 'warehouse', 5000, 60, 1, 5, 700, 0),
        ]:
            options.append({'id': kind, 'platform': platform, 'batch_size': batch, 'lag_minutes': lag,
                            'region': 'eu', 'capabilities': capabilities if kind != 'bulk' else ['events', 'analytics'],
                            'event_cents_per_1000': event_price, 'request_cents_per_1000': request_price,
                            'warehouse_cents_per_tib': warehouse, 'egress_cents_per_gib': egress,
                            'crm_calls_per_request': crm, 'work_units_per_request': 3 if kind == 'stream' else 1})
        workloads.append({'id': name, 'source_events_month': events, 'downstream_multiplier': fanout,
                          'payload_bytes': 1800 if 'events' in name else 3000,
                          'peak_hour_ppm': 7000 if name == 'campaign-activation' else 4000,
                          'max_lag_minutes': sla, 'required_capabilities': capabilities,
                          'allowed_regions': ['eu'], 'purpose': purpose, 'options': options})
    return {'schema': 'enterprise-economics/v1', 'id': 'multibrand-2026', 'currency': 'USD', 'year': 2026,
            'synthetic': True, 'customer_population': 12_000_000,
            'price_basis': 'All rates are synthetic allocated planning assumptions, not vendor prices or quotes.',
            'months': [{'id': f'2026-{m:02}', 'days': calendar.monthrange(2026, m)[1], 'demand_percent': weight}
                       for m, weight in enumerate([80, 82, 90, 95, 98, 100, 96, 100, 105, 115, 130, 109], 1)],
            'conditions': [
                {'id': 'operating', 'demand_percent': 100, 'retry_percent': 2,
                 'peak_percent': 100, 'quota_percent': 100},
                {'id': 'campaign-disruption', 'demand_percent': 125, 'retry_percent': 10,
                 'peak_percent': 180, 'quota_percent': 70}],
            'platforms': [{'id': 'event-fabric', 'monthly_fixed_cents': 350000},
                          {'id': 'integration-hub', 'monthly_fixed_cents': 600000},
                          {'id': 'warehouse', 'monthly_fixed_cents': 180000}],
            'tiers': [
                {'id': 'standard', 'workers': 4, 'worker_month_cents': 110000, 'support_hours': 8,
                 'work_units_hour': 50000, 'crm_calls_hour': 16000, 'included_requests_month': 400000},
                {'id': 'expanded', 'workers': 8, 'worker_month_cents': 110000, 'support_hours': 14,
                 'work_units_hour': 110000, 'crm_calls_hour': 36000, 'included_requests_month': 900000},
                {'id': 'resilient', 'workers': 16, 'worker_month_cents': 110000, 'support_hours': 22,
                 'work_units_hour': 240000, 'crm_calls_hour': 80000, 'included_requests_month': 1800000}],
            'support_hour_cents': 15000, 'overage_cents_per_request': 1,
            'capacity_utilization_percent': 80, 'annual_budget_cents': 80_000_000,
            'workloads': workloads,
            'reference': {'tier': 'expanded', 'routes': {w['id']: 'stream' if w['max_lag_minutes'] <= 1
                          else 'bulk' if w['id'] == 'attribution' else 'microbatch' for w in workloads}}}
