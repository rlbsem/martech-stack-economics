import copy
import json
import subprocess
import sys
import time

import pytest

from stack_economics.assurance.demo import trial
from stack_economics.assurance.execution import Services, process_batch, profile, request
from stack_economics.assurance.reconcile import reconcile
from stack_economics.assurance.storage import (
    authorize, database, encode, initialize, propose, rows, transition, verify_authorized,
)
from stack_economics.fixtures import campaign_launch
from stack_economics.planner import solve


@pytest.fixture
def small():
    spec = campaign_launch()
    spec['slots'] = 1
    for work in spec['workloads']:
        work['max_lag_minutes'] = 60
    for scenario in spec['scenarios']:
        scenario['demands'] = {w['id']: [13] for w in spec['workloads']}
        for cap in scenario['capacities'].values():
            cap['per_slot'] = [100]
    return spec


def read_observation(path):
    import gzip
    with gzip.open(path / 'observations.json.gz', 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def test_real_http_arithmetic_partial_batches_and_mutated_evidence(tmp_path, small):
    ledger = tmp_path / 'ledger.sqlite'
    initialize(ledger)
    result = trial(tmp_path / 'normal', small, solve(small), small['scenarios'][0]['id'],
                   profile(window_seconds=2), 'normal', ledger)
    observed = read_observation(tmp_path / 'normal')
    checked = result['result']
    assert checked['acceptable'], checked
    assert checked['source_records'] == checked['on_time_records'] == 65
    assert checked['predicted_cost_cents'] == checked['actual_synthetic_cost_cents'] == 30
    assert checked['actual_requests'] == {'crm-api': 5, 'destination-api': 5, 'bulk-jobs': 0}
    assert len(observed['receivers']['destination-api']['records']) == 55  # Two deletes per 13-record batch.
    assert [e['state'] for e in rows(ledger, 'transitions')] == [
        'proposed', 'validated', 'authorized', 'observed', 'acceptable']
    mutations = []
    changed = copy.deepcopy(observed)
    changed['receivers']['destination-api']['requests'][0]['size'] += 1
    mutations.append((changed, 'receiver_content_contract'))
    changed = copy.deepcopy(observed)
    changed['receivers']['destination-api']['receipts'][0]['body_hash'] = 'altered'
    mutations.append((changed, 'receipt_content_conflict'))
    changed = copy.deepcopy(observed)
    changed['receivers']['destination-api']['records'][0]['content'] = '{}'
    mutations.append((changed, 'destination_readback_mismatch'))
    changed = copy.deepcopy(observed)
    changed['control']['batches'][0]['deadline_ns'] += 1_000_000_000
    mutations.append((changed, 'source_clock_contract'))
    changed = copy.deepcopy(observed)
    changed['receivers']['crm-api']['config']['per_slot'] += 1
    mutations.append((changed, 'receiver_configuration_binding'))
    changed = copy.deepcopy(observed)
    changed['receivers']['crm-api']['requests'].pop()
    mutations.append((changed, 'client_receiver_request_disagreement'))
    for changed, reason in mutations:
        assert reason in reconcile(changed)['violations']


def prepare_batch(control, run, workflow='lead-handoff'):
    initialize(control)
    body = {'key': run + ':' + workflow + ':0:0', 'workflow': workflow, 'slot': 0, 'batch_size': 100,
            'records': [{'id': workflow + ':0:1', 'operation': 'upsert',
                         'fields': {'synthetic': True, 'custom_segment': 'enterprise'}}]}
    now = time.time_ns()
    with database(control) as db:
        db.execute("INSERT INTO batches(key,workflow,slot,payload,created_ns,ready_ns,deadline_ns) VALUES(?,?,?,?,?,?,?)",
                   (body['key'], workflow, 0, encode(body), now, now, now + 8_000_000_000))
    return body


def test_process_loss_exact_recovery_duplicate_and_content_conflict(tmp_path, small):
    runtime = profile(window_seconds=10)
    control = tmp_path / 'control.sqlite'
    with Services(tmp_path / 'receivers', small, runtime, 'crash') as services:
        time.sleep(max(0, (services.epoch_ns - time.time_ns()) / 1e9))
        body = prepare_batch(control, 'crash')
        option = next(o for o in small['workloads'][0]['options'] if o['id'] == 'rest')
        # A real child process exits after the destination committed, before saving its acknowledgement.
        command = ('import json; from pathlib import Path; '
                   'from stack_economics.assurance.execution import process_batch; '
                   f'process_batch(Path({str(control)!r}),{body["key"]!r},json.loads({encode(option)!r}),'
                   f'json.loads({encode(services.urls)!r}),json.loads({encode(runtime)!r}),"destination-api")')
        child = subprocess.run([sys.executable, '-c', command], timeout=15)
        assert child.returncode == 17
        assert rows(control, 'calls')[-1]['state'] == 'dispatching'
        process_batch(control, body['key'], option, services.urls, runtime)
        assert rows(control, 'batches')[0]['state'] == 'confirmed'
        status, receipt = request(services.urls['destination-api'] + '/batches', 'POST', body, 1)
        assert status == 200
        changed = copy.deepcopy(body)
        changed['records'][0]['fields']['custom_segment'] = 'wrong'
        status, error = request(services.urls['destination-api'] + '/batches', 'POST', changed, 1)
        assert (status, error['error']) == (409, 'content_conflict')
        snapshot = services.snapshot()['destination-api']
        assert len(snapshot['receipts']) == len(snapshot['records']) == 1
        assert json.loads(snapshot['receipts'][0]['receipt']) == receipt
        assert [r['method'] for r in snapshot['requests']] == ['POST', 'GET', 'POST', 'POST']


def test_lost_acknowledgement_and_transient_failures_are_counted(tmp_path, small):
    ledger = tmp_path / 'ledger.sqlite'
    initialize(ledger)
    runtime = profile(window_seconds=3, faults=[{'resource': 'crm-api', 'kind': '503'},
                      {'resource': 'destination-api', 'kind': '429'},
                      {'resource': 'destination-api', 'kind': 'lost_ack', 'workflow': 'product-enrichment'}])
    result = trial(tmp_path / 'recovery', small, solve(small), small['scenarios'][0]['id'], runtime, 'recovery', ledger)
    checked = result['result']
    assert checked['acceptable'], checked
    assert checked['actual_requests']['crm-api'] == 6
    assert checked['actual_requests']['destination-api'] == 7
    assert checked['actual_synthetic_cost_cents'] == 37  # 30 + retried destination POST6 + GET1.
    assert checked['failures']['crm-api'] == {'503': 1}
    assert checked['failures']['destination-api'] == {'429': 1}


def test_expired_sources_and_revoked_permission_do_not_create_effects(tmp_path, small):
    ledger = tmp_path / 'ledger.sqlite'
    initialize(ledger)
    runtime = profile(window_seconds=0.3, source_delay={w['id']: 0.4 for w in small['workloads']})
    result = trial(tmp_path / 'expired', small, solve(small), small['scenarios'][0]['id'], runtime, 'expired', ledger)
    assert result['result']['unresolved_records'] == 65
    assert not any(result['result']['actual_requests'].values())
    result = trial(tmp_path / 'revoked', small, solve(small), small['scenarios'][0]['id'],
                   profile(window_seconds=2, permission=False), 'revoked', ledger)
    assert result['result']['unresolved_records'] == 65
    assert result['result']['actual_synthetic_cost_cents'] == 0
    assert result['result']['failures']['crm-api'] == {'403': 5}


def test_admission_capacity_is_not_an_arrival_rate_guarantee(tmp_path, small):
    ledger = tmp_path / 'ledger.sqlite'
    initialize(ledger)
    runtime = profile(window_seconds=1, capacity_override={'crm-api': 2})
    result = trial(tmp_path / 'quota', small, solve(small), small['scenarios'][0]['id'], runtime, 'quota', ledger)
    checked = result['result']
    crm = next(c for c in checked['capacity'] if c['resource'] == 'crm-api')
    assert crm['admitted'] == 2
    assert crm['max_arrivals_per_window'] > 2
    assert crm['arrival_windows_over_capacity'] == 1
    assert not checked['acceptable']
    assert checked['unresolved_records'] == 39
    assert 'receiver_admission_quota' not in checked['violations']


def test_decisions_are_immutable_scoped_and_revisions_cannot_relax_semantics(tmp_path, small):
    ledger = tmp_path / 'ledger.sqlite'
    initialize(ledger)
    runtime = profile()
    decision = propose(ledger, small, solve(small), runtime)
    with pytest.raises(ValueError, match='Invalid architecture transition'):
        authorize(ledger, decision, runtime)
    transition(ledger, decision, 'validated', 'test-checker', {})
    with pytest.raises(ValueError, match='profile differs'):
        authorize(ledger, decision, profile(workers=1))
    authorize(ledger, decision, runtime)
    with pytest.raises(ValueError, match='content differs'):
        verify_authorized(ledger, decision, small, solve(small), runtime, 'changed-run', 'normal')
    with database(ledger) as db:
        with pytest.raises(Exception, match='immutable decision'):
            db.execute('UPDATE decisions SET document=?', ('{}',))
    revised = copy.deepcopy(small)
    revised['workloads'][0]['max_lag_minutes'] += 1
    with pytest.raises(ValueError, match='protected requirements'):
        propose(ledger, revised, solve(revised), runtime, decision)
    revised = copy.deepcopy(small)
    for scenario in revised['scenarios']:
        scenario['capacities']['crm-api']['per_slot'] = [1]
        scenario['capacities']['crm-api']['total'] = 1
    plan = solve(revised)
    assert plan['status'] == 'infeasible'
    blocked = trial(tmp_path / 'blocked', revised, plan, revised['scenarios'][0]['id'], runtime,
                    'blocked', ledger, decision)
    assert blocked['blocked']
    assert not (tmp_path / 'blocked').exists()
    assert len(rows(ledger, 'decisions')) == 2


def test_source_failure_isolation_and_observed_budget_breach(tmp_path, small):
    ledger = tmp_path / 'ledger.sqlite'
    initialize(ledger)
    result = trial(tmp_path / 'isolated', small, solve(small), small['scenarios'][0]['id'],
                   profile(window_seconds=1, source_delay={'lead-handoff': 1.2}), 'isolated', ledger)
    assert result['result']['on_time_records'] == 52
    assert result['result']['workflows']['lead-handoff']['on_time_records'] == 0
    for name, workflow in result['result']['workflows'].items():
        if name != 'lead-handoff':
            assert workflow['on_time_records'] == 13
    budget = copy.deepcopy(small)
    budget['budget_cents'] = 30
    result = trial(tmp_path / 'budget', budget, solve(budget), budget['scenarios'][0]['id'],
                   profile(window_seconds=2, faults=[{'resource': 'destination-api', 'kind': '429'}]),
                   'budget', ledger)
    assert result['result']['on_time_records'] == 65
    assert result['result']['actual_synthetic_cost_cents'] == 36
    assert result['result']['violations'] == ['synthetic_budget_breach']


def test_late_remote_commits_remain_visible(tmp_path, small):
    ledger = tmp_path / 'ledger.sqlite'
    initialize(ledger)
    result = trial(tmp_path / 'late', small, solve(small), small['scenarios'][0]['id'],
                   profile(window_seconds=1, faults=[{'resource': 'destination-api', 'kind': 'latency', 'seconds': 1.2}]),
                   'late', ledger)
    assert result['result']['late_records'] > 0
    assert 'freshness_breach' in result['result']['violations']
    assert not result['result']['acceptable']
