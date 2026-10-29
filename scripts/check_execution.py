"""Recompute all recorded acceptance results from independent raw observations."""
import argparse
import gzip
import json
from pathlib import Path

from stack_economics.assurance.reconcile import reconcile
from stack_economics.contracts import digest
from stack_economics.planner import check_plan


def check(directory):
    summary = json.loads((directory / 'summary.json').read_text(encoding='utf-8'))
    ids = set()
    for trial in summary['trials']:
        decision_row = next(d for d in summary['decisions'] if d['id'] == trial['decision'])
        decision = json.loads(decision_row['document'])
        assert digest(decision) == trial['decision'], 'Decision content hash mismatch'
        assert decision['parent'] == decision_row['parent'], 'Parent mismatch'
        assert trial['name'] not in ids, 'Duplicate experiment name'
        ids.add(trial['name'])
        states = [e['state'] for e in summary['transitions'] if e['decision'] == trial['decision']]
        if trial.get('blocked'):
            assert decision['plan']['status'] == 'infeasible'
            assert states == ['proposed', 'blocked']
            continue
        with gzip.open(directory / trial['name'] / 'observations.json.gz', 'rt', encoding='utf-8') as stream:
            observed = json.load(stream)
        assert digest(observed) == trial['evidence_hash'], 'Observation hash mismatch'
        assert observed['decision'] == trial['decision'] and observed['run'] == trial['name']
        assert decision['spec'] == observed['spec'] and decision['profile'] == observed['profile']
        assert decision['plan'] == observed['plan']
        check_plan(observed['spec'], observed['plan'])
        result = reconcile(observed)
        assert result == trial['result'], 'Recomputed result differs'
        assert digest(result) == trial['result_hash'], 'Result hash mismatch'
        assert result == json.loads((directory / trial['name'] / 'result.json').read_text()), 'Result file differs'
        assert states == ['proposed', 'validated', 'authorized', 'observed',
                          'acceptable' if result['acceptable'] else 'revision_required']
        print(trial['name'], 'acceptable' if result['acceptable'] else ', '.join(result['violations']))
    # These are engineering expectations, not values to overwrite into a measured result.
    # A surge's operational verdict is measured, never forced to match modeled feasibility.
    for name in ('normal', 'capacity-revision'):
        if name in ids:
            assert next(t for t in summary['trials'] if t['name'] == name)['result']['acceptable'], name
    for name in ('delayed-source', 'slow-destination', 'shared-quota-pressure', 'revoked-permission'):
        if name in ids:
            assert not next(t for t in summary['trials'] if t['name'] == name)['result']['acceptable'], name
    return len(ids)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True, type=Path)
    args = parser.parse_args()
    print('Reconciled', check(args.evidence), 'recorded architecture decisions')
