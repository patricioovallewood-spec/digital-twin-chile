"""One-time idempotent source migration; hardened files are committed after tests."""
from pathlib import Path
p=Path('scripts/prepare_atlas.py');s=p.read_text()
a=" if params:url+='?'+urllib.parse.urlencode(params)\n req=urllib.request.Request(url,headers={'User-Agent':'DigitalTwinChile/0.4 public municipal pilot','Accept':'application/json,*/*'})"
b=""" payload=None
 if params:
  encoded=urllib.parse.urlencode(params)
  if '/query' in url and len(encoded)>1300:payload=encoded.encode()
  else:url+='?'+encoded
 req=urllib.request.Request(url,data=payload,headers={'User-Agent':'DigitalTwinChile/0.4 public municipal pilot','Accept':'application/json,*/*','Content-Type':'application/x-www-form-urlencoded'})"""
if a in s:s=s.replace(a,b)
# Smaller bounded batches protect services with strict request limits.
s=s.replace('range(0,len(ids),1000)','range(0,len(ids),250)').replace('ids[n:n+1000]','ids[n:n+250]')
a="  obj,endpoint=overpass(query);groups={r[0]:[] for r in rows}"
b="""  if building_mode:
   # Four geographic queries, sequential, deduplicated by OSM id.
   midx=(BBOX[0]+BBOX[2])/2;midy=(BBOX[1]+BBOX[3])/2
   cells=[(BBOX[0],BBOX[1],midx,midy),(midx,BBOX[1],BBOX[2],midy),(BBOX[0],midy,midx,BBOX[3]),(midx,midy,BBOX[2],BBOX[3])]
   parts={};timestamps=[]
   for west,south,east,north in cells:
    q='[out:json][timeout:45];way["building"]('+','.join(map(str,[south,west,north,east]))+');out body geom;'
    part,endpoint=overpass(q)
    for el in part.get('elements',[]):parts[(el['type'],el['id'])]=el
    if part.get('osm3s',{}).get('timestamp_osm_base'):timestamps.append(part['osm3s']['timestamp_osm_base'])
    time.sleep(1.2)
   obj={'elements':list(parts.values()),'osm3s':{'timestamp_osm_base':min(timestamps) if timestamps else None}}
  else:obj,endpoint=overpass(query)
  groups={r[0]:[] for r in rows}"""
if a in s:s=s.replace(a,b)
p.write_text(s)
p=Path('atlas/app.mjs');s=p.read_text()
s=s.replace("if(!mapReady||!map?.isStyleLoaded())return;","if(!mapReady||!map?.getStyle())return;")
s=s.replace("markPreset(name);selectedFeature=null;","markPreset(name);selectedFeature=null;$('featureDetail').innerHTML='<span class=\"muted\">Selecciona un objeto para ver su ficha.</span>';")
p.write_text(s)
print('Source hardening applied idempotently')
