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

from check_execution import check

ROOT = Path(__file__).resolve().parents[1]


def sources():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src', 'tests', 'scripts', 'fixtures', '.github') for p in sorted((ROOT / folder).rglob('*'))
            if p.is_file() and p.suffix in ('.py', '.html', '.css', '.js', '.json', '.yml')
            and '__pycache__' not in p.parts} | {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in ('pyproject.toml', 'requirements.lock', 'requirements-browser.lock', 'Dockerfile.assurance')}


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
    start = time.monotonic()
    def execute(*arguments):
        subprocess.run([sys.executable, *arguments], cwd=ROOT, check=True)
    execute('scripts/verify.py', '--output', str(output / 'mathematics'))
    execute('-m', 'stack_economics.assurance.demo', '--root', str(ROOT), '--output', str(output / 'execution'),
            *(['--quick'] if args.quick else []))
    count = check(output / 'execution')
    assert before == sources(), 'Execution source changed during acceptance'
    head = (subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            if (ROOT / '.git').exists() else os.environ['STACK_ECONOMICS_SOURCE_COMMIT'])
    uncommitted = (subprocess.check_output(['git', 'status', '--porcelain', '--',
                                          'src', 'tests', 'scripts', 'fixtures', '.github', 'pyproject.toml',
                                          'requirements.lock', 'Dockerfile.assurance'], cwd=ROOT, text=True).strip()
                   if (ROOT / '.git').exists() else None)
    record = {'schema': 1, 'source_commit': head, 'source_sha256': before,
              'source_committed': not bool(uncommitted) if uncommitted is not None else None,
              'source_revision_origin': 'git' if (ROOT / '.git').exists() else 'container_build_argument',
              'executed_at': datetime.now(UTC).isoformat(),
              'python': platform.python_version(), 'platform': platform.platform(),
              'seconds': round(time.monotonic() - start, 3), 'decisions_reconciled': count,
              'scope': 'Actual local HTTP subprocesses, durable SQLite intent and independent receiver databases; '
                       'synthetic costs/records; accelerated timing. No external vendor or production acceptance.'}
    (output / 'verification.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print('Acceptance completed:', output)


if __name__ == '__main__':
    main()
