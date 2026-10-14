/* Digital Twin Chile 0.3.1. No synthetic records are used by this application. */
'use strict';
(async function () {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  // If the primary CDN failed, recover instead of leaving inert filter controls.
  if (!window.L) {
    try {
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        const timer = setTimeout(() => reject(Error('Tiempo de espera del mapa agotado.')), 12000);
        script.src = 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js';
        script.onload = () => { clearTimeout(timer); resolve(); };
        script.onerror = () => { clearTimeout(timer); reject(Error('No se pudo cargar la biblioteca del mapa.')); };
        document.head.appendChild(script);
      });
    } catch (error) {
      $('mapstatus').textContent = error.message + ' Comprueba la conexión y recarga la página.';
      $('layers').textContent = 'Filtros no disponibles: no se pudo cargar el mapa.';
      return;
    }
  }
  const locations = {
    chile:{label:'Chile · Vista nacional',center:[-33.4,-70.66],zoom:5},
    santiago:{label:'Santiago',center:[-33.4489,-70.6693],zoom:15},
    providencia:{label:'Providencia',center:[-33.428,-70.612],zoom:15},
    nunoa:{label:'Ñuñoa',center:[-33.456,-70.597],zoom:15},
    valparaiso:{label:'Valparaíso',center:[-33.0458,-71.6197],zoom:15},
    vina:{label:'Viña del Mar',center:[-33.0245,-71.5518],zoom:15},
    concepcion:{label:'Concepción',center:[-36.8269,-73.0498],zoom:15},
    antofagasta:{label:'Antofagasta',center:[-23.65,-70.4],zoom:15},
    temuco:{label:'Temuco',center:[-38.7359,-72.5904],zoom:15},
    puertomontt:{label:'Puerto Montt',center:[-41.4693,-72.9424],zoom:15},
    miraflores:{label:'Miraflores · Perú',center:[-12.121,-77.03],zoom:15}
  };
  const defs = [
    {id:'parks',label:'Parques y áreas verdes',tag:'["leisure"~"^(park|garden|playground)$"]',color:'#2b9c78',test:t=>['park','garden','playground'].includes(t.leisure)},
    {id:'health',label:'Salud',tag:'["amenity"~"^(hospital|clinic|doctors|pharmacy)$"]',color:'#e0716c',test:t=>['hospital','clinic','doctors','pharmacy'].includes(t.amenity)},
    {id:'education',label:'Educación',tag:'["amenity"~"^(school|university|college|kindergarten)$"]',color:'#d5a142',test:t=>['school','university','college','kindergarten'].includes(t.amenity)},
    {id:'commerce',label:'Comercio y servicios',tag:'["shop"]',color:'#5679c7',test:t=>!!t.shop},
    {id:'sports',label:'Deporte y recreación',tag:'["leisure"~"^(sports_centre|pitch|swimming_pool)$"]',color:'#a36ec6',test:t=>['sports_centre','pitch','swimming_pool'].includes(t.leisure)},
    {id:'culture',label:'Cultura y comunidad',tag:'["amenity"~"^(library|community_centre|arts_centre|theatre)$"]',color:'#d17d43',test:t=>['library','community_centre','arts_centre','theatre'].includes(t.amenity)},
    {id:'cycling',label:'Ciclovías',tag:'["highway"="cycleway"]',color:'#159caa',test:t=>t.highway==='cycleway'}
  ];
  const LIMIT = 450, CACHE_MS = 300000, MAX_RADIUS = 1500;
  const endpoints = ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter'];
  const map = L.map('map', {zoomControl:false}).setView(locations.santiago.center, 15);
  L.control.zoom({position:'bottomright'}).addTo(map);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:19, attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
  const markers = L.layerGroup().addTo(map);
  let focus = null, circle = null, boundary = null, searchMarker = null;
  let scope = null, worker = null, moveTimer = null, lastRequest = 0, geoBusy = false, lastGeo = 0;
  let rows = [], lastDraw = '', navigation = 0;
  const scopes = new Map(), geoCache = new Map();
  const stateFor = id => scope?.layers.get(id);
  const selected = () => defs.filter(d => $('layer-'+d.id).checked);
  const radius = () => Number($('radius').value);
  const pretty = n => n.toLocaleString('es-CL');
  const validPoint = (lat, lon) => Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat)<=90 && Math.abs(lon)<=180;

  // Visible feedback sits next to the controls, not below a long scrolled panel.
  const style = document.createElement('style');
  style.textContent = '.layer.is-active{border-color:#62c2a8;background:#173e45}.layer small{min-width:35px;text-align:right}.layer input{width:17px;height:17px;flex:none}.filter-feedback{margin:12px 0;padding:12px;border:1px solid #44636b;border-radius:7px;color:#dbecea;font-size:12px;line-height:1.55}.filter-feedback[data-state="error"]{border-color:#eb9b66;background:#452c28;color:#ffe4c6}.filter-feedback[data-state="loading"]{border-color:#87cabc}.filter-toolbar{display:flex;gap:7px;margin-bottom:9px}.filter-toolbar button{flex:1;font-size:11px;padding:8px;background:#193e49;color:#e6f5f1;border:1px solid #486b74;border-radius:5px;cursor:pointer}.map-notice{padding:10px 16px;background:#e5f4ee;color:#245449;font-size:12px;line-height:1.5;border-bottom:1px solid #cfe4dc}.map-notice[data-state="error"]{background:#fff0e0;color:#844417}.layer small[data-state="error"]{color:#ffc495}.searchrow button:disabled{opacity:.55}.analysis-config .searchfeedback{font-size:11px}.insights .eyebrow{color:#287761}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #e9bb53;outline-offset:3px}.filter-feedback a{color:#b0f1de}';
  document.head.appendChild(style);
  $('layers').innerHTML = defs.map(d => '<label class="layer" id="label-'+d.id+'"><input id="layer-'+d.id+'" type="checkbox" value="'+d.id+'"><span>'+d.label+'</span><small id="status-'+d.id+'">—</small></label>').join('');
  $('layers').insertAdjacentHTML('beforebegin','<div class="filter-toolbar"><button id="allLayers" type="button">Todas</button><button id="noLayers" type="button">Ninguna</button></div><div id="filterFeedback" class="filter-feedback" role="status" aria-live="polite"></div>');
  $('map').insertAdjacentHTML('beforebegin','<div id="mapNotice" class="map-notice" role="status"></div>');
  document.querySelector('.brand small').textContent = 'CHILE / BETA 0.3.1';
  $('clock').textContent = new Intl.DateTimeFormat('es-CL',{day:'2-digit',month:'short',year:'numeric'}).format(new Date());
  $('place').insertAdjacentHTML('beforeend','<option value="custom">Vista personalizada</option>');
  $('place').value = 'santiago';
  $('layer-parks').checked = true;
  document.querySelector('.analysis-config .searchfeedback').textContent = 'Cambia el radio para filtrar los puntos. Sin punto seleccionado se usa el centro del mapa. También puedes hacer clic en otro lugar. Distancia en línea recta, no caminata.';
  document.querySelector('.method-note').textContent = 'Registros OSM disponibles, hasta 450 por categoría y consulta. El mapa, los conteos y el CSV usan el mismo filtro. No son totales oficiales ni un catastro exhaustivo. Ciclovías y polígonos se representan por su centro.';
  $('selection').textContent = 'Vista inicial: entorno de Santiago. Selecciona categorías o un radio para filtrar.';

  function notice(text, kind='ready') {
    for (const id of ['filterFeedback','mapNotice']) { $(id).textContent=text; $(id).dataset.state=kind; }
    $('mapstatus').textContent=text;
  }
  function scopeSpec() {
    if (focus) {
      const lat=focus.lat.toFixed(5),lon=focus.lng.toFixed(5);
      return {key:'circle:'+lat+','+lon, query:'(around:'+MAX_RADIUS+','+lat+','+lon+')'};
    }
    const b=map.getBounds();
    if (map.getZoom()<14 || map.distance(b.getSouthWest(),b.getNorthEast())>12000) return null;
    const bbox=[b.getSouth(),b.getWest(),b.getNorth(),b.getEast()].map(v=>v.toFixed(5)).join(',');
    return {key:'view:'+bbox,query:'('+bbox+')'};
  }
  function drawCircle(fit=false) {
    if(circle){map.removeLayer(circle);circle=null;}
    if(focus){circle=L.circle(focus,{radius:radius(),color:'#12a789',weight:2,fillOpacity:.08,interactive:false}).addTo(map);if(fit)map.fitBounds(circle.getBounds(),{padding:[22,22],animate:false,maxZoom:17});}
  }
  function changeScope(force=false) {
    clearTimeout(moveTimer);
    const spec=scopeSpec();
    if (!spec) {
      if(worker)worker.controller.abort();scope=null;render();return;
    }
    const old=scopes.get(spec.key);
    const expired=old && Date.now()-old.created>CACHE_MS;
    if(!force && !expired && scope?.key===spec.key){render();pump();return;}
    if(worker)worker.controller.abort();
    if(force || expired || !old) {
      scope={...spec,created:Date.now(),layers:new Map(defs.map(d=>[d.id,{status:'idle',rows:[],error:'',limited:false}]))};
      scopes.set(spec.key,scope);
      while(scopes.size>8)scopes.delete(scopes.keys().next().value);
    }else scope=old;
    render();pump();
  }
  function filteredRows() {
    const unique=new Map();
    for(const d of selected()){
      const bucket=stateFor(d.id);
      if(bucket?.status!=='ready')continue;
      for(const p of bucket.rows){
        if(focus ? map.distance(focus,[p.lat,p.lon])>radius() : !map.getBounds().contains([p.lat,p.lon]))continue;
        if(!unique.has(p.id))unique.set(p.id,{...p,categories:[],color:d.color});
        unique.get(p.id).categories.push(d.label);
      }
    }
    return Array.from(unique.values());
  }
  function render() {
    const active=selected(); rows=filteredRows();
    const ready=active.filter(d=>stateFor(d.id)?.status==='ready');
    const failed=active.filter(d=>stateFor(d.id)?.status==='error');
    const pending=active.filter(d=>['idle','loading'].includes(stateFor(d.id)?.status));
    const limited=ready.some(d=>stateFor(d.id).limited);
    $('activeCount').textContent=String(active.length);
    $('count').textContent=ready.length || !active.length ? pretty(rows.length) : '—';
    $('countlabel').textContent=focus?'Registros filtrados dentro de '+pretty(radius())+' m':'Registros de las capas activas en esta vista';
    $('areaName').textContent=(locations[$('place').value]?.label || 'Vista personalizada')+' · '+(focus?'radio de '+pretty(radius())+' m':'área visible, no total comunal');
    for(const d of defs){
      const bucket=stateFor(d.id),checked=$('layer-'+d.id).checked;
      const count=rows.filter(p=>p.categories.includes(d.label)).length;
      $('label-'+d.id).classList.toggle('is-active',checked);
      $('status-'+d.id).textContent=!checked?'—':bucket?.status==='ready'?pretty(count):bucket?.status==='error'?'Error':scope?'…':'Zoom';
      $('status-'+d.id).dataset.state=bucket?.status || 'idle';
      $('status-'+d.id).title=bucket?.error || (bucket?.limited?'Consulta limitada a 450 registros':'Registros visibles de esta categoría');
    }
    const signature=JSON.stringify(rows.map(p=>[p.id,p.categories]));
    if(signature!==lastDraw){
      markers.clearLayers();
      for(const p of rows){
        L.circleMarker([p.lat,p.lon],{radius:6,color:'#fff',weight:1.5,fillColor:p.color,fillOpacity:.95,className:'dtc-record',bubblingMouseEvents:false})
          .bindPopup('<strong>'+esc(p.name)+'</strong><br>'+esc(p.categories.join(' · '))+'<br><small>OpenStreetMap · '+esc(p.id)+'</small>')
          .addTo(markers);
      }
      lastDraw=signature;
    }
    const scopeText=focus?'dentro del radio de '+pretty(radius())+' m':'en el área visible';
    if(!active.length)notice('No hay categorías activas. Marca una o pulsa «Todas».','empty');
    else if(!scope)notice('Acerca el mapa para cargar datos, o elige un radio. La vista nacional no descarga todo Chile.','zoom');
    else if(failed.length)notice('No se pudieron cargar: '+failed.map(d=>d.label).join(', ')+'. '+(ready.length?'Se conservan las otras capas. ':'')+'Pulsa «Actualizar datos» para reintentar.','error');
    else if(pending.length)notice('Cargando '+pending.map(d=>d.label).join(', ')+'… '+(ready.length?pretty(rows.length)+' registros ya disponibles.':'La primera consulta puede tardar unos segundos.'),'loading');
    else notice(pretty(rows.length)+' registros '+scopeText+'. '+(limited?'Resultado parcial: límite alcanzado en alguna categoría.':'Fuente: OpenStreetMap; cobertura no exhaustiva.'),'ready');
    $('map').setAttribute('aria-busy',String(pending.length>0));
    $('exportCsv').disabled=!rows.length;
    $('analysisNote').textContent=ready.length?pretty(rows.length)+' registros '+scopeText+'.'+(pending.length||failed.length||limited?' Resultado parcial.':''):'Activa categorías y espera su carga para analizar.';
    const max=Math.max(1,...defs.map(d=>rows.filter(p=>p.categories.includes(d.label)).length));
    $('breakdown').innerHTML=active.map(d=>{
      const bucket=stateFor(d.id),n=rows.filter(p=>p.categories.includes(d.label)).length;
      const value=bucket?.status==='ready'?String(n):bucket?.status==='error'?'Sin conexión':'Pendiente';
      return '<div class="breakrow"><div><span>'+d.label+'</span><b>'+value+'</b></div><div class="bartrack"><span style="width:'+(100*n/max)+'%;background:'+d.color+'"></span></div></div>';
    }).join('');
  }
  async function fetchJSON(url,signal,timeout=26000){
    const controller=new AbortController();
    const abort=()=>controller.abort();
    if(signal?.aborted)throw new DOMException('Cancelled','AbortError');
    signal?.addEventListener('abort',abort,{once:true});
    const timer=setTimeout(()=>controller.abort(),timeout);
    try{
      const response=await fetch(url,{signal:controller.signal,headers:{Accept:'application/json'}});
      if(!response.ok){const error=Error('HTTP '+response.status);error.status=response.status;throw error;}
      return await response.json();
    }catch(error){
      if(signal?.aborted)throw new DOMException('Cancelled','AbortError');
      if(error.name==='AbortError')throw Error('La fuente no respondió a tiempo.');
      throw error;
    }finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}
  }
  async function queryLayer(d,current,signal){
    const query='[out:json][timeout:20];nwr'+d.tag+current.query+';out center '+LIMIT+';';
    let lastError;
    for(const endpoint of endpoints){
      await pause(Math.max(0,1200-(Date.now()-lastRequest)));
      if(signal.aborted)throw new DOMException('Cancelled','AbortError');
      lastRequest=Date.now();
      try{
        const json=await fetchJSON(endpoint+'?'+new URLSearchParams({data:query}),signal);
        if(json.remark || !Array.isArray(json.elements))throw Error(json.remark || 'Respuesta no válida de la fuente.');
        const points=json.elements.flatMap(el=>{
          const lat=Number(el.lat ?? el.center?.lat),lon=Number(el.lon ?? el.center?.lon),tags=el.tags||{};
          if(!validPoint(lat,lon)||!d.test(tags))return [];
          return [{id:el.type+'/'+el.id,name:tags.name||'Sin nombre registrado',lat,lon}];
        });
        return {status:'ready',rows:points,limited:json.elements.length>=LIMIT,error:'',retrieved:new Date().toISOString(),sourceTimestamp:json.osm3s?.timestamp_osm_base||null};
      }catch(error){
        if(signal.aborted)throw error;
        lastError=error;
        // Respect rate limiting: do not evade HTTP 429 by switching server.
        if(error.status===429 || error.status===400)break;
      }
    }
    throw lastError || Error('Fuente no disponible.');
  }
  async function pump(){
    if(worker || !scope)return;
    const current=scope;
    const task={scope:current,controller:new AbortController()};worker=task;
    try{
      while(scope===current && !task.controller.signal.aborted){
        const d=selected().find(d=>current.layers.get(d.id).status==='idle');
        if(!d)break;
        const bucket=current.layers.get(d.id);bucket.status='loading';render();
        try{
          const result=await queryLayer(d,current,task.controller.signal);
          if(scope!==current || task.controller.signal.aborted){bucket.status='idle';break;}
          current.layers.set(d.id,result);
        }catch(error){
          if(task.controller.signal.aborted){bucket.status='idle';break;}
          bucket.status='error';bucket.error=error.message;
        }
        if(scope===current)render();
      }
    }finally{
      if(worker===task)worker=null;
      if(scope && selected().some(d=>stateFor(d.id)?.status==='idle'))void pump();
    }
  }
  function filtersChanged(){render();pump();}
  $('layers').addEventListener('change',filtersChanged);
  $('allLayers').onclick=()=>{defs.forEach(d=>$('layer-'+d.id).checked=true);filtersChanged();};
  $('noLayers').onclick=()=>{defs.forEach(d=>$('layer-'+d.id).checked=false);filtersChanged();};
  $('refresh').onclick=()=>changeScope(true);
  map.on('moveend',()=>{clearTimeout(moveTimer);if(focus){render();return;}moveTimer=setTimeout(()=>changeScope(),450);});
  function selectPoint(point,fit){focus=L.latLng(point);drawCircle(fit);$('selection').textContent='Centro del análisis: '+focus.lat.toFixed(5)+', '+focus.lng.toFixed(5)+'. Distancia en línea recta.';changeScope();}
  map.on('click',event=>selectPoint(event.latlng,false));
  $('radius').onchange=()=>selectPoint(focus||map.getCenter(),true);
  $('clearAnalysis').onclick=()=>{focus=null;drawCircle();$('selection').textContent='Análisis del área visible. Haz clic en el mapa para fijar un nuevo centro.';changeScope();};
  $('place').onchange=()=>{
    const place=locations[$('place').value];if(!place)return;
    navigation++;focus=null;drawCircle();
    if(boundary){map.removeLayer(boundary);boundary=null;}
    if(searchMarker){map.removeLayer(searchMarker);searchMarker=null;}
    $('boundaryFeedback').textContent='';$('searchFeedback').textContent='Búsqueda geográfica mediante OpenStreetMap.';
    $('selection').textContent='Entorno de '+place.label+'. Se consulta el área visible, no el total de la comuna.';
    map.setView(place.center,place.zoom,{animate:false});changeScope();
  };

  // Preserve explicit place search, with timeouts, caching and single-request throttling.
  // Public Nominatim is only suitable for a small pilot; a shared rate-limited service is required at scale.
  function setGeoBusy(value){geoBusy=value;$('searchBtn').disabled=value;$('boundaryBtn').disabled=value;}
  async function geocode(query,polygon=false){
    const params=new URLSearchParams({q:query,format:'jsonv2',limit:'3',addressdetails:'1',countrycodes:$('place').value==='miraflores'?'pe':'cl'});
    if(polygon)params.set('polygon_geojson','1');
    const key=params.toString();if(geoCache.has(key))return geoCache.get(key);
    await pause(Math.max(0,1100-(Date.now()-lastGeo)));lastGeo=Date.now();
    const result=await fetchJSON('https://nominatim.openstreetmap.org/search?'+key,null,18000);
    if(!Array.isArray(result))throw Error('Respuesta geográfica no válida.');
    geoCache.set(key,result);return result;
  }
  $('searchBtn').onclick=async()=>{
    const query=$('address').value.trim();if(geoBusy)return;
    if(query.length<3){$('searchFeedback').textContent='Escribe al menos tres caracteres.';return;}
    setGeoBusy(true);const own=++navigation;$('searchFeedback').textContent='Buscando…';
    try{
      const results=await geocode(query);if(own!==navigation)return;
      if(!results.length){$('searchFeedback').textContent='No encontramos coincidencias. Añade calle, número y comuna.';return;}
      const p=results[0],lat=Number(p.lat),lon=Number(p.lon);if(!validPoint(lat,lon))throw Error('Coordenadas no válidas.');
      if(searchMarker)map.removeLayer(searchMarker);
      searchMarker=L.circleMarker([lat,lon],{radius:9,color:'#153b43',fillColor:'#f7c66a',fillOpacity:1,bubblingMouseEvents:false}).addTo(map).bindPopup(esc(p.display_name)).openPopup();
      $('place').value='custom';map.setView([lat,lon],16,{animate:false});selectPoint([lat,lon],false);
      $('searchFeedback').textContent=p.display_name+' · Resultado referencial OSM.';
    }catch(error){if(own===navigation)$('searchFeedback').textContent='No se pudo buscar: '+error.message;}
    finally{setGeoBusy(false);}
  };
  $('address').onkeydown=event=>{if(event.key==='Enter')$('searchBtn').click();};
  $('boundaryBtn').onclick=async()=>{
    if(geoBusy)return;const place=locations[$('place').value];
    if(!place||$('place').value==='chile'){$('boundaryFeedback').textContent='Selecciona una ciudad o comuna para consultar su límite referencial.';return;}
    setGeoBusy(true);const own=navigation;$('boundaryFeedback').textContent='Buscando límite…';
    try{
      const results=await geocode(place.label,true);if(own!==navigation)return;
      const p=results.find(r=>['Polygon','MultiPolygon'].includes(r.geojson?.type));
      if(!p){$('boundaryFeedback').textContent='No hay un polígono disponible para esta consulta.';return;}
      if(boundary)map.removeLayer(boundary);
      boundary=L.geoJSON(p.geojson,{style:{color:'#00a782',weight:2,fillOpacity:.04},interactive:false}).addTo(map);
      // The boundary is a visual reference, not an unvalidated spatial filter.
      $('boundaryFeedback').textContent='Límite referencial OSM mostrado. Los filtros siguen usando el área visible o el radio; no es un límite oficial.';
    }catch(error){if(own===navigation)$('boundaryFeedback').textContent='No se pudo consultar el límite: '+error.message;}
    finally{setGeoBusy(false);}
  };
  $('exportCsv').onclick=()=>{
    if(!rows.length)return;
    const quote=value=>{let s=String(value??'');if(/^[=+@\t\r]/.test(s)||/^-[^0-9]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
    const stamp=new Date().toISOString();
    const csv='id,nombre,categorias,latitud,longitud,fuente,radio_m,fecha_exportacion,advertencia\r\n'+rows.map(p=>[p.id,p.name,p.categories.join(' | '),p.lat,p.lon,'OpenStreetMap',focus?radius():'',stamp,'Cobertura no exhaustiva; hasta 450 registros por categoria y consulta'].map(quote).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'}));
    const a=document.createElement('a');a.href=url;a.download='digital-twin-chile-filtros.csv';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  $('shareView').onclick=async()=>{
    const u=new URL(location.href),c=map.getCenter();
    u.searchParams.set('lat',c.lat.toFixed(5));u.searchParams.set('lon',c.lng.toFixed(5));u.searchParams.set('z',String(map.getZoom()));u.searchParams.set('place',$('place').value);u.searchParams.set('layers',selected().map(d=>d.id).join(','));
    u.searchParams.delete('focus');u.searchParams.delete('r');
    if(focus){u.searchParams.set('focus',focus.lat.toFixed(5)+','+focus.lng.toFixed(5));u.searchParams.set('r',String(radius()));}
    try{await navigator.clipboard.writeText(u.toString());$('analysisNote').textContent='Enlace de la vista y filtros copiado.';}catch{window.prompt('Copia el enlace de esta vista:',u.toString());}
  };
  try{
    const u=new URL(location.href),lat=Number(u.searchParams.get('lat')),lon=Number(u.searchParams.get('lon')),z=Number(u.searchParams.get('z'));
    if(u.searchParams.has('lat')&&u.searchParams.has('lon')&&validPoint(lat,lon)&&z>=1&&z<=19){map.setView([lat,lon],z,{animate:false});$('place').value=locations[u.searchParams.get('place')]?u.searchParams.get('place'):'custom';}
    if(u.searchParams.has('layers')){const ids=u.searchParams.get('layers').split(',');defs.forEach(d=>$('layer-'+d.id).checked=ids.includes(d.id));}
    const f=(u.searchParams.get('focus')||'').split(',').map(Number);
    if(f.length===2&&validPoint(f[0],f[1])){focus=L.latLng(f[0],f[1]);if(['400','800','1500'].includes(u.searchParams.get('r')))$('radius').value=u.searchParams.get('r');drawCircle();}
  }catch(error){console.warn('No se pudo restaurar la vista:',error);}
  window.DTC=Object.freeze({version:'0.3.1',snapshot:()=>({version:'0.3.1',count:rows.length,focus:focus?{lat:focus.lat,lon:focus.lng}:null,radius:focus?radius():null,scope:scope?.key||null,layers:defs.map(d=>({id:d.id,active:$('layer-'+d.id).checked,status:stateFor(d.id)?.status||'idle',count:rows.filter(p=>p.categories.includes(d.label)).length})),records:rows.map(p=>({id:p.id,categories:[...p.categories]}))})});
  changeScope();
})();
