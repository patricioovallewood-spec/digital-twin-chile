"""Idempotent migration of atlas 0.4 to 0.5 without replacing existing datasets."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=ROOT/'atlas/app.mjs';s=app.read_text()
def replace(old,new):
 global s
 if new in s:return
 if old not in s:raise RuntimeError('Expected application fragment not found: '+old[:90])
 s=s.replace(old,new,1)
replace("const $=id=>", "import {installIndicators} from './indicators.mjs';\nconst $=id=>")
replace("permitYear:'all',base:","permitYear:'all',projectState:'all',base:")
replace("planning:['boundary','permits','buildings'],buildings", "planning:['boundary','permits','buildings'],projects:['boundary','projects'],climate:['boundary','heat','parks'],buildings")
replace("const fill=d.id==='census'?", "const fill=d.id==='heat'?['interpolate',['linear'],['to-number',['get','temp_c'],0],0,'#315779',10,'#528f96',20,'#b7c78a',30,'#eea36d',40,'#d9564f',50,'#962e48']:d.id==='census'?")
replace("'fill-opacity':d.id==='census'?.66:.31", "'fill-opacity':['census','heat'].includes(d.id)?.66:.31")
replace("  if(id==='permits'){", "  if(id==='projects'){\n   const values=[...new Set(obj.features.map(f=>f.properties.project_state).filter(Boolean))].sort();\n   $('projectState').innerHTML='<option value=\"all\">Todos los estados ambientales</option>'+values.map(v=>'<option value=\"'+esc(v)+'\">'+esc(v)+'</option>').join('');$('projectState').value=state.projectState;\n  }\n  if(id==='permits'){")
replace("+(state.mode==='heat'?'<div", "+(state.active.has('heat')?'<div class=\"legend-note\">Temperatura de superficie (°C), no aire. Escala fija: 0 azul, 20 verde, 30 naranja, 40 rojo. '+esc(defs.find(d=>d.id==='heat')?.reference||'')+'</div>':'')+(state.active.has('projects')?'<div class=\"legend-note\">SEIA: puntos de referencia; aprobación ambiental no implica obra ejecutada ni financiada.</div>':'')+(state.mode==='heat'?'<div")
replace("const notReady=defs.filter(d=>d.status!=='ready');$('pendingNote').textContent=notReady.length+' capas pendientes o sin acceso. No se muestran filtros vacíos. Consulta el catálogo.';", "const notReady=defs.filter(d=>['pending','requires_access','unavailable'].includes(d.status));const tables=defs.filter(d=>d.status==='tabular').length;$('pendingNote').textContent=tables+' conjuntos de indicadores comunales en el menú lateral. '+notReady.length+' dominios sin capa operativa. Las referencias documentales no son zonificación. Consulta Fuentes.';")
replace("state.permitYear='all';$('search')", "state.permitYear='all';state.projectState='all';$('projectState').value='all';$('search')")
replace("const keys=['rubro'", "const keys=['project_state','project_form','project_date','qualification_date','project_type','communes','temp_c','temp_min_c','temp_max_c','surface_date','valid_fraction','valid_pixels','cell_m','native_thermal_m','rubro'")
replace("const labels={height:","const labels={project_state:'Estado ambiental',project_form:'Ingreso EIA/DIA',project_date:'Fecha de presentación',qualification_date:'Fecha de calificación',project_type:'Tipología',communes:'Comunas declaradas',temp_c:'Superficie media (°C)',temp_min_c:'Mínima (°C)',temp_max_c:'Máxima (°C)',surface_date:'Observación satelital (UTC)',valid_fraction:'Fracción de píxeles válidos',valid_pixels:'Píxeles válidos',cell_m:'Lado de celda (m)',native_thermal_m:'Resolución térmica nativa (m)',height:")
replace("+safeLink(d.url,'Fuente del registro ↗');", "+safeLink(d.url,'Fuente del registro ↗')+(p.source_record_url?'<p>'+safeLink(p.source_record_url,'Expediente oficial del proyecto ↗')+'</p>':'');")
replace("const label={ready:'Preparada',pending:'Pendiente',unavailable:'No disponible'};", "const label={ready:'Capa preparada',tabular:'Indicadores disponibles',reference:'Referencia documental',requires_access:'Pendiente de acceso/datos',pending:'Pendiente',unavailable:'No disponible'};")
replace("if(d.id==='boundary')", "if(d.id==='boundary')") if False else None
replace(" $('permitYear').onchange=()=>{state.permitYear=$('permitYear').value;render();};", " $('permitYear').onchange=()=>{state.permitYear=$('permitYear').value;render();};\n $('projectState').onchange=()=>{state.projectState=$('projectState').value;render();};")
replace("Flujos peatonales, datos de delincuencia, natalidad, normativa vigente y sistemas municipales privados siguen pendientes cuando así lo indica el catálogo.", "Natalidad y seguridad están disponibles como indicadores comunales, no puntos de hechos. El expediente documental del PRC no valida normativa predial. SEIA no es la cartera completa de inversiones. El calor superficial corresponde a una escena Landsat, no tiempo real. Patentes, flujos horarios y sistemas municipales privados requieren datos o autorización.")
replace("  layerList();restore();controls();initMap();ensureActive();", "  layerList();restore();controls();installIndicators({manifest,openDialog,download,safeLink});initMap();ensureActive();")
replace("radius:state.radius,focus:state.focus,mapReady", "radius:state.radius,focus:state.focus,projectState:state.projectState,mapReady")
replace("state.query=(u.get('q')||'').slice", "state.projectState=(u.get('projectState')||'all').slice(0,120);\n state.query=(u.get('q')||'').slice")
app.write_text(s)
core=ROOT/'atlas/core.mjs';s=core.read_text().replace("VERSION='0.4.0'","VERSION='0.5.0'")
needle="  if(state.permitYear!=='all'&&id==='permits'&&String(p['AÑO'])!==state.permitYear)return false;"
if "id==='projects'&&state.projectState" not in s:
 assert needle in s;s=s.replace(needle,needle+"\n  if(id==='projects'&&state.projectState&&state.projectState!=='all'&&p.project_state!==state.projectState)return false;")
needle="u.searchParams.set('base',state.base);"
if "u.searchParams.set('projectState'" not in s:s=s.replace(needle,"if(state.projectState&&state.projectState!=='all')u.searchParams.set('projectState',state.projectState);"+needle)
# Preserve analytical values in CSV instead of exporting only names/coordinates.
s=s.replace("'condiciones_de_uso'];","'condiciones_de_uso','estado_ambiental','fecha_presentacion','superficie_celsius','fecha_satelital_utc'];")
s=s.replace("d.provider,d.license].map(cell)","d.provider,d.license,p.project_state,p.project_date,p.temp_c,p.surface_date].map(cell)")
core.write_text(s)
p=ROOT/'atlas/index.html';s=p.read_text().replace('v=040','v=050').replace('ATLAS 0.4','ATLAS 0.5').replace('0.4.0','0.5.0').replace('(puede no haber) (puede no haber)','(puede no haber)')
if 'id="indicatorsNav"' not in s:
 needle='<button class="nav-item" id="sourcesNav"'
 add='<button class="nav-item" id="indicatorsNav"><span>◷</span>Natalidad y salud</button><button class="nav-item" id="securityNav"><span>△</span>Seguridad comunal</button><button class="nav-item" data-preset="projects"><span>◇</span>Proyectos SEIA</button><button class="nav-item" data-preset="climate"><span>☀</span>Calor superficial</button><button class="nav-item" id="zoningNav"><span>▤</span>Plan regulador</button><button class="nav-item" id="integrationNav"><span>⇄</span>Accesos pendientes</button>'
 assert needle in s;s=s.replace(needle,add+needle)
if 'id="projectState"' not in s:
 needle='<label class="label" for="permitYear">';add='<label class="label" for="projectState">PROYECTOS SEIA · ESTADO AMBIENTAL</label><select id="projectState"><option value="all">Todos los estados ambientales</option></select>'
 assert needle in s;s=s.replace(needle,add+needle)
p.write_text(s)
p=ROOT/'atlas/style.css';s=p.read_text()
if '/* indicators-v05 */' not in s:s+='''\n/* indicators-v05 */\n.indicator-tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}.indicator-tabs .selected{border-color:#60d7bc;background:#204e49}.scope-warning{padding:15px;border:1px solid #4c7d80;border-radius:8px;background:#173439;line-height:1.7}.indicator-controls{display:flex;gap:16px;align-items:end;flex-wrap:wrap;margin:20px 0}.indicator-controls label{display:grid;gap:8px;flex:1;min-width:170px}.indicator-controls select{padding:11px;border:1px solid #426069;background:#132c35;color:#dcebee;max-width:100%;border-radius:6px}.indicator-notes{font-size:13px;line-height:1.7;color:#a8bec4}.document-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}.document-list article,.evidence-card{background:#122932;border:1px solid #32515a;padding:16px;border-radius:8px}.document-list h3{font-size:14px;overflow-wrap:anywhere}.evidence-card{margin:12px 0}.badge.tabular{color:#9be5d6}.badge.reference{color:#dfca92}.badge.requires_access{color:#e6b193}.rail nav{overflow-y:auto;min-height:0}.rail-bottom{flex-shrink:0}@media(max-height:900px) and (min-width:701px){.rail{height:100vh;position:sticky;top:0}.rail-bottom p{display:none}.nav-item{padding-top:9px;padding-bottom:9px}}\n'''
p.write_text(s)
# Deployment checks the new release and both old and new regression suites.
p=ROOT/'.github/workflows/deploy.yml';s=p.read_text().replace("VERSION='0.4.0'","VERSION='0.5.0'")
if 'python tests/test_pending.py' not in s:s=s.replace('          python tests/test_atlas.py\n','          python tests/test_atlas.py\n          python tests/test_pending.py\n')
p.write_text(s)
print('Atlas UI upgraded to 0.5.0')
