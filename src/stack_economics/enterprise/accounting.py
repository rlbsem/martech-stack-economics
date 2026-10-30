"""Integer annual accountant and finite independent oracle; no solver/compiler imports."""
import itertools

from stack_economics.contracts import Invalid

from .contract import validate


def ceiling(numerator, denominator):
    quotient, remainder = divmod(numerator, denominator)
    return quotient + int(remainder != 0)


def line(workload, route, month, condition):
    source = ceiling(workload['source_events_month'] * month['demand_percent'] * condition['demand_percent'], 10000)
    records = source * workload['downstream_multiplier']
    windows = month['days'] * 1440 // max(1, route['lag_minutes'])
    peak_windows_hour = 60 // route['lag_minutes']
    declared_peak = ceiling(records * workload['peak_hour_ppm'] * condition['peak_percent'], 100_000_000)
    peak_records_month = min(records, declared_peak * month['days'])
    peak_windows_month = peak_windows_hour * month['days']
    batches = 0
    for population, count in [(peak_records_month, peak_windows_month),
                              (records - peak_records_month, windows - peak_windows_month)]:
        whole, remainder = divmod(population, count)
        batches += (count - remainder) * ceiling(whole, route['batch_size'])
        batches += remainder * ceiling(whole + 1, route['batch_size'])
    retries = ceiling(batches * condition['retry_percent'], 100)
    attempts = batches + retries
    peak_records = ceiling(peak_records_month, month['days'])
    peak_windows = peak_windows_hour
    peak_low, peak_extra = divmod(peak_records, peak_windows)
    peak_batches = ((peak_windows - peak_extra) * ceiling(peak_low, route['batch_size'])
                    + peak_extra * ceiling(peak_low + 1, route['batch_size']))
    peak_attempts = peak_batches + ceiling(peak_batches * condition['retry_percent'], 100)
    payload = records * workload['payload_bytes']
    parts = {'processing': ceiling(records * route['event_cents_per_1000'], 1000),
             'requests': ceiling(attempts * route['request_cents_per_1000'], 1000),
             'egress': ceiling(payload * route['egress_cents_per_gib'], 2**30),
             'warehouse': ceiling(payload * route['warehouse_cents_per_tib'], 2**40)}
    return {'workload': workload['id'], 'route': route['id'], 'platform': route['platform'],
            'source_events': source, 'downstream_records': records, 'payload_bytes': payload,
            'records_in_daily_peak_hours': peak_records_month, 'peak_records_hour': peak_records,
            'emission_windows': windows, 'batches': batches, 'retry_requests': retries, 'attempts': attempts,
            'peak_attempts_hour': peak_attempts, 'crm_peak_calls_hour': peak_attempts * route['crm_calls_per_request'],
            'work_peak_units_hour': peak_attempts * route['work_units_per_request'],
            'components_cents': parts, 'variable_cents': sum(parts.values())}


def eligible(workload, route):
    return (route['lag_minutes'] <= workload['max_lag_minutes']
            and route['region'] in workload['allowed_regions']
            and set(workload['required_capabilities']) <= set(route['capabilities']))


def assess(spec, selection, conditions=None):
    spec = validate(spec)
    if set(selection) != {'tier', 'routes'} or set(selection['routes']) != {w['id'] for w in spec['workloads']}:
        raise Invalid('one_enterprise_route_per_workload_required')
    tier = next((t for t in spec['tiers'] if t['id'] == selection['tier']), None)
    if tier is None:
        raise Invalid('unknown_tier')
    chosen, violations = {}, []
    for w in spec['workloads']:
        route = next((o for o in w['options'] if o['id'] == selection['routes'][w['id']]), None)
        if route is None:
            raise Invalid('unknown_route')
        chosen[w['id']] = route
        if not eligible(w, route):
            violations.append({'kind': 'route_requirements', 'workload': w['id']})
    enabled = {o['platform'] for o in chosen.values()}
    fixed_parts = {'subscriptions': sum(p['monthly_fixed_cents'] for p in spec['platforms'] if p['id'] in enabled),
                   'workers': tier['workers'] * tier['worker_month_cents'],
                   'operations': tier['support_hours'] * spec['support_hour_cents']}
    reports = []
    selected_conditions = [c for c in spec['conditions'] if conditions is None or c['id'] in conditions]
    if not selected_conditions or conditions is not None and set(conditions) != {c['id'] for c in selected_conditions}:
        raise Invalid('unknown_or_empty_conditions')
    for c in selected_conditions:
        months = []
        for m in spec['months']:
            lines = [line(w, chosen[w['id']], m, c) for w in spec['workloads']]
            work = sum(row['work_peak_units_hour'] for row in lines)
            crm = sum(row['crm_peak_calls_hour'] for row in lines)
            work_limit = tier['work_units_hour'] * spec['capacity_utilization_percent'] // 100
            crm_limit = tier['crm_calls_hour'] * c['quota_percent'] // 100
            overage = max(0, sum(row['attempts'] for row in lines) - tier['included_requests_month'])
            parts = dict(fixed_parts)
            for key in ('processing', 'requests', 'egress', 'warehouse'):
                parts[key] = sum(row['components_cents'][key] for row in lines)
            parts['shared_overage'] = overage * spec['overage_cents_per_request']
            total = sum(parts.values())
            # Fixed shared costs allocated by delivered-record volume; residual cents go to first workload.
            shared = sum(fixed_parts.values()) + parts['shared_overage']
            denominator = sum(row['downstream_records'] for row in lines)
            allocation = [shared * row['downstream_records'] // max(1, denominator) for row in lines]
            allocation[0] += shared - sum(allocation)
            for row, allocated in zip(lines, allocation):
                row['allocated_shared_cents'] = allocated
                row['fully_allocated_cents'] = row['variable_cents'] + allocated
            for kind, used, limit in [('shared_work', work, work_limit), ('crm_quota', crm, crm_limit)]:
                if used > limit:
                    violations.append({'kind': kind, 'condition': c['id'], 'month': m['id'], 'used': used, 'limit': limit})
            months.append({'id': m['id'], 'cost_cents': total, 'components_cents': parts, 'lines': lines,
                           'shared_work': {'used': work, 'limit': work_limit, 'headroom': work_limit - work},
                           'crm_quota': {'used': crm, 'limit': crm_limit, 'headroom': crm_limit - crm},
                           'overage_requests': overage})
        annual = sum(m['cost_cents'] for m in months)
        if annual > spec['annual_budget_cents']:
            violations.append({'kind': 'annual_budget', 'condition': c['id'], 'actual': annual,
                               'limit': spec['annual_budget_cents']})
        reports.append({'id': c['id'], 'annual_cents': annual, 'months': months})
    return {'feasible': not violations, 'violations': violations, 'enabled_platforms': sorted(enabled),
            'selection': selection, 'conditions': reports, 'worst_annual_cents': max(c['annual_cents'] for c in reports)}


def oracle(spec, conditions):
    """Enumerate this bounded enterprise fixture independently; never claim this scales without bounds."""
    spec = validate(spec)
    count, eligible_count, best = 0, 0, None
    # Accountant's per-route monthly lines are cached without importing compiler coefficients.
    pool = []
    for w in spec['workloads']:
        pool.append([o for o in w['options'] if eligible(w, o)])
    raw_space = len(spec['tiers'])
    for w in spec['workloads']:
        raw_space *= len(w['options'])
    if raw_space > 100000:
        raise Invalid('enterprise_oracle_budget_exceeded')
    cached = {(w['id'], o['id'], c['id'], m['id']): line(w, o, m, c)
              for w, opts in zip(spec['workloads'], pool) for o in opts
              for c in spec['conditions'] if c['id'] in conditions for m in spec['months']}
    for options in itertools.product(*pool):
        enabled = {o['platform'] for o in options}
        base = sum(p['monthly_fixed_cents'] for p in spec['platforms'] if p['id'] in enabled)
        for t in spec['tiers']:
            eligible_count += 1
            totals, feasible = [], True
            for c in spec['conditions']:
                if c['id'] not in conditions:
                    continue
                total = 0
                for m in spec['months']:
                    rows = [cached[(w['id'], o['id'], c['id'], m['id'])]
                            for w, o in zip(spec['workloads'], options)]
                    if (sum(r['work_peak_units_hour'] for r in rows) * 100
                            > t['work_units_hour'] * spec['capacity_utilization_percent']
                            or sum(r['crm_peak_calls_hour'] for r in rows) * 100
                            > t['crm_calls_hour'] * c['quota_percent']):
                        feasible = False
                    total += (base + t['workers'] * t['worker_month_cents']
                              + t['support_hours'] * spec['support_hour_cents']
                              + sum(r['variable_cents'] for r in rows)
                              + max(0, sum(r['attempts'] for r in rows) - t['included_requests_month'])
                              * spec['overage_cents_per_request'])
                totals.append(total)
            count += 1
            objective = max(totals)
            if objective > spec['annual_budget_cents']:
                feasible = False
            if feasible and (best is None or objective < best['annual_cents']):
                best = {'annual_cents': objective, 'selection': {'tier': t['id'], 'routes':
                        {w['id']: o['id'] for w, o in zip(spec['workloads'], options)}}}
    return {'status': 'optimal' if best else 'infeasible', 'best': best, 'raw_space': raw_space,
            'eligible_configurations_checked': eligible_count, 'configurations_assessed': count,
            'method': 'Independent bounded enumeration after hard route-eligibility pruning'}
