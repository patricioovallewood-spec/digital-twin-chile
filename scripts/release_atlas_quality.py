"""Idempotent quality migration applied before release tests; no external data fetch."""
import json
from pathlib import Path
p=Path('atlas/data/manifest.json');m=json.loads(p.read_text())
for d in m['datasets']:
 if d['id'] in ['culture','parks','education','health','commerce','animals']:
  note=' El registro no confirma acceso público, capacidad, horarios ni funcionamiento actual; puede incluir instalaciones privadas.'
  if note not in d['note']:d['note']+=note
 if d['id']=='culture':d['name']='Cultura, deporte y piscinas'
m['territory']['scope']='Objetos que intersectan el límite de la capa comunal consultada' if m['territory']['boundary_verified'] else m['territory']['scope']
p.write_text(json.dumps(m,ensure_ascii=False,indent=2))
p=Path('atlas/app.mjs');s=p.read_text()
s=s.replace("'Edificios OSM · 3D'","'Edificación · volúmenes 3D'")
s=s.replace("'fill-extrusion-color':['case',['==',['get','height_quality'],'Altura declarada OSM'],'#b4d8dc',['==',['get','height_quality'],'Estimada: 3 m por piso OSM'],'#789ba8','#526770']", "'fill-extrusion-color':['case',['==',['get','height_quality'],'Altura declarada OSM'],'#b4d8dc',['>', ['to-number',['get','height'],0],1],'#8aadb9','#526770']")
s=s.replace('3D: claro = altura OSM; azul = estimada por pisos; gris = sin altura.','3D: volúmenes cartográficos, no edificios únicos. Azul = altura derivada; gris = volumen simbólico. No medición verificada.')
s=s.replace('La visualización 3D usa alturas declaradas en OSM, estimaciones de 3 metros por piso o volúmenes simbólicos de 0,6 metros cuando falta altura. No hay terreno 3D calibrado ni simulación física.','La visualización 3D usa polígonos y alturas cartográficas OpenMapTiles, con origen OSM, o volúmenes simbólicos de 0,6 metros cuando falta altura. Son partes cartográficas, no edificios únicos; sus alturas no están verificadas como mediciones. No hay terreno 3D calibrado ni simulación física.')
s=s.replace("const labels={height:'Altura visual (m)'", "const labels={height:'Altura cartográfica (m)'")
s=s.replace("let on=state.active.has(d.id);", "let on=state.active.has(d.id);")
a="state.active=new Set((presets[name]||presets.overview).filter(id=>defs.some(d=>d.id===id&&d.status==='ready')));"
b=a+"\n const missing=(presets[name]||[]).filter(id=>!defs.some(d=>d.id===id&&d.status==='ready'));if(missing.length)toast('Sin datos preparados para: '+missing.join(', ')+'. Consulta Fuentes.');"
if b not in s:s=s.replace(a,b)
s=s.replace("get(id).length):'…'", "get(id).length):'…'")
s=s.replace("map?{loaded:map.loaded(),pitch:map.getPitch(),ownLayers:", "map?{loaded:map.loaded(),pitch:map.getPitch(),renderedCount:mapReady?map.queryRenderedFeatures().filter(f=>f.layer.id.startsWith('dtc-')).length:0,ownLayers:")
p.write_text(s)
p=Path('atlas/index.html');s=p.read_text().replace('Todas (incluye estimaciones)','Todas (incluye alturas cartográficas)')
s=s.replace('Solo altura declarada OSM','Solo altura declarada OSM (puede no haber)')
p.write_text(s)
p=Path('atlas/core.mjs');s=p.read_text()
s=s.replace("'fecha_extraccion','metodo'", "'fecha_extraccion','metodo','proveedor','condiciones_de_uso'")
s=s.replace("'Punto representativo; cobertura y fechas segun fuente'].map", "'Punto representativo; cobertura y fechas segun fuente',d.provider,d.license].map")
p.write_text(s)
p=Path('tests/test_atlas.py');s=p.read_text()
s=s.replace("if live:\n  page.screenshot", "if live:\n  page.wait_for_timeout(3500)\n  assert page.evaluate('DTC.mapSnapshot().renderedCount')>0\n  page.screenshot")
a=" # Preset changes must change data layers, not just button styles."
b=""" # Verify real 3D volume data and actual rendered map features.
 page.locator('.rail [data-preset=buildings]').click();settle(page)
 page.wait_for_timeout(3500)
 assert page.evaluate('DTC.snapshot().counts.buildings')>100
 assert page.evaluate('DTC.mapSnapshot().renderedCount')>0
 assert any(l['id']=='dtc-buildings-extrusion' and l['visibility']=='visible' for l in page.evaluate('DTC.mapSnapshot().ownLayers'))
 page.screenshot(path=str(OUT/(name+'-buildings.png')),full_page=True)
"""+a
if b not in s:s=s.replace(a,b)
p.write_text(s)
print('Height provenance, public access limitations and export attribution updated')
