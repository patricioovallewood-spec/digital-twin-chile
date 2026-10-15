"""Validate the actual prototype interactions and the separation of synthetic data."""
import argparse,csv,io,json,pathlib,threading
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright,expect
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True);REPORT=[]
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/'atlas'),**kw)
 def log_message(self,*a):pass
def settle(page):
 page.wait_for_function('window.DTC && DTC.snapshot().loading.length===0',timeout=120000)
 assert not page.evaluate('DTC.snapshot().errors'),page.evaluate('DTC.snapshot()')
def browser(engine,name,url):
 args=['--enable-webgl','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'] if name=='chromium' else []
 browser=engine.launch(args=args);ctx=browser.new_context(viewport={'width':1536,'height':1000},accept_downloads=True)
 page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 import base64
 png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==')
 page.route('https://server.arcgisonline.com/**',lambda route:route.fulfill(content_type='image/png',body=png))
 page.goto(url,wait_until='domcontentloaded',timeout=60000);settle(page)
 page.wait_for_function('DTC.snapshot().mapReady',timeout=30000)
 assert page.evaluate('DTC.version')=='0.6.0'
 assert page.evaluate('DTC.snapshot().demoCount')==0
 expect(page.locator('#demoNotice')).to_be_hidden()
 # Thematic cross-selection: current records must feed every indicator.
 page.locator('[data-mission=business]').click();settle(page)
 assert page.evaluate('DTC.snapshot().radius')==800
 assert page.evaluate('DTC.snapshot().selectionMode')=='area'
 summary=page.evaluate('DTC.analysisSnapshot()');count=page.evaluate('DTC.snapshot().counts.commerce')
 assert summary['commerce']==count and summary['population'] is not None
 page.click('#saveZone');page.select_option('#quickRadius','1500');settle(page)
 bigger=page.evaluate('DTC.analysisSnapshot()');assert bigger['commerce']>=count
 page.click('#compareZone');expect(page.locator('#comparisonTable')).to_be_visible();page.click('#closeDialog')
 page.click('#summaryBtn');expect(page.locator('#analysisMetrics [data-metric=population]')).to_be_visible()
 with page.expect_download() as item:page.click('#analysisExport')
 exported=json.loads(pathlib.Path(item.value.path()).read_text());assert exported['summary']['commerce']==bigger['commerce']
 page.click('#closeDialog')
 # Explicit area mode changes center even when the click lands on a feature.
 before=page.evaluate('DTC.snapshot().focus')
 page.locator('#map').click(position={'x':690,'y':300});settle(page)
 after=page.evaluate('DTC.snapshot().focus');assert before!=after
 # Spatial reset and street grouping of actual OSM records, not fabricated segments.
 page.select_option('#quickRadius','0');page.click('#streetsNav');expect(page.locator('#streetTable')).to_be_visible()
 groups=page.evaluate('DTC.streetSnapshot()');assert groups['total']==1059
 assert groups['withoutStreet']==294 and groups['rows']
 with page.expect_download() as item:page.click('#streetExport')
 rows=list(csv.DictReader(io.StringIO(pathlib.Path(item.value.path()).read_text(encoding='utf-8-sig'))));assert sum(int(r['establecimientos']) for r in rows)==groups['total']
 page.locator('[data-street-index="0"]').click();settle(page)
 assert page.evaluate('DTC.snapshot().street')==groups['rows'][0]['name']
 assert page.evaluate('DTC.snapshot().counts.commerce')==groups['rows'][0]['count']
 with page.expect_download() as item:page.click('#exportCsv')
 rows=list(csv.DictReader(io.StringIO(pathlib.Path(item.value.path()).read_text(encoding='utf-8-sig'))));assert len(rows)==page.evaluate('DTC.snapshot().count')
 street_rows=[r for r in rows if r['capa']=='Comercios y gastronomía']
 assert len(street_rows)==groups['rows'][0]['count']
 assert all(r['calle']==groups['rows'][0]['name'] for r in street_rows)
 # Metric changes without replacing the source, observed map style is checked.
 page.locator('.rail [data-preset=people]').click();settle(page)
 page.locator('.settings summary').click();page.select_option('#censusMetric','density')
 assert page.evaluate('DTC.snapshot().censusMetric')=='density'
 assert 'hab/ha' in page.locator('#legend').inner_text()
 page.screenshot(path=str(OUT/(name+'-density-v06.png')),full_page=True)
 # Optional DEMO layers have explicit evidence flags in the map, catalog and exports.
 page.locator('.rail [data-preset=scenario]').click();settle(page)
 assert page.evaluate('DTC.snapshot().demoCount')==10
 expect(page.locator('#demoNotice')).to_be_visible()
 with page.expect_download() as item:page.click('#exportCsv')
 rows=list(csv.DictReader(io.StringIO(pathlib.Path(item.value.path()).read_text(encoding='utf-8-sig'))))
 assert sum(r['tipo_de_evidencia']=='DEMO SINTÉTICA' for r in rows)==10
 page.screenshot(path=str(OUT/(name+'-demo-v06.png')),full_page=True)
 page.click('#allBtn');settle(page);assert page.evaluate('DTC.snapshot().demoCount')==0
 expect(page.locator('#demoNotice')).to_be_hidden()
 page.click('#integrationNav');expect(page.locator('.integration-flow')).to_be_visible()
 assert 'sin conexión' in page.locator('#dialogBody').inner_text()
 assert page.locator('a[download="contrato-integracion-municipal.json"]').count()==1
 page.click('#closeDialog');page.locator('.rail [data-preset=overview]').click();settle(page)
 page.click('#closePanel');page.screenshot(path=str(OUT/(name+'-workspace-v06.png')),full_page=True)
 page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(350)
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
 page.click('#summaryBtn');expect(page.locator('#analysisMetrics')).to_be_visible()
 page.screenshot(path=str(OUT/(name+'-mobile-analysis-v06.png')),full_page=True)
 assert not errors,errors
 REPORT.append({'test':'municipal prototype','browser':name,'result':'PASS','streets':len(groups['rows']),'no_street':groups['withoutStreet'],'checks':['cross-layer indicators','zone comparison','area click','street grouping','CSV parity','density metric','demo separation','integration contract','mobile']})
 ctx.close();browser.close()
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--url');parser.add_argument('--chromium-only',action='store_true');args=parser.parse_args();server=None
 try:
  if not args.url:
   server=ThreadingHTTPServer(('127.0.0.1',8768),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
  with sync_playwright() as p:
   browser(p.chromium,'chromium',args.url or 'http://127.0.0.1:8768/')
   if not args.chromium_only:browser(p.webkit,'webkit',args.url or 'http://127.0.0.1:8768/')
 finally:
  (OUT/'prototype-acceptance.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2));print('PROTOTYPE_ACCEPTANCE',json.dumps(REPORT,ensure_ascii=False))
  if server:server.shutdown()
