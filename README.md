# Digital Twin Chile

Infraestructura de inteligencia territorial para el bien público. **Versión inicial (beta 0.1).**

## Qué funciona hoy

- Explorador geográfico interactivo con OpenStreetMap/Leaflet.
- Navegación por Chile y ciudades/comunas de referencia.
- Capas consultables en vivo: parques, salud, educación, comercio, deporte, cultura y ciclovías.
- Ficha de lectura del territorio, conteos de elementos mostrados, ubicación seleccionada y atribución de fuentes.
- Diseño adaptable a escritorio y móvil.

## Limitaciones de la versión inicial

- **No es todavía un gemelo digital 3D ni un sistema de simulación.** Es el primer módulo exploratorio geoespacial.
- Los puntos proceden de OpenStreetMap consultado mediante Overpass API: su cobertura y actualización varían. No equivalen a un catastro oficial exhaustivo.
- Las consultas solo se ejecutan a zoom 12 o superior para evitar solicitudes nacionales costosas; se limitan a 450 elementos por consulta. Los conteos **no son totales oficiales**.
- Las ciclovías se muestran por puntos centrales de elementos OSM; la geometría lineal queda pendiente.
- No hay todavía datos de luminarias, flujo peatonal horario ni conexiones con sistemas municipales; no se inventan.
- La disponibilidad del servicio Overpass depende de un proveedor externo y sus límites de uso.

## Ejecución

Abrir `index.html` con un servidor web estático. Ejemplo: `python3 -m http.server 8000` y visitar http://localhost:8000.

El proyecto no requiere compilación. Usa Leaflet y tipografías externas mediante CDN.

## Próximos hitos

1. Catálogo versionado de fuentes oficiales chilenas, licencias, metadatos y cobertura.
2. Capa geográfica de límites comunales y selección por territorio administrativo real.
3. Modelo PostGIS + API para datos oficiales y municipales.
4. Geometrías de calles, ciclovías, plazas y predios; búsqueda por calle.
5. Inventario de alumbrado y activos urbanos donde existan fuentes autorizadas.
6. Datos temporales de movilidad y flujos solo cuando exista una fuente verificable.
7. Análisis territorial, accesibilidad, escenarios y trazabilidad de decisiones.

## Principios

**Datos abiertos. Inteligencia compartida. Mejores decisiones.**

Proyecto orientado al bien público digital, no a la comercialización. Diferenciar siempre registros observados, estimaciones y simulaciones, y respetar licencias, privacidad y restricciones de cada fuente.
