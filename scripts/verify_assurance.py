"""Source-bound acceptance, writing a new record rather than replacing historical proof."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import stack_economics
from stack_economics.cli import write_json

from check_execution import check

ROOT = Path(__file__).resolve().parents[1]


def sources():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src', 'tests', 'scripts', 'fixtures', '.github') for p in sorted((ROOT / folder).rglob('*'))
            if p.is_file() and p.suffix in ('.py', '.html', '.css', '.js', '.json', '.yml')
            and '__pycache__' not in p.parts} | {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in ('pyproject.toml', 'requirements.lock', 'requirements-browser.lock',
                             'Dockerfile.assurance', '.dockerignore')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Use a new output directory to preserve prior observations')
    output.mkdir(parents=True)
    before = sources()
    installed = Path(stack_economics.__file__).parent
    for path in (ROOT / 'src/stack_economics').rglob('*'):
        if path.is_file() and path.suffix in ('.py', '.html', '.css', '.js'):
            assert path.read_bytes() == (installed / path.relative_to(ROOT / 'src/stack_economics')).read_bytes(), \
                'Installed execution package differs from source'
    (output / 'input-fingerprints.json').write_text(json.dumps(before, indent=2) + '\n', encoding='utf-8')
    start = time.monotonic()
    def execute(*arguments):
        subprocess.run([sys.executable, *arguments], cwd=ROOT, check=True)
    execute('scripts/verify.py', '--output', str(output / 'mathematics'))
    execute('-m', 'stack_economics.assurance.demo', '--root', str(ROOT), '--output', str(output / 'execution'),
            *(['--quick'] if args.quick else []))
    count = check(output / 'execution')
    assert count == (2 if args.quick else 9), 'Incomplete experiment suite'
    trials = json.loads((output / 'execution/summary.json').read_text(encoding='utf-8'))['trials']
    required = {'normal', 'launch-surge'} if args.quick else {
        'normal', 'launch-surge', 'transient-recovery', 'delayed-source', 'slow-destination',
        'shared-quota-pressure', 'revoked-permission', 'capacity-revision', 'capacity-blocked'}
    assert {t['name'] for t in trials} == required, 'Missing or unexpected experiment'
    execute('scripts/financial_audit.py', '--evidence', str(output / 'execution'),
            '--output', str(output / 'financial-audit.json'))
    execute('scripts/enterprise_verify.py', '--output', str(output / 'enterprise'))
    assert before == sources(), 'Execution source changed during acceptance'
    head = (subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            if (ROOT / '.git').exists() else os.environ['STACK_ECONOMICS_SOURCE_COMMIT'])
    uncommitted = (subprocess.check_output(['git', 'status', '--porcelain', '--',
                                          'src', 'tests', 'scripts', 'fixtures', '.github', 'pyproject.toml',
                                          'requirements.lock', 'Dockerfile.assurance'], cwd=ROOT, text=True).strip()
                   if (ROOT / '.git').exists() else None)
    record = {'schema': 1, 'source_commit': head, 'source_sha256': before,
              'verification_passed': True,
              'outcomes': {t['name']: 'blocked' if t.get('blocked') else
                           'acceptable' if t['result']['acceptable'] else 'revision_required' for t in trials},
              'source_committed': not bool(uncommitted) if uncommitted is not None else None,
              'source_revision_origin': 'git' if (ROOT / '.git').exists() else 'container_build_argument',
              'executed_at': datetime.now(UTC).isoformat(),
              'python': platform.python_version(), 'platform': platform.platform(),
              'numerical_threads': {k: os.getenv(k) for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS')},
              'seconds': round(time.monotonic() - start, 3), 'decisions_reconciled': count,
              'scope': 'Actual local HTTP subprocesses, durable SQLite intent and independent receiver databases; '
                       'synthetic costs/records; accelerated timing. No external vendor or production acceptance.'}
    write_json(output / 'verification.json', record)
    print('Evidence verification completed:', output)


if __name__ == '__main__':
    main()
