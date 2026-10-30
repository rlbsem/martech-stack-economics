"""Deterministic enterprise decision package, including independently rejected alternatives."""
import copy
import json
from pathlib import Path

from stack_economics.contracts import digest

from .accounting import assess, oracle
from .contract import validate
from .planning import solve


def build(value):
    spec = validate(value)
    operating = ['operating']
    robust = [c['id'] for c in spec['conditions']]
    plans = {'optimized': solve(spec, operating), 'resilient': solve(spec, robust)}
    independent = {name: oracle(spec, plan['conditions']) for name, plan in plans.items()}
    for name, plan in plans.items():
        assert plan['status'] == independent[name]['status']
        if plan['status'] == 'optimal':
            assert plan['annual_cents'] == independent[name]['best']['annual_cents']
    alternatives = {'reference': {'selection': spec['reference'], 'basis': 'Declared mixed-route, eight-worker reference'}}
    for name, plan in plans.items():
        alternatives[name] = {'selection': plan['selection'], 'basis': 'MILP optimum over ' + ', '.join(plan['conditions'])}
    for item in alternatives.values():
        item['assessment'] = assess(spec, item['selection']) if item['selection'] else None
    sensitivity = []
    for dimension, values in [('demand_percent', [75, 100, 125, 150, 200, 300]),
                              ('quota_percent', [1, 5, 25, 50, 100]),
                              ('event_price_delta_cents', [-1, 0, 1]),
                              ('work_capacity_percent', [1, 2, 5, 25, 100]),
                              ('freshness_minutes', [1, 5, 15])]:
        for amount in values:
            adjusted = copy.deepcopy(spec)
            if dimension in ('demand_percent', 'quota_percent'):
                adjusted['conditions'][0][dimension] = amount
            elif dimension == 'work_capacity_percent':
                for t in adjusted['tiers']:
                    t['work_units_hour'] = max(1, t['work_units_hour'] * amount // 100)
            elif dimension == 'freshness_minutes':
                for w in adjusted['workloads']:
                    w['max_lag_minutes'] = min(w['max_lag_minutes'], amount)
            else:
                for w in adjusted['workloads']:
                    for o in w['options']:
                        o['event_cents_per_1000'] = max(0, o['event_cents_per_1000'] + amount)
            plan = solve(adjusted, operating)
            check = oracle(adjusted, operating)
            assert plan['status'] == check['status']
            assert plan['annual_cents'] == (check['best']['annual_cents'] if check['best'] else None)
            sensitivity.append({'dimension': dimension, 'value': amount, 'plan': plan,
                                'independent_annual_cents': check['best']['annual_cents'] if check['best'] else None,
                                'configurations_checked': check['configurations_assessed']})
    # One-cent budget cut is checked with an independent oracle as well as the solver.
    impossible = copy.deepcopy(spec)
    impossible['annual_budget_cents'] = plans['optimized']['annual_cents'] - 1
    rejected = solve(impossible, operating)
    rejected_oracle = oracle(impossible, operating)
    assert rejected['status'] == rejected_oracle['status'] == 'infeasible'
    return {'schema': 'enterprise-decision/v1', 'currency': spec['currency'], 'synthetic': True,
            'input_sha256': digest(spec), 'scenario': spec, 'plans': plans, 'independent_oracles': independent,
            'alternatives': alternatives, 'sensitivity': sensitivity, 'budget_rejection': rejected,
            'boundary': 'Synthetic annual planning, not measured enterprise throughput, vendor quotes or commercial savings.',
            'bounded_execution': 'Separate preserved local HTTP acceptance: docs/evidence/execution/README.md',
            'projection': 'No measured scale factor converts the local HTTP timings into enterprise capacity.'}


def write(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
