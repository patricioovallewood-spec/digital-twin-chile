# Referencia técnica: Cerebro Ñuñoa

Revisión: 14 de octubre de 2026. Referencia facilitada por Patricio Ovalle.
Sitio: https://cerebro-nunoa.vercel.app/#gemelo

## Alcance de la revisión y evidencia

Se inspeccionaron el HTML y seis archivos JavaScript públicos. Se abrió el sitio en Chromium, sin autenticar y sin modificar el sitio externo.
El servidor entregó el HTML y los seis scripts con HTTP 200.
Las rutas #gemelo y #fuentes mostraron una pantalla de acceso con clave. No se entró en la aplicación autenticada ni se intentó eludir esa protección.
Por ello, esta revisión valida la configuración pública y la pantalla de acceso, NO la integridad de los datasets, las licencias, su actualización ni el funcionamiento interactivo del gemelo protegido.
Evidencia reproducible: ejecución GitHub Actions https://github.com/patricioovallewood-spec/digital-twin-chile/actions/runs/38623167227 . El artefacto temporal de diagnóstico se denomina nunoa-reference-review.
La revisión no cambió la aplicación publicada de Digital Twin Chile. Se realizó en la rama review/cerebro-nunoa-reference.

## Arquitectura observada en archivos públicos

El HTML referencia MapLibre GL JS 4.7.1. El archivo mapa.js configura terreno, edificios extruidos, mapas base, capas geográficas y vistas temáticas.
La declaración CAPAS de mapa.js contiene 25 entradas, incluidas capas virtuales y representaciones 3D; no equivale a 25 datasets comprobados.
Las entradas cubren territorio, Censo 2024, planificación, patrimonio, permisos, áreas verdes, arbolado, sismos, edificios, movilidad, equipamientos y alumbrado.
La función cargarCapas utiliza cargadores de datos propios de la aplicación y conserva geometrías; setCapa cambia la visibilidad de capas ya registradas. Hay carga diferida para el conjunto específico de edificios de Ñuñoa.
Las bases configuradas incluyen ESRI, OpenFreeMap, OSM, topografía y fondos grises. También hay configuración para productos NASA GIBS y Sentinel-2; su disponibilidad real no se comprobó.

Fuentes de esta inspección estática: https://cerebro-nunoa.vercel.app/ y https://cerebro-nunoa.vercel.app/mapa.js . No se obtuvo acceso al repositorio original.

## Diferencias que importa conservar al adaptar el diseño

| Componente | Lo que declara la configuración pública | Precaución |
| --- | --- | --- |
| Alumbrado | Densidad de luminarias por hectárea en grilla | No confundir con inventario individual, fallas o estado operativo |
| Arbolado | Árboles por hectárea en grilla | No confundir con inspección individual o estado sanitario |
| Edificios | Representación general y conjunto específico de Ñuñoa; distingue pisos OSM, altura OSM y estimación por tipología | No presentar todas las alturas como mediciones |
| Permisos | Serie identificada como 2010–2023 | No afirmar que incluye los permisos más recientes |
| Ciclovías | OSM y una capa identificada como MINVU 2016 | Mantener fecha de referencia por fuente |
| Censo | Configuración de manzanas y variables temáticas | Pendiente revisar archivo, diccionario, cobertura y controles de divulgación |

El número de 12.746 edificios está anunciado en el sitio y sus etiquetas. No se contó ni validó el dataset correspondiente.

## Recomendación para Digital Twin Chile

Adoptar una experiencia centrada en el mapa: navegación temática lateral, explorador flotante, vistas preparadas, leyenda con estado y ficha territorial.
Separar ingesta de datos e interacción: descargar y validar fuentes autorizadas, conservar versiones y servir capas preparadas. Evitar que cada cambio de filtro dependa de una consulta nueva a un servicio externo.
Hacer que mapa, conteos, listado y exportación compartan el mismo estado de filtros. Distinguir cero registros, carga pendiente y error de conexión.
Usar Ñuñoa como primer territorio de comparación es una propuesta, no una decisión ya implementada. La arquitectura debe permitir extenderse a otras comunas.
Conservar el propósito de bien público, sin asumir que eso autoriza reutilizar cualquier fuente o código ajeno.
Para reutilizar este desarrollo concreto se necesita acceso autorizado a su repositorio o una copia del proyecto y sus condiciones de uso. Para un desarrollo independiente inspirado en su diseño no se necesita su contraseña.

## Pendiente

Acceso autorizado a las capas para auditar datos y probar filtros; comprobación de licencias; revisión de fechas y resolución; contraste con fuentes oficiales; diseño e implementación de la nueva interfaz en una rama de desarrollo; pruebas de navegador antes de publicar.
