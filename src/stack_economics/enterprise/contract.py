"""Closed units, bounded integer arithmetic, and detached versioned input snapshots."""
import calendar
import json

from stack_economics.contracts import Invalid, canonical, identity, integer, shape


def validate(value):
    shape(value, 'schema id currency year synthetic customer_population price_basis months conditions platforms '
                 'tiers support_hour_cents overage_cents_per_request capacity_utilization_percent '
                 'annual_budget_cents workloads reference')
    if value['schema'] != 'enterprise-economics/v1' or value['currency'] != 'USD' or value['synthetic'] is not True:
        raise Invalid('versioned_synthetic_USD_required')
    identity(value['id'])
    integer(value['year'], 2020, 2100)
    integer(value['customer_population'], 1, 100_000_000)
    if not isinstance(value['price_basis'], str) or not value['price_basis']:
        raise Invalid('price_basis_required')
    for key in ('support_hour_cents', 'overage_cents_per_request', 'annual_budget_cents'):
        integer(value[key], 0, 1_000_000_000)
    integer(value['capacity_utilization_percent'], 1, 100)

    def objects(key, low, high):
        items = value[key]
        if not isinstance(items, list) or not low <= len(items) <= high:
            raise Invalid('invalid_list:' + key)
        ids = [item['id'] for item in items]
        if len(ids) != len(set(ids)):
            raise Invalid('duplicate:' + key)
        return items

    for month, m in enumerate(objects('months', 12, 12), 1):
        shape(m, 'id days demand_percent')
        integer(m['days'], 28, 31)
        if m['id'] != f"{value['year']}-{month:02}" or m['days'] != calendar.monthrange(value['year'], month)[1]:
            raise Invalid('complete_calendar_year_required')
        integer(m['demand_percent'], 1, 500)
    for c in objects('conditions', 1, 4):
        shape(c, 'id demand_percent retry_percent peak_percent quota_percent')
        identity(c['id'])
        for key in ('demand_percent', 'peak_percent', 'quota_percent'):
            integer(c[key], 1, 500)
        integer(c['retry_percent'], 0, 100)
    platforms = set()
    for p in objects('platforms', 1, 5):
        shape(p, 'id monthly_fixed_cents')
        identity(p['id'])
        integer(p['monthly_fixed_cents'], 0, 10_000_000)
        platforms.add(p['id'])
    for t in objects('tiers', 1, 5):
        shape(t, 'id workers worker_month_cents support_hours work_units_hour crm_calls_hour included_requests_month')
        identity(t['id'])
        for key in set(t) - {'id'}:
            integer(t[key], 1, 10_000_000)
    for w in objects('workloads', 1, 10):
        shape(w, 'id source_events_month downstream_multiplier payload_bytes peak_hour_ppm max_lag_minutes '
                 'required_capabilities allowed_regions purpose options')
        identity(w['id'])
        integer(w['source_events_month'], 0, 500_000_000)
        integer(w['downstream_multiplier'], 1, 10)
        integer(w['payload_bytes'], 1, 100000)
        integer(w['peak_hour_ppm'], 1, 1_000_000)
        integer(w['max_lag_minutes'], 0, 1440)
        if not w['required_capabilities'] or not w['allowed_regions'] or not isinstance(w['purpose'], str):
            raise Invalid('workload_requirements_required')
        ids = set()
        if not isinstance(w['options'], list) or not 1 <= len(w['options']) <= 4:
            raise Invalid('bounded_routes_required')
        for o in w['options']:
            shape(o, 'id platform batch_size lag_minutes region capabilities event_cents_per_1000 '
                     'request_cents_per_1000 warehouse_cents_per_tib egress_cents_per_gib '
                     'crm_calls_per_request work_units_per_request')
            identity(o['id'])
            if o['id'] in ids or o['platform'] not in platforms:
                raise Invalid('duplicate_route_or_unknown_platform')
            ids.add(o['id'])
            for key in ('batch_size', 'work_units_per_request'):
                integer(o[key], 1, 100000)
            for key in ('lag_minutes', 'event_cents_per_1000', 'request_cents_per_1000',
                        'warehouse_cents_per_tib', 'egress_cents_per_gib', 'crm_calls_per_request'):
                integer(o[key], 0, 10000)
            if o['lag_minutes'] < 1 or o['lag_minutes'] > 60 or 60 % o['lag_minutes']:
                raise Invalid('emission_interval_must_divide_hour')
            identity(o['region'])
            for cap in o['capabilities']:
                identity(cap)
        for c in value['conditions']:
            for m in value['months']:
                share = w['peak_hour_ppm'] * c['peak_percent'] * m['days']
                if share > 100_000_000 or share * 24 < 100_000_000:
                    raise Invalid('inconsistent_daily_peak_profile')
    # Conservative coefficient guard: preserve exact integer arithmetic through the float MILP interface.
    maximum = 0
    for w in value['workloads']:
        records = ((w['source_events_month'] * max(m['demand_percent'] for m in value['months'])
                    * max(c['demand_percent'] for c in value['conditions']) + 9999) // 10000
                   * w['downstream_multiplier'])
        maximum += records * 2 * max(o['work_units_per_request'] for o in w['options']) * 100
    if maximum >= 2**50:
        raise Invalid('arithmetic_envelope_exceeded')
    shape(value['reference'], 'tier routes')
    if value['reference']['tier'] not in {t['id'] for t in value['tiers']}:
        raise Invalid('unknown_reference_tier')
    if set(value['reference']['routes']) != {w['id'] for w in value['workloads']}:
        raise Invalid('complete_reference_required')
    for w in value['workloads']:
        if value['reference']['routes'][w['id']] not in {o['id'] for o in w['options']}:
            raise Invalid('unknown_reference_route')
    return json.loads(canonical(value))
