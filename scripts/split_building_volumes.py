"""Split grouped MVT multipolygons locally so proximity works per visible volume.
No new download; preserves total geometry area and source attributes.
"""
import hashlib,json
from pathlib import Path
from shapely.geometry import shape,mapping
p=Path('atlas/data/manifest.json');m=json.loads(p.read_text());d=next(x for x in m['datasets'] if x['id']=='buildings')
if d['status']=='ready' and not d.get('parts_split'):
 path=Path('atlas')/d['path'];fc=json.loads(path.read_text());out=[];old_area=0;new_area=0
 for f in fc['features']:
  geom=shape(f['geometry']);old_area+=geom.area
  parts=list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]
  for i,part in enumerate(parts):
   point=part.representative_point();fid=f['id']+':p'+str(i)
   props={**f['properties'],'id':fid,'x':round(point.x,6),'y':round(point.y,6)}
   out.append({'type':'Feature','id':fid,'properties':props,'geometry':mapping(part)});new_area+=part.area
 assert abs(new_area-old_area)<=max(1e-14,old_area*1e-9),'Geometry area must be preserved'
 data=json.dumps({'type':'FeatureCollection','features':out},ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();path.write_bytes(data)
 d.update(raw_group_count=len(fc['features']),count=len(out),parts_split=True,sha256=hashlib.sha256(data).hexdigest())
 d['note']+=' Se separaron los multipolígonos en piezas individuales para filtrar proximidad, preservando su superficie total. Las piezas no equivalen a edificios únicos.'
 m['methodology']+=' Edificación cartográfica desagregada en piezas poligonales, no inventario de edificios únicos.'
 p.write_text(json.dumps(m,ensure_ascii=False,indent=2))
 print('BUILDING_PARTS',len(fc['features']),'groups ->',len(out),'polygon volumes; area preserved')
p=Path('atlas/app.mjs');s=p.read_text()
s=s.replace('Capas: fuentes en Catálogo · © OpenStreetMap contributors (ODbL)','Capas: Fuentes · © OpenStreetMap contributors · © OpenMapTiles · OpenFreeMap')
p.write_text(s)
p=Path('atlas/style.css');s=p.read_text()
patch='\n/* Readability refinement: controls remain scrollable, not clipped. */\n.layer-row .name{font-size:12px}.hint{font-size:11px}.feature-detail p{font-size:11px}\n'
if patch not in s:p.write_text(s+patch)
