"""Actual desktop/mobile enterprise console, exact downloads, a11y and preserved execution view."""
import argparse
import hashlib
import json
import subprocess
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

from fetch_browser_tools import AXE_SHA256
from stack_economics.enterprise.console import console


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--enterprise', type=Path, required=True)
    parser.add_argument('--execution', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--axe', type=Path, default=Path('.local/axe.min.js'))
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve prior screenshots; choose a fresh output directory')
    args.output.mkdir(parents=True)
    assert hashlib.sha256(args.axe.read_bytes()).hexdigest() == AXE_SHA256
    decision_path = args.enterprise / 'decision.json'
    decision = json.loads(decision_path.read_text())
    server = console(args.enterprise, args.execution)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    states, captures, errors = [], {}, []
    address = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            version = browser.version
            for label, viewport in [('desktop', {'width': 1440, 'height': 1050}),
                                    ('mobile', {'width': 390, 'height': 844})]:
                page = browser.new_page(viewport=viewport, reduced_motion='reduce')
                page.on('pageerror', lambda exc: errors.append(str(exc)))
                response = page.goto(address)
                assert response.status == 200
                assert "form-action 'none'" in response.headers['content-security-policy']
                page.locator('#content').wait_for(state='visible')
                assert page.locator('#source').inner_text() == '1,200,000,000'
                assert page.locator('#records').inner_text() == '1,332,000,000'
                assert page.locator('#comparison tr').count() == 3
                for architecture in ('reference', 'optimized', 'resilient'):
                    page.select_option('#architecture', architecture)
                    for condition in ('operating', 'campaign-disruption'):
                        page.select_option('#condition', condition)
                        for month in ('2026-01', '2026-11'):
                            page.select_option('#month', month)
                            expected = next(m for c in decision['alternatives'][architecture]['assessment']['conditions']
                                            if c['id'] == condition for m in c['months'] if m['id'] == month)
                            assert page.locator('#monthly').inner_text() == f"${expected['cost_cents']/100:,.2f}"
                            assert page.locator('#routes tr').count() == 8
                            assert json.loads(page.locator('#month-record').text_content())['month'] == expected
                            for expanded in (False, True):
                                page.locator('details').evaluate_all('(items,open)=>items.forEach(i=>i.open=open)', expanded)
                                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal page overflow'
                                page.evaluate(args.axe.read_text(encoding='utf-8'))
                                result = page.evaluate("async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
                                assert not result['violations'], [(v['id'], v['nodes']) for v in result['violations']]
                                states.append({'viewport': label, 'architecture': architecture, 'condition': condition,
                                               'month': month, 'expanded': expanded, 'axe_violations': 0})
                            page.locator('details').evaluate_all('(items)=>items.forEach(i=>i.open=false)')
                            if month == '2026-11' and ((architecture == 'optimized' and condition == 'operating')
                                    or label == 'desktop' and architecture == 'resilient' and condition == 'campaign-disruption'):
                                filename = f'{architecture}-{condition}-{label}.png'
                                page.evaluate('scrollTo(0,0);document.activeElement.blur()')
                                page.screenshot(path=str(args.output / filename), full_page=True, animations='disabled')
                                captures[filename] = hashlib.sha256((args.output / filename).read_bytes()).hexdigest()
                for dimension in {r['dimension'] for r in decision['sensitivity']}:
                    page.select_option('#sensitivity', dimension)
                    assert page.locator('#sensitivity-results tr').count() == sum(
                        r['dimension'] == dimension for r in decision['sensitivity'])
                with page.expect_download() as download:
                    page.locator('#download').click()
                assert Path(download.value.path()).read_bytes() == decision_path.read_bytes()
                page.keyboard.press('Tab')
                assert page.evaluate('document.activeElement.tagName') in ('SUMMARY', 'A', 'SELECT', 'PRE')
                for endpoint in ('/api/enterprise', '/enterprise/decision.json', '/'):
                    assert page.request.get(address + endpoint, headers={'Origin': 'https://example.invalid'}).status == 403
                    assert page.request.get(address + endpoint, headers={'Host': 'example.invalid'}).status == 403
                    assert page.request.post(address + endpoint, data='{}').status == 501
                assert page.request.get(address + '/.local/private').status == 404
                page.goto(address + '/execution')
                page.locator('#trial').wait_for()
                assert page.locator('#trial option').count() == 9
                page.close()
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    root = Path(__file__).resolve().parents[1]
    ui = root / 'src/stack_economics/enterprise/web'
    record = {'ui_source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'ui_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ui.iterdir())},
              'decision_sha256': hashlib.sha256(decision_path.read_bytes()).hexdigest(),
              'evidence_source_commit': json.loads((args.enterprise / 'verification.json').read_text())['source_commit'],
              'chromium': version, 'axe_version': '4.11.0', 'axe_sha256': AXE_SHA256,
              'states': states, 'screenshots_sha256': captures, 'page_errors': errors,
              'boundary': 'Actual rendered read-only local console; all enterprise financial values are modeled.'}
    (args.output / 'browser-verification.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print('Verified', len(states), 'enterprise browser/a11y states and', len(captures), 'genuine screenshots')


if __name__ == '__main__':
    main()
