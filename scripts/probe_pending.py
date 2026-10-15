"""Bounded read-only audit of public sources; never authentication or personal records."""
import concurrent.futures,datetime,json,pathlib,re,requests
from bs4 import BeautifulSoup
OUT=pathlib.Path('pending-audit');OUT.mkdir(exist_ok=True)
S=requests.Session();S.headers.update({'User-Agent':'DigitalTwinChile/0.5 public-data verification','Accept':'application/json,text/html;q=0.9'})
BBOX='-70.634,-33.492,-70.554,-33.428'
def get(url,params=None):
 r=S.get(url,params=params,timeout=(10,28));r.raise_for_status();return r
REPORT={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'bcn':[],'gis':[],'pages':[],'satellite':[],'errors':[]}
for year in [2026,2025,2024,2023,2021]:
 url=f'https://www.bcn.cl/siit/reportescomunales/comunas_v.html?anno={year}&idcom=13120'
 try:
  r=get(url);soup=BeautifulSoup(r.text,'html.parser');(OUT/f'bcn-{year}.html').write_text(r.text)
  rows=[]
  for table in soup.find_all('table'):
   heading=table.find_previous(re.compile('^h[1-6]$'))
   label=heading.get_text(' ',strip=True) if heading else ''
   text=table.get_text(' ',strip=True)
   if any(k in (label+' '+text).lower() for k in ['natalidad','mortalidad','delitos','denuncias','policial','fecundidad']):
    rows.append({'heading':label,'rows':[[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'])] for tr in table.find_all('tr')], 'context':str(table.find_next_sibling())[:1000]})
  REPORT['bcn'].append({'url':url,'report_year':year,'tables':rows})
 except Exception as e:REPORT['errors'].append({'url':url,'error':str(e)})
for url in ['https://www.nunoa.cl/plan-regulador-comunal/','https://www.nunoa.cl/transparencia/','https://www.nunoa.cl/transparencia-municipal/']:
 try:
  r=get(url);soup=BeautifulSoup(r.text,'html.parser');links=[]
  for a in soup.find_all('a',href=True):
   text=a.get_text(' ',strip=True);href=requests.compat.urljoin(url,a['href'])
   if any(k in (text+' '+href).lower() for k in ['patente','regulador','ordenanza','zonific','modific','transparen','arcgis','proexsi','consejo','portaltransparencia']):links.append({'text':text,'url':href})
  REPORT['pages'].append({'url':url,'links':links,'text':soup.get_text(' ',strip=True)[-15000:]})
 except Exception as e:REPORT['errors'].append({'url':url,'error':str(e)})
root='https://services6.arcgis.com/wXIYE6xA1E2Vw4Je/arcgis/rest/services'
try:
 services=get(root,{'f':'json'}).json();REPORT['municipal_services']=services
 for srv in services.get('services',[]):
  if any(k in srv['name'].lower() for k in ['patente','plan_reg','zonifica','prc','flujo','peaton']):
   url=srv['url'];m=get(url,{'f':'json'}).json();REPORT['gis'].append({'url':url,'metadata':m})
except Exception as e:REPORT['errors'].append({'url':root,'error':str(e)})
for idx in [1,2]:
 url=f'https://arcgisv11.sea.gob.cl/server/rest/services/WEBServices/ProyectosSEIA/MapServer/{idx}'
 try:
  meta=get(url,{'f':'json'}).json()
  params={'f':'json','where':'1=1','geometry':BBOX,'geometryType':'esriGeometryEnvelope','inSR':'4326','spatialRel':'esriSpatialRelIntersects','returnCountOnly':'true'}
  count=get(url+'/query',params).json();REPORT['gis'].append({'url':url,'metadata':meta,'pilot_count':count})
 except Exception as e:REPORT['errors'].append({'url':url,'error':str(e)})
try:
 url='https://planetarycomputer.microsoft.com/api/stac/v1/search'
 params={'collections':'landsat-c2-l2','bbox':BBOX,'datetime':'2026-01-01T00:00:00Z/2026-10-14T23:59:59Z','limit':8,'sortby':'-datetime'}
 result=get(url,params).json();REPORT['satellite']=[{'id':f.get('id'),'properties':f.get('properties'),'assets':f.get('assets'),'links':f.get('links')} for f in result.get('features',[])]
 REPORT['satellite_error']=result.get('error')
except Exception as e:REPORT['errors'].append({'source':'Planetary Computer','error':str(e)})
(OUT/'report.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2))
print(json.dumps({'bcn':REPORT['bcn'],'gis':[{k:v for k,v in x.items() if k!='metadata'}|{'name':x['metadata'].get('name'),'fields':[{'name':f['name'],'alias':f.get('alias')} for f in x['metadata'].get('fields',[])]} for x in REPORT['gis']],'satellite':[{'id':x['id'],'datetime':x['properties'].get('datetime'),'cloud':x['properties'].get('eo:cloud_cover'),'assets':list(x['assets'])} for x in REPORT['satellite']],'errors':REPORT['errors']},ensure_ascii=False))
