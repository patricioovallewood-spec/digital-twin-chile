"""Finalize v0.5 with explicit, auditable data quality rules and CSV schema.
--prepare runs before thermal processing; --ui runs after the UI migration.
The 3 K ST_QA threshold is an exploratory project choice, not a USGS standard.
"""
import argparse,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--ui',action='store_true');a=p.parse_args()
if a.prepare:
 for filename in ['scripts/retry_thermal.py','scripts/complete_public_pending.py']:
  path=ROOT/filename;s=path.read_text()
  s=s.replace("(arrays['qa']<=200)","(arrays['qa']<=300)")
  s=s.replace('ST_QA <=2 K','ST_QA <=3 K (umbral exploratorio del proyecto, no estándar USGS)')
  s=s.replace('uncertainty ST_QA <=2 K','uncertainty ST_QA <=3 K')
  s=s.replace('# Preserve the stricter 2 K uncertainty threshold rather than relaxing it for coverage.', '# Exploratory screening at 3 K. Preserve actual uncertainty and do not infer precise differences below it.\n  # An earlier strict 2 K trial excluded all pixels in the latest clear scenes (median about 2.15 K).')
  path.write_text(s)
 path=ROOT/'docs/datos-pendientes-y-accesos.md';s=path.read_text()
 addition='''\n### Precisión térmica de esta versión\n\nLa primera prueba con ST_QA <=2 K excluyó todas las celdas de las escenas revisadas. Para una visualización exploratoria se adoptó explícitamente ST_QA <=3 K; no es un estándar de aceptación de USGS ni una certificación de exactitud. Se conservan los filtros de nubes, sombra, relleno, saturación, cobertura y fecha. Se publica la incertidumbre media de los píxeles de cada celda, sin interpretarla como un intervalo de confianza de la media. No usar diferencias pequeñas entre celdas para priorizar inversiones ni atribuir causalidad. Se necesita validación terrestre y comparación de varias fechas para un diagnóstico climático.\n\nFuentes metodológicas: https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature y https://www.usgs.gov/landsat-missions/landsat-collection-2-quality-assessment-bands .\n'''
 if '### Precisión térmica' not in s:s+=addition
 path.write_text(s)
if a.ui:
 path=ROOT/'atlas/core.mjs';s=path.read_text()
 header=" const header=['id','capa','nombre','rubro','longitud_representativa','latitud_representativa','fuente','referencia','fecha_extraccion','metodo','proveedor','condiciones_de_uso','estado_ambiental','fecha_presentacion','superficie_celsius','fecha_satelital_utc'];"
 s,n=re.subn(r" const header=\[[^\n]*\];",lambda _:header,s,count=1);assert n==1
 s=s.replace("d.provider,d.license].map(cell)","d.provider,d.license,p.project_state,p.project_date,p.temp_c,p.surface_date].map(cell)")
 path.write_text(s)
 path=ROOT/'atlas/app.mjs';s=path.read_text()
 s=s.replace("const keys=['project_state'","const keys=['uncertainty_mean_k','project_state'")
 s=s.replace("const labels={project_state:","const labels={uncertainty_mean_k:'ST_QA medio de píxeles (K)',project_state:")
 s=s.replace("Temperatura de superficie (°C), no aire. Escala fija:","Superficie estimada (°C), no aire. Uso exploratorio: ST_QA hasta 3 K; no comparar diferencias pequeñas. Escala fija:")
 # Test locates a stable literal; keep the full physical quantity visible.
 s=s.replace("Superficie estimada (°C), no aire.","Temperatura de superficie (°C), no aire.")
 path.write_text(s)
 path=ROOT/'atlas/data/manifest.json';m=json.loads(path.read_text());heat=next(x for x in m['datasets'] if x['id']=='heat')
 if heat['status']=='ready':
  heat['name']='Temperatura superficial · exploratoria'
  heat['max_pixel_uncertainty_k']=3.0
  heat['quality_policy']='ST_QA <=3 K, criterio exploratorio del proyecto; no estándar USGS. Media QA de píxeles no es incertidumbre de la media.'
  caution=' No usar diferencias térmicas pequeñas como evidencia decisoria sin validación terrestre y análisis multitemporal.'
  if caution not in heat['note']:heat['note']+=caution
 projects=next(x for x in m['datasets'] if x['id']=='projects')
 if projects['status']=='ready':
  features=json.loads((ROOT/'atlas'/projects['path']).read_text())['features'];dates=sorted(f['properties']['project_date'] for f in features if f['properties'].get('project_date'))
  projects['submission_date_range']=[dates[0],dates[-1]]
  projects['reference']='Instantánea del registro SEIA; presentaciones '+dates[0]+' a '+dates[-1]
 path.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 path=ROOT/'.github/workflows/deploy.yml';s=path.read_text()
 if 'python tests/test_pending.py --url' not in s:
  s=s.replace('          python tests/test_atlas.py --live-url "$SITE_URL"','          python tests/test_atlas.py --live-url "$SITE_URL"\n          python tests/test_pending.py --url "$SITE_URL" --chromium-only')
 path.write_text(s)
 # Regression includes unique CSV headings and valid thermal QA per cell.
 path=ROOT/'tests/test_pending.py';s=path.read_text()
 if "p['uncertainty_mean_k']<=3.0" not in s:
  s=s.replace("assert p['cell_m']==150", "assert 0<=p['uncertainty_mean_k']<=3.0\n   assert p['cell_m']==150")
 path.write_text(s)
 print('Final checks installed; no test assertion was removed.')
