"""Separate financial arithmetic audit, using only Python's standard library."""
import argparse
import gzip
import json
from collections import Counter
from pathlib import Path


def audit(directory):
    checks = []
    for file in sorted(directory.glob('*/observations.json.gz')):
        with gzip.open(file, 'rt', encoding='utf-8') as stream:
            observation = json.load(stream)
        result = json.loads((file.parent / 'result.json').read_text())
        spec = observation['spec']
        chosen = observation['plan']['selection']
        options = {w['id']: next(o for o in w['options'] if o['id'] == chosen[w['id']]) for w in spec['workloads']}
        scenario = next(s for s in spec['scenarios'] if s['id'] == observation['scenario'])
        fixed = sum(p['fixed_cost_cents'] for p in spec['platforms'] if p['id'] in {o['platform'] for o in options.values()})
        predicted = fixed
        expected_requests = Counter()
        for name, option in options.items():
            batches = sum((n + option['batch_size'] - 1) // option['batch_size'] for n in scenario['demands'][name])
            predicted += batches * option['cost_per_batch_cents']
            for resource, units in option['resources'].items():
                expected_requests[resource] += batches * units
        batches = {b['key']: b for b in observation['control']['batches']}
        actual = fixed
        actual_requests = {}
        for resource, receiver in observation['receivers'].items():
            actual_requests[resource] = len(receiver['requests'])
            for request in receiver['requests']:
                if request['method'] == 'GET':
                    actual += observation['profile']['recovery_probe_cents']
                elif resource == 'destination-api':
                    actual += options[batches[request['key']]['workflow']]['cost_per_batch_cents']
        assert predicted == result['predicted_cost_cents'], file.parent.name
        assert actual == result['actual_synthetic_cost_cents'], file.parent.name
        assert dict(expected_requests) == result['predicted_requests']
        assert actual_requests == result['actual_requests']
        checks.append({'trial': file.parent.name, 'currency': spec['currency'], 'predicted_cents': predicted,
                       'observed_synthetic_cents': actual, 'recorded_acceptable': result['acceptable'],
                       'source_records': sum(sum(v) for v in scenario['demands'].values())})
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = {'boundary': 'Independent standard-library arithmetic over actual recorded local HTTP operations; synthetic prices only',
              'trials': audit(args.evidence)}
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('Independently reconciled arithmetic for', len(result['trials']), 'executed trials')
