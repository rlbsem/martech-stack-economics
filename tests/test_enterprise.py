"""Independent financial, unit, constraint, optimization and rejection controls."""
import copy

import pytest

from stack_economics.contracts import Invalid, digest
from stack_economics.enterprise.accounting import assess, ceiling, line, oracle
from stack_economics.enterprise.contract import validate
from stack_economics.enterprise.fixture import scenario
from stack_economics.enterprise.planning import coefficients, solve


@pytest.mark.parametrize('status', [1, 4])
def test_unresolved_solver_never_recommends(monkeypatch, status):
    from types import SimpleNamespace
    monkeypatch.setattr('stack_economics.enterprise.planning.milp', lambda *a, **k: SimpleNamespace(status=status))
    r = solve(scenario(), ['operating'])
    assert r['status'] == 'unresolved' and r['selection'] is None and r['annual_cents'] is None


def test_fixture_matches_versioned_source():
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'fixtures/enterprise/multibrand-2026.json'
    assert json.loads(path.read_text()) == scenario()


def test_solver_exception_never_recommends(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError('injected solver failure')
    monkeypatch.setattr('stack_economics.enterprise.planning.milp', fail)
    r = solve(scenario(), ['operating'])
    assert r['selection'] is None and r['status'] == 'unresolved'


def test_known_total_and_condition_selection_are_independent():
    s = scenario()
    check = assess(s, s['reference'], ['operating'])
    assert check['conditions'][0]['annual_cents'] > 0
    assert check['worst_annual_cents'] == check['conditions'][0]['annual_cents']
    routes = copy.deepcopy(s['reference'])
    routes['routes']['web-events'] = 'missing'
    with pytest.raises(Invalid):
        assess(s, routes)


def test_calendar_source_units_and_currency():
    s = validate(scenario())
    assert sum(w['source_events_month'] for w in s['workloads']) == 100_000_000
    assert sum(m['demand_percent'] for m in s['months']) == 1200
    a = assess(s, s['reference'], ['operating'])
    months = a['conditions'][0]['months']
    assert sum(r['source_events'] for m in months for r in m['lines']) == 1_200_000_000
    assert sum(r['downstream_records'] for m in months for r in m['lines']) == 1_332_000_000
    assert len({m['cost_cents'] for m in months}) > 1
    assert s['currency'] == 'USD'


@pytest.mark.parametrize('conditions', [['operating'], ['operating', 'campaign-disruption']])
def test_milp_matches_independent_bounded_oracle(conditions):
    s = scenario()
    plan = solve(s, conditions)
    other = oracle(s, conditions)
    assert plan['status'] == other['status'] == 'optimal'
    assert plan['annual_cents'] == other['best']['annual_cents']
    assert other['raw_space'] == 19683
    assert other['configurations_assessed'] == 576
    assert plan['mip_gap'] == 0
    assert plan['dual_bound_cents'] == plan['annual_cents']
    assert assess(s, plan['selection'], conditions)['feasible']


def test_independent_monthly_coefficients_and_allocation():
    s = scenario()
    for w in s['workloads']:
        for o in w['options']:
            for m in s['months']:
                for c in s['conditions']:
                    a = line(w, o, m, c)
                    assert coefficients(w, o, m, c) == (a['variable_cents'], a['attempts'],
                                                          a['work_peak_units_hour'], a['crm_peak_calls_hour'])
    a = assess(s, s['reference'])
    for c in a['conditions']:
        assert c['annual_cents'] == sum(m['cost_cents'] for m in c['months'])
        for m in c['months']:
            assert sum(r['fully_allocated_cents'] for r in m['lines']) == m['cost_cents']
            assert sum(m['components_cents'].values()) == m['cost_cents']
            assert m['components_cents']['subscriptions'] == 1_130_000


def test_exact_zero_partial_batch_and_retries():
    s = scenario()
    w, m, c = copy.deepcopy(s['workloads'][0]), s['months'][0], s['conditions'][0]
    o = copy.deepcopy(w['options'][0])
    w['source_events_month'] = 0
    assert line(w, o, m, c)['batches'] == 0
    w['source_events_month'] = 1
    a = line(w, o, m, c)
    assert a['source_events'] == a['batches'] == 1
    assert a['retry_requests'] == 1
    assert ceiling(0, 3) == 0 and ceiling(4, 3) == 2
    o['batch_size'] = 1
    w['source_events_month'] = 1001
    a = line(w, o, m, c)
    assert a['batches'] == a['downstream_records']


def test_rejections_budget_region_freshness_capability_and_capacity():
    s = scenario()
    selected = solve(s, ['operating'])
    s['annual_budget_cents'] = selected['annual_cents'] - 1
    assert solve(s, ['operating'])['status'] == oracle(s, ['operating'])['status'] == 'infeasible'
    for field, value in [('region', 'us'), ('lag_minutes', 60), ('capabilities', [])]:
        s = scenario()
        for o in s['workloads'][4]['options']:
            o[field] = value
        assert solve(s, ['operating'])['status'] == 'infeasible'
    s = scenario()
    for t in s['tiers']:
        t['crm_calls_hour'] = 1
    assert solve(s, ['operating'])['status'] == oracle(s, ['operating'])['status'] == 'infeasible'


@pytest.mark.parametrize('field,value', [('currency', 'CAD'), ('synthetic', False), ('year', 2026.0),
                                        ('annual_budget_cents', -1), ('support_hour_cents', True),
                                        ('schema', 'unknown'), ('months', [])])
def test_invalid_input_rejected(field, value):
    s = scenario()
    s[field] = value
    with pytest.raises(Invalid):
        validate(s)


def test_unknown_duplicate_and_detached_inputs():
    s = scenario()
    validated = validate(s)
    before = digest(validated)
    s['months'][0]['demand_percent'] = 100
    assert digest(validated) == before
    s = scenario()
    s['tiers'].append(s['tiers'][0])
    with pytest.raises(Invalid):
        validate(s)
    s = scenario()
    s['workloads'][0]['options'][0]['platform'] = 'unknown'
    with pytest.raises(Invalid):
        validate(s)
    with pytest.raises(Invalid):
        assess(scenario(), scenario()['reference'], ['missing'])


def test_tiers_are_not_linear_cost_scaling():
    s = scenario()
    normal = solve(s, ['operating'])
    for c in s['conditions']:
        c['demand_percent'] = 300
    growth = solve(s, ['operating'])
    assert growth['status'] == 'optimal'
    assert growth['annual_cents'] != normal['annual_cents'] * 3
    assert assess(s, normal['selection'], ['operating'])['worst_annual_cents'] > normal['annual_cents']


def test_failure_envelope_can_reject_cheapest_operating_plan():
    s = scenario()
    normal = solve(s, ['operating'])
    # A separate explicitly constrained quota, not a fabricated failure in the base scenario.
    s['conditions'][1]['quota_percent'] = 1
    assessment = assess(s, normal['selection'])
    assert any(v['kind'] in ('shared_work', 'crm_quota') and v['condition'] == 'campaign-disruption'
               for v in assessment['violations'])
    robust = solve(s, ['operating', 'campaign-disruption'])
    assert assess(s, robust['selection'])['feasible']


def test_daily_peak_profile_billing_and_capacity_use_same_records():
    s = scenario()
    w, m, c = s['workloads'][0], s['months'][0], s['conditions'][0]
    a = line(w, w['options'][0], m, c)
    assert a['peak_records_hour'] * m['days'] == a['records_in_daily_peak_hours']
    assert a['records_in_daily_peak_hours'] < a['downstream_records']
    total_batches = 0
    # Explicitly materialize emission-window counts for an independent billing check.
    peak_windows = m['days'] * 60
    for population, n in [(a['records_in_daily_peak_hours'], peak_windows),
                           (a['downstream_records']-a['records_in_daily_peak_hours'], a['emission_windows']-peak_windows)]:
        records = [population // n + int(i < population % n) for i in range(n)]
        assert sum(records) == population
        total_batches += sum((count + 249) // 250 for count in records)
    assert total_batches == a['batches']
    s['workloads'][0]['peak_hour_ppm'] = 1000000
    with pytest.raises(Invalid):
        validate(s)
