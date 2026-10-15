import {escapeHTML as esc} from './core.mjs?v=061';

export function installEntrepreneurship({openDialog,download}) {
 const $=id=>document.getElementById(id), fmt=n=>Number(n).toLocaleString('es-CL');
 let cache=null;
 const pct=(a,b)=>b?((a/b)*100).toLocaleString('es-CL',{maximumFractionDigits:1})+'%':'—';
 function bars(rows,labelKey='category',valueKey='profiles'){
   const max=Math.max(1,...rows.map(r=>Number(r[valueKey])||0));
   return '<div class="eco-bars">'+rows.map(r=>'<div class="eco-bar-row"><span>'+esc(r[labelKey])+'</span><div><i style="--w:'+Math.round((Number(r[valueKey])||0)/max*100)+'%"></i></div><b>'+fmt(r[valueKey])+'</b></div>').join('')+'</div>';
 }
 async function load(){
   if(cache)return cache;
   const r=await fetch('data/entrepreneurship-aggregate.json?v=061'); if(!r.ok)throw Error('HTTP '+r.status);
   const d=await r.json(); if(d.type!=='AggregateEntrepreneurshipProfile'||d.privacy?.contains_personal_data!==false)throw Error('El archivo agregado no cumple el contrato de privacidad.');
   cache=d; return d;
 }
 function exportSummary(d){
   const rows=[['indicador','valor'],['Perfiles únicos',d.kpis.unique_profiles],['Participaciones en programas',d.kpis.program_memberships],['Perfiles con residencia declarada en Providencia',d.kpis.providencia_profiles],['Perfiles presentes en 2 o más programas',d.kpis.multi_program_profiles],['Perfiles presentes en los 3 programas',d.kpis.three_program_profiles],['Mediana de edad conocida',d.kpis.median_age_known]];
   const q=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
   download('\uFEFF'+rows.map(r=>r.map(q).join(',')).join('\r\n'),'text/csv;charset=utf-8','providencia-ecosistema-emprendedor-resumen.csv');
 }
 async function show(){
   openDialog('Ecosistema emprendedor · Providencia','<p role="status">Preparando indicadores anonimizados…</p>');
   try{
    const d=await load();
    const knownAge=d.kpis.unique_profiles-d.age_bands.find(x=>x.category==='Sin dato').profiles;
    const knownEdu=d.kpis.unique_profiles-d.education.find(x=>x.category==='Sin dato').profiles;
    const female=d.gender_explicit_socios.find(x=>x.category==='Femenino')?.profiles||0;
    const genderTotal=d.gender_explicit_socios.reduce((a,b)=>a+b.profiles,0);
    openDialog('Ecosistema emprendedor · Providencia',
      '<p class="scope-warning"><strong>Vista agregada y anonimizada.</strong> Este módulo no contiene RUT, nombres, teléfonos, correos ni domicilios particulares. Tampoco dibuja personas en el mapa.</p>'+
      '<div class="eco-kpis">'+
        '<article><strong>'+fmt(d.kpis.unique_profiles)+'</strong><span>perfiles únicos</span><small>deduplicados entre 3 bases</small></article>'+
        '<article><strong>'+fmt(d.kpis.providencia_profiles)+'</strong><span>declaran Providencia</span><small>'+pct(d.kpis.providencia_profiles,d.kpis.unique_profiles)+' del universo único</small></article>'+
        '<article><strong>'+fmt(d.kpis.multi_program_profiles)+'</strong><span>están en 2+ programas</span><small>'+pct(d.kpis.multi_program_profiles,d.kpis.unique_profiles)+' · señal de continuidad</small></article>'+
        '<article><strong>'+fmt(d.kpis.median_age_known)+'</strong><span>años · mediana conocida</span><small>'+fmt(knownAge)+' perfiles con edad</small></article>'+
      '</div>'+
      '<div class="eco-grid">'+
        '<section class="eco-card"><div class="eyebrow">ALCANCE PROGRAMÁTICO</div><h3>Participación por programa</h3>'+bars(d.programs,'name','unique_profiles')+'<p class="hint">Una misma persona puede aparecer en más de un programa.</p></section>'+
        '<section class="eco-card"><div class="eyebrow">CONTINUIDAD</div><h3>¿Cuántos programas toca cada perfil?</h3>'+bars(d.participation,'program_count','profiles').replace(/>1</g,'>1 programa<').replace(/>2</g,'>2 programas<').replace(/>3</g,'>3 programas<')+'<p class="hint">'+fmt(d.kpis.three_program_profiles)+' perfiles aparecen en las tres bases.</p></section>'+
        '<section class="eco-card"><div class="eyebrow">EDAD</div><h3>Distribución etaria</h3>'+bars(d.age_bands)+'<p class="hint">Edad calculada al '+esc(d.reference_date)+' cuando existe fecha de nacimiento.</p></section>'+
        '<section class="eco-card"><div class="eyebrow">FORMACIÓN</div><h3>Nivel educacional homologado</h3>'+bars(d.education)+'<p class="hint">'+fmt(knownEdu)+' perfiles tienen información educacional interpretable; homologación exploratoria.</p></section>'+
        '<section class="eco-card"><div class="eyebrow">GÉNERO · CAMPO EXPLÍCITO</div><h3>Base Socios</h3>'+bars(d.gender_explicit_socios)+'<p class="hint">'+pct(female,genderTotal)+' de los perfiles únicos de Socios con campo explícito corresponden a femenino. No se infiere género desde otros programas.</p></section>'+
        '<section class="eco-card"><div class="eyebrow">CAPITAL HUMANO</div><h3>Profesiones/oficios más frecuentes</h3>'+bars(d.top_professions,'profession','profiles')+'<p class="hint">Texto libre sin diccionario ocupacional oficial; solo se muestran grupos con 10+ registros.</p></section>'+
      '</div>'+
      '<section class="eco-card eco-wide"><div class="eyebrow">LECTURA PARA DECIDIR</div><h3>Qué empieza a revelar esta base</h3><div class="eco-insights"><article><b>Programas conectados</b><p>'+fmt(d.kpis.multi_program_profiles)+' personas aparecen en más de una iniciativa. Esto permite medir continuidad y diseñar rutas de acompañamiento, no solo actividades aisladas.</p></article><article><b>Brecha de información</b><p>'+fmt(d.residence.find(x=>x.category==='Sin dato').profiles)+' perfiles no tienen comuna utilizable y '+fmt(d.age_bands.find(x=>x.category==='Sin dato').profiles)+' no tienen fecha suficiente para edad. La calidad del dato se vuelve un problema de gestión visible.</p></article><article><b>Siguiente salto territorial</b><p>Para mapear el ecosistema debemos recibir una geografía autorizada y publicar solo agregados con umbral mínimo. No usaremos domicilios particulares como puntos públicos.</p></article></div></section>'+
      '<h3>Solapamiento entre programas</h3>'+bars(d.overlap,'combination','profiles')+
      '<details class="eco-method"><summary>Metodología y privacidad</summary><ul>'+d.interpretation_notes.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><p><strong>Campos excluidos del producto público:</strong> '+d.privacy.excluded_fields.map(esc).join(', ')+'.</p><p>Umbral de diseño para futuros agregados territoriales: '+fmt(d.privacy.minimum_public_group_size)+' o más casos por grupo.</p></details>'+
      '<div class="actions"><button class="small-btn" id="ecoExport">↓ Resumen CSV</button></div>'
    );
    $('ecoExport').onclick=()=>exportSummary(d);
   }catch(e){openDialog('Ecosistema emprendedor · Providencia','<p role="alert">No se pudo abrir el agregado anonimizado: '+esc(e.message)+'. No se sustituye por datos inventados.</p>');}
 }
 const nav=$('entrepreneurNav'); if(nav)nav.onclick=show;
 return {show};
}