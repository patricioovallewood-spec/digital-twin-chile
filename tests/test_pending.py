"""Acceptance for v0.5, using actual prepared public data (no fabricated records)."""
import argparse,csv,hashlib,io,json,pathlib,threading
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright,expect
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True);REPORT=[]
M=json.loads((ROOT/'atlas/data/manifest.json').read_text());D={x['id']:x for x in M['datasets']}
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**k):super().__init__(*a,directory=str(ROOT/'atlas'),**k)
 def log_message(self,*a):pass

def data(id):
 raw=(ROOT/'atlas'/D[id]['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==D[id]['sha256'];return json.loads(raw)

def validate():
 assert M['version']=='0.5.0'
 for id in ['births','crime']:
  d=data(id);assert D[id]['status']=='tabular' and d['type']=='IndicatorTable'
  assert len(d['rows'])==D[id]['count'] and len({x['id'] for x in d['rows']})==len(d['rows'])
  assert all('geometry' not in x and 'x' not in x and x['source_url'].startswith('https://www.bcn.cl/') for x in d['rows'])
  assert all(isinstance(x['value'],(int,float)) and x['value']>=0 for x in d['rows'])
 assert len(data('crime')['rows'])==18 and {x['year'] for x in data('crime')['rows']}=={2023,2024,2025}
 assert {x['indicator'] for x in data('crime')['rows']}=={'integridad_personas','vif'}
 assert all('DMCS' not in x['label'] for x in data('crime')['rows'])
 assert D['zoning']['status']=='reference' and len(data('zoning')['documents'])==D['zoning']['count']
 for id in ['licenses','municipal','pedestrians']:assert D[id]['status']=='requires_access'
 projects=data('projects')['features'];assert len(projects)==D['projects']['count'] and len({f['id'] for f in projects})==len(projects)
 for f in projects:
  assert f['properties']['project_state'] and f['properties']['layer']=='projects'
  assert all(k not in f['properties'] for k in ['TITULAR','USUARIO','RUT','nombre_persona'])
 if D['heat']['status']=='ready':
  for f in data('heat')['features']:
   p=f['properties'];assert -80<p['temp_c']<90 and p['valid_fraction']>=.75 and p['valid_pixels']>=5
   assert 0<=p['uncertainty_mean_k']<=3.0
   assert p['cell_m']==150 and p['native_thermal_m']==100 and p['surface_date'][:10]<='2026-10-14'
 REPORT.append({'test':'new source integrity','result':'PASS','states':{k:{'status':D[k]['status'],'count':D[k].get('count')} for k in ['births','crime','projects','heat','zoning','licenses','pedestrians','municipal']}})

def settle(page):
 page.wait_for_function('window.DTC && DTC.snapshot().loading.length===0',timeout=100000)
 assert not page.evaluate('DTC.snapshot().errors')

def browser(engine,name,url):
 args=['--enable-webgl','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'] if name=='chromium' else []
 b=engine.launch(args=args);context=b.new_context(viewport={'width':1536,'height':1000},accept_downloads=True);page=context.new_page();errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 import base64
 png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==')
 page.route('https://server.arcgisonline.com/**',lambda r:r.fulfill(content_type='image/png',body=png))
 page.goto(url,wait_until='domcontentloaded');settle(page)
 assert page.evaluate('DTC.version')=='0.5.0'
 initial=page.evaluate('DTC.snapshot().count');page.click('#indicatorsNav')
 expect(page.locator('#indicatorTable')).to_be_visible(timeout=20000)
 page.select_option('#indicatorYear','2023');expect(page.locator('#indicatorTable tbody tr')).to_have_count(3)
 assert '7,72' in page.locator('#indicatorTable').inner_text()
 assert page.evaluate('DTC.snapshot().count')==initial
 with page.expect_download() as item:page.click('#indicatorExport')
 rows=list(csv.reader(io.StringIO(pathlib.Path(item.value.path()).read_text(encoding='utf-8-sig'))));assert len(rows)==4
 page.click('#closeDialog');page.click('#securityNav');expect(page.locator('#indicatorTable')).to_be_visible(timeout=20000)
 page.select_option('#indicatorChoice','vif');page.select_option('#indicatorYear','2025')
 expect(page.locator('#indicatorTable tbody tr')).to_have_count(3);assert '328,6' in page.locator('#indicatorTable').inner_text()
 page.screenshot(path=str(OUT/(name+'-security-v05.png')),full_page=True)
 page.click('#closeDialog');page.click('#zoningNav');expect(page.locator('.document-list article')).to_have_count(D['zoning']['count'],timeout=20000)
 assert 'no zonificación predial' in page.locator('#dialogBody').inner_text()
 page.click('#closeDialog');page.click('#integrationNav');expect(page.locator('.evidence-card')).to_have_count(3)
 page.click('#closeDialog');page.locator('.rail [data-preset=projects]').click();settle(page)
 assert page.evaluate('DTC.snapshot().counts.projects')==D['projects']['count']
 page.locator('.settings summary').click();options=page.locator('#projectState option').evaluate_all('(xs)=>xs.map(x=>x.value).filter(x=>x!=="all")');assert options
 value=options[0];expected=sum(f['properties']['project_state']==value for f in data('projects')['features'])
 page.select_option('#projectState',value);expect(page.locator('#recordCount')).to_have_text(f'{expected:,}'.replace(',','.'))
 with page.expect_download() as item:page.click('#exportCsv')
 rows=list(csv.DictReader(io.StringIO(pathlib.Path(item.value.path()).read_text(encoding='utf-8-sig'))));assert len(rows)==expected
 assert all(r['estado_ambiental']==value for r in rows)
 page.select_option('#projectState','all');page.select_option('#radius','400');a=page.evaluate('DTC.snapshot().count')
 page.select_option('#radius','1500');bigger=page.evaluate('DTC.snapshot().count');assert bigger>=a
 page.select_option('#radius','0');page.screenshot(path=str(OUT/(name+'-projects-v05.png')),full_page=True)
 if D['heat']['status']=='ready':
  page.locator('.rail [data-preset=climate]').click();settle(page)
  assert page.evaluate('DTC.snapshot().counts.heat')==D['heat']['count']
  assert 'Temperatura de superficie' in page.locator('#legend').inner_text()
  page.wait_for_timeout(1200)
  assert any(l['id']=='dtc-heat-fill' and l['visibility']=='visible' for l in page.evaluate('DTC.mapSnapshot().ownLayers'))
  page.screenshot(path=str(OUT/(name+'-heat-v05.png')),full_page=True)
 page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(300)
 assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+2')
 page.screenshot(path=str(OUT/(name+'-mobile-v05.png')),full_page=True)
 assert not errors,errors
 REPORT.append({'test':'new-domain browser acceptance','browser':name,'result':'PASS','project_count':D['projects']['count'],'filter_value':value,'filtered_count':expected,'radius_400':a,'radius_1500':bigger,'thermal_status':D['heat']['status']})
 context.close();b.close()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--url');p.add_argument('--chromium-only',action='store_true');args=p.parse_args();server=None
 try:
  validate()
  if not args.url:
   server=ThreadingHTTPServer(('127.0.0.1',8767),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
  with sync_playwright() as pw:
   browser(pw.chromium,'chromium',args.url or 'http://127.0.0.1:8767/')
   if not args.chromium_only:browser(pw.webkit,'webkit',args.url or 'http://127.0.0.1:8767/')
 finally:
  (OUT/'pending-acceptance.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2));print('PENDING_ACCEPTANCE',json.dumps(REPORT,ensure_ascii=False))
  if server:server.shutdown()
