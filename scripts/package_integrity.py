"""Preserve baseline evidence and hash public delivery files, excluding private runtime state."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'c5944464c8711ee2c8bb510226c25b5f8dbb56ac'
PRESERVED = ROOT / 'docs/evidence/execution/preserved-files.json'
MANIFEST = ROOT / 'package-manifest.json'
UPGRADE_BASE = '5f39b77'


def previous_execution():
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', UPGRADE_BASE], cwd=ROOT, text=True).splitlines()
    names = [n for n in names if n.startswith(('docs/evidence/', 'docs/images/', 'src/stack_economics/', 'tests/', 'fixtures/'))
             or n == 'LICENSE']
    for name in names:
        expected = subprocess.check_output(['git', 'rev-parse', UPGRADE_BASE + ':' + name], cwd=ROOT, text=True).strip()
        actual = subprocess.check_output(['git', 'hash-object', '--path', name, name], cwd=ROOT, text=True).strip()
        original = subprocess.check_output(['git', 'show', UPGRADE_BASE + ':' + name], cwd=ROOT)
        assert (ROOT / name).read_bytes() == original or actual == expected, \
            'Prior execution implementation/evidence changed: ' + name
    return {'source_revision': subprocess.check_output(['git', 'rev-parse', UPGRADE_BASE], cwd=ROOT, text=True).strip(),
            'files': len(names), 'boundary': 'All original source, tests, fixtures, evidence, images and license unchanged'}


def preserved():
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE], cwd=ROOT, text=True).splitlines()
    protected = [name for name in names if name.startswith(('docs/evidence/', 'docs/images/'))
                 or name.startswith('src/stack_economics/') or name.startswith('tests/')
                 or name.startswith('fixtures/') or name == 'LICENSE']
    hashes = {}
    for name in protected:
        original = subprocess.check_output(['git', 'show', BASE + ':' + name], cwd=ROOT)
        actual_object = subprocess.check_output(['git', 'hash-object', '--path', name, name], cwd=ROOT, text=True).strip()
        expected_object = subprocess.check_output(['git', 'rev-parse', BASE + ':' + name], cwd=ROOT, text=True).strip()
        assert (ROOT / name).read_bytes() == original or actual_object == expected_object, 'Protected baseline changed: ' + name
        hashes[name] = hashlib.sha256(original).hexdigest()
    return {'baseline': BASE, 'files': hashes}


def public_files():
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
                                    cwd=ROOT, text=True).splitlines()
    return {name: hashlib.sha256(public_bytes(ROOT / name)).hexdigest() for name in sorted(set(names))
            if name != MANIFEST.name and (ROOT / name).is_file()}


def public_bytes(path):
    raw = path.read_bytes()
    name = path.relative_to(ROOT).as_posix()
    previous = subprocess.run(['git', 'show', ':' + name], cwd=ROOT, capture_output=True)
    # Some original evidence was committed with CRLF. Preserve those public bytes too.
    if previous.returncode == 0 and raw.replace(b'\r\n', b'\n') == previous.stdout.replace(b'\r\n', b'\n'):
        return previous.stdout
    # New/changed repository text is normalized by the ordinary Git text filter.
    if path.suffix in {'.py', '.md', '.json', '.xml', '.svg', '.txt', '.yml', '.toml', '.lock', '.html', '.css', '.js'} \
            or path.name in {'LICENSE', '.gitignore', '.gitattributes', 'Dockerfile.assurance'}:
        return raw.replace(b'\r\n', b'\n')
    return raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    expected = preserved()
    prior = previous_execution()
    prior_path = ROOT / 'docs/evidence/enterprise/preserved-files.json'
    if args.write:
        PRESERVED.parent.mkdir(parents=True, exist_ok=True)
        PRESERVED.write_text(json.dumps(expected, indent=2) + '\n', encoding='utf-8')
        prior_path.parent.mkdir(parents=True, exist_ok=True)
        prior_path.write_text(json.dumps(prior, indent=2) + '\n', encoding='utf-8')
        MANIFEST.write_text(json.dumps({'boundary': 'SHA-256 of public Git content; existing blob endings preserved',
                                       'sha256': public_files()}, indent=2) + '\n', encoding='utf-8')
    else:
        assert expected == json.loads(PRESERVED.read_text()), 'Preservation manifest differs'
        assert prior == json.loads(prior_path.read_text()), 'Prior execution preservation record differs'
        assert public_files() == json.loads(MANIFEST.read_text())['sha256'], 'Package file/hash mismatch'
    print('Verified', len(expected['files']), 'immutable baseline files and', len(public_files()), 'public files')
    print('Preserved', prior['files'], 'files from merged PR #3')


if __name__ == '__main__':
    main()
