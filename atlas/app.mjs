import {VERSION,escapeHTML as esc,filterFeatures,circleFeature,emptyCollection,csv,serialise} from './core.mjs';
import {enrichCensus,summarize,metricsHTML,streetGroups,comparisonHTML} from './analysis.mjs';
import {installIndicators} from './indicators.mjs';
const $=id=>document.getElementById(id),fmt=n=>Number(n).toLocaleString('es-CL');
const state={active:new Set(),query:'',radius:0,focus:null,business:'all',heightQuality:'all',permitYear:'all',projectState:'all',street:'',censusMetric:'persons',selectionMode:'consult',base:'satellite',mode:'points',three:true};
const cache=new Map(),filtered=new Map(),loads=new Map(),errors=new Map(),signatures=new Map();
let manifest,defs=[],map=null,mapReady=false,currentRecords=[],selectedFeature=null,toastTimer,savedZone=null;
const presets={overview:['boundary','buildings','parks','mobility'],people:['boundary','census','health','education'],commerce:['boundary','commerce','health'],mobility:['boundary','cycling','mobility'],green:['boundary','parks','trees'],infrastructure:['boundary','lights'],planning:['boundary','permits','buildings'],projects:['boundary','projects'],climate:['boundary','heat','parks'],buildings:['boundary','buildings'],scenario:['boundary','buildings','demoZoning','demoWorks']};
const colors={};
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4500);}
function date(value){if(!value)return 'No declarada';const d=new Date(value);return Number.isFinite(d.getTime())?d.toLocaleDateString('es-CL',{day:'2-digit',month:'short',year:'numeric'}):String(value);}
function safeLink(url,label='Abrir fuente ↗'){try{const u=new URL(url);return ['https:','http:'].includes(u.protocol)?'<a target="_blank" rel="noopener" href="'+esc(u.href)+'">'+esc(label)+'</a>':'';}catch{return '';}}
function status(text,kind='ready'){$('status').textContent=text;$('status').dataset.state=kind;}
async function fetchTimed(url){const c=new AbortController(),t=setTimeout(()=>c.abort(),40000);try{const r=await fetch(url,{signal:c.signal});if(!r.ok)throw Error('HTTP '+r.status);return r;}finally{clearTimeout(t);}}
function mapStyle(){
 if(state.base==='dark')return 'https://tiles.openfreemap.org/styles/dark';
 if(state.base==='streets')return 'https://tiles.openfreemap.org/styles/liberty';
 return {version:8,sources:{satellite:{type:'raster',tileSize:256,tiles:['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],attribution:'Tiles © Esri · Maxar · Earthstar Geographics · fecha de imagen variable'}},layers:[{id:'background',type:'background',paint:{'background-color':'#182c35'}},{id:'satellite-base',type:'raster',source:'satellite',paint:{'raster-saturation':-.38,'raster-brightness-max':.72}}]};
}
function initMap(){
 try{
  if(!window.maplibregl)throw Error('No se pudo cargar MapLibre.');
  map=new maplibregl.Map({container:'map',style:mapStyle(),center:manifest.territory.center,zoom:13.8,pitch:state.three?48:0,bearing:-12,attributionControl:false,maxPitch:68});
  map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),'top-right');
  map.addControl(new maplibregl.AttributionControl({compact:true,customAttribution:'Capas: Fuentes · © OpenStreetMap contributors · © OpenMapTiles · OpenFreeMap'}),'bottom-right');
  map.on('style.load',()=>{mapReady=true;signatures.clear();drawAll();});
  map.on('error',e=>{console.warn('Map source:',e.error?.message||e.message);});
  map.on('moveend',()=>{const c=map.getCenter();$('cameraLabel').textContent=c.lat.toFixed(4)+' / '+c.lng.toFixed(4)+' · Z'+map.getZoom().toFixed(1);});
  map.on('click',e=>{
   const layerIds=defs.flatMap(d=>['-point','-fill','-line','-extrusion'].map(s=>'dtc-'+d.id+s)).filter(id=>map.getLayer(id)&&!id.includes('boundary'));
   const hit=map.queryRenderedFeatures(e.point,{layers:layerIds}).find(f=>f.properties?.id);
   if(hit&&state.selectionMode==='consult'){const f=currentRecords.find(x=>x.properties.id===hit.properties.id);if(f){showFeature(f);return;}}
   state.focus=[e.lngLat.lng,e.lngLat.lat];if(!state.radius)state.radius=800;$('radius').value=String(state.radius);$('quickRadius').value=String(state.radius);selectedFeature=null;render();
  });
  const cam=new URL(location.href).searchParams.get('camera')?.split(',').map(Number);
  if(cam?.length===3&&cam.every(Number.isFinite)&&Math.abs(cam[0])<=180&&Math.abs(cam[1])<85&&cam[2]>=2&&cam[2]<=19)map.jumpTo({center:cam.slice(0,2),zoom:cam[2]});
 }catch(error){$('mapFailure').hidden=false;$('mapFailure').textContent='El mapa 3D no pudo iniciarse en este navegador. Los filtros y la tabla siguen disponibles. '+error.message;$('threeBtn').disabled=true;}
}
function addDatasetLayers(d){
 const source='dtc-'+d.id;
 if(map.getSource(source))return;
 map.addSource(source,{type:'geojson',data:emptyCollection(),promoteId:'id'});
 const base={source,layout:{visibility:'none'}};
 if(d.id==='boundary'){
  map.addLayer({...base,id:source+'-line',type:'line',paint:{'line-color':d.color,'line-width':2.2,'line-opacity':.85}});return;
 }
 const polygon=['==',['geometry-type'],'Polygon'],line=['==',['geometry-type'],'LineString'],point=['==',['geometry-type'],'Point'];
 const fill=d.id==='demoZoning'?['get','zone_color']:d.id==='heat'?['interpolate',['linear'],['to-number',['get','temp_c'],0],0,'#315779',10,'#528f96',20,'#b7c78a',30,'#eea36d',40,'#d9564f',50,'#962e48']:d.id==='census'?['case',['has','n_per'],['step',['to-number',['get','n_per'],0],'#32444f',1,'#c5d2ef',50,'#8dacdf',150,'#5889ce',350,'#3866ae',800,'#9e71cc'],'#697681']:d.color;
 map.addLayer({...base,id:source+'-fill',type:'fill',filter:polygon,paint:{'fill-color':fill,'fill-opacity':['census','heat'].includes(d.id)?.66:.31,'fill-outline-color':d.color}});
 map.addLayer({...base,id:source+'-line',type:'line',filter:line,paint:{'line-color':d.color,'line-width':d.id==='cycling'?3:1.5,'line-opacity':.88}});
 map.addLayer({...base,id:source+'-point',type:'circle',filter:point,paint:{'circle-radius':['interpolate',['linear'],['zoom'],11,2,15,d.id==='trees'||d.id==='lights'?3:4.5,18,7],'circle-color':d.color,'circle-opacity':.85,'circle-stroke-width':.7,'circle-stroke-color':'#0b212a'}});
 map.addLayer({...base,id:source+'-heat',type:'heatmap',filter:point,paint:{'heatmap-weight':1,'heatmap-intensity':.8,'heatmap-radius':22,'heatmap-opacity':.72,'heatmap-color':['interpolate',['linear'],['heatmap-density'],0,'rgba(0,0,0,0)',.25,'#316b96',.5,d.color,.85,'#ffe5a6',1,'#fff1d1']}});
 if(d.id==='buildings')map.addLayer({...base,id:source+'-extrusion',type:'fill-extrusion',filter:polygon,paint:{'fill-extrusion-color':['case',['==',['get','height_quality'],'Altura declarada OSM'],'#b4d8dc',['>', ['to-number',['get','height'],0],1],'#8aadb9','#526770'],'fill-extrusion-height':['to-number',['get','height'],.6],'fill-extrusion-base':0,'fill-extrusion-opacity':.88}});
}
function drawAll(){
 if(!mapReady||!map?.getStyle())return;
 for(const d of defs.filter(x=>x.status==='ready')){
  if(!cache.has(d.id)&&!map.getSource('dtc-'+d.id))continue;
  addDatasetLayers(d);
  const features=filtered.get(d.id)||[],key=features.map(f=>f.id).join('|');
  if(signatures.get(d.id)!==key){map.getSource('dtc-'+d.id).setData({type:'FeatureCollection',features});signatures.set(d.id,key);}
  for(const suffix of ['line','point','fill','heat','extrusion']){
   const id='dtc-'+d.id+'-'+suffix;if(!map.getLayer(id))continue;
   let on=state.active.has(d.id);
   if(suffix==='heat')on=on&&state.mode==='heat';
   if(suffix==='point')on=on&&state.mode!=='heat';
   if(d.id==='buildings'&&suffix==='fill')on=on&&!state.three;
   if(suffix==='extrusion')on=on&&state.three;
   map.setLayoutProperty(id,'visibility',on?'visible':'none');
  }
 }
 if(!map.getSource('selection')){map.addSource('selection',{type:'geojson',data:emptyCollection()});map.addLayer({id:'selection-fill',type:'fill',source:'selection',paint:{'fill-color':'#75efcb','fill-opacity':.05}});map.addLayer({id:'selection-line',type:'line',source:'selection',paint:{'line-color':'#a4f2dc','line-width':2,'line-dasharray':[3,2]}});}
 map.getSource('selection').setData(state.focus&&state.radius?circleFeature(state.focus,state.radius):emptyCollection());
 if(map.getLayer('dtc-census-fill')){const metric=state.censusMetric==='density'?'density_ha':'n_per';const steps=state.censusMetric==='density'?[50,'#8dacdf',150,'#5889ce',300,'#3866ae',600,'#9e71cc']:[1,'#c5d2ef',50,'#8dacdf',150,'#5889ce',350,'#3866ae',800,'#9e71cc'];map.setPaintProperty('dtc-census-fill','fill-color',['case',['==',['typeof',['get',metric]],'number'],['step',['get',metric],'#32444f',...steps],'#697681']);}
 drawSelection();
 if(map.getLayer('dtc-boundary-line'))map.moveLayer('dtc-boundary-line');
 map.moveLayer('selection-line');
}
async function loadLayer(id){
 if(cache.has(id)||loads.has(id))return loads.get(id);
 const d=defs.find(d=>d.id===id);if(!d||d.status!=='ready')return;
 errors.delete(id);
 const promise=(async()=>{
  const r=await fetchTimed(d.path+'?sha='+d.sha256.slice(0,12));const bytes=await r.arrayBuffer();
  if(crypto.subtle){const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(v=>v.toString(16).padStart(2,'0')).join('');if(digest!==d.sha256)throw Error('La instantánea no coincide con su manifiesto.');}
  const obj=JSON.parse(new TextDecoder().decode(bytes));if(obj.type!=='FeatureCollection'||!Array.isArray(obj.features)||obj.features.length!==d.count)throw Error('Recuento de la instantánea no válido.');
  cache.set(id,id==='census'?enrichCensus(obj.features):obj.features);
  if(['commerce','health'].includes(id))updateStreetOptions();
  if(id==='projects'){
   const values=[...new Set(obj.features.map(f=>f.properties.project_state).filter(Boolean))].sort();
   $('projectState').innerHTML='<option value="all">Todos los estados ambientales</option>'+values.map(v=>'<option value="'+esc(v)+'">'+esc(v)+'</option>').join('');$('projectState').value=state.projectState;
  }
  if(id==='permits'){
   const values=[...new Set(obj.features.map(f=>f.properties['AÑO']).filter(x=>Number.isInteger(Number(x))))].sort((a,b)=>a-b);
   $('permitYear').innerHTML='<option value="all">Todos los años disponibles</option>'+values.map(y=>'<option>'+esc(y)+'</option>').join('');$('permitYear').value=state.permitYear;
  }
 })().catch(e=>errors.set(id,e.name==='AbortError'?'Tiempo de descarga agotado.':e.message)).finally(()=>{loads.delete(id);render();});
 loads.set(id,promise);render();return promise;
}
function ensureActive(){for(const id of state.active)void loadLayer(id);render();}
function render(){
 if(!manifest)return;
 filtered.clear();currentRecords=[];
 for(const d of defs){const f=filterFeatures(cache.get(d.id)||[],d.id,state);filtered.set(d.id,f);if(d.id!=='boundary')currentRecords.push(...f);}
 const pending=[...state.active].filter(id=>!cache.has(id)&&!errors.has(id));
 const failed=[...state.active].filter(id=>errors.has(id));
 const available=[...state.active].filter(id=>cache.has(id)&&id!=='boundary');
 $('recordCount').textContent=pending.length&&!available.length?'—':failed.length&&!available.length?'—':fmt(currentRecords.length);
 $('activeCount').textContent=String(state.active.size);
 $('scopeLabel').textContent=(state.radius?'Radio de '+fmt(state.radius)+' m · referencia geométrica. ':manifest.territory.scope+'. ')+(pending.length||failed.length?'Resultado parcial. ':'')+'No equivale al total visible en la cámara.'+(state.street?' Calle en comercios/salud: '+state.street+'.':'');
 if(failed.length)status('No se pudieron abrir '+failed.join(', ')+'. Desactiva y reactiva para reintentar.','error');
 else if(pending.length)status('Cargando instantáneas: '+pending.map(id=>defs.find(d=>d.id===id)?.name).join(', ')+'…','loading');
 else status(state.active.size?fmt(currentRecords.length)+' objetos · filtros aplicados · '+(state.radius?fmt(state.radius)+' m':'área piloto'):'Sin capas activas. Selecciona una capa o una vista.');
 for(const d of defs){
  const input=$('layer-'+d.id),count=$('count-'+d.id);if(!input)continue;
  input.checked=state.active.has(d.id);input.closest('label').classList.toggle('checked',input.checked);
  count.textContent=input.checked?(errors.has(d.id)?'Error':cache.has(d.id)?fmt(filtered.get(d.id).length):'…'):fmt(d.count);
 }
 $('breakdown').innerHTML=defs.filter(d=>state.active.has(d.id)&&d.id!=='boundary').map(d=>'<div class="breakdown-row"><span><i style="background:'+d.color+'"></i>'+esc(d.name)+'</span><b>'+(cache.has(d.id)?fmt(filtered.get(d.id).length):errors.has(d.id)?'Error':'…')+'</b></div>').join('');
 $('legend').innerHTML=defs.filter(d=>state.active.has(d.id)).map(d=>'<div><span class="swatch" style="background:'+d.color+'"></span>'+esc(d.name)+'</div>').join('')+(state.active.has('demoZoning')?'<div class="legend-note">DEMO: D-M1 mixta (lila); D-R1 residencial (azul); D-E1 equipamiento (verde); D-M2 mixta intensa (naranja). Zonas y alturas ficticias.</div>':'')+(state.active.has('census')?'<div class="legend-note">'+(state.censusMetric==='density'?'Densidad: hab/ha de manzana completa · 0–49, 50–149, 150–299, 300–599, 600+.':'Censo: personas/manzana · 0, 1–49, 50–149, 150–349, 350–799, 800+.')+' Gris: sin dato. No son habitantes exactos del radio.</div>':'')+(state.active.has('buildings')?'<div class="legend-note">3D: volúmenes cartográficos, no edificios únicos. Azul = altura derivada; gris = volumen simbólico. No medición verificada.</div>':'')+(state.active.has('heat')?'<div class="legend-note">Temperatura de superficie (°C), no aire. Uso exploratorio: ST_QA hasta 3 K; no comparar diferencias pequeñas. Escala fija: 0 azul, 20 verde, 30 naranja, 40 rojo. '+esc(defs.find(d=>d.id==='heat')?.reference||'')+'</div>':'')+(state.active.has('projects')?'<div class="legend-note">SEIA: puntos de referencia; aprobación ambiental no implica obra ejecutada ni financiada.</div>':'')+(state.mode==='heat'?'<div class="legend-note">Concentración visual de registros. No es flujo de peatones ni temperatura.</div>':'');
 $('exportCsv').disabled=!currentRecords.length||pending.length>0||failed.length>0;$('exportGeo').disabled=$('exportCsv').disabled;
 if(selectedFeature&&!currentRecords.some(f=>f.id===selectedFeature.id)){selectedFeature=null;$('featureDetail').innerHTML='<span class="muted">Selecciona un objeto para ver su ficha y procedencia.</span>';}
 drawAll();
 renderIndicators();
}
function layerList(){
 const groups=[...new Set(defs.filter(d=>d.status==='ready').map(d=>d.group))];
 $('layers').innerHTML=groups.map(g=>'<div class="group-title">'+esc(g)+'</div>'+defs.filter(d=>d.group===g&&d.status==='ready').map(d=>'<label class="layer-row"><input type="checkbox" id="layer-'+d.id+'" value="'+d.id+'"><span class="name">'+esc(d.name)+'<small>'+esc(d.reference)+'</small></span><span class="layer-count" id="count-'+d.id+'">'+fmt(d.count)+'</span></label>').join('')).join('');
 const notReady=defs.filter(d=>['pending','requires_access','unavailable'].includes(d.status));const tables=defs.filter(d=>d.status==='tabular').length;$('pendingNote').textContent=tables+' conjuntos de indicadores comunales en el menú lateral. '+notReady.length+' dominios sin capa operativa. Las referencias documentales no son zonificación. Consulta Fuentes.';
 $('layers').addEventListener('change',e=>{const id=e.target.value;if(!defs.some(d=>d.id===id))return;if(e.target.checked)state.active.add(id);else state.active.delete(id);markPreset(null);ensureActive();});
}
function markPreset(name){document.querySelectorAll('[data-preset]').forEach(b=>b.classList.toggle('active',b.dataset.preset===name));}
function preset(name){
 state.active=new Set((presets[name]||presets.overview).filter(id=>defs.some(d=>d.id===id&&d.status==='ready')));
 const missing=(presets[name]||[]).filter(id=>!defs.some(d=>d.id===id&&d.status==='ready'));if(missing.length)toast('Sin datos preparados para: '+missing.join(', ')+'. Consulta Fuentes.');
 state.street='';$('streetFilter').value='';state.query='';state.business='all';state.heightQuality='all';state.permitYear='all';state.projectState='all';$('projectState').value='all';$('search').value='';$('business').value='all';$('heightQuality').value='all';$('permitYear').value='all';markPreset(name);$('inspector').scrollTop=0;selectedFeature=null;$('featureDetail').innerHTML='<span class="muted">Selecciona un objeto para ver su ficha.</span>';
 if(name==='buildings'){state.three=true;$('threeBtn').setAttribute('aria-pressed','true');map?.easeTo({pitch:55,duration:650});}
 ensureActive();
}
function showFeature(f){
 selectedFeature=f;const p=f.properties,d=defs.find(d=>d.id===p.layer);
 const keys=['evidence_type','zone_code','permitted_use_demo','max_floors_demo','work_state','investment_clp_million','warning','area_ha','density_ha','uncertainty_mean_k','project_state','project_form','project_date','qualification_date','project_type','communes','temp_c','temp_min_c','temp_max_c','surface_date','valid_fraction','valid_pixels','cell_m','native_thermal_m','rubro','calle','CALLE','ESPECIE','NOMBRE_CIENTIFICO','ALTURA','ESTADO_GENERAL','ESTADO_FITOSANITARIO','POTENCIA1','MODELO1','TPOSTE','n_per','prom_edad','n_edad_0_5','n_edad_60_mas','n_hog','AÑO','NUM_PISOS','SUPERFICIE','height','floors','height_quality'];
 const labels={evidence_type:'Tipo de evidencia',zone_code:'Zona ficticia',permitted_use_demo:'Uso de ejemplo',max_floors_demo:'Máximo ficticio (pisos)',work_state:'Etapa simulada',investment_clp_million:'Monto ficticio (millones CLP)',warning:'Alcance de demostración',area_ha:'Área de manzana (ha)',density_ha:'Densidad derivada (hab/ha)',uncertainty_mean_k:'ST_QA medio de píxeles (K)',project_state:'Estado ambiental',project_form:'Ingreso EIA/DIA',project_date:'Fecha de presentación',qualification_date:'Fecha de calificación',project_type:'Tipología',communes:'Comunas declaradas',temp_c:'Superficie media (°C)',temp_min_c:'Mínima (°C)',temp_max_c:'Máxima (°C)',surface_date:'Observación satelital (UTC)',valid_fraction:'Fracción de píxeles válidos',valid_pixels:'Píxeles válidos',cell_m:'Lado de celda (m)',native_thermal_m:'Resolución térmica nativa (m)',height:'Altura cartográfica (m)',floors:'Pisos OSM',height_quality:'Origen de altura',n_per:'Personas (2024)',prom_edad:'Edad promedio',n_edad_0_5:'Personas de 0 a 5',n_edad_60_mas:'Personas de 60+',n_hog:'Hogares','AÑO':'Año del permiso',POTENCIA1:'Potencia (campo fuente)'};
 $('featureDetail').innerHTML=(d.is_demo?'<p class="scope-warning demo"><strong>DEMO · Datos ficticios.</strong> No es información normativa ni una obra real.</p>':'')+'<h3>'+esc(p.name)+'</h3><span class="badge">'+esc(d.name)+'</span><dl>'+keys.filter(k=>p[k]!==undefined&&p[k]!==null).map(k=>'<dt>'+esc(labels[k]||d.field_aliases?.[k]||k)+'</dt><dd>'+esc(p[k])+'</dd>').join('')+'</dl><p>'+esc(d.reference)+' · extracción '+date(d.retrieved_at)+'</p><p>'+esc(d.note)+'</p>'+safeLink(d.url,'Fuente del registro ↗')+(p.source_record_url?'<p>'+safeLink(p.source_record_url,'Expediente oficial del proyecto ↗')+'</p>':'');
 drawSelection();
 if(window.innerWidth<=700){openDialog('Ficha del registro',$('featureDetail').innerHTML);}
}
function openDialog(title,html){$('dialogTitle').textContent=title;$('dialogBody').innerHTML=html;if(!$('dialog').open)$('dialog').showModal();}
function catalogue(){
 const label={ready:'Capa preparada',tabular:'Indicadores disponibles',reference:'Referencia documental',requires_access:'Pendiente de acceso/datos',pending:'Pendiente',unavailable:'No disponible'};
 openDialog('Fuentes, vigencia y alcance','<p>Una capa preparada ha superado comprobaciones técnicas de descarga, formato, identificadores y conteo. <strong>No es una certificación de calidad estadística ni una licencia automática de reutilización.</strong> Las fechas de edición no equivalen al periodo observado. No hay actualización en tiempo real.</p><p>'+esc(manifest.territory.scope)+' · instantánea construida el '+date(manifest.built_at)+'.</p><table><thead><tr><th>CAPA Y ALCANCE</th><th>ORIGEN / REFERENCIA</th><th>ESTADO</th><th>REGISTROS</th></tr></thead><tbody>'+defs.map(d=>'<tr><td><strong>'+esc(d.name)+'</strong><details><summary>Metodología y condiciones</summary><p>'+esc(d.note)+'</p><p>'+esc(d.license||'Condiciones pendientes de verificar.')+'</p><p>Cuenta publicadora: '+esc(d.owner||d.provider)+'. Datos editados: '+date(d.source_edited_at)+'. Extraídos: '+date(d.retrieved_at)+'.</p>'+(d.error?'<p>'+esc(d.error)+'</p>':'')+(d.sha256?'<code>SHA-256 '+esc(d.sha256)+'</code>':'')+'</details></td><td>'+esc(d.provider)+'<br>'+esc(d.reference)+'<br>'+safeLink(d.url)+'</td><td><span class="badge '+(d.is_demo?'demo':d.status)+'">'+(d.is_demo?'DEMO · sintética':label[d.status])+'</span></td><td>'+(d.count===null||d.count===undefined?'—':fmt(d.count))+'</td></tr>').join('')+'</tbody></table>');
}
function table(){openDialog('Registros de la selección','<p>'+fmt(currentRecords.length)+' objetos en el mismo filtro del mapa. Vista previa de los primeros 200; la exportación incluye todos. Las coordenadas representan el objeto, no necesariamente una entrada accesible.</p><table><thead><tr><th>NOMBRE</th><th>CAPA</th><th>RUBRO</th><th>ACCIÓN</th></tr></thead><tbody>'+currentRecords.slice(0,200).map(f=>'<tr><td>'+esc(f.properties.name)+'</td><td>'+esc(defs.find(d=>d.id===f.properties.layer)?.name)+'</td><td>'+esc(f.properties.rubro||'—')+'</td><td><button class="small-btn" data-feature="'+esc(f.id)+'">Ver</button></td></tr>').join('')+'</tbody></table>');$('dialogBody').querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>{const f=currentRecords.find(x=>x.id===b.dataset.feature);if(!f)return;$('dialog').close();showFeature(f);map?.flyTo({center:[f.properties.x,f.properties.y],zoom:16,duration:650});});}
function download(text,type,name){const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);}
function updateStreetOptions(){
 const streets=[...new Set(['commerce','health'].flatMap(id=>(cache.get(id)||[]).map(f=>f.properties.calle).filter(Boolean)))].sort((a,b)=>a.localeCompare(b));
 if(state.street&&!streets.includes(state.street))streets.push(state.street);
 $('streetFilter').innerHTML='<option value="">Todas las calles</option>'+streets.map(x=>'<option value="'+esc(x)+'">'+esc(x)+'</option>').join('');$('streetFilter').value=state.street;
}
function drawSelection(){
 if(!mapReady||!map?.getStyle())return;
 if(!map.getSource('selected-feature')){
  map.addSource('selected-feature',{type:'geojson',data:emptyCollection()});
  map.addLayer({id:'selected-feature-fill',source:'selected-feature',type:'fill',filter:['==',['geometry-type'],'Polygon'],paint:{'fill-color':'#fff4c2','fill-opacity':.17}});
  map.addLayer({id:'selected-feature-line',source:'selected-feature',type:'line',paint:{'line-color':'#fff1ac','line-width':3}});
  map.addLayer({id:'selected-feature-point',source:'selected-feature',type:'circle',filter:['==',['geometry-type'],'Point'],paint:{'circle-radius':9,'circle-color':'rgba(0,0,0,0)','circle-stroke-color':'#fff1ac','circle-stroke-width':3}});
 }
 map.getSource('selected-feature').setData(selectedFeature||emptyCollection());
 for(const id of ['selected-feature-fill','selected-feature-line','selected-feature-point'])map.moveLayer(id);
}
function setRadius(radius){
 state.radius=radius;if(radius&&!state.focus){const c=map?.getCenter();state.focus=c?[c.lng,c.lat]:manifest.territory.center;}
 if(!radius)state.focus=null;
 $('radius').value=String(radius);$('quickRadius').value=String(radius);selectedFeature=null;render();
}
function scopeDescription(){return (state.radius?'Radio '+fmt(state.radius)+' m centrado en '+state.focus.map(v=>v.toFixed(5)).join(', '):'Todo el piloto de Ñuñoa')+(state.query?' · búsqueda: '+state.query:'')+(state.street?' · calle de comercio/salud: '+state.street:'')+' · capas: '+[...state.active].map(id=>defs.find(d=>d.id===id)?.name||id).join(', ');}
function selectionSummary(){return summarize(currentRecords,new Set([...state.active].filter(id=>cache.has(id)&&!errors.has(id))));}
function captureZone(){return {summary:selectionSummary(),scope:scopeDescription(),captured_at:new Date().toISOString()};}
function renderIndicators(){
 $('selectionIndicators').innerHTML=metricsHTML(selectionSummary(),true);
 const demos=defs.filter(d=>d.is_demo&&state.active.has(d.id));$('demoNotice').hidden=!demos.length;
 $('demoNotice').textContent='DEMOSTRACIÓN ACTIVA · '+demos.map(d=>d.name.replace('DEMO · ','')).join(' + ')+'. Datos ficticios, no municipales.';
 $('compareZone').disabled=!savedZone||[...state.active].some(id=>loads.has(id)||errors.has(id));
 $('saveZone').disabled=[...state.active].some(id=>loads.has(id)||errors.has(id))||!currentRecords.length;
 $('saveZone').textContent=savedZone?'✓ Zona A guardada · reemplazar':'＋ Guardar zona A';
 $('consultMode').setAttribute('aria-pressed',String(state.selectionMode==='consult'));
 $('areaMode').setAttribute('aria-pressed',String(state.selectionMode==='area'));
 $('map').classList.toggle('area-mode',state.selectionMode==='area');
}
function analysisDialog(){
 const s=selectionSummary(),partial=[...state.active].some(id=>loads.has(id)||errors.has(id));
 openDialog('Cruzar información del territorio','<p class="analysis-scope">'+esc(scopeDescription())+'</p>'+(partial?'<p class="scope-warning" role="status">Resultado parcial: hay capas cargando o con error. Cierra esta ventana y vuelve a abrirla cuando termine la carga.</p>':'')+'<div id="analysisMetrics" class="analysis-grid">'+metricsHTML(s)+'</div>'+(s.demo?'<p class="scope-warning demo"><strong>'+s.demo+' objetos DEMO en el filtro.</strong> Se excluyen de los indicadores de fuentes públicas de esta ficha.</p>':'')+'<h3>Explora una pregunta</h3><div class="mission-cards"><button data-analysis-mission="public"><b>¿Dónde mirar el espacio público?</b><span>Población, parques, alumbrado y superficie térmica.</span></button><button data-analysis-mission="business"><b>¿Cómo es el entorno comercial?</b><span>Establecimientos OSM, población y transporte.</span></button><button data-analysis-mission="investment"><b>¿Qué hay alrededor de un proyecto?</b><span>SEIA, edificios, permisos históricos y movilidad.</span></button></div><h3>Cómo leer estos cruces</h3><ul><li>La selección radial incluye cada objeto por su punto representativo. Las manzanas y celdas se consideran completas; no se prorratean habitantes.</li><li>Las fuentes tienen fechas y coberturas diferentes. La densidad usa el área de las manzanas con población conocida; no el área del círculo.</li><li>La temperatura es la media aritmética de celdas de una sola escena Landsat. No mide el aire ni el efecto de una intervención.</li><li>Más comercios no implica mayor demanda ni rentabilidad. SEIA aprobado no equivale a obra financiada o en ejecución.</li></ul><div class="actions"><button class="small-btn" id="analysisSave">Guardar esta zona como A</button><button class="small-btn" id="analysisCompare" '+(!savedZone||partial?'disabled':'')+'>Comparar con A</button><button class="small-btn" id="analysisExport" '+(partial?'disabled':'')+'>↓ Ficha JSON</button></div>');
 document.querySelectorAll('[data-analysis-mission]').forEach(b=>b.onclick=()=>{$('dialog').close();mission(b.dataset.analysisMission);});
 $('analysisSave').disabled=partial||!currentRecords.length;$('analysisSave').onclick=()=>{saveZone();$('analysisCompare').disabled=false;$('analysisSave').textContent='✓ Zona A guardada';};
 $('analysisCompare').onclick=compareZones;
 $('analysisExport').onclick=()=>download(JSON.stringify({...captureZone(),methodology:'Indicadores descriptivos de las instantáneas seleccionadas. Manzanas completas; no población exacta del radio. Sin inferencia de rentabilidad.',sources:defs.filter(d=>state.active.has(d.id))},null,2),'application/json','nunoa-ficha-territorial.json');
}
function saveZone(){savedZone=captureZone();renderIndicators();toast('Zona A guardada en esta sesión. Cambia el centro o radio para comparar.');}
function compareZones(){if(!savedZone)return;openDialog('Comparar dos entornos',comparisonHTML(savedZone,captureZone()));}
function mission(name){
 const targets={public:['boundary','census','parks','lights','heat'],business:['boundary','commerce','census','mobility'],investment:['boundary','projects','buildings','permits','mobility']};
 preset('overview');state.active=new Set(targets[name]||targets.public);markPreset(null);state.selectionMode='area';
 if(!state.radius){state.radius=800;const c=map?.getCenter();state.focus=c?[c.lng,c.lat]:manifest.territory.center;}
 $('radius').value=String(state.radius);$('quickRadius').value=String(state.radius);ensureActive();
 toast('Cruce preparado. Haz clic en el mapa para mover la zona de análisis.');
}
async function streetsDialog(){
 if(!state.active.has('commerce'))preset('commerce');
 openDialog('Actividad comercial por calle','<p role="status">Preparando establecimientos y calles…</p>');
 await loadLayer('commerce');
 if(!$('dialog').open||$('dialogTitle').textContent!=='Actividad comercial por calle')return;
 if(errors.has('commerce')){$('dialogBody').innerHTML='<p role="alert">No se pudo cargar comercio. Reintenta desde su capa; no se interpreta el error como cero.</p>';return;}
 const g=streetGroups(currentRecords);
 $('dialogBody').innerHTML='<p>Establecimientos del mismo filtro territorial del mapa, agrupados por la calle declarada en OpenStreetMap. No son patentes municipales ni ventas o flujo peatonal.</p><div class="street-overview"><strong>'+fmt(g.total)+' <span>establecimientos seleccionados</span></strong><strong>'+fmt(g.rows.length)+' <span>calles con registros</span></strong><strong>'+fmt(g.withoutStreet)+' <span>sin calle declarada</span></strong></div><p class="hint">No asignamos por proximidad los registros sin dirección. Variantes escritas de una misma vía pueden aparecer separadas. El filtro de calle afecta únicamente comercios y salud.</p><div class="table-scroll"><table id="streetTable"><thead><tr><th>Calle</th><th>Establecimientos</th><th>Rubros</th><th>Consulta</th></tr></thead><tbody>'+g.rows.map((r,i)=>'<tr><td>'+esc(r.name)+'</td><td><span class="street-bar" style="--bar:'+Math.round(r.count/Math.max(1,g.rows[0].count)*100)+'%"></span>'+fmt(r.count)+'</td><td>'+r.rubros+'</td><td><button class="small-btn" data-street-index="'+i+'">Ver en mapa</button></td></tr>').join('')+'</tbody></table></div>'+(g.rows.length?'':'<p>No hay registros con calle en esta selección.</p>')+'<button class="small-btn" id="streetExport">↓ Resumen CSV</button>';
 document.querySelectorAll('[data-street-index]').forEach(b=>b.onclick=()=>{
  state.street=g.rows[Number(b.dataset.streetIndex)].name;updateStreetOptions();$('dialog').close();render();
  const points=currentRecords.filter(f=>f.properties.layer==='commerce').map(f=>[f.properties.x,f.properties.y]);
  if(points.length&&map){const bounds=points.reduce((b,p)=>b.extend(p),new maplibregl.LngLatBounds(points[0],points[0]));map.fitBounds(bounds,{padding:window.innerWidth>1100?{left:320,right:290,top:130,bottom:120}:70,maxZoom:16,duration:650});}
  toast('Calle seleccionada: '+state.street+'. Puedes quitarla en Mapa y análisis.');
 });
 $('streetExport').onclick=()=>{const q=v=>'"'+String(v).replace(/"/g,'""')+'"';download('\uFEFF'+['calle,establecimientos,rubros,fuente,alcance',...g.rows.map(r=>[r.name,r.count,r.rubros,'OpenStreetMap · instantánea 14 oct 2026','Registros del filtro actual; no catastro exhaustivo'].map(q).join(',')),['SIN CALLE DECLARADA',g.withoutStreet,'','OpenStreetMap','No asignados a ninguna vía'].map(q).join(',')].join('\r\n'),'text/csv;charset=utf-8','nunoa-comercio-por-calle.csv');};
}
function installAnalysisControls(){
 for(const id of ['summaryBtn','decisionBtn','decisionNav','mobileIndicators'])$(id).onclick=analysisDialog;
 $('streetsNav').onclick=streetsDialog;$('saveZone').onclick=saveZone;$('compareZone').onclick=compareZones;
 $('consultMode').onclick=()=>{state.selectionMode='consult';renderIndicators();};
 $('areaMode').onclick=()=>{state.selectionMode='area';if(!state.radius)setRadius(800);else renderIndicators();toast('Haz clic en cualquier punto para analizar su entorno.');};
 document.querySelectorAll('[data-mission]').forEach(b=>b.onclick=()=>mission(b.dataset.mission));
}
function controls(){
 document.querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>preset(b.dataset.preset));
 $('noneBtn').onclick=()=>{state.active.clear();markPreset(null);render();};
 $('allBtn').onclick=()=>{state.active=new Set(defs.filter(d=>d.status==='ready'&&!d.is_demo).map(d=>d.id));markPreset(null);ensureActive();};
 let searchTimer;$('search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{state.query=$('search').value;render();},150);};
 $('clearSearch').onclick=()=>{$('search').value='';state.query='';render();};
 $('radius').onchange=()=>setRadius(Number($('radius').value));
 $('quickRadius').onchange=()=>setRadius(Number($('quickRadius').value));
 $('censusMetric').onchange=()=>{state.censusMetric=$('censusMetric').value;render();};
 $('streetFilter').onchange=()=>{state.street=$('streetFilter').value;render();};
 $('visualMode').onchange=()=>{state.mode=$('visualMode').value;render();};
 $('business').onchange=()=>{state.business=$('business').value;state.active=new Set(['boundary','commerce','health'].filter(id=>defs.some(d=>d.id===id&&d.status==='ready')));markPreset('commerce');ensureActive();};
 $('heightQuality').onchange=()=>{state.heightQuality=$('heightQuality').value;render();};
 $('permitYear').onchange=()=>{state.permitYear=$('permitYear').value;render();};
 $('projectState').onchange=()=>{state.projectState=$('projectState').value;render();};
 $('basemap').onchange=()=>{state.base=$('basemap').value;if(map){mapReady=false;map.setStyle(mapStyle());}};
 $('threeBtn').onclick=()=>{state.three=!state.three;$('threeBtn').setAttribute('aria-pressed',String(state.three));map?.easeTo({pitch:state.three?50:0,duration:600});drawAll();};
 $('homeBtn').onclick=()=>map?.flyTo({center:manifest.territory.center,zoom:13.8,bearing:-12,pitch:state.three?48:0,duration:700});
 $('fullscreenBtn').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.querySelector('.map-stage').requestFullscreen();}catch{toast('Pantalla completa no disponible en este navegador.');}};
 $('clearBtn').onclick=()=>{state.radius=0;state.focus=null;$('radius').value='0';$('quickRadius').value='0';preset('overview');};
 $('exportCsv').onclick=()=>download(csv(currentRecords,defs),'text/csv;charset=utf-8','digital-twin-chile-seleccion.csv');
 $('exportGeo').onclick=()=>download(JSON.stringify({type:'FeatureCollection',features:currentRecords,metadata:{version:VERSION,exported_at:new Date().toISOString(),scope:manifest.territory.scope,method:manifest.methodology,sources:defs.filter(d=>state.active.has(d.id))}}),'application/geo+json','digital-twin-chile-seleccion.geojson');
 $('shareBtn').onclick=async()=>{const link=serialise(state,map);try{await navigator.clipboard.writeText(link);toast('Enlace con tus filtros copiado.');}catch{openDialog('Compartir vista','<p>Copia este enlace:</p><textarea readonly style="width:100%;height:110px">'+esc(link)+'</textarea>');}};
 for(const id of ['sourcesNav','catalogBtn'])$(id).onclick=catalogue;
 $('tableBtn').onclick=table;installAnalysisControls();
 $('aboutBtn').onclick=()=>openDialog('Un piloto, con límites claros','<p>Digital Twin Chile es una infraestructura de inteligencia territorial orientada al bien público. Esta versión contiene un piloto de Ñuñoa, no todas las comunas del país.</p><p>'+esc(manifest.territory.scope)+'.</p><p>Los filtros operan sobre instantáneas locales con fecha y huella digital. No se consultan servicios externos cada vez que marcas una capa. El mapa base sí depende del proveedor cartográfico.</p><p>La visualización 3D usa polígonos y alturas cartográficas OpenMapTiles, con origen OSM, o volúmenes simbólicos de 0,6 metros cuando falta altura. Son partes cartográficas, no edificios únicos; sus alturas no están verificadas como mediciones. No hay terreno 3D calibrado ni simulación física.</p><p>El radio se calcula por punto representativo de cada objeto. No mide recorrido caminable ni reparte habitantes entre sectores. Los conteos de distintas categorías no miden calidad de vida. Las capas opcionales DEMO de zonificación y obras son ficticias y se identifican en mapa, fichas y exportaciones.</p><p>Natalidad y seguridad están disponibles como indicadores comunales, no puntos de hechos. El expediente documental del PRC no valida normativa predial. SEIA no es la cartera completa de inversiones. El calor superficial corresponde a una escena Landsat, no tiempo real. Patentes, flujos horarios y sistemas municipales privados requieren datos o autorización. Las fuentes de terceros conservan sus propias condiciones de uso.</p>');
 $('closeDialog').onclick=()=>$('dialog').close();
 function panel(open){$('explorer').hidden=!open;$('panelBtn').setAttribute('aria-expanded',String(open));}
 $('panelBtn').onclick=()=>panel($('explorer').hidden);$('closePanel').onclick=()=>panel(false);
 $('inspectToggle').onclick=()=>{$('inspectorBody').hidden=!$('inspectorBody').hidden;$('inspectToggle').textContent=$('inspectorBody').hidden?'+':'−';};
}
function restore(){
 const u=new URL(location.href).searchParams;state.active=new Set((u.get('layers')||presets.overview.join(',')).split(',').filter(id=>defs.some(d=>d.id===id&&d.status==='ready')));
 if(u.has('layers')&&!u.get('layers'))state.active.clear();
 state.street=(u.get('street')||'').slice(0,200);state.censusMetric=u.get('censusMetric')==='density'?'density':'persons';$('censusMetric').value=state.censusMetric;
 state.projectState=(u.get('projectState')||'all').slice(0,120);
 state.query=(u.get('q')||'').slice(0,200);$('search').value=state.query;
 const f=(u.get('focus')||'').split(',').map(Number),r=Number(u.get('radius'));
 if(f.length===2&&f.every(Number.isFinite)&&Math.abs(f[0])<=180&&Math.abs(f[1])<85&&[400,800,1500].includes(r)){state.focus=f;state.radius=r;}$('radius').value=String(state.radius);$('quickRadius').value=String(state.radius);
 for(const [param,key,id,values] of [['business','business','business',['all','pharmacy','books','supermarket','cafe','restaurant','convenience','hairdresser']],['base','base','basemap',['satellite','dark','streets']],['mode','mode','visualMode',['points','heat']],['height','heightQuality','heightQuality',['all','known']]])if(values.includes(u.get(param))){state[key]=u.get(param);$(id).value=state[key];}
 if(/^\d{4}$/.test(u.get('year')||''))state.permitYear=u.get('year');state.three=u.get('three')!=='false';$('threeBtn').setAttribute('aria-pressed',String(state.three));
}
async function start(){
 try{
  manifest=await (await fetchTimed('data/manifest.json?v='+VERSION)).json();
  if(!Array.isArray(manifest.datasets)||!manifest.territory)throw Error('Manifiesto no válido.');
  defs=manifest.datasets;defs.forEach(d=>colors[d.id]=d.color);$('datasetCount').textContent=defs.filter(d=>d.status==='ready'&&!d.is_demo).length+' + '+defs.filter(d=>d.is_demo).length;$('snapshotDate').textContent='INSTANTÁNEA / '+date(manifest.built_at);$('provenance').textContent='Fuentes y periodos distintos · consulta el catálogo · '+manifest.territory.scope;
  layerList();restore();controls();if(window.innerWidth<=700){$('explorer').hidden=true;$('panelBtn').setAttribute('aria-expanded','false');}installIndicators({manifest,openDialog,download,safeLink});initMap();ensureActive();
  window.DTC=Object.freeze({version:VERSION,snapshot:()=>({version:VERSION,active:[...state.active],loading:[...loads.keys()].filter(id=>state.active.has(id)),errors:[...errors.keys()].filter(id=>state.active.has(id)),counts:Object.fromEntries([...filtered].map(([k,f])=>[k,f.length])),count:currentRecords.length,records:currentRecords.map(f=>({id:f.id,layer:f.properties.layer,rubro:f.properties.rubro})),radius:state.radius,focus:state.focus,street:state.street,censusMetric:state.censusMetric,selectionMode:state.selectionMode,demoCount:currentRecords.filter(f=>f.properties.evidence_type==='demo').length,projectState:state.projectState,mapReady,base:state.base,mode:state.mode,three:state.three,sourceCount:defs.filter(d=>d.status==='ready').length}),analysisSnapshot:()=>selectionSummary(),streetSnapshot:()=>streetGroups(currentRecords),mapSnapshot:()=>map?{loaded:map.loaded(),pitch:map.getPitch(),renderedCount:mapReady?map.queryRenderedFeatures().filter(f=>f.layer.id.startsWith('dtc-')).length:0,ownLayers:(map.getStyle()?.layers||[]).filter(l=>l.id.startsWith('dtc-')).map(l=>({id:l.id,visibility:map.getLayoutProperty(l.id,'visibility')}))}:null});
 }catch(error){status('No se pudo abrir el catálogo: '+error.message,'error');$('mapFailure').hidden=false;$('mapFailure').textContent='El catálogo o sus archivos no están disponibles. No se sustituyen fuentes fallidas por datos de demostración.';}
}
start();
