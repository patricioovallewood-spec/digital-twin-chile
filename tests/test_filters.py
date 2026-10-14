"""Browser regression checks. Synthetic fixtures exist only in tests, never in the app.
Run against the checked-out code using a local HTTP server. --live verifies actual
OSM connectivity separately; it does not replace deterministic assertions.
"""
import argparse
import csv
import io
import json
import pathlib
import threading
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect

OUT = pathlib.Path('test-results')
OUT.mkdir(exist_ok=True)
ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = []

class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)
    def log_message(self, *_):
        pass


def fixtures(query):
    # Well inside 400 m, between 400 and 800 m, and between 800 and 1500 m.
    kinds = [
        ('parks', '"leisure"~"^(park|garden|playground)$"', {'leisure': 'park'}),
        ('health', '"amenity"~"^(hospital|clinic|doctors|pharmacy)$"', {'amenity': 'pharmacy'}),
        ('education', '"amenity"~"^(school|university|college|kindergarten)$"', {'amenity': 'school'}),
        ('commerce', '"shop"', {'shop': 'books'}),
        ('sports', '"leisure"~"^(sports_centre|pitch|swimming_pool)$"', {'leisure': 'pitch'}),
        ('culture', '"amenity"~"^(library|community_centre|arts_centre|theatre)$"', {'amenity': 'library'}),
        ('cycling', '"highway"="cycleway"', {'highway': 'cycleway'}),
    ]
    elements = []
    for index, (name, token, tags) in enumerate(kinds):
        if token in query:
            for i, offset in enumerate([0.0005, 0.005, 0.010]):
                elements.append({'type':'node', 'id':index * 100 + i + 1,
                    'lat':-33.4489 + offset, 'lon':-70.6693,
                    'tags':{**tags, 'name':f'TEST ONLY {name} {i}'}})
    return {'elements':elements, 'osm3s':{'timestamp_osm_base':'2026-10-14T00:00:00Z'}}


def settle(page):
    page.wait_for_function("window.DTC && DTC.snapshot().layers.filter(x=>x.active).every(x=>['ready','error'].includes(x.status))", timeout=45000)


def run_mock(browser_type, name):
    browser = browser_type.launch()
    context = browser.new_context(viewport={'width':1440,'height':1000}, accept_downloads=True)
    page = context.new_page()
    errors, calls = [], []
    flags = {'outage':False, 'fallback':False}
    page.on('pageerror', lambda e: errors.append(str(e)))

    def route_api(route):
        request = route.request
        query = parse_qs(urlparse(request.url).query).get('data', [''])[0]
        if not query and request.post_data:
            query = parse_qs(request.post_data).get('data',[''])[0]
        calls.append(request.url)
        if flags['outage'] or (flags['fallback'] and 'private.coffee' in request.url):
            route.fulfill(status=503, content_type='text/plain', body='test outage')
        else:
            route.fulfill(status=200, content_type='application/json', body=json.dumps(fixtures(query)))
    page.route('**/api/interpreter**', route_api)
    # Tests do not download map tiles or send fixture coordinates to third parties.
    page.route('**.tile.openstreetmap.org/**', lambda r:r.abort())
    page.goto('http://127.0.0.1:8765/?layers=parks&lat=-33.4489&lon=-70.6693&z=15&place=santiago&focus=-33.4489,-70.6693&r=800', wait_until='domcontentloaded')
    page.wait_for_function('window.DTC !== undefined', timeout=30000)
    settle(page)
    expect(page.locator('#count')).to_have_text('2')
    assert page.locator('.dtc-record').count() == 2
    for layer in ['health','education','commerce','sports','culture','cycling']:
        page.check('#layer-'+layer)
    settle(page)
    expect(page.locator('#count')).to_have_text('14')
    assert page.locator('.dtc-record').count() == 14
    before = len(calls)
    page.select_option('#radius','400')
    expect(page.locator('#count')).to_have_text('7')
    assert page.locator('.dtc-record').count() == 7
    page.select_option('#radius','1500')
    expect(page.locator('#count')).to_have_text('21')
    assert page.locator('.dtc-record').count() == 21
    assert len(calls) == before, 'Radius changes must reuse loaded records, not reload the API'
    for layer in ['health','education','commerce','sports','culture','cycling']:
        page.uncheck('#layer-'+layer)
    expect(page.locator('#count')).to_have_text('3')
    page.uncheck('#layer-parks')
    expect(page.locator('#count')).to_have_text('0')
    assert page.locator('.dtc-record').count() == 0
    page.check('#layer-health')
    expect(page.locator('#count')).to_have_text('3')
    assert len(calls) == before
    with page.expect_download() as download:
        page.click('#exportCsv')
    rows = list(csv.reader(io.StringIO(pathlib.Path(download.value.path()).read_text(encoding='utf-8-sig'))))
    assert len(rows) == 4 and all('Salud' in r[2] for r in rows[1:])
    page.select_option('#radius','400')
    expect(page.locator('#count')).to_have_text('1')
    page.screenshot(path=str(OUT / f'{name}-filtered.png'), full_page=True)
    # A new territory must not retain an old analysis circle or old points.
    page.select_option('#place','providencia')
    settle(page)
    assert page.evaluate('DTC.snapshot().focus') is None
    expect(page.locator('#count')).to_have_text('0')
    # National scale must display an actionable message rather than silently fail.
    page.select_option('#place','chile')
    expect(page.locator('#filterFeedback')).to_have_attribute('data-state','zoom')
    # All-off, rapid toggles and cancellation must never revive deselected points.
    page.select_option('#place','santiago')
    page.click('#noLayers')
    page.check('#layer-parks')
    page.uncheck('#layer-parks')
    page.wait_for_timeout(1600)
    expect(page.locator('#count')).to_have_text('0')
    # Explicit failures cannot appear as a genuine zero count; recovery is visible.
    flags['outage'] = True
    page.check('#layer-parks')
    page.click('#refresh')
    settle(page)
    expect(page.locator('#status-parks')).to_have_text('Error')
    expect(page.locator('#filterFeedback')).to_have_attribute('data-state','error')
    expect(page.locator('#count')).to_have_text('\u2014')
    flags['outage'] = False
    flags['fallback'] = True
    page.click('#refresh')
    settle(page)
    expect(page.locator('#status-parks')).not_to_have_text('Error')
    assert page.evaluate("DTC.snapshot().layers.find(x=>x.id==='parks').status") == 'ready'
    assert any('overpass-api.de' in x for x in calls), 'Backup endpoint must be used after a 503'
    assert not errors, errors
    REPORT.append({'browser':name,'result':'PASS','checks':['seven categories','visible marker counts','400/800/1500 m radii','no repeated API calls for radius and cached toggles','all off','CSV rows','territory change','national-scale guidance','rapid toggles','outage state','fallback and recovery'],'api_calls_intercepted':len(calls)})
    context.close()
    browser.close()


def run_live(browser_type):
    browser = browser_type.launch()
    page = browser.new_page(viewport={'width':1440,'height':1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8765/?place=providencia&lat=-33.428&lon=-70.612&z=15&layers=parks,health&focus=-33.428,-70.612&r=800', wait_until='domcontentloaded')
    page.wait_for_function('window.DTC !== undefined', timeout=30000)
    settle(page)
    data = page.evaluate('DTC.snapshot()')
    data['notice'] = page.locator('#filterFeedback').inner_text()
    data['errors'] = errors
    data['test_type'] = 'live OSM, not fixtures'
    page.screenshot(path=str(OUT / 'live-providencia.png'), full_page=True)
    pathlib.Path(OUT / 'live.json').write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print('LIVE_RESULT', json.dumps(data,ensure_ascii=False))
    assert not errors, errors
    assert any(x['status']=='ready' and x['count']>0 for x in data['layers'] if x['active']), 'No live records returned by either source'
    before = data['count']
    page.uncheck('#layer-parks')
    after = page.evaluate('DTC.snapshot()')
    assert all('Parques y áreas verdes' not in r['categories'] for r in after['records'])
    REPORT.append({'browser':'chromium','test_type':'live OSM','result':'PASS','before_unchecking_parks':before,'after_unchecking_parks':after['count']})
    browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1',8765),QuietHandler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            if args.live:
                run_live(p.chromium)
            else:
                run_mock(p.chromium,'chromium')
                run_mock(p.webkit,'webkit')
    finally:
        (OUT / ('live-summary.json' if args.live else 'regression.json')).write_text(json.dumps(REPORT,ensure_ascii=False,indent=2))
        print('FILTER_TEST_REPORT',json.dumps(REPORT,ensure_ascii=False))
        server.shutdown()
