"""Genuine rendered console checks, screenshots, downloads and axe WCAG checks."""
import argparse
import hashlib
import json
import subprocess
import threading
from pathlib import Path

from fetch_browser_tools import AXE_SHA256
from playwright.sync_api import sync_playwright

from stack_economics.assurance.console import console


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--axe', type=Path, default=Path('.local/axe.min.js'))
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Screenshot record must use a fresh directory')
    args.output.mkdir(parents=True)
    assert hashlib.sha256(args.axe.read_bytes()).hexdigest() == AXE_SHA256
    summary_path = args.evidence / 'summary.json'
    summary = json.loads(summary_path.read_text())
    server = console(args.evidence)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}'
    observations, errors, captures = [], [], {}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            version = browser.version
            for size, viewport in [('desktop', {'width': 1440, 'height': 1050}),
                                   ('mobile', {'width': 390, 'height': 844})]:
                page = browser.new_page(viewport=viewport, reduced_motion='reduce')
                page.on('pageerror', lambda error: errors.append(str(error)))
                response = page.goto(url)
                assert response.status == 200
                assert "frame-ancestors 'none'" in response.headers['content-security-policy']
                page.locator('#content').wait_for(state='visible')
                assert page.locator('#trial option').count() == len(summary['trials'])
                for trial in summary['trials']:
                    page.select_option('#trial', trial['name'])
                    if not trial.get('blocked'):
                        expected = 'Acceptable under this finite trial' if trial['result']['acceptable'] else 'Revision required'
                        assert page.locator('#outcome').inner_text() == expected
                        assert page.locator('#workflows tr').count() == 5
                        with page.expect_download() as download:
                            page.locator('#download').click()
                        raw = Path(download.value.path()).read_bytes()
                        original = (args.evidence / trial['name'] / 'observations.json.gz').read_bytes()
                        assert raw == original, 'Downloaded evidence differs'
                    else:
                        assert page.locator('#outcome').inner_text() == 'Blocked · no execution'
                        assert not page.locator('#download').is_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), page.evaluate(
                        "Array.from(document.querySelectorAll('*')).filter(e=>e.getBoundingClientRect().right>innerWidth)"
                        ".map(e=>e.tagName+':'+e.className)")
                    page.evaluate(args.axe.read_text(encoding='utf-8'))  # DevTools evaluation; application CSP stays strict.
                    axe = page.evaluate("async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
                    assert not axe['violations'], [(v['id'], v['nodes']) for v in axe['violations']]
                    observations.append({'viewport': size, 'trial': trial['name'], 'violations': 0,
                                         'state': 'collapsed', 'axe_passes': len(axe['passes']), 'download_verified': not trial.get('blocked', False)})
                    for item in page.locator('details').all():
                        item.locator('summary').click()
                    expanded = page.evaluate("async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
                    assert not expanded['violations'], [(v['id'], v['nodes']) for v in expanded['violations']]
                    observations.append({'viewport': size, 'trial': trial['name'], 'state': 'expanded',
                                         'violations': 0, 'axe_passes': len(expanded['passes'])})
                    for item in page.locator('details').all():
                        item.locator('summary').click()
                    if (size == 'desktop' and trial['name'] in ('normal', 'launch-surge', 'shared-quota-pressure', 'capacity-revision')
                            or size == 'mobile' and trial['name'] in ('normal', 'capacity-blocked')):
                        path = args.output / f"{trial['name']}-{size}.png"
                        page.evaluate('window.scrollTo(0,0); document.activeElement.blur()')
                        page.screenshot(path=str(path), full_page=True, animations='disabled')
                        captures[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                page.select_option('#trial', summary['trials'][0]['name'])
                page.get_by_text('Decision, source revision and evidence hashes', exact=True).click()
                assert page.locator('#provenance').is_visible()
                assert summary['source_commit'] in page.locator('#provenance').inner_text()
                page.keyboard.press('Tab')
                assert page.evaluate('document.activeElement.tagName') in ('SUMMARY', 'A', 'SELECT', 'PRE')
                assert page.request.post(url + '/api/summary', data='{}').status == 501
                assert page.request.get(url + '/api/summary', headers={'Origin': 'https://example.invalid'}).status == 403
                assert page.request.get(url + '/api/summary', headers={'Host': 'example.invalid'}).status == 403
                assert page.request.get(url + '/.local/credentials').status == 404
                page.close()
            browser.close()
        assert not errors, errors
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    ui_root = Path(__file__).resolve().parents[1] / 'src/stack_economics/assurance/web'
    ui_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    record = {'ui_source_commit': ui_commit,
              'ui_files_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ui_root.iterdir()) if p.is_file()},
              'source_commit': summary['source_commit'], 'summary_sha256': hashlib.sha256(summary_path.read_bytes()).hexdigest(),
              'chromium': version, 'axe_version': '4.11.0', 'axe_sha256': AXE_SHA256,
              'states': observations, 'page_errors': errors, 'screenshots_sha256': captures,
              'boundary': 'Actual loopback UI, recorded synthetic HTTP trials; no deployment or vendor execution'}
    (args.output / 'browser-verification.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print('Verified', len(observations), 'rendered desktop/mobile states and', len(captures), 'genuine screenshots')


if __name__ == '__main__':
    main()
