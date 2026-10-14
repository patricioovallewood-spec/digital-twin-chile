"""UI regression fixtures are TEST ONLY. --live never uses synthetic records."""
import argparse
import csv
import io
import json
import pathlib
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect

OUT=pathlib.Path('test-results'); OUT.mkdir(exist_ok=True)
ROOT=pathlib.Path(__file__).resolve().parents[1]
REPORT=[]

class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
    def log_message(self,*_): pass


def fixtures(query):
    kinds=[
        ('parks','"leisure"~"^(park|garden|playground)$"',{'leisure':'park'}),
        ('health','"amenity"~"^(hospital|clinic|doctors|pharmacy)$"',{'amenity':'pharmacy'}),
        ('education','"amenity"~"^(school|university|college|kindergarten)$"',{'amenity':'school'}),
        ('commerce','"shop"',{'shop':'books'}),
        ('sports','"leisure"~"^(sports_centre|pitch|swimming_pool)$"',{'leisure':'pitch'}),
        ('culture','"amenity"~"^(library|community_centre|arts_centre|theatre)$"',{'amenity':'library'}),
        ('cycling','"highway"="cycleway"',{'highway':'cycleway'})]
    elements=[]
    for k,(name,token,tags) in enumerate(kinds):
        if token in query:
            for i,dy in enumerate([0.0005,0.005,0.010]):
                elements.append({'type':'node','id':k*100+i+1,'lat':-33.4489+dy,'lon':-70.6693,'tags':{**tags,'name':f'TEST ONLY {name} {i}'}})
    return {'elements':elements,'osm3s':{'timestamp_osm_base':'2026-10-14T00:00:00Z'}}


def settle(page):
    page.wait_for_function("window.DTC && DTC.snapshot().layers.filter(x=>x.active).every(x=>['ready','error'].includes(x.status))",timeout=70000)


def block_tiles(page):
    # OSM prohibits automated panning/zooming to download tiles. Test data/UI only.
    page.route('**/*tile.openstreetmap.org/**',lambda route:route.abort())


def run_mock(browser_type,name):
    browser=browser_type.launch()
    context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
    page=context.new_page(); errors=[]; calls=[]
    flags={'outage':False,'fallback':False}
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async(text)=>{window._shared=text;}}});")
    def route_api(route):
        r=route.request
        query=parse_qs(urlparse(r.url).query).get('data',[''])[0]
        if not query and r.post_data: query=parse_qs(r.post_data).get('data',[''])[0]
        calls.append(r.url)
        if flags['outage'] or (flags['fallback'] and 'private.coffee' in r.url):
            route.fulfill(status=503,content_type='text/plain',body='TEST outage')
        else:
            route.fulfill(status=200,content_type='application/json',body=json.dumps(fixtures(query)))
    page.route('**/api/interpreter**',route_api); block_tiles(page)
    try:
        page.goto('http://127.0.0.1:8765/?layers=parks&lat=-33.4489&lon=-70.6693&z=15&place=santiago&focus=-33.4489,-70.6693&r=800',wait_until='domcontentloaded')
        page.wait_for_function('window.DTC !== undefined',timeout=30000)
        settle(page); expect(page.locator('#count')).to_have_text('2')
        assert page.locator('.dtc-record').count()==2
        for layer in ['health','education','commerce','sports','culture','cycling']: page.check('#layer-'+layer)
        settle(page); expect(page.locator('#count')).to_have_text('14')
        assert page.locator('.dtc-record').count()==14
        before=len(calls)
        page.select_option('#radius','400'); expect(page.locator('#count')).to_have_text('7')
        assert page.locator('.dtc-record').count()==7
        page.select_option('#radius','1500'); expect(page.locator('#count')).to_have_text('21')
        assert page.locator('.dtc-record').count()==21
        assert len(calls)==before,'Radius must reuse the same records'
        for layer in ['health','education','commerce','sports','culture','cycling']: page.uncheck('#layer-'+layer)
        expect(page.locator('#count')).to_have_text('3')
        page.uncheck('#layer-parks'); expect(page.locator('#count')).to_have_text('0')
        assert page.locator('.dtc-record').count()==0
        page.check('#layer-health'); expect(page.locator('#count')).to_have_text('3')
        assert len(calls)==before,'Cached toggles must not hit the API'
        with page.expect_download() as download: page.click('#exportCsv')
        rows=list(csv.reader(io.StringIO(pathlib.Path(download.value.path()).read_text(encoding='utf-8-sig'))))
        assert len(rows)==4 and all('Salud' in r[2] for r in rows[1:])
        page.select_option('#radius','400'); expect(page.locator('#count')).to_have_text('1')
        page.screenshot(path=str(OUT/f'{name}-filtered.png'),full_page=True)
        page.click('#shareView'); shared=page.evaluate('window._shared')
        assert parse_qs(urlparse(shared).query)['layers']==['health']
        page.goto(shared,wait_until='domcontentloaded'); settle(page)
        expect(page.locator('#count')).to_have_text('1')
        assert page.evaluate('DTC.snapshot().radius')==400
        page.select_option('#place','providencia'); settle(page)
        assert page.evaluate('DTC.snapshot().focus') is None
        expect(page.locator('#count')).to_have_text('0')
        page.select_option('#place','chile')
        expect(page.locator('#filterFeedback')).to_have_attribute('data-state','zoom')
        page.select_option('#place','santiago'); page.click('#noLayers')
        page.check('#layer-parks'); page.uncheck('#layer-parks'); page.wait_for_timeout(1600)
        expect(page.locator('#count')).to_have_text('0')
        flags['outage']=True
        page.check('#layer-parks'); page.click('#refresh'); settle(page)
        expect(page.locator('#status-parks')).to_have_text('Error')
        expect(page.locator('#filterFeedback')).to_have_attribute('data-state','error')
        expect(page.locator('#count')).to_have_text('\u2014')
        flags['outage']=False; flags['fallback']=True
        page.click('#refresh'); settle(page)
        assert page.evaluate("DTC.snapshot().layers.find(x=>x.id==='parks').status")=='ready'
        assert any('overpass-api.de' in x for x in calls),'Backup not attempted'
        page.select_option('#radius','800'); settle(page)
        expect(page.locator('#count')).to_have_text('2')
        assert page.evaluate('DTC.snapshot().focus') is not None
        # Mobile responsive controls retain their behavior.
        page.set_viewport_size({'width':390,'height':844})
        page.uncheck('#layer-parks'); expect(page.locator('#count')).to_have_text('0')
        page.check('#layer-parks'); expect(page.locator('#count')).to_have_text('2')
        page.screenshot(path=str(OUT/f'{name}-mobile.png'),full_page=True)
        assert not errors,errors
        REPORT.append({'browser':name,'result':'PASS','checks':['seven categories','visible marker counts','400/800/1500 m radii','cached toggles and radii','all-off','CSV','shared view restoration','territory change','national zoom guidance','rapid toggles','outage state','fallback recovery','radius without prior point','mobile controls'],'intercepted_requests':len(calls)})
    except Exception:
        page.screenshot(path=str(OUT/f'{name}-failure.png'),full_page=True)
        print('FAILED_STATE',page.evaluate('window.DTC ? DTC.snapshot() : null'))
        raise
    finally:
        context.close(); browser.close()


def run_live(browser_type,base_url):
    browser=browser_type.launch(); page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]; page.on('pageerror',lambda e:errors.append(str(e))); block_tiles(page)
    url=base_url+'?v=0.3.1&place=providencia&lat=-33.428&lon=-70.612&z=15&layers=parks,health&focus=-33.428,-70.612&r=800'
    try:
        page.goto(url,wait_until='domcontentloaded')
        page.wait_for_function("window.DTC && DTC.version==='0.3.1'",timeout=45000)
        settle(page)
        data=page.evaluate('DTC.snapshot()'); data['notice']=page.locator('#filterFeedback').inner_text(); data['errors']=errors
        data['test_type']='live OSM, no fixtures'; data['url']=url
        (OUT/'live.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
        print('LIVE_RESULT',json.dumps(data,ensure_ascii=False))
        page.screenshot(path=str(OUT/'live-providencia.png'),full_page=True)
        assert not errors,errors
        assert any(x['status']=='ready' and x['count']>0 for x in data['layers'] if x['active']),'No live source records returned'
        before=data['count']; page.uncheck('#layer-parks'); after=page.evaluate('DTC.snapshot()')
        assert all('Parques y áreas verdes' not in r['categories'] for r in after['records'])
        REPORT.append({'browser':'chromium','test_type':'live OSM','result':'PASS','before':before,'after_unchecking_parks':after['count'],'url':base_url})
    finally: browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--live',action='store_true'); parser.add_argument('--url',default='http://127.0.0.1:8765/')
    args=parser.parse_args(); server=ThreadingHTTPServer(('127.0.0.1',8765),QuietHandler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            if args.live: run_live(p.chromium,args.url)
            else:
                run_mock(p.chromium,'chromium')
                run_mock(p.webkit,'webkit')
    finally:
        (OUT/('live-summary.json' if args.live else 'regression.json')).write_text(json.dumps(REPORT,ensure_ascii=False,indent=2))
        print('FILTER_TEST_REPORT',json.dumps(REPORT,ensure_ascii=False)); server.shutdown()
