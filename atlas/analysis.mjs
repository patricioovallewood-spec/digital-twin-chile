/* Deterministic descriptive analysis of the selected records. No external requests. */
import {normalize,escapeHTML as esc} from './core.mjs?v=060';
const number=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
const fmt=(v,d=0)=>v===null||v===undefined?'Sin dato':Number(v).toLocaleString('es-CL',{maximumFractionDigits:d});
function ringArea(ring){
 let sum=0;const rad=Math.PI/180;
 for(let i=0;i<ring.length-1;i++){
  const a=ring[i],b=ring[i+1];
  sum+=(b[0]-a[0])*rad*(2+Math.sin(a[1]*rad)+Math.sin(b[1]*rad));
 }
 return Math.abs(sum*6371008.8**2/2);
}
export function areaHa(geometry){
 const polys=geometry?.type==='Polygon'?[geometry.coordinates]:geometry?.type==='MultiPolygon'?geometry.coordinates:[];
 return polys.reduce((sum,rings)=>sum+Math.max(0,ringArea(rings[0]||[])-rings.slice(1).reduce((s,r)=>s+ringArea(r),0)),0)/10000;
}
export function enrichCensus(features){return features.map(f=>{
 const area=areaHa(f.geometry),population=f.properties.n_per;
 return {...f,properties:{...f.properties,area_ha:area,density_ha:number(population)&&area>0?population/area:null}};
});}
export function streetGroups(records){
 const groups=new Map();let withoutStreet=0,total=0;
 for(const f of records.filter(f=>f.properties.layer==='commerce')){
  total++;const name=String(f.properties.calle||'').trim(),key=normalize(name);
  if(!name){withoutStreet++;continue;}
  if(!groups.has(key))groups.set(key,{key,name,count:0,rubros:new Set(),ids:[]});
  const g=groups.get(key);g.count++;g.ids.push(f.id);if(f.properties.rubro)g.rubros.add(f.properties.rubro);
 }
 return {total,withoutStreet,rows:[...groups.values()].map(g=>({...g,rubros:g.rubros.size})).sort((a,b)=>b.count-a.count||a.name.localeCompare(b.name))};
}
export function summarize(records,active){
 const by=id=>records.filter(f=>f.properties.layer===id),census=by('census');
 const known=census.filter(f=>number(f.properties.n_per)),area=known.reduce((s,f)=>s+(f.properties.area_ha||areaHa(f.geometry)),0);
 const people=known.length?known.reduce((s,f)=>s+f.properties.n_per,0):null;
 const households=census.filter(f=>number(f.properties.n_hog));
 const temperatures=by('heat').map(f=>f.properties.temp_c).filter(Number.isFinite);
 const heights=by('buildings').map(f=>f.properties.height).filter(v=>Number.isFinite(v)&&v>1);
 const demo=records.filter(f=>f.properties.evidence_type==='demo');
 return {
  population:people,manzanas:known.length,missingPopulation:census.length-known.length,
  households:households.length?households.reduce((s,f)=>s+f.properties.n_hog,0):null,
  density:people!==null&&area>0?people/area:null,
  commerce:active.has('commerce')?by('commerce').length:null,
  lights:active.has('lights')?by('lights').length:null,
  parks:active.has('parks')?by('parks').length:null,
  mobility:active.has('mobility')?by('mobility').length:null,
  projects:active.has('projects')?by('projects').length:null,
  meanHeight:heights.length?heights.reduce((a,b)=>a+b,0)/heights.length:null,
  meanSurface:temperatures.length?temperatures.reduce((a,b)=>a+b,0)/temperatures.length:null,
  thermalCells:temperatures.length,demo:demo.length,
  streets:streetGroups(records),active:[...active]
 };
}
export function metricRows(s){return [
 {key:'population',name:'Personas censadas',value:s.population,detail:s.manzanas+' manzanas completas · Censo 2024'+(s.missingPopulation?' · '+s.missingPopulation+' sin dato':''),unit:''},
 {key:'density',name:'Densidad de manzanas',value:s.density,detail:'Área de manzanas con población conocida',unit:'hab/ha',digits:1},
 {key:'commerce',name:'Comercios registrados',value:s.commerce,detail:'OSM · cobertura colaborativa y no exhaustiva',unit:''},
 {key:'meanSurface',name:'Superficie · media de celdas',value:s.meanSurface,detail:s.thermalCells+' celdas · escena del 15 sep 2026',unit:'°C',digits:1},
 {key:'lights',name:'Puntos de alumbrado',value:s.lights,detail:'Catastro · no informa fallas actuales',unit:''},
 {key:'parks',name:'Parques y plazas registrados',value:s.parks,detail:'OSM · puede incluir instalaciones privadas',unit:''},
 {key:'projects',name:'Proyectos en SEIA',value:s.projects,detail:'Ubicación de referencia · no cartera vigente',unit:''},
 {key:'meanHeight',name:'Altura media cartográfica',value:s.meanHeight,detail:'Media de piezas con altura >1 m; no edificios únicos',unit:'m',digits:1},
 {key:'mobility',name:'Puntos de transporte',value:s.mobility,detail:'OSM · no frecuencia ni accesibilidad caminable',unit:''}
 ];}
export function metricsHTML(s,compact=false){
 const available=metricRows(s).filter(r=>r.value!==null);
 return available.length?(compact?available.slice(0,4):available).map(r=>'<article class="metric-card" data-metric="'+r.key+'"><span>'+esc(r.name)+'</span><strong>'+fmt(r.value,r.digits)+' <small>'+esc(r.unit)+'</small></strong><p>'+esc(r.detail)+'</p></article>').join(''):'<p class="hint">Activa población, comercio, áreas verdes, edificios o infraestructura para consultar indicadores.</p>';
}
export function comparisonHTML(a,b){return '<div class="scope-warning">Comparación descriptiva de los dos filtros guardados. Revisa sus radios y capas: las coberturas pueden ser distintas. No es una evaluación de rentabilidad ni causalidad.</div><table id="comparisonTable"><thead><tr><th>Indicador</th><th>Zona A</th><th>Zona actual</th></tr></thead><tbody>'+metricRows(a.summary).map(r=>{const other=metricRows(b.summary).find(x=>x.key===r.key);return '<tr><td>'+esc(r.name)+' '+esc(r.unit)+'</td><td>'+fmt(r.value,r.digits)+'</td><td>'+fmt(other.value,other.digits)+'</td></tr>';}).join('')+'</tbody></table><p><strong>Zona A:</strong> '+esc(a.scope)+'<br><strong>Zona actual:</strong> '+esc(b.scope)+'</p>';}
