"""Prepare public, non-personal data snapshots. No portal access or credentials.
GeoJSON and manifest are served together; toggles never call external data APIs.
A failed source remains unavailable; no synthetic records enter a deployment.
"""
import concurrent.futures as cf
import datetime as dt
import hashlib
import html
import json
import math
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from shapely.geometry import shape, mapping, box
from shapely.validation import make_valid

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'atlas'/'data'; OUT.mkdir(parents=True,exist_ok=True)
BBOX=[-70.634,-33.492,-70.554,-33.428]
NOW=dt.datetime.now(dt.timezone.utc).isoformat()
CENSUS='https://services5.arcgis.com/hUyD8u3TeZLKPe4T/arcgis/rest/services/Censo2024_v2/FeatureServer'
MUNI='https://services6.arcgis.com/wXIYE6xA1E2Vw4Je/arcgis/rest/services/'
OCUC='https://services9.arcgis.com/kKJR3Qt68ohAWuet/arcgis/rest/services/'
REG=[]; BOUNDARY=None

def request(url,params=None,timeout=45,raw=False):
 if params:url+='?'+urllib.parse.urlencode(params)
 req=urllib.request.Request(url,headers={'User-Agent':'DigitalTwinChile/0.4 public municipal pilot','Accept':'application/json,*/*'})
 with urllib.request.urlopen(req,timeout=timeout) as r:
  data=r.read(80000000)
 if raw:return data
 obj=json.loads(data)
 if isinstance(obj,dict) and obj.get('error'):raise ValueError(str(obj['error']))
 return obj

def stamp(ms):
 return dt.datetime.fromtimestamp(ms/1000,dt.timezone.utc).isoformat() if ms else None

def clean_terms(s):return html.unescape(re.sub('<[^>]+>',' ',s or '')).strip()[:3000]

def source_info(url):
 m=request(url,{'f':'json'}); fields={f['name']:f for f in m.get('fields',[])}
 terms='No se declara una licencia en los metadatos consultados. Revisar antes de redistribuir.'
 try:
  item=request('https://www.arcgis.com/sharing/rest/content/items/'+m['serviceItemId'],{'f':'json'})
  terms=clean_terms(item.get('licenseInfo')) or terms
  owner=item.get('owner','')
 except Exception:owner='No comprobado'
 return m,fields,terms,owner

def arc_features(url,fields,where='1=1',bbox=True):
 params={'f':'json','where':where,'returnIdsOnly':'true'}
 if bbox:params.update(geometry=','.join(map(str,BBOX)),geometryType='esriGeometryEnvelope',inSR='4326',spatialRel='esriSpatialRelIntersects')
 ids=request(url+'/query',params).get('objectIds') or []
 if len(ids)>90000:raise ValueError('Excede el limite de seguridad del piloto')
 result=[]
 for n in range(0,len(ids),1000):
  q={'f':'geojson','objectIds':','.join(map(str,ids[n:n+1000])),'outFields':','.join(fields),'outSR':'4326','returnGeometry':'true','geometryPrecision':'6'}
  page=request(url+'/query',q)
  if page.get('exceededTransferLimit'):raise ValueError('Fuente trunco la pagina')
  result.extend(page.get('features',[]))
  time.sleep(.12)
 if len(result)!=len(ids):raise ValueError('Recuento inconsistente: '+str(len(result))+' / '+str(len(ids)))
 return result,len(ids)

def normalized(feature,layer,props,clip=True):
 try:
  geom=make_valid(shape(feature['geometry']))
  if geom.is_empty:return None
  if BOUNDARY is not None and clip:
   if not geom.intersects(BOUNDARY):return None
   if geom.geom_type in ['LineString','MultiLineString']:geom=geom.intersection(BOUNDARY)
  if geom.geom_type not in ['Point','MultiPoint','Polygon','MultiPolygon','LineString','MultiLineString']:return None
  if not (-180<=geom.bounds[0]<=180 and -90<=geom.bounds[1]<=90):return None
  p=geom.representative_point()
  fid=str(feature.get('id',props.get('id','')))
  props={k:v for k,v in props.items() if v is not None}
  props.update(id=layer+':'+fid,layer=layer,x=round(p.x,6),y=round(p.y,6))
  return {'type':'Feature','id':props['id'],'geometry':mapping(geom),'properties':props}
 except Exception:return None

def save(entry,features,raw_count=None):
 features=[f for f in features if f]
 ids=[f['id'] for f in features]
 if len(ids)!=len(set(ids)):raise ValueError('IDs duplicados en '+entry['id'])
 obj={'type':'FeatureCollection','features':features}
 data=json.dumps(obj,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
 (OUT/(entry['id']+'.geojson')).write_bytes(data)
 entry.update(status='ready',path='data/'+entry['id']+'.geojson',count=len(features),raw_count=raw_count,retrieved_at=NOW,sha256=hashlib.sha256(data).hexdigest())
 REG.append(entry)
 print('DATASET',entry['id'],len(features),entry.get('reference',''),flush=True)

def unavailable(entry,error):
 entry.update(status='unavailable',count=None,error=str(error)[:350],checked_at=NOW)
 REG.append(entry);print('UNAVAILABLE',entry['id'],str(error)[:140],flush=True)

# Administrative polygon is independently discovered; never assume a layer id.
try:
 root=request(CENSUS,{'f':'json'})
 layers=root.get('layers',[])
 candidates=[l for l in layers if 'comuna' in l['name'].lower() and 'manzana' not in l['name'].lower()]
 for candidate in candidates:
  url=CENSUS+'/'+str(candidate['id']); m,fields,terms,owner=source_info(url)
  key=next((k for k in ['CUT','COD_COMUNA','COMUNA'] if k in fields),None)
  if not key:continue
  numeric=fields[key]['type'] in ['esriFieldTypeInteger','esriFieldTypeSmallInteger','esriFieldTypeDouble']
  value='13120' if key!='COMUNA' else 'Ñuñoa'
  where=key+'='+ (value if numeric else "'"+value+"'")
  feats,_=arc_features(url,[key],where,bbox=False)
  if not feats:continue
  from shapely.ops import unary_union
  BOUNDARY=unary_union([make_valid(shape(f['geometry'])) for f in feats])
  save({'id':'boundary','name':'Límite comunal','group':'Territorio','geometry':'polygon','color':'#43dbc3','provider':'Servicio Censo 2024 · cartografía publicada en ArcGIS','url':url,'reference':'Cartografía CPV 2024','license':terms,'owner':owner,'note':'Delimitación de la capa comunal del servicio consultado; no certificación jurídica del deslinde.'},[normalized({'id':'13120','geometry':mapping(BOUNDARY)},'boundary',{'name':'Ñuñoa','CUT':'13120'},False)])
  break
except Exception as e:print('BOUNDARY_AUDIT',str(e),flush=True)
if BOUNDARY is None:
 save({'id':'boundary','name':'Área piloto (no límite oficial)','group':'Territorio','geometry':'polygon','color':'#43dbc3','provider':'Digital Twin Chile','reference':'Área de consulta','license':'Geometría propia','url':'','note':'Rectángulo de consulta alrededor de Ñuñoa; puede incluir sectores vecinos. No usar como límite comunal.'},[normalized({'id':'bbox','geometry':mapping(box(*BBOX))},'boundary',{'name':'Área piloto referencial'},False)])

ARCS=[
 {'id':'lights','name':'Luminarias','group':'Infraestructura','geometry':'point','color':'#ffcf70','url':MUNI+'Luminarias_2026_ARCGIS_ONLINE_Georreferenciada_2.0/FeatureServer/0','provider':'Catastro atribuido a Municipalidad de Ñuñoa · ArcGIS','reference':'Catastro identificado como 2026','fields':['ObjectId','CALLE','TPOSTE','POTENCIA1','MODELO1','CANTIDAD1'],'note':'Ubicaciones de catastro, no fallas ni estado operativo en tiempo real.'},
 {'id':'trees','name':'Arbolado urbano','group':'Naturaleza','geometry':'point','color':'#63bb8e','url':MUNI+'CATASTRO_ARBOLADO_URBANO_ARCGIS_ONLINE/FeatureServer/0','provider':'Catastro atribuido a Municipalidad de Ñuñoa · ArcGIS','reference':'Catastro con campos de actualización 2024','fields':['FID','ESPECIE','NOMBRE_CIENTIFICO','ALTURA','ESTADO_GENERAL','ESTADO_FITOSANITARIO'],'note':'Catastro de individuos. Estado observado en la fecha de la fuente; no diagnóstico actual.'},
 {'id':'permits','name':'Permisos históricos','group':'Planificación','geometry':'point','color':'#cc8fec','url':OCUC+'Permisos_edificacion_2010_2018/FeatureServer/0','provider':'OCUC · fuente declarada INE','reference':'Serie 2010–2018 (nombre del servicio)','fields':['FID','COD_COMUNA','AÑO','GLOSA_DEST','NUM_PISOS','SUPERFICIE','CANTIDAD_U'],'where':'COD_COMUNA=13120','note':'Permisos históricos, no proyectos vigentes ni obras ejecutadas. La fecha de edición del servicio no renueva la serie.'},
 {'id':'census','name':'Población por manzana','group':'Personas','geometry':'polygon','color':'#8b9bea','url':CENSUS+'/6','provider':'Servicio Censo2024_v2 · fuente declarada INE','reference':'Censo 2024','fields':['OBJECTID','CUT','MANZENT','COMUNA','n_per','prom_edad','n_edad_0_5','n_edad_60_mas','n_hog'],'where':"CUT='13120'",'note':'Personas por manzana, no densidad ni población actual. Nulos y valores negativos se preservan como no disponibles. Filtrado radial por punto representativo, sin prorratear población.'},
 {'id':'cycling','name':'Ciclovías históricas','group':'Movilidad','geometry':'line','color':'#5fe0dc','url':OCUC+'Red_ciclovias_RM/FeatureServer/0','provider':'OCUC · fuente declarada MINVU','reference':'Serie histórica; edición de datos del servicio 2019','fields':['FID','name','longitud'],'note':'Red histórica. No representa por sí sola la red actual; segmentos recortados al área piloto.'}
]

def process_arc(e):
 entry=dict(e)
 try:
  m,fields,terms,owner=source_info(entry['url'])
  want=[f for f in entry.pop('fields') if f in fields]
  where=entry.pop('where','1=1')
  feats,raw=arc_features(entry['url'],want,where)
  oid=next((f for f in want if fields[f]['type']=='esriFieldTypeOID'),want[0])
  built=[]
  for f in feats:
   p=f.get('properties') or {}; fid=f.get('id',p.get(oid))
   if fid is None:continue
   f['id']=fid
   props={'name':str(p.get('CALLE') or p.get('ESPECIE') or p.get('name') or ('Manzana '+str(p.get('MANZENT','')) if entry['id']=='census' else entry['name']))}
   for key in want:
    value=p.get(key)
    if entry['id']=='census' and isinstance(value,(int,float)) and value<0:value=None
    if isinstance(value,float) and not math.isfinite(value):value=None
    if key!=oid:props[key]=value
   built.append(normalized(f,entry['id'],props))
  entry.update(license=terms,owner=owner,source_edited_at=stamp(m.get('editingInfo',{}).get('dataLastEditDate')),copyright=m.get('copyrightText',''),field_aliases={k:fields[k].get('alias',k) for k in want})
  save(entry,built,raw)
 except Exception as ex:unavailable(entry,ex)

with cf.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(process_arc,ARCS))

OSM=[
 ('parks','Parques y plazas','Naturaleza','polygon','#49bb86'),
 ('health','Salud y farmacias','Servicios','point','#ee8da1'),
 ('education','Educación','Servicios','point','#83aef5'),
 ('commerce','Comercios y gastronomía','Economía','point','#ffb684'),
 ('mobility','Transporte público','Movilidad','point','#56b9e4'),
 ('culture','Cultura y deporte','Servicios','point','#dc90c8'),
 ('animals','Bienestar animal','Servicios','point','#c6b483'),
 ('buildings','Edificios OSM · 3D','Territorio','polygon','#79a8b2')]
ENDPOINTS=['https://overpass.private.coffee/api/interpreter','https://overpass-api.de/api/interpreter']
boxtext=','.join(map(str,[BBOX[1],BBOX[0],BBOX[3],BBOX[2]]))

def overpass(query):
 last=None
 for endpoint in ENDPOINTS:
  try:
   obj=request(endpoint,{'data':query},timeout=65)
   if obj.get('remark'):raise ValueError(obj['remark'])
   return obj,endpoint
  except urllib.error.HTTPError as e:
   last=e
   if e.code in [400,429]:break
  except Exception as e:last=e
  time.sleep(2)
 raise ValueError(str(last))

def osm_geom(el):
 if el['type']=='node':return {'type':'Point','coordinates':[el['lon'],el['lat']]}
 seq=el.get('geometry')
 if seq and all('lat' in p and 'lon' in p for p in seq):
  coords=[[p['lon'],p['lat']] for p in seq]
  closed=len(coords)>3 and coords[0]==coords[-1]
  return {'type':'Polygon','coordinates':[coords]} if closed and ('building' in el.get('tags',{}) or 'leisure' in el.get('tags',{})) else {'type':'LineString','coordinates':coords}
 if el.get('center'):return {'type':'Point','coordinates':[el['center']['lon'],el['center']['lat']]}
 return None

def numeric(v):
 try:
  n=float(str(v).replace(' m','').strip());return n if 0<n<400 else None
 except Exception:return None

def osm_entry(row):
 id,name,group,geom,color=row
 return {'id':id,'name':name,'group':group,'geometry':geom,'color':color,'provider':'OpenStreetMap contributors','url':'https://www.openstreetmap.org/copyright','license':'ODbL 1.0 · atribución a OpenStreetMap contributors','reference':'Instantánea OSM, no catastro oficial','note':'Cobertura colaborativa no exhaustiva. Un cero no demuestra ausencia. Polígonos complejos no reconstruidos pueden quedar fuera.'}

for building_mode in [False,True]:
 rows=[r for r in OSM if (r[0]=='buildings')==building_mode]
 try:
  if building_mode:terms=['way["building"]']
  else:terms=['nwr["shop"]','nwr["amenity"~"^(hospital|clinic|doctors|dentist|pharmacy|school|university|college|kindergarten|restaurant|cafe|bar|fast_food|bank|marketplace|library|theatre|cinema|community_centre|veterinary|animal_shelter)$"]','nwr["leisure"~"^(park|garden|playground|dog_park|sports_centre|pitch|swimming_pool)$"]','nwr["public_transport"~"^(platform|station)$"]','nwr["highway"="bus_stop"]','nwr["railway"~"^(station|subway_entrance)$"]']
  query='[out:json][timeout:45];('+''.join(t+'('+boxtext+');' for t in terms)+');out body geom;'
  obj,endpoint=overpass(query);groups={r[0]:[] for r in rows}
  for el in obj.get('elements',[]):
   t=el.get('tags',{});geom=osm_geom(el)
   if not geom:continue
   a=t.get('amenity');l=t.get('leisure');g=None
   if building_mode:g='buildings'
   elif a in ['veterinary','animal_shelter'] or l=='dog_park':g='animals'
   elif a in ['hospital','clinic','doctors','dentist','pharmacy']:g='health'
   elif a in ['school','university','college','kindergarten']:g='education'
   elif 'shop' in t or a in ['restaurant','cafe','bar','fast_food','bank','marketplace']:g='commerce'
   elif l in ['park','garden','playground']:g='parks'
   elif a in ['library','theatre','cinema','community_centre'] or l in ['sports_centre','pitch','swimming_pool']:g='culture'
   else:g='mobility'
   props={'name':t.get('name') or t.get('brand') or 'Sin nombre en OSM','rubro':t.get('shop') or a or l or t.get('public_transport') or t.get('railway'),'calle':t.get('addr:street'),'osm_id':str(el['type'])+'/'+str(el['id'])}
   if g=='buildings':
    h=numeric(t.get('height'));floors=numeric(t.get('building:levels'))
    props.update(height=h if h else floors*3 if floors else .6,floors=floors,height_quality='Altura declarada OSM' if h else 'Estimada: 3 m por piso OSM' if floors else 'Sin altura: volumen simbólico 0,6 m',building=t.get('building'))
   f=normalized({'id':props['osm_id'],'geometry':geom},g,props)
   if f:groups[g].append(f)
  for row in rows:
   entry=osm_entry(row);entry['source_edited_at']=obj.get('osm3s',{}).get('timestamp_osm_base');entry['query_endpoint']=endpoint
   if row[0]=='buildings':entry['note']='Huellas de edificios OSM (ways). Altura declarada, o estimada a 3 m por piso, o volumen simbólico de 0,6 m cuando falta el dato. No es levantamiento de alturas ni incorpora todos los multipolígonos.'
   save(entry,groups[row[0]])
 except Exception as e:
  for row in rows:unavailable(osm_entry(row),e)

# Explicitly unavailable analytical themes: no random data and no inert toggles.
for id,name,group,note,url in [
 ('pedestrians','Flujos peatonales por hora','Movilidad','Requiere mediciones, sensores o un estudio con cobertura y metodología documentadas.',''),
 ('crime','Delitos y seguridad','Seguridad','Pendiente serie oficial georreferenciada, escala publicable y denominadores.','https://cead.spd.gov.cl/'),
 ('births','Natalidad y estadísticas vitales','Personas','Pendiente conectar series por residencia, año y territorio.','https://www.ine.gob.cl/'),
 ('zoning','Plan regulador vigente','Planificación','Pendiente validar ordenanza, planos y modificaciones vigentes.','https://ide.minvu.cl/'),
 ('projects','Cartera de inversiones','Planificación','Pendiente distinguir anunciado, aprobado, financiado y en ejecución.','https://sig.sea.gob.cl/mapadeproyectos/'),
 ('heat','Temperatura superficial','Ambiente','Pendiente producto satelital fechado y procesamiento; no confundir con temperatura del aire.','https://www.usgs.gov/landsat-missions'),
 ('municipal','Conectores municipales','Gestión','Requiere convenio, permisos y API de solo lectura. No hay sistemas privados conectados.',''),
 ('licenses','Patentes comerciales','Economía','Pendiente registro autorizado de establecimientos; OSM no reemplaza patentes.','')]:
  REG.append({'id':id,'name':name,'group':group,'status':'pending','note':note,'provider':'Pendiente de integración','reference':'Sin datos cargados','url':url,'count':None,'color':'#6c808c'})
REG.sort(key=lambda e:e['id'])
manifest={'version':'0.4.0','territory':{'name':'Ñuñoa','code':'13120','center':[-70.595,-33.457],'bbox':BBOX,'boundary_verified':BOUNDARY is not None,'scope':'Comuna recortada a cartografía del servicio Censo' if BOUNDARY is not None else 'Área piloto rectangular; no total comunal'},'built_at':NOW,'datasets':REG,'methodology':'Inventario descriptivo de registros públicos. Filtros por punto representativo, no tiempo de caminata. Conteos de objetos heterogéneos no son indicadores de calidad de vida. No se trasladaron datos ni código del portal de referencia.'}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
# Pin the map library locally; its upstream license accompanies the distribution.
vendor=ROOT/'atlas'/'vendor';vendor.mkdir(exist_ok=True)
for name in ['maplibre-gl.js','maplibre-gl.css']:
 (vendor/name).write_bytes(request('https://unpkg.com/maplibre-gl@4.7.1/dist/'+name,raw=True,timeout=40))
try:(vendor/'LICENSE.txt').write_bytes(request('https://unpkg.com/maplibre-gl@4.7.1/LICENSE.txt',raw=True))
except Exception:(vendor/'LICENSE.txt').write_text('MapLibre GL JS 4.7.1 · BSD-3-Clause · https://github.com/maplibre/maplibre-gl-js/blob/v4.7.1/LICENSE.txt\n')
print('MANIFEST_SUMMARY',json.dumps({'ready':[(e['id'],e['count']) for e in REG if e['status']=='ready'],'unavailable':[e['id'] for e in REG if e['status']=='unavailable'],'boundary':BOUNDARY is not None},ensure_ascii=False),flush=True)
