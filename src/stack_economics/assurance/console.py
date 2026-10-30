"""Read-only, loopback-only inspection of a completed finite evidence package."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


def console(output, port=0):
    output = Path(output).resolve()
    summary = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
    downloads = {'/evidence/' + t['name']: output / t['name'] / 'observations.json.gz'
                 for t in summary['trials'] if not t.get('blocked')}
    assets = Path(__file__).parent / 'web'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.headers.get('Host') not in {f'127.0.0.1:{self.server.server_port}',
                                               f'localhost:{self.server.server_port}'}:
                self.send_error(403)
                return
            origin = self.headers.get('Origin')
            if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',
                                         f'http://localhost:{self.server.server_port}'}:
                self.send_error(403)
                return
            path = urlparse(self.path).path
            attachment = False
            if path == '/api/summary':
                body, mime = json.dumps(summary).encode(), 'application/json'
            elif path in downloads:
                body, mime, attachment = downloads[path].read_bytes(), 'application/gzip', True
            elif path in ('/', '/style.css', '/app.js'):
                filename = 'index.html' if path == '/' else path[1:]
                body = (assets / filename).read_bytes()
                mime = {'index.html': 'text/html; charset=utf-8', 'style.css': 'text/css',
                        'app.js': 'text/javascript'}[filename]
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            if attachment:
                self.send_header('Content-Disposition', 'attachment; filename="observations.json.gz"')
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--port', type=int, default=8578)
    args = parser.parse_args()
    server = console(args.evidence, args.port)
    print(f'Read-only evidence console: http://127.0.0.1:{server.server_port}/', flush=True)
    server.serve_forever()
