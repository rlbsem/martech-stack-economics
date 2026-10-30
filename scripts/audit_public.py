"""Public delivery checks: local Markdown targets and obvious credential/file leaks."""
import argparse
import gzip
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def check():
    names = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    paths = [ROOT/name for name in sorted(set(names)) if (ROOT/name).is_file()]
    forbidden = ('.local/', '.venv/', 'work/', '.aws/', '.env')
    secrets = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?:AKIA|ASIA)[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{30,}')
    links = 0
    for path in paths:
        relative=path.relative_to(ROOT).as_posix()
        assert not relative.startswith(forbidden), 'Private path in package: '+relative
        assert path.suffix not in {'.sqlite','.db','.pem','.key','.log'}, 'Runtime/private artifact: '+relative
        raw=path.read_bytes()
        if path.name.endswith('.json.gz'):
            raw=gzip.decompress(raw)
        try:
            text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            continue
        assert not secrets.search(text), 'Credential-shaped content: '+relative
        if path.suffix != '.md':
            continue
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',text):
            target=target.strip().split(' "',1)[0].strip('<>')
            if urlsplit(target).scheme or target.startswith('#'):
                continue
            destination=(path.parent/unquote(target.split('#',1)[0])).resolve()
            assert destination.is_relative_to(ROOT), 'Link leaves repository: '+relative
            assert destination.exists(), 'Missing target: '+relative+' -> '+target
            links+=1
    return {'files_checked':len(paths),'relative_markdown_links':links,'credential_patterns_found':0,
            'boundary':'Heuristic credential scan and repository-local Markdown target checks; not a formal security audit'}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=check()
    if args.output:
        args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
