"""Thermal-only preparation with local QA and bounded scene fallback.
Does not replace a valid existing layer when every candidate fails.
"""
import datetime as dt,hashlib,json,math,pathlib,requests
import numpy as np,rasterio,planetary_computer
from rasterio.windows import Window,from_bounds,transform as window_transform
from rasterio.warp import transform_bounds
from rasterio.features import geometry_mask
from shapely.geometry import shape,mapping,box
from shapely.ops import transform as trans,unary_union
from pyproj import Transformer
ROOT=pathlib.Path(__file__).resolve().parents[1];D=ROOT/'atlas/data';OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True)
M=json.loads((D/'manifest.json').read_text());ENTRY=next(d for d in M['datasets'] if d['id']=='heat');STAMP=dt.datetime.now(dt.timezone.utc).isoformat()
G=unary_union([shape(f['geometry']) for f in json.loads((D/'boundary.geojson').read_text())['features']])
S=requests.Session();S.headers['User-Agent']='DigitalTwinChile/0.5 public thermal QA'
def get(url,params=None):
 r=S.get(url,params=params,timeout=(10,45));r.raise_for_status();return r.json()
items=get('https://planetarycomputer.microsoft.com/api/stac/v1/search',{'collections':'landsat-c2-l2','bbox':','.join(map(str,G.bounds)),'datetime':'2026-01-01T00:00:00Z/2026-10-14T23:59:59Z','limit':20,'sortby':'-datetime'}).get('features',[])
candidates=[x for x in items if x['properties'].get('eo:cloud_cover',100)<15 and '_L2SP_' in x['id'] and 'lwir11' in x['assets']][:5]
report={'attempts':[],'selected':None};selected=None
for item in candidates:
 try:
  a=item['assets'];arrays={};band=a['lwir11']['raster:bands'][0]
  with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_HTTP_TIMEOUT='35',GDAL_HTTP_MAX_RETRY='1',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.TIF,.tif'):
   with rasterio.open(planetary_computer.sign(a['lwir11']['href'])) as src:
    crs=src.crs;raw=from_bounds(*transform_bounds('EPSG:4326',crs,*G.bounds),transform=src.transform)
    col=math.floor(raw.col_off/5)*5;row=math.floor(raw.row_off/5)*5;w=math.ceil((raw.col_off+raw.width-col)/5)*5;h=math.ceil((raw.row_off+raw.height-row)/5)*5
    assert 0<w<1000 and 0<h<1000
    window=Window(col,row,w,h);aff=window_transform(window,src.transform);base=src.transform;arrays['temp']=src.read(1,window=window)
   for key in ['qa_pixel','qa','qa_radsat']:
    with rasterio.open(planetary_computer.sign(a[key]['href'])) as src:
     assert src.crs==crs and src.transform==base
     arrays[key]=src.read(1,window=window)
  to_local=Transformer.from_crs(4326,crs,always_xy=True).transform;to_geo=Transformer.from_crs(crs,4326,always_xy=True).transform
  bound=trans(to_local,G);inside=geometry_mask([mapping(bound)],out_shape=(h,w),transform=aff,invert=True)
  temp=arrays['temp'].astype(float)*band['scale']+band['offset']-273.15
  clear=inside&(arrays['temp']>0)&((arrays['qa_pixel']&63)==0)&(arrays['qa_radsat']==0)&(temp>-80)&(temp<90)
  # Exploratory screening at 3 K. Preserve actual uncertainty and do not infer precise differences below it.
  # An earlier strict 2 K trial excluded all pixels in the latest clear scenes (median about 2.15 K).
  valid=clear&(arrays['qa']>=0)&(arrays['qa']<=300)
  diag={'scene':item['id'],'observed':item['properties']['datetime'],'inside_pixels':int(inside.sum()),'clear_pixels':int(clear.sum()),'valid_pixels':int(valid.sum()),'uncertainty_k_median':float(np.median(arrays['qa'][clear])*.01) if clear.any() else None}
  report['attempts'].append(diag);features=[];used=0
  for y in range(0,h,5):
   for x in range(0,w,5):
    n0=int(inside[y:y+5,x:x+5].sum());mask=valid[y:y+5,x:x+5];n=int(mask.sum())
    if n0<5 or n/n0<.75:continue
    left,top=aff*(x,y);right,bottom=aff*(x+5,y+5);cell=box(left,bottom,right,top).intersection(bound)
    if cell.is_empty or cell.area<1:continue
    geo=trans(to_geo,cell);p=geo.representative_point();v=temp[y:y+5,x:x+5][mask];key=f'heat:{item["id"]}:{x}:{y}'
    prop={'id':key,'layer':'heat','name':'Temperatura superficial · '+item['properties']['datetime'][:10],'x':p.x,'y':p.y,'temp_c':round(float(v.mean()),2),'temp_min_c':round(float(v.min()),2),'temp_max_c':round(float(v.max()),2),'surface_date':item['properties']['datetime'],'valid_fraction':round(n/n0,3),'valid_pixels':n,'cell_m':150,'native_thermal_m':100,'uncertainty_mean_k':round(float(arrays['qa'][y:y+5,x:x+5][mask].mean())*.01,2)}
    features.append({'type':'Feature','id':key,'properties':prop,'geometry':mapping(geo)});used+=n
  diag['cells']=len(features);diag['retained_coverage']=used/max(1,int(inside.sum()));print('THERMAL_QA',json.dumps(diag),flush=True)
  # Avoid presenting a tiny surviving patch as a city-wide usable scene.
  if len(features)<30 or diag['retained_coverage']<.3:continue
  selected=(item,features,diag,band);break
 except Exception as e:
  report['attempts'].append({'scene':item['id'],'error':str(e).split('?')[0][:300]});print('THERMAL_ERROR',item['id'],type(e).__name__,flush=True)
if selected:
 item,features,diag,band=selected;raw=json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();(D/'heat.geojson').write_bytes(raw)
 ENTRY.update(status='ready',format='geojson',geometry='polygon',group='Ambiente',name='Temperatura superficial · Landsat',color='#faac79',count=len(features),path='data/heat.geojson',sha256=hashlib.sha256(raw).hexdigest(),provider='USGS/NASA Landsat · Microsoft Planetary Computer',url='https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2',reference='Escena '+item['id']+' · '+item['properties']['datetime'],license='Datos Landsat de dominio público (USGS); atribución USGS/NASA y Microsoft Planetary Computer.',retrieved_at=STAMP,scene_id=item['id'],observation_time=item['properties']['datetime'],completion='partial',valid_pixel_fraction=round(diag['retained_coverage'],4),scale=band['scale'],offset=band['offset'],source_assets={k:item['assets'][k]['href'] for k in ['lwir11','qa_pixel','qa','qa_radsat']},note='Temperatura de SUPERFICIE estimada por satélite, no del aire ni tiempo real. Celdas de 150 m; sensor térmico 100 m, producto a 30 m. Píxeles internos sin relleno, nubes, cirros, sombra o nieve, sin saturación y ST_QA <=3 K (umbral exploratorio del proyecto, no estándar USGS); al menos 75% válidos y 5 internos por celda. Sin dato no significa frío. Escena elegida entre candidatas recientes de baja nubosidad por QA local; no se garantiza ser la adquisición más reciente. No prueba por sí sola una isla de calor.')
 M['updated_at']=STAMP;(D/'manifest.json').write_text(json.dumps(M,ensure_ascii=False,indent=2)+'\n');report['selected']={'id':item['id'],'cells':len(features),'coverage':diag['retained_coverage']}
(OUT/'thermal-qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('THERMAL_RESULT',json.dumps(report),flush=True)
