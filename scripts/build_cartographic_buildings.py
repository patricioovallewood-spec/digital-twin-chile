"""Small bounded public vector-tile download, not an OSM inventory of buildings.
OpenFreeMap permits <=3000 tiles/50 MB and <=4 parallel requests. This script
uses <=36 tiles, <=40 MB, sequential requests, a project-specific User-Agent.
Source polygons are clipped to each tile core so vector-tile buffers are not
counted twice. Parts crossing tiles remain parts, never claimed unique buildings.
No inference from DEM or private portal data is performed.
"""
import datetime as dt
import hashlib
import json
import math
import pathlib
import time
import urllib.request
import urllib.parse
import mapbox_vector_tile
from shapely.geometry import shape, mapping, box
from shapely.ops import transform, unary_union
from shapely.validation import make_valid

ROOT=pathlib.Path(__file__).resolve().parents[1];DATA=ROOT/'atlas/data'
m=json.loads((DATA/'manifest.json').read_text())
entry=next(d for d in m['datasets'] if d['id']=='buildings')
if entry['status']=='ready':
 print('Existing building snapshot retained');raise SystemExit(0)
UA='DigitalTwinChile-Nunoa-public-pilot/0.4 (bounded cartographic snapshot)'
bytes_read=0

def get(url):
 global bytes_read
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,application/x-protobuf,*/*'})
 with urllib.request.urlopen(req,timeout=35) as r:data=r.read(4000001)
 if len(data)>4000000:raise ValueError('Per-file download bound exceeded')
 bytes_read+=len(data)
 if bytes_read>40000000:raise ValueError('40 MB safety bound exceeded')
 return data

def tile(lon,lat,z):
 n=2**z
 return int((lon+180)/360*n),int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)

def ll(x,y,z):
 n=2**z
 return x/n*360-180,math.degrees(math.atan(math.sinh(math.pi*(1-2*y/n))))

try:
 style_url='https://tiles.openfreemap.org/styles/liberty'
 style=json.loads(get(style_url))
 source_key=next(l['source'] for l in style['layers'] if l.get('source-layer')=='building')
 src=style['sources'][source_key]
 tilejson_url=src.get('url',style_url)
 tj=json.loads(get(tilejson_url)) if src.get('url') else src
 template=tj['tiles'][0]
 z=min(14,int(tj.get('maxzoom',14)))
 west,south,east,north=m['territory']['bbox']
 x0,y0=tile(west,north,z);x1,y1=tile(east,south,z)
 if (x1-x0+1)*(y1-y0+1)>36:raise ValueError('Too many tiles for bounded pilot')
 bfc=json.loads((DATA/'boundary.geojson').read_text())
 boundary=unary_union([shape(f['geometry']) for f in bfc['features']])
 features=[];source_fields=set();tiles=[];unknown_height=0;derived_height=0
 for x in range(x0,x1+1):
  for y in range(y0,y1+1):
   url=template.replace('{z}',str(z)).replace('{x}',str(x)).replace('{y}',str(y))
   raw=get(url);tiles.append({'z':z,'x':x,'y':y,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
   decoded=mapbox_vector_tile.decode(raw,default_options={'y_coord_down':True})
   layer=decoded.get('building',{});extent=layer.get('extent',4096)
   nw=ll(x,y,z);se=ll(x+1,y+1,z);core=box(nw[0],se[1],se[0],nw[1])
   def convert(a,b,c=None):
    # Shapely may first attempt array conversion; scalar fallback is supported.
    return ll(x+a/extent,y+b/extent,z)
   for index,f in enumerate(layer.get('features',[])):
    props=f.get('properties',{});source_fields.update(props)
    geom=make_valid(transform(convert,shape(f['geometry'])))
    if geom.is_empty or not geom.intersects(boundary):continue
    geom=make_valid(geom.intersection(core).intersection(boundary))
    if geom.is_empty or geom.geom_type not in ['Polygon','MultiPolygon'] or geom.area<1e-12:continue
    p=geom.representative_point()
    try:h=float(props.get('render_height') or 0)
    except Exception:h=0
    valid=math.isfinite(h) and 0<h<400
    if valid:derived_height+=1
    else:unknown_height+=1
    fid='buildings:omt:'+str(z)+'/'+str(x)+'/'+str(y)+':'+str(index)
    quality='Altura cartográfica OpenMapTiles; no medición verificada' if valid else 'Sin altura: volumen simbólico 0,6 m'
    features.append({'type':'Feature','id':fid,'properties':{'id':fid,'layer':'buildings','name':'Volumen cartográfico de edificación','height':h if valid else .6,'height_quality':quality,'x':round(p.x,6),'y':round(p.y,6),'source_feature_id':str(f.get('id','')),'tile':str(z)+'/'+str(x)+'/'+str(y)},'geometry':mapping(geom)})
   time.sleep(.3)
 if len(features)<100:raise ValueError('Insufficient cartographic buildings returned')
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 data=json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
 (DATA/'buildings.geojson').write_bytes(data)
 entry.clear();entry.update(id='buildings',name='Edificación · volúmenes 3D',group='Territorio',geometry='polygon',color='#79a8b2',status='ready',count=len(features),path='data/buildings.geojson',provider='OpenFreeMap · OpenMapTiles · OpenStreetMap contributors',url='https://openfreemap.org/quick_start/',reference='Instantánea cartográfica; fecha OSM de cada objeto no verificada',license='Datos OpenStreetMap bajo ODbL 1.0; atribución OpenFreeMap, OpenMapTiles y OpenStreetMap contributors. https://www.openstreetmap.org/copyright',retrieved_at=now,sha256=hashlib.sha256(data).hexdigest(),tilejson_url=tilejson_url,tile_template=template,tiles_downloaded=len(tiles),download_bytes=bytes_read,source_fields=sorted(source_fields),height_count=derived_height,unknown_height_count=unknown_height,note='Volúmenes cartográficos derivados de teselas z'+str(z)+'. Pueden ser partes de edificios; NO es un conteo de edificios únicos ni un catastro oficial. Altura render_height cartográfica, no certificada como medida; 0,6 m simbólicos si falta. Buffers eliminados recortando cada tesela y el área piloto. No hay alturas estimadas desde terreno. No sustituye levantamiento predial.')
 m['buildings_added_at']=now
 (DATA/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
 pathlib.Path('test-results').mkdir(exist_ok=True)
 pathlib.Path('test-results/building-provenance.json').write_text(json.dumps({'entry':entry,'tiles':tiles},ensure_ascii=False,indent=2))
 print('BUILDING_SNAPSHOT',json.dumps({'parts':len(features),'derived_heights':derived_height,'missing_heights':unknown_height,'tiles':len(tiles),'download_bytes':bytes_read,'fields':sorted(source_fields)},ensure_ascii=False))
except Exception as error:
 print('BUILDING_FALLBACK_FAILED',str(error))
 raise
