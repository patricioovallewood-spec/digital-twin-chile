/* Pure domain functions. No network or map dependencies. */
export const VERSION='0.4.0';
export const normalize=v=>String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
export const escapeHTML=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function distance(a,b){const r=Math.PI/180,dlat=(b[1]-a[1])*r,dlon=(b[0]-a[0])*r;const h=Math.sin(dlat/2)**2+Math.cos(a[1]*r)*Math.cos(b[1]*r)*Math.sin(dlon/2)**2;return 6371008.8*2*Math.atan2(Math.sqrt(h),Math.sqrt(Math.max(0,1-h)));}
export function filterFeatures(features,id,state){
 if(!state.active.has(id))return [];
 if(id==='boundary')return features;
 const q=normalize(state.query).trim();
 return features.filter(f=>{
  const p=f.properties||{};
  if(state.radius&&state.focus&&distance(state.focus,[p.x,p.y])>state.radius)return false;
  if(q&&!normalize([p.name,p.rubro,p.calle,p.CALLE,p.ESPECIE,p.MANZENT].filter(Boolean).join(' ')).includes(q))return false;
  if(state.business!=='all'&&['commerce','health'].includes(id)&&p.rubro!==state.business)return false;
  if(state.heightQuality==='known'&&id==='buildings'&&!String(p.height_quality).startsWith('Altura declarada'))return false;
  if(state.permitYear!=='all'&&id==='permits'&&String(p['AÑO'])!==state.permitYear)return false;
  return true;
 });
}
export function circleFeature(point,metres){const ring=[],lat=point[1]*Math.PI/180;for(let i=0;i<=96;i++){const theta=i/96*2*Math.PI;ring.push([point[0]+metres*Math.cos(theta)/(111195*Math.cos(lat)),point[1]+metres*Math.sin(theta)/111195]);}return {type:'Feature',properties:{},geometry:{type:'Polygon',coordinates:[ring]}};}
export const emptyCollection=()=>({type:'FeatureCollection',features:[]});
export function csv(features,metadata){
 const cell=value=>{let s=String(value??'');if(/^[\s]*[=+@]/.test(s)||/^\s*-[^\d]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
 const header=['id','capa','nombre','rubro','longitud_representativa','latitud_representativa','fuente','referencia','fecha_extraccion','metodo','proveedor','condiciones_de_uso','proveedor','condiciones_de_uso'];
 const lines=features.map(f=>{const p=f.properties,d=metadata.find(x=>x.id===p.layer)||{};return [p.id,d.name,p.name,p.rubro,p.x,p.y,d.url,d.reference,d.retrieved_at,'Punto representativo; cobertura y fechas segun fuente',d.provider,d.license].map(cell).join(',');});
 return '\uFEFF'+header.map(cell).join(',')+'\r\n'+lines.join('\r\n');
}
export function serialise(state,map){const u=new URL(location.href);u.hash='';u.search='';u.searchParams.set('v',VERSION);u.searchParams.set('layers',[...state.active].join(','));if(state.query)u.searchParams.set('q',state.query);if(state.focus&&state.radius){u.searchParams.set('focus',state.focus.join(','));u.searchParams.set('radius',String(state.radius));}if(state.business!=='all')u.searchParams.set('business',state.business);if(state.heightQuality!=='all')u.searchParams.set('height',state.heightQuality);if(state.permitYear!=='all')u.searchParams.set('year',state.permitYear);u.searchParams.set('base',state.base);u.searchParams.set('mode',state.mode);u.searchParams.set('three',String(state.three));if(map){const c=map.getCenter();u.searchParams.set('camera',[c.lng.toFixed(5),c.lat.toFixed(5),map.getZoom().toFixed(2)].join(','));}return u.toString();}
