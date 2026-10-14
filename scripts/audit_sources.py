"""Inspect public endpoints only. No portal credentials or personal fields."""
import json, pathlib, urllib.request, urllib.parse, concurrent.futures
SOURCES={
'lights':'https://services6.arcgis.com/wXIYE6xA1E2Vw4Je/arcgis/rest/services/Luminarias_2026_ARCGIS_ONLINE_Georreferenciada_2.0/FeatureServer/0',
'trees':'https://services6.arcgis.com/wXIYE6xA1E2Vw4Je/arcgis/rest/services/CATASTRO_ARBOLADO_URBANO_ARCGIS_ONLINE/FeatureServer/0',
'permits':'https://services9.arcgis.com/kKJR3Qt68ohAWuet/arcgis/rest/services/Permisos_edificacion_2010_2018/FeatureServer/0',
'census':'https://services5.arcgis.com/hUyD8u3TeZLKPe4T/arcgis/rest/services/Censo2024_v2/FeatureServer/6',
'cycleways':'https://services9.arcgis.com/kKJR3Qt68ohAWuet/arcgis/rest/services/Red_ciclovias_RM/FeatureServer/0',
'green':'https://geoide.minvu.cl/server/rest/services/Catastros/Areas_Verdes_MINVU_INE_2023/FeatureServer/0'}
BBOX='-70.627,-33.491,-70.555,-33.429'
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'DigitalTwinChile-public-data-audit/0.4','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=22) as r:return json.load(r)
def inspect(pair):
 name,url=pair; result={'id':name,'url':url}
 try:
  m=get(url+'?f=json'); result['metadata']={k:m.get(k) for k in ['name','type','geometryType','description','copyrightText','extent','editingInfo','serviceItemId','maxRecordCount','supportedQueryFormats','error']}
  result['fields']=[{'name':f['name'],'alias':f.get('alias'),'type':f.get('type')} for f in m.get('fields',[])]
  if not m.get('error'):
   params={'f':'json','where':'1=1','geometry':BBOX,'geometryType':'esriGeometryEnvelope','inSR':'4326','spatialRel':'esriSpatialRelIntersects','returnCountOnly':'true'}
   result['pilot_count']=get(url+'/query?'+urllib.parse.urlencode(params))
 except Exception as e:result['error']=str(e)
 return result
out=list(concurrent.futures.ThreadPoolExecutor(max_workers=3).map(inspect,SOURCES.items()))
pathlib.Path('test-results').mkdir(exist_ok=True)
pathlib.Path('test-results/source-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print('AUDIT_BEGIN')
for r in out:
 print(json.dumps(r,ensure_ascii=False))
print('AUDIT_END')
