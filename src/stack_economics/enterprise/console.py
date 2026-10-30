"""Additive annual decision view; preserved read-only execution console remains at /execution."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from stack_economics.assurance.console import console as execution_console
from stack_economics.contracts import digest


def console(enterprise, execution, port=0):
    enterprise = Path(enterprise)
    raw = (enterprise / 'decision.json').read_bytes()
    data = json.loads(raw)
    verification = json.loads((enterprise / 'verification.json').read_text())
    assert verification['verification_passed'] is True
    assert digest(data) == verification['decision_sha256'], 'Enterprise decision integrity mismatch'
    server = execution_console(execution, port)
    base = server.RequestHandlerClass
    assets = Path(__file__).parent / 'web'

    class Handler(base):
        def do_GET(self):
            path = urlparse(self.path).path
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in allowed or (self.headers.get('Origin') and
                    self.headers['Origin'] not in {'http://' + h for h in allowed}):
                self.send_error(403)
                return
            if path == '/execution':
                self.path = '/'
                super().do_GET()
                return
            files = {'/': ('index.html', 'text/html; charset=utf-8'),
                     '/enterprise.css': ('style.css', 'text/css'), '/enterprise.js': ('app.js', 'text/javascript')}
            download = False
            if path in files:
                name, mime = files[path]
                body = (assets / name).read_bytes()
            elif path == '/api/enterprise':
                body = json.dumps({'decision': data, 'verification': verification,
                                   'download_sha256': hashlib.sha256(raw).hexdigest()}).encode()
                mime = 'application/json'
            elif path == '/enterprise/decision.json':
                body, mime, download = raw, 'application/json', True
            else:
                super().do_GET()
                return
            self.send_response(200)
            for name, value in {'Content-Type': mime, 'Content-Length': str(len(body)), 'Cache-Control': 'no-store',
                                'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
                                'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; "
                                "connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"}.items():
                self.send_header(name, value)
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="enterprise-decision.json"')
            self.end_headers()
            self.wfile.write(body)

    server.RequestHandlerClass = Handler
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--enterprise', type=Path, default=Path('docs/evidence/enterprise/acceptance'))
    parser.add_argument('--execution', type=Path, default=Path('docs/evidence/execution/acceptance/execution'))
    parser.add_argument('--port', type=int, default=8578)
    args = parser.parse_args()
    server = console(args.enterprise, args.execution, args.port)
    print(f'Read-only enterprise console: http://127.0.0.1:{server.server_port}/', flush=True)
    server.serve_forever()
