"""Build verifiable public additions. No personal data or private-service credentials.
Existing geographic datasets are preserved. Tabular indicators are never placed
at invented coordinates; institutional dependencies are not marked as integrated.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, math, os, pathlib, re, requests
from bs4 import BeautifulSoup
from shapely.geometry import shape, mapping, Point, box
from shapely.ops import unary_union, transform as shp_transform
from pyproj import Transformer
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'atlas/data'; EVID=ROOT/'test-results'; EVID.mkdir(exist_ok=True)
M=json.loads((DATA/'manifest.json').read_text()); ITEMS={x['id']:x for x in M['datasets']}
BOUNDARY=unary_union([shape(f['geometry']) for f in json.loads((DATA/'boundary.geojson').read_text())['features']])
STAMP=dt.datetime.now(dt.timezone.utc).isoformat(); CUTOFF='2026-10-14'
S=requests.Session(); S.headers.update({'User-Agent':'DigitalTwinChile/0.5 public-interest data integration','Accept':'application/json,text/html;q=0.8'})
REPORT={'generated_at':STAMP,'steps':[],'errors':[]}

def fetch(url,params=None):
 r=S.get(url,params=params,timeout=(12,50));r.raise_for_status();return r

def save(id,body,ext='json',**metadata):
 file=DATA/(id+'.'+ext); raw=json.dumps(body,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();file.write_bytes(raw)
 entry=ITEMS[id];entry.update(metadata,path='data/'+file.name,sha256=hashlib.sha256(raw).hexdigest(),retrieved_at=STAMP)
 REPORT['steps'].append({'id':id,'status':entry['status'],'count':entry.get('count'),'path':entry['path']})

def numeric(value):
 s=str(value).strip().replace('.','').replace(',','.');return float(s) if re.fullmatch(r'-?\d+(\.\d+)?',s) else None

def bcn_tables(year):
 url=f'https://www.bcn.cl/siit/reportescomunales/comunas_v.html?anno={year}&idcom=13120'
 r=fetch(url);soup=BeautifulSoup(r.text,'html.parser');tables=[]
 for t in soup.find_all('table'):
  h=t.find_previous(re.compile('^h[1-6]$'));heading=h.get_text(' ',strip=True) if h else ''
  rows=[[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'])] for tr in t.find_all('tr')]
  tables.append({'heading':heading,'rows':rows})
 return url,tables

def indicators():
 observations=[];sources=[]
 for report_year in [2026,2025,2024,2023]:
  url,tables=bcn_tables(report_year);sources.append(url)
  for t in tables:
   if not t['heading'].startswith(('3.3','3.4')):continue
   years=re.findall(r'\b20\d{2}\b',t['heading']);
   if not years:continue
   year=int(years[-1]);kind='birth' if 'natalidad' in t['heading'].lower() else 'death'
   for row in t['rows']:
    if len(row)!=3:continue
    territory='Ñuñoa' if 'uñoa' in row[0] else 'Región Metropolitana' if row[0].startswith('Región') else 'Chile' if row[0]=='País' else None
    if not territory:continue
    # Do not import the fecundity value: its source heading ambiguously groups units.
    vals=[('natalidad','Tasa de natalidad',row[2],'Nacidos vivos por 1.000 habitantes')] if kind=='birth' else [('mortalidad_general','Mortalidad general',row[1],'Defunciones por 1.000 habitantes'),('mortalidad_infantil','Mortalidad infantil',row[2],'Defunciones de menores de un año por 1.000 nacidos vivos')]
    for key,label,value,unit in vals:
     number=numeric(value)
     if number is None:continue
     observations.append({'id':f'{key}-{year}-{territory}','indicator':key,'label':label,'year':year,'territory':territory,'value':number,'unit':unit,'source_url':url,'report_year':report_year,'source_label':'DEIS / MINSAL, publicado por BCN','original_heading':t['heading']})
 unique={x['id']:x for x in observations};observations=list(unique.values())
 assert len(observations)>=18
 save('births',{'type':'IndicatorTable','rows':observations,'sources':sources,'notes':['Escala comunal, regional y país. No hay microdatos ni ubicaciones de nacimientos.','Años disponibles: no se interpolan años ausentes. Las tasas no equivalen a conteos.','No se importa fecundidad por ambigüedad de unidades del encabezado fuente.']},status='tabular',format='table',name='Natalidad y mortalidad · indicadores',count=len(observations),provider='BCN · fuente declarada DEIS/MINSAL',url=sources[0],reference='Años 2019, 2020, 2022 y 2023; reportes BCN 2023–2026',license='Valores estadísticos públicos con atribución a BCN y DEIS/MINSAL; no se redistribuyen microdatos.',note='Indicadores agregados, no nacimientos georreferenciados. Los filtros espaciales no se aplican. No son datos de 2026.',completion='partial')
 url,tables=bcn_tables(2026);crime=[]
 for t in tables:
  if not t['heading'].startswith(('7.1','7.2')):continue
  # Never concatenate DMCS/violent-crime classifications from previous editions.
  key='integridad_personas' if t['heading'].startswith('7.1') else 'vif'
  label='Denuncias: delitos contra la vida o integridad de las personas' if key=='integridad_personas' else 'Denuncias: violencia intrafamiliar'
  years=[]
  for row in t['rows']:
   if row and row[0]=='Unidad Territorial':years=[int(x) for x in row[1:] if re.fullmatch('20\d{2}',x)]
  assert years==[2023,2024,2025],years
  for row in t['rows']:
   if len(row)!=4:continue
   territory='Ñuñoa' if 'uñoa' in row[0] else 'Región Metropolitana' if row[0].startswith('Región') else 'Chile' if row[0]=='País' else None
   if not territory:continue
   for year,value in zip(years,row[1:]):
    n=numeric(value)
    if n is not None:crime.append({'id':f'{key}-{year}-{territory}','indicator':key,'label':label,'year':year,'territory':territory,'value':n,'unit':'Denuncias por 100.000 habitantes','source_url':url,'report_year':2026,'source_label':'BCN · fuente declarada CEAD / Subsecretaría de Prevención del Delito','original_heading':t['heading']})
 assert len(crime)==18
 save('crime',{'type':'IndicatorTable','rows':crime,'sources':[url],'notes':['Tasas de denuncias; no son incidencia real, victimización ni casos policiales totales.','No hay ubicación de hechos individuales: no se fabrica un mapa de calor.','Serie tomada de una sola edición BCN 2026. No concatenar con DMCS o delitos violentos de ediciones anteriores.','Indicadores de 2023–2025, no delitos ocurridos en 2026.']},status='tabular',format='table',name='Seguridad · tasas comunales de denuncias',count=len(crime),provider='BCN · fuente declarada CEAD/SPD',url=url,reference='2023–2025 · clasificación de la edición BCN 2026',license='Estadísticas agregadas públicas; atribución BCN y organismo productor.',note='Tasas comunales de dos grupos de denuncias. No ubica delitos por calle. No usar como mapa de riesgo individual ni concatenar clasificaciones distintas.',completion='partial')

def projects():
 features=[];seen=set();sources=[];meta=[]; bbox=','.join(map(str,BOUNDARY.bounds))
 fields=['ID_EXPEDIENTE','NOMBRE_PROYECTO','FORMA_PRESENTACION','ESTADO_EVALUACION','FECHA_PRESENTACION','FECHA_CALIFICACION','COMUNAS','URL_EXPEDIENTE','NOMBRE_TIPOLOGIA']
 for layer in [1,2]:
  url=f'https://arcgisv11.sea.gob.cl/server/rest/services/WEBServices/ProyectosSEIA/MapServer/{layer}';sources.append(url)
  m=fetch(url,{'f':'json'}).json();assert not m.get('error'),m
  meta.append({'url':url,'name':m.get('name'),'copyright':m.get('copyrightText'),'fields':[x['name'] for x in m.get('fields',[])]})
  params={'f':'json','where':'1=1','geometry':bbox,'geometryType':'esriGeometryEnvelope','inSR':'4326','spatialRel':'esriSpatialRelIntersects','returnIdsOnly':'true'}
  ids=fetch(url+'/query',params).json();assert not ids.get('error'),ids
  object_ids=ids.get('objectIds') or [];oid=ids.get('objectIdFieldName','OBJECTID')
  for i in range(0,len(object_ids),150):
   p={'f':'geojson','objectIds':','.join(map(str,object_ids[i:i+150])),'outFields':','.join([oid]+fields),'outSR':'4326','returnGeometry':'true'}
   result=fetch(url+'/query',p).json();assert result.get('type')=='FeatureCollection',str(result)[:500]
   for f in result['features']:
    if not f.get('geometry'):continue
    geom=shape(f['geometry']);
    if geom.is_empty or not geom.intersects(BOUNDARY):continue
    a=f['properties'];eid=str(a.get('ID_EXPEDIENTE') or f'{layer}-{a[oid]}')
    if eid in seen:continue
    seen.add(eid);point=geom.representative_point()
    def day(v):
     try:return dt.datetime.fromtimestamp(float(v)/1000,dt.timezone.utc).date().isoformat() if v is not None else None
     except (TypeError,ValueError,OverflowError):return str(v) if v else None
    prop={'id':'projects:'+eid,'layer':'projects','name':a.get('NOMBRE_PROYECTO') or 'Proyecto SEIA','x':point.x,'y':point.y,'project_state':a.get('ESTADO_EVALUACION') or 'No declarado','project_form':a.get('FORMA_PRESENTACION'),'project_date':day(a.get('FECHA_PRESENTACION')),'qualification_date':day(a.get('FECHA_CALIFICACION')),'project_type':a.get('NOMBRE_TIPOLOGIA'),'communes':a.get('COMUNAS'),'source_record_url':a.get('URL_EXPEDIENTE'),'source_endpoint':url}
    features.append({'type':'Feature','id':prop['id'],'properties':prop,'geometry':mapping(geom)})
 assert features,'No SEIA records intersect the pilot boundary'
 save('projects',{'type':'FeatureCollection','features':features},ext='geojson',status='ready',format='geojson',geometry='point',name='Proyectos SEIA · ubicación de referencia',group='Planificación',color='#ffcf77',count=len(features),provider='Servicio de Evaluación Ambiental (SEA)',url=sources[0].rsplit('/',1)[0],reference='Registro SEIA consultado el '+STAMP[:10],license='Servicio público del SEA; atribución y respeto a condiciones del organismo. No incluye expedientes completos.',note='Puntos de proyectos EIA/DIA que intersectan el límite piloto, no huellas ni áreas de impacto. Puede omitir proyectos multicomunales cuyo punto quede fuera. Estado ambiental no equivale a financiamiento, permiso de obra ni ejecución. No constituye la cartera completa municipal. Se excluyen campos personales y montos cuya unidad no se verificó.',completion='partial',source_layers=sources)
 REPORT['project_metadata']=meta

def zoning():
 url='https://www.nunoa.cl/plan-regulador-comunal/';soup=BeautifulSoup(fetch(url).text,'html.parser');docs=[];seen=set()
 for a in soup.select('a[href]'):
  href=requests.compat.urljoin(url,a['href']);text=a.get_text(' ',strip=True)
  if not re.search(r'\.(pdf|tif)(\?|$)',href,re.I):continue
  if not href.startswith('https://www.nunoa.cl/'):continue
  if href in seen:continue
  seen.add(href)
  if not text or text.lower().startswith('descargar'):
   text=href.split('/')[-1].rsplit('.',1)[0].replace('-',' ')
  docs.append({'title':text,'url':href,'source_page':url,'role':'Referencia documental; vigencia predial no certificada'})
 assert len(docs)>=3
 save('zoning',{'type':'ReferenceDossier','documents':docs,'notes':['Índice de documentos enlazados por la página municipal; no se certificó la correspondencia de todos los títulos ni su vigencia jurídica.','No es una capa de zonificación ni un motor de usos o alturas permitidas.','La verificación predial requiere ordenanza, planos, modificaciones, eventuales fallos y certificados de la DOM. No inferir vigencia desde la fecha de subida.']},status='reference',format='documents',name='Plan regulador · expediente documental',count=len(docs),provider='Municipalidad de Ñuñoa',url=url,reference='Página municipal consultada el '+STAMP[:10],license='Enlaces al repositorio municipal; no se redistribuyen documentos.',note='Referencias oficiales disponibles. Pendiente validar polígonos, ordenanza consolidada y modificaciones para análisis normativo predial.',completion='partial')

def heat():
 import numpy as np, rasterio, planetary_computer
 from rasterio.windows import Window,from_bounds,transform as window_transform
 from rasterio.warp import transform_bounds
 from rasterio.features import geometry_mask
 search='https://planetarycomputer.microsoft.com/api/stac/v1/search'
 items=fetch(search,{'collections':'landsat-c2-l2','bbox':','.join(map(str,BOUNDARY.bounds)),'datetime':'2026-01-01T00:00:00Z/'+CUTOFF+'T23:59:59Z','limit':15,'sortby':'-datetime'}).json().get('features',[])
 candidates=[x for x in items if x.get('properties',{}).get('eo:cloud_cover',100)<15 and 'lwir11' in x.get('assets',{}) and '_L2SP_' in x['id']]
 if not candidates:raise ValueError('No suitable public Landsat surface-temperature scene')
 item=candidates[0];assets=item['assets'];bands=assets['lwir11'].get('raster:bands',[{}])[0];scale=bands.get('scale');offset=bands.get('offset')
 assert scale is not None and offset is not None
 env={'GDAL_DISABLE_READDIR_ON_OPEN':'EMPTY_DIR','GDAL_HTTP_TIMEOUT':'40','GDAL_HTTP_MAX_RETRY':'1','CPL_VSIL_CURL_ALLOWED_EXTENSIONS':'.TIF,.tif'}
 arrays={}
 with rasterio.Env(**env):
  # The signed URLs are ephemeral transport values and are never saved in output.
  with rasterio.open(planetary_computer.sign(assets['lwir11']['href'])) as src:
   crs=src.crs;bounds=transform_bounds('EPSG:4326',crs,*BOUNDARY.bounds);raw=from_bounds(*bounds,transform=src.transform)
   col=int(math.floor(raw.col_off/5)*5);row=int(math.floor(raw.row_off/5)*5);w=int(math.ceil((raw.col_off+raw.width-col)/5)*5);h=int(math.ceil((raw.row_off+raw.height-row)/5)*5)
   assert 0<w<1000 and 0<h<1000
   window=Window(col,row,w,h);affine=window_transform(window,src.transform);arrays['lwir11']=src.read(1,window=window);grid_transform=src.transform
   assert abs(abs(affine.a)-30)<.1 and abs(abs(affine.e)-30)<.1
  for key in ['qa_pixel','qa','qa_radsat']:
   with rasterio.open(planetary_computer.sign(assets[key]['href'])) as src:
    assert src.crs==crs and src.transform==grid_transform,'QA raster grid mismatch'
    arrays[key]=src.read(1,window=window)
 to_utm=Transformer.from_crs('EPSG:4326',crs,always_xy=True).transform;to_wgs=Transformer.from_crs(crs,'EPSG:4326',always_xy=True).transform
 local_boundary=shp_transform(to_utm,BOUNDARY);inside=geometry_mask([mapping(local_boundary)],out_shape=(h,w),transform=affine,invert=True)
 temp=arrays['lwir11'].astype(float)*scale+offset-273.15
 valid=inside&(arrays['lwir11']>0)&((arrays['qa_pixel']&63)==0)&(arrays['qa_radsat']==0)&(arrays['qa']>=0)&(arrays['qa']<=300)&(temp>-80)&(temp<90)
 features=[];covered=0
 for y in range(0,h,5):
  for x in range(0,w,5):
   possible=int(inside[y:y+5,x:x+5].sum());mask=valid[y:y+5,x:x+5];n=int(mask.sum())
   if possible<5 or n/possible<.75:continue
   left,top=affine*(x,y);right,bottom=affine*(x+5,y+5);cell=box(left,bottom,right,top).intersection(local_boundary)
   if cell.is_empty or cell.area<1:continue
   g=shp_transform(to_wgs,cell);p=g.representative_point();v=temp[y:y+5,x:x+5][mask];key=f'heat:{item["id"]}:{x}:{y}'
   props={'id':key,'layer':'heat','name':'Temperatura superficial · '+item['properties']['datetime'][:10],'x':p.x,'y':p.y,'temp_c':round(float(v.mean()),2),'temp_min_c':round(float(v.min()),2),'temp_max_c':round(float(v.max()),2),'valid_fraction':round(n/possible,3),'valid_pixels':n,'surface_date':item['properties']['datetime'],'cell_m':150,'native_thermal_m':100}
   features.append({'type':'Feature','id':key,'properties':props,'geometry':mapping(g)});covered+=n
 assert len(features)>30,'Insufficient usable thermal cells after QA'
 url='https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2'
 save('heat',{'type':'FeatureCollection','features':features},ext='geojson',status='ready',format='geojson',geometry='polygon',group='Ambiente',name='Temperatura superficial · Landsat',color='#faac79',count=len(features),provider='USGS/NASA Landsat · Microsoft Planetary Computer',url=url,reference='Escena '+item['id']+' · '+item['properties']['datetime'],license='Datos Landsat de dominio público (USGS); atribución USGS/NASA y Microsoft Planetary Computer.',note='Estimación satelital de temperatura de superficie, no aire, confort ni tiempo real. Celdas de 150 m; banda térmica nativa 100 m, producto remuestreado a 30 m. Media de píxeles con QA válida dentro de la comuna; al menos 75% válidos y 5 píxeles internos por celda. QA: sin relleno, nubes, cirros, sombras o nieve; sin saturación; incertidumbre ST_QA <=3 K (umbral exploratorio del proyecto, no estándar USGS). Sin dato no significa frío. El contraste de esta escena no prueba por sí solo una isla de calor.',completion='partial',scene_id=item['id'],observation_time=item['properties']['datetime'],source_edited_at=None,valid_pixel_fraction=round(covered/max(1,int(inside.sum())),4),scale=scale,offset=offset,source_assets={k:v['href'] for k,v in assets.items() if k in ['lwir11','qa_pixel','qa','qa_radsat']})

for name,fn in [('indicators',indicators),('projects',projects),('zoning',zoning),('heat',heat)]:
 try:fn()
 except Exception as e:REPORT['errors'].append({'task':name,'error':str(e)[:500]});print('SOURCE_ERROR',name,str(e)[:200],flush=True)
for id,note in {
 'licenses':'Pendiente registro de patentes autorizadas y vigencia. El directorio público ArcGIS revisado no identificó una capa de patentes. OSM no acredita autorización. Solicitar extracto municipal sin RUT ni domicilios privados.',
 'pedestrians':'Requiere conteos por tramo y fecha/hora, sensores o estudio documentado. No se identificó en esta revisión una serie abierta horaria validada para todas las calles de Ñuñoa; no se infiere flujo desde comercios, población ni luminarias.',
 'municipal':'Contrato de integración y validador preparados; sin API privada conectada. Requiere autorización municipal, endpoint, campos permitidos y credenciales guardadas fuera del código.'}.items():
 ITEMS[id].update(status='requires_access',completion='blocked',note=note,count=None,reference='Sin registros operativos conectados')
M['version']='0.5.0';M['updated_at']=STAMP;M['datasets']=[ITEMS[x['id']] for x in M['datasets']];M['new_domains_note']='Tablas comunales y referencias documentales no son capas espaciales; SEIA no es cartera ejecutada; Landsat es una escena fechada.'
(DATA/'manifest.json').write_text(json.dumps(M,ensure_ascii=False,indent=2)+'\n')
(EVID/'pending-ingestion-report.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2)+'\n')
print('PENDING_INTEGRATION',json.dumps(REPORT,ensure_ascii=False),flush=True)
# Public indicators and projects are minimum deliverables. Thermal failure remains explicit.
assert ITEMS['births']['status']=='tabular' and ITEMS['crime']['status']=='tabular'
assert ITEMS['projects']['status']=='ready'
