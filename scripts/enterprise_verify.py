"""Reproduce the annual package and reject altered financial or optimization evidence."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from stack_economics.contracts import digest
from stack_economics.enterprise.contract import validate
from stack_economics.enterprise.report import build, write

ROOT = Path(__file__).resolve().parents[1]


def fingerprints():
    result = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src/stack_economics/enterprise', 'fixtures/enterprise')
            for p in sorted((ROOT / folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    for name in ('scripts/enterprise_verify.py', 'scripts/enterprise_browser.py', 'tests/test_enterprise.py'):
        result[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    inputs = fingerprints()
    spec = validate(json.loads((ROOT / 'fixtures/enterprise/multibrand-2026.json').read_text()))
    result = build(spec)
    if args.check:
        saved = json.loads((args.check / 'decision.json').read_text())
        assert saved == result, 'Enterprise decision differs from independent fresh reproduction'
        record = json.loads((args.check / 'verification.json').read_text())
        assert record['decision_sha256'] == digest(saved), 'Decision hash mismatch'
        for name, sha in record['source_sha256'].items():
            assert inputs[name] == sha, 'Source bytes differ from recorded execution: ' + name
        print('Enterprise evidence independently reproduced, including all sensitivities')
    if args.output:
        if args.output.exists():
            raise ValueError('Use a fresh enterprise evidence directory')
        args.output.mkdir(parents=True)
        write(args.output / 'decision.json', result)
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() \
            if (ROOT / '.git').exists() else os.environ['STACK_ECONOMICS_SOURCE_COMMIT']
        dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', 'src', 'scripts', 'tests', 'fixtures'],
                                        cwd=ROOT, text=True).strip() if (ROOT / '.git').exists() else None
        assert inputs == fingerprints(), 'Inputs changed during execution'
        write(args.output / 'verification.json', {'verification_passed': True, 'source_commit': revision,
              'source_committed': not bool(dirty) if dirty is not None else None,
              'executed_at': datetime.now(UTC).isoformat(), 'python': platform.python_version(),
              'platform': platform.platform(), 'source_sha256': inputs, 'decision_sha256': digest(result),
              'comparisons': len(result['sensitivity']) + 3,
              'boundary': 'Actual MILP and independently enumerated synthetic financial planning; no vendor calls.'})
        print('Verified enterprise alternatives and', len(result['sensitivity']), 'sensitivity cases')
    if not (args.output or args.check):
        parser.error('--output or --check required')


if __name__ == '__main__':
    main()
