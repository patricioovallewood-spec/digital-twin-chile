# Digital Twin Chile · Atlas 0.4

Infraestructura de inteligencia territorial orientada al **bien público, sin propósito comercial**. Esta entrega es un piloto de Ñuñoa, no un gemelo predictivo de todas las comunas de Chile.

## Aplicación actual

La aplicación que publica GitHub Pages está en `atlas/`. El código Leaflet anterior de la raíz se conserva como antecedente, pero no se despliega.

- Mapa MapLibre 2D/3D, base satelital Esri o cartografía OpenFreeMap.
- Explorador de capas, vistas temáticas, búsqueda dentro de registros, fichas, catálogo, tabla y enlaces compartibles.
- Filtros de categoría, rubro, radios de 400/800/1500 metros, año de permisos y calidad de altura.
- Mapa, contadores, tabla y exportaciones CSV/GeoJSON utilizan la misma selección.
- Instantáneas públicas preparadas y versionadas: los filtros no dependen de nuevas consultas a Overpass o ArcGIS.
- Verificación SHA-256 y recuento del archivo al cargar cada capa; fallos diferenciados de un resultado vacío.

## Fuentes y cobertura

`atlas/data/manifest.json` contiene proveedor, fuente, periodo, fecha de extracción, geometría, recuento, condiciones de uso, limitaciones y SHA-256 de cada instantánea. El catálogo de la interfaz refleja este manifiesto; no declara integrados los datos pendientes.

Hay datos públicos obtenidos directamente de servicios ArcGIS del catastro de Ñuñoa, servicios de Censo 2024, OCUC y OpenStreetMap. No se copiaron código, credenciales ni datasets del portal protegido de Cerebro Ñuñoa.

Los objetos se seleccionan por intersección con la geometría comunal consultada. Las líneas se recortan. Los edificios cartográficos se recortan al límite y al núcleo de cada tesela. No se equipara automáticamente el recuento obtenido con un total oficial de la comuna.

### Edificios y 3D

La capa de edificación alternativa usa una descarga limitada de teselas OpenFreeMap/OpenMapTiles, con datos de OpenStreetMap. Sus elementos son **partes o volúmenes cartográficos**, no un censo de edificios únicos. `render_height` no está certificado aquí como altura medida; cuando falta se utiliza un volumen simbólico de 0,6 m explícitamente identificado. No hay estimación de pisos a partir de terreno ni simulación física.

Atribución: **OpenFreeMap · © OpenMapTiles · © OpenStreetMap contributors**. Datos OSM: https://www.openstreetmap.org/copyright . Servicio y límites de uso: https://openfreemap.org/quick_start/ . Los proveedores de mapas base conservan su atribución propia.

### Precauciones de interpretación

- Censo: personas por manzana en 2024; no población actual ni densidad automática. Nulos/valores de supresión no son ceros.
- Proximidad: distancia en línea recta al punto representativo de cada objeto; no recorrido caminable, entrada del edificio ni distribución proporcional de población.
- Alumbrado y árboles: catastro fechado; no estado operativo ni fallas en tiempo real.
- Ciclovías y permisos: series históricas según el manifiesto; no red actual ni cartera vigente de inversiones.
- Equipamientos OSM: cobertura colaborativa no exhaustiva. Puede incluir instalaciones privadas; no confirma acceso público, horarios o capacidad.
- Concentración: mapa de densidad visual de puntos, no flujo peatonal ni temperatura.
- Conteos de objetos de categorías distintas no son un índice de calidad de vida.

## Derechos y privacidad

Cada fuente conserva sus condiciones de uso. Algunas publican CC BY-NC; otras no declaran licencia en sus metadatos y requieren aclaración antes de usos adicionales o redistribución fuera del piloto. Acceso público no equivale a autorización irrestricta. Las exportaciones incluyen procedencia y condiciones.

No incorporar datos personales, secretos, credenciales, expedientes reservados ni bases municipales privadas a este repositorio público. La integración futura de sistemas municipales necesita un servicio autenticado y controles separados.

## Ejecución y pruebas

```
python3 -m http.server 8000 --directory atlas
```

Abrir `http://localhost:8000`. La interfaz requiere JavaScript/WebGL; las teselas base y las fuentes web necesitan conexión. Los datos de las capas se sirven desde `atlas/data`.

```
pip install playwright==1.55.0
python -m playwright install --with-deps chromium webkit
python tests/test_atlas.py
```

Las pruebas usan las instantáneas reales del piloto. Aíslan el proveedor de mapa base durante regresión; la comprobación posterior al despliegue utiliza el mapa base público real. Comprueban integridad, filtros, ceros, radios, búsqueda, exportación, persistencia sin nuevas descargas, renderizado, 3D, catálogo y móvil. No se usan registros inventados de ciudad.

## Preparación y actualización

`scripts/prepare_atlas.py` documenta la extracción pública y la normalización. `scripts/build_cartographic_buildings.py` prepara la alternativa cartográfica cuando Overpass no entrega edificios. Las actualizaciones requieren volver a ejecutar los conectores, revisar resultados y pasar las pruebas. **No hay una promesa de sincronización continua ni tiempo real** en esta versión.

GitHub Pages despliega exclusivamente `atlas/` desde `main`, después de las pruebas, y vuelve a comprobar el sitio publicado. Las evidencias quedan como artefactos de GitHub Actions.

## Pendiente

Cobertura multicomuna; PRC y modificaciones vigentes; patentes autorizadas; natalidad; delitos a escala publicable; flujos peatonales medidos; imágenes térmicas procesadas; cartera de inversiones con etapas; actualización incremental; conectores municipales privados; validación de indicadores y simulaciones. Las capas sin datos no simulan resultados.

**Datos abiertos. Inteligencia compartida. Mejores decisiones.**
