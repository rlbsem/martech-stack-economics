"""Annual MILP: shared subscriptions, tiered allowance/overage, peak capacity and hard eligibility.

Compiler arithmetic intentionally does not call the independent accountant's line calculator.
"""
import math

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from stack_economics.contracts import digest

from .contract import validate


def coefficients(w, o, month, condition):
    def up(n, d):
        return (n + d - 1) // d
    source = up(w['source_events_month'] * month['demand_percent'] * condition['demand_percent'], 10000)
    records = source * w['downstream_multiplier']
    windows = month['days'] * 1440 // max(1, o['lag_minutes'])
    intervals = max(1, 60 // max(1, o['lag_minutes']))
    peak_total = min(records, up(records * w['peak_hour_ppm'] * condition['peak_percent'], 100_000_000) * month['days'])
    peak_count = intervals * month['days']
    def rounded_population(population, count):
        lower, extra = population // count, population % count
        return (count - extra) * up(lower, o['batch_size']) + extra * up(lower + 1, o['batch_size'])
    requests = rounded_population(peak_total, peak_count) + rounded_population(records - peak_total, windows - peak_count)
    requests += up(requests * condition['retry_percent'], 100)
    peak = up(peak_total, month['days'])
    residual = peak % intervals
    base = peak // intervals
    peak = (intervals - residual) * up(base, o['batch_size']) + residual * up(base + 1, o['batch_size'])
    peak += up(peak * condition['retry_percent'], 100)
    cost = (up(records * o['event_cents_per_1000'], 1000)
            + up(requests * o['request_cents_per_1000'], 1000)
            + up(records * w['payload_bytes'] * o['egress_cents_per_gib'], 2**30)
            + up(records * w['payload_bytes'] * o['warehouse_cents_per_tib'], 2**40))
    return cost, requests, peak * o['work_units_per_request'], peak * o['crm_calls_per_request']


def solve(value, conditions, seconds=30):
    spec = validate(value)
    cs = [c for c in spec['conditions'] if c['id'] in conditions]
    if not cs or {c['id'] for c in cs} != set(conditions):
        raise ValueError('unknown_or_empty_conditions')
    options = [(w, o) for w in spec['workloads'] for o in w['options']]
    tiers = {t['id']: len(options) + i for i, t in enumerate(spec['tiers'])}
    platforms = {p['id']: len(options) + len(tiers) + i for i, p in enumerate(spec['platforms'])}
    offsets = len(options) + len(tiers) + len(platforms)
    overages = {(c['id'], m['id']): offsets + i for i, (c, m) in enumerate(
        (c, m) for c in cs for m in spec['months'])}
    z = offsets + len(overages)
    rows, lows, highs = [], [], []

    def add(coeff, low=-math.inf, high=math.inf):
        row = np.zeros(z + 1)
        for index, amount in coeff.items():
            row[index] = amount
        rows.append(row)
        lows.append(low)
        highs.append(high)

    for w in spec['workloads']:
        add({i: 1 for i, (work, _) in enumerate(options) if w['id'] == work['id']}, 1, 1)
    add({i: 1 for i in tiers.values()}, 1, 1)
    lower, upper = np.zeros(z + 1), np.ones(z + 1)
    for i, (w, o) in enumerate(options):
        if (o['lag_minutes'] > w['max_lag_minutes'] or o['region'] not in w['allowed_regions']
                or not set(w['required_capabilities']) <= set(o['capabilities'])):
            upper[i] = 0
        add({i: 1, platforms[o['platform']]: -1}, high=0)
    for p, j in platforms.items():
        add({**{i: -1 for i, (_, o) in enumerate(options) if o['platform'] == p}, j: 1}, high=0)
    fixed = {platforms[p['id']]: 12 * p['monthly_fixed_cents'] for p in spec['platforms']}
    fixed.update({tiers[t['id']]: 12 * (t['workers'] * t['worker_month_cents']
                                      + t['support_hours'] * spec['support_hour_cents']) for t in spec['tiers']})
    for c in cs:
        annual = dict(fixed)
        for m in spec['months']:
            values = [coefficients(w, o, m, c) for w, o in options]
            for i, v in enumerate(values):
                annual[i] = annual.get(i, 0) + v[0]
            k = overages[(c['id'], m['id'])]
            upper[k] = 1_000_000_000_000
            annual[k] = spec['overage_cents_per_request']
            add({**{i: v[1] for i, v in enumerate(values)}, k: -1,
                 **{tiers[t['id']]: -t['included_requests_month'] for t in spec['tiers']}}, high=0)
            add({**{i: v[2] * 100 for i, v in enumerate(values)},
                 **{tiers[t['id']]: -t['work_units_hour'] * spec['capacity_utilization_percent']
                    for t in spec['tiers']}}, high=0)
            add({**{i: v[3] * 100 for i, v in enumerate(values)},
                 **{tiers[t['id']]: -t['crm_calls_hour'] * c['quota_percent'] for t in spec['tiers']}}, high=0)
        add({**annual, z: -1}, high=0)
    upper[z] = spec['annual_budget_cents']
    objective = np.zeros(z + 1)
    objective[z] = 1
    record = {'schema': 1, 'input_sha256': digest(spec), 'conditions': conditions, 'status': 'unresolved',
              'solver_status': None, 'selection': None, 'annual_cents': None}
    try:
        result = milp(objective, integrality=np.ones(z + 1), bounds=Bounds(lower, upper),
                      constraints=LinearConstraint(rows, lows, highs),
                      options={'time_limit': seconds, 'mip_rel_gap': 0.0})
    except (ValueError, RuntimeError):
        return record
    record['solver_status'] = int(result.status)
    if result.status == 2:
        record['status'] = 'infeasible'
    elif result.status == 0:
        selection = {'tier': next(t for t, j in tiers.items() if result.x[j] > .5),
                     'routes': {w['id']: o['id'] for i, (w, o) in enumerate(options) if result.x[i] > .5}}
        from .accounting import assess
        check = assess(spec, selection, conditions)
        assert check['feasible'], 'Independent accountant rejected solver selection'
        assert abs(check['worst_annual_cents'] - result.fun) < .01, 'Objective/accounting mismatch'
        record.update(status='optimal', selection=selection, annual_cents=check['worst_annual_cents'],
                      dual_bound_cents=round(float(result.mip_dual_bound)), mip_gap=float(result.mip_gap))
    return record
