"""Acceptance tests use the real public snapshots, never fabricated city records."""
import argparse, csv, io, json, pathlib, hashlib, threading, sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright, expect
ROOT=pathlib.Path(__file__).resolve().parents[1]; OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True)
REPORT=[]
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/'atlas'),**kw)
 def log_message(self,*_):pass

def validate():
 m=json.loads((ROOT/'atlas/data/manifest.json').read_text())
 ready=[d for d in m['datasets'] if d['status']=='ready']
 assert len(ready)>=8, 'At least eight actual data layers required'
 for d in ready:
  b=(ROOT/'atlas'/d['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==d['sha256'],d['id']
  f=json.loads(b)['features'];assert len(f)==d['count'];assert len({x['id'] for x in f})==len(f)
  for x in f:
   p=x['properties'];assert p['layer']==d['id'];assert -180<=p['x']<=180 and -90<=p['y']<=90
 assert next(d for d in ready if d['id']=='health')['count']>0
 REPORT.append({'test':'snapshot integrity','result':'PASS','counts':{d['id']:d['count'] for d in ready}})
 return m

def settle(page):
 page.wait_for_function('window.DTC && DTC.snapshot().loading.length===0',timeout=120000)
 assert not page.evaluate('DTC.snapshot().errors'),page.evaluate('DTC.snapshot()')

def browser_check(engine,name,url,live=False):
 args=['--enable-webgl','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'] if name=='chromium' else []
 browser=engine.launch(args=args)
 ctx=browser.new_context(viewport={'width':1536,'height':1000},accept_downloads=True)
 page=ctx.new_page();errors=[];calls=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:calls.append(r.url) if '.geojson' in r.url else None)
 # UI tests isolate map-provider outages. City data still comes from actual snapshots.
 # This transparent tile is a map-basemap test fixture, not a geographic dataset.
 if not live:
  import base64
  png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==')
  page.route('https://server.arcgisonline.com/**',lambda r:r.fulfill(content_type='image/png',body=png))
 page.goto(url,wait_until='domcontentloaded',timeout=60000)
 settle(page)
 page.wait_for_function('DTC.snapshot().mapReady',timeout=30000)
 page.wait_for_timeout(1800)
 assert page.evaluate('DTC.mapSnapshot().ownLayers.length')>0
 assert page.evaluate('DTC.snapshot().count')>0
 initial=page.evaluate('DTC.snapshot()')
 if live:
  page.screenshot(path=str(OUT/'atlas-live.png'),full_page=True)
  page.click('#closePanel');page.screenshot(path=str(OUT/'atlas-live-map.png'))
  REPORT.append({'test':'deployed live map','result':'PASS','snapshot':initial})
  assert not errors,errors;ctx.close();browser.close();return
 # Preset changes must change data layers, not just button styles.
 page.locator('.presets [data-preset=commerce]').click();settle(page)
 assert set(page.evaluate('DTC.snapshot().active'))<={'boundary','commerce','health'}
 count=page.evaluate('DTC.snapshot().count');assert count>0
 before=len(calls)
 page.uncheck('#layer-commerce');settle(page)
 assert all(x['layer']!='commerce' for x in page.evaluate('DTC.snapshot().records'))
 page.check('#layer-commerce');settle(page)
 assert page.evaluate('DTC.snapshot().count')==count
 assert len(calls)==before,'Toggling loaded categories must not refetch data'
 # Business/radius filters affect both records and counters.
 page.locator('.settings summary').click()
 page.select_option('#business','pharmacy');settle(page)
 pharmacy=page.evaluate('DTC.snapshot()');assert pharmacy['count']>0
 assert all(r['rubro']=='pharmacy' for r in pharmacy['records'])
 page.select_option('#radius','400');small=page.evaluate('DTC.snapshot().count')
 page.select_option('#radius','1500');large=page.evaluate('DTC.snapshot().count')
 assert large>=small
 assert len(calls)==before,'Changing radius/business cannot download datasets again'
 page.select_option('#radius','0')
 page.fill('#search','ZZZ_NO_SUCH_PLACE_998');page.wait_for_timeout(300)
 expect(page.locator('#recordCount')).to_have_text('0')
 page.click('#clearSearch');assert page.evaluate('DTC.snapshot().count')==pharmacy['count']
 with page.expect_download() as item:page.click('#exportCsv')
 rows=list(csv.reader(io.StringIO(pathlib.Path(item.value.path()).read_text(encoding='utf-8-sig'))))
 assert len(rows)==pharmacy['count']+1
 page.click('#noneBtn');expect(page.locator('#recordCount')).to_have_text('0')
 assert not page.evaluate('DTC.snapshot().active')
 assert all(l['visibility']=='none' for l in page.evaluate('DTC.mapSnapshot().ownLayers'))
 page.locator('.presets [data-preset=green]').click();settle(page)
 page.select_option('#visualMode','heat')
 assert page.evaluate('DTC.snapshot().mode')=='heat'
 assert 'No es flujo' in page.locator('#legend').inner_text()
 page.click('#threeBtn');page.wait_for_timeout(800)
 assert not page.evaluate('DTC.snapshot().three')
 assert page.evaluate('DTC.mapSnapshot().pitch')<1
 page.click('#catalogBtn');expect(page.locator('#dialog')).to_be_visible()
 assert 'Flujos peatonales' in page.locator('#dialogBody').inner_text()
 assert 'Pendiente' in page.locator('#dialogBody').inner_text()
 page.click('#closeDialog')
 # No fixture records are used even for screenshots of deterministic UI tests.
 page.screenshot(path=str(OUT/(name+'-filters.png')),full_page=True)
 page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(300)
 assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+2')
 page.screenshot(path=str(OUT/(name+'-mobile.png')),full_page=True)
 assert not errors,errors
 REPORT.append({'test':'filter regression','browser':name,'result':'PASS','initial_count':initial['count'],'business_count':count,'pharmacies':pharmacy['count'],'radius_400':small,'radius_1500':large,'checks':['rendered map','presets','category off/on','zero state','radius','business','search','CSV parity','no extra requests','heat mode','3D toggle','sources','mobile layout']})
 ctx.close();browser.close()

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--live-url');parser.add_argument('--chromium-only',action='store_true');args=parser.parse_args()
 server=None
 try:
  if not args.live_url:
   validate();server=ThreadingHTTPServer(('127.0.0.1',8766),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
  with sync_playwright() as p:
   browser_check(p.chromium,'chromium',args.live_url or 'http://127.0.0.1:8766/',bool(args.live_url))
   if not args.live_url and not args.chromium_only:browser_check(p.webkit,'webkit','http://127.0.0.1:8766/')
 finally:
  (OUT/'atlas-report.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2))
  print('ATLAS_REPORT',json.dumps(REPORT,ensure_ascii=False))
  if server:server.shutdown()
