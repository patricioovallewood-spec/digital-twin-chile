/* Non-spatial observations must never be counted or located as map objects. */
import {escapeHTML as esc} from './core.mjs';
export function installIndicators({manifest,openDialog,download,safeLink}) {
 const $=id=>document.getElementById(id),cache=new Map();
 const find=id=>manifest.datasets.find(x=>x.id===id);
 const labels={ready:'Capa preparada',tabular:'Indicadores disponibles',reference:'Referencia documental',requires_access:'Requiere datos o autorización',pending:'Pendiente',unavailable:'No disponible'};
 let dialogGeneration=0;
 async function read(d) {
  if(cache.has(d.id))return cache.get(d.id);
  const c=new AbortController(),timer=setTimeout(()=>c.abort(),20000);
  try {
   const r=await fetch(d.path+'?sha='+d.sha256.slice(0,12),{signal:c.signal});if(!r.ok)throw Error('HTTP '+r.status);
   const b=await r.arrayBuffer();if(crypto.subtle){const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',b))).map(v=>v.toString(16).padStart(2,'0')).join('');if(hash!==d.sha256)throw Error('La versión de datos no coincide con el catálogo.');}
   const data=JSON.parse(new TextDecoder().decode(b));cache.set(d.id,data);return data;
  }finally{clearTimeout(timer);}
 }
 function menu(current){return '<div class="indicator-tabs" role="group" aria-label="Secciones de información"><button class="small-btn '+(current==='births'?'selected':'')+'" data-indicator="births">Natalidad y mortalidad</button><button class="small-btn '+(current==='crime'?'selected':'')+'" data-indicator="crime">Seguridad</button><button class="small-btn" data-indicator="zoning">Plan regulador</button><button class="small-btn" data-indicator="dependencies">Accesos pendientes</button></div>';}
 function wire(){document.querySelectorAll('[data-indicator]').forEach(b=>b.onclick=()=>show(b.dataset.indicator));}
 function exportRows(rows){const q=v=>'"'+String(v??'').replace(/"/g,'""')+'"';const cols=['label','year','territory','value','unit','source_url','report_year'];download('\uFEFF'+cols.map(q).join(',')+'\r\n'+rows.map(r=>cols.map(c=>q(r[c])).join(',')).join('\r\n'),'text/csv;charset=utf-8','nunoa-indicadores-comunales.csv');}
 async function show(id='births'){
  const own=++dialogGeneration;
  if(id==='dependencies'){
   openDialog('Lo que todavía requiere acceso',menu(id)+'<p>No hay conexiones privadas activas. Las capas opcionales DEMO del mapa son sintéticas y no resuelven estas dependencias institucionales.</p>'+['licenses','pedestrians','municipal'].map(k=>{const d=find(k);return '<article class="evidence-card"><h3>'+esc(d.name)+'</h3><span class="badge">'+esc(labels[d.status]||d.status)+'</span><p>'+esc(d.note)+'</p>'+safeLink(d.url)+'</article>';}).join('')+'<h3>Ruta de integración preparada conceptualmente</h3><div class="integration-flow"><div><b>01 · Autorizar</b><span>Acordar finalidad, campos publicables, cobertura y responsable municipal.</span></div><div><b>02 · Validar</b><span>Adaptador de solo lectura en servidor. Comprobar geometría, fechas, IDs y calidad.</span></div><div><b>03 · Versionar</b><span>Publicar una instantánea aprobada y conservar la última válida ante errores.</span></div></div><p><strong>Estado: sin conexión.</strong> No hay endpoint municipal operativo ni credenciales guardadas. El contrato es conceptual.</p><p><a href="integration-contract.json" download="contrato-integracion-municipal.json">Descargar contrato conceptual JSON ↓</a></p><p>Un archivo público no autoriza a publicar datos personales. Las integraciones futuras deben acordar campos permitidos, finalidad, periodo, cobertura y control de acceso.</p>');wire();return;
  }
  const d=find(id);if(!d)return;
  openDialog(d.name,menu(id)+'<p role="status">Cargando datos documentados…</p>');wire();
  if(!['tabular','reference'].includes(d.status)){openDialog(d.name,menu(id)+'<p>'+esc(d.note)+'</p>');wire();return;}
  try{
   const data=await read(d);if(own!==dialogGeneration||!$('dialog').open)return;
   if(data.type==='ReferenceDossier'){
    openDialog(d.name,menu(id)+'<p class="scope-warning"><strong>Consulta documental, no zonificación predial validada.</strong> El mapa no deduce usos permitidos, alturas ni constructibilidad a partir de estos enlaces.</p><p>'+esc(d.reference)+' · '+safeLink(d.url,'Página municipal de origen ↗')+'</p>'+(data.notes||[]).map(n=>'<p>'+esc(n)+'</p>').join('')+'<div class="document-list">'+data.documents.map(x=>'<article><h3>'+esc(x.title)+'</h3>'+safeLink(x.url,'Consultar documento en el municipio ↗')+'</article>').join('')+'</div>');wire();return;
   }
   if(data.type!=='IndicatorTable'||!Array.isArray(data.rows)||data.rows.length!==d.count)throw Error('Tabla no válida.');
   const indicators=[...new Map(data.rows.map(r=>[r.indicator,r.label])).entries()];
   openDialog(d.name,menu(id)+'<p class="scope-warning"><strong>Escala comunal, regional y país.</strong> Estos valores no se localizan por calle y no cambian al modificar el radio del mapa.</p><p>'+esc(d.reference)+' · '+esc(d.provider)+'</p><div class="indicator-controls"><label>Indicador<select id="indicatorChoice">'+indicators.map(([k,v])=>'<option value="'+esc(k)+'">'+esc(v)+'</option>').join('')+'</select></label><label>Año<select id="indicatorYear"><option value="all">Todos los disponibles</option></select></label><button class="small-btn" id="indicatorExport">↓ CSV de esta tabla</button></div><div id="indicatorResults"></div><div class="indicator-notes">'+(data.notes||[]).map(n=>'<p>'+esc(n)+'</p>').join('')+'</div>');wire();
   let selectedRows=[];
   function render(rebuildYears=false){const id=$('indicatorChoice').value;const all=data.rows.filter(r=>r.indicator===id);if(rebuildYears){const years=[...new Set(all.map(x=>x.year))].sort((a,b)=>b-a);$('indicatorYear').innerHTML='<option value="all">Todos los disponibles</option>'+years.map(y=>'<option>'+y+'</option>').join('');}
    const year=$('indicatorYear').value;selectedRows=all.filter(r=>year==='all'||String(r.year)===year).sort((a,b)=>b.year-a.year||a.territory.localeCompare(b.territory));
    $('indicatorResults').innerHTML='<p><strong>Unidad:</strong> '+esc(all[0]?.unit||'')+'. '+selectedRows.length+' observaciones; no se suman tasas entre años o territorios.</p><table id="indicatorTable"><thead><tr><th>Año observado</th><th>Territorio</th><th>Valor</th><th>Fuente</th></tr></thead><tbody>'+selectedRows.map(r=>'<tr><td>'+r.year+'</td><td>'+esc(r.territory)+'</td><td>'+Number(r.value).toLocaleString('es-CL',{maximumFractionDigits:2})+'</td><td>'+safeLink(r.source_url,'BCN · reporte '+r.report_year+' ↗')+'</td></tr>').join('')+'</tbody></table>';
   }
   $('indicatorChoice').onchange=()=>render(true);$('indicatorYear').onchange=()=>render();$('indicatorExport').onclick=()=>exportRows(selectedRows);render(true);
  }catch(e){if(own===dialogGeneration){openDialog(d.name,menu(id)+'<p role="alert">No se pudo cargar esta tabla: '+esc(e.message)+'. La ausencia de respuesta no equivale a cero.</p>');wire();}}
 }
 $('indicatorsNav').onclick=()=>show('births');$('securityNav').onclick=()=>show('crime');$('zoningNav').onclick=()=>show('zoning');$('integrationNav').onclick=()=>show('dependencies');
 return {show};
}
