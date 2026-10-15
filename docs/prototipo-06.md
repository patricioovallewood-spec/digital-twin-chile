# Prototipo municipal de Ñuñoa · 0.6

Continúa el Atlas existente y sus instantáneas. No incorpora conexiones privadas. Se publica en el GitHub Pages del repositorio por instrucción del propietario.

## Lectura territorial

Consultar abre fichas con procedencia; Analizar zona coloca un radio desde cualquier clic, incluso sobre un objeto. El mismo filtro alimenta mapa, conteos, indicadores y exportación. Guardar zona A permite comparar su lectura con otro punto o radio durante la sesión. No se guardan datos de usuarios en un servidor.

Los habitantes se suman por manzanas completas cuyo punto representativo está dentro del radio. No son habitantes exactos del círculo. La densidad divide la población conocida por el área geográfica de esas mismas manzanas completas, excluyendo manzanas sin población. No usa el área del radio ni asigna habitantes por interpolación. El área se calcula mediante integración esférica de anillos WGS84, restando huecos.

La temperatura es una media aritmética de celdas seleccionadas de la escena Landsat de 15 de septiembre de 2026; no temperatura del aire, medición actual ni diagnóstico causal. La altura media corresponde a piezas cartográficas con altura superior a un metro; no a edificios únicos.

## Comercio por calle

Se agrupan establecimientos OSM por el campo calle normalizado en acentos y mayúsculas. No se asignan coordenadas a vías por proximidad. Se informa el número sin calle declarada; no se distribuye entre las restantes. No se deducen patentes, facturación, demanda, flujo de personas ni rentabilidad. El filtro de calle solo afecta comercios y salud; los otros indicadores conservan su selección espacial.

## Escenario de demostración

`demoZoning` contiene cuatro zonas ficticias. `demoWorks` contiene seis obras y montos ficticios. Las capas llevan prefijo DEMO, propiedad `evidence_type=demo`, grupo separado y aviso persistente cuando están activas. Están apagadas inicialmente. El botón Todas activa únicamente las fuentes reales; el usuario debe activar cada demostración o la vista Escenario demo. Los indicadores reales excluyen los registros sintéticos y las exportaciones los identifican por fila.

El expediente oficial del plan regulador continúa disponible por separado. Las zonas ficticias no corresponden al PRC ni sirven para certificados, alturas permitidas, permisos o decisiones prediales. Los proyectos SEIA conservan su estado ambiental, que no se interpreta como ejecución o financiamiento.

## Integraciones futuras

El archivo `atlas/integration-contract.json` define metadatos, geometría, tipos de evidencia, estados de calidad y dominios de una futura ingesta de solo lectura. Es un contrato conceptual con endpoint nulo, sin conexión ni credenciales. Se propone un adaptador del lado servidor, validación previa, instantáneas versionadas y conservación de la última versión válida ante errores. Las claves nunca irán en el navegador ni en este repositorio. La autorización municipal y la selección de campos preceden cualquier integración real.
