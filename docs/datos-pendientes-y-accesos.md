# Digital Twin Chile 0.5 — alcance de los dominios pendientes

La ampliación mantiene el piloto de Ñuñoa. No convierte información comunal en datos por calle ni sustituye permisos de acceso a sistemas municipales.

## Incorporaciones públicas

- **Natalidad y mortalidad:** indicadores publicados en reportes comunales BCN, con origen declarado DEIS/MINSAL. Periodos 2019, 2020, 2022 y 2023; no se interpolan años ausentes ni se crean puntos de nacimientos. Son tasas, no conteos. La fecundidad se excluyó porque el encabezado fuente agrupa unidades de manera ambigua.
- **Seguridad:** tasas de denuncias de 2023–2025, en dos grupos de la edición BCN 2026: delitos contra la vida/integridad y violencia intrafamiliar. No se mezclan con DMCS o delitos violentos de otras ediciones. No hay georreferencias de incidentes individuales.
- **Proyectos:** registros EIA y DIA de la API pública del SEA cuyo punto de referencia intersecta la comuna. Se preserva estado ambiental, tipología y fechas. El punto no es huella ni área de influencia. No es cartera completa, avance físico, financiamiento ni ejecución; puede omitir proyectos multicomunales ubicados fuera del polígono.
- **Plan regulador:** índice de documentos enlazados por la página oficial municipal. Es un expediente de consulta, no un motor normativo predial. Falta contrastar planos, ordenanza, modificaciones, fallos y polígonos antes de automatizar usos/alturas.
- **Temperatura superficial:** el procesador busca escenas Landsat L2SP hasta 2026-10-14. Solo publica una capa cuando supera controles locales de nubes, sombras, relleno, saturación e incertidumbre; consulta su estado en el manifiesto. La escena representa superficie, no temperatura del aire ni tiempo real. Las celdas de 150 m no son mediciones independientes a esa resolución; la señal térmica nativa es de 100 m y el producto está remuestreado a 30 m.

## Lo que necesitamos del municipio

### Patentes
Solicitar un extracto autorizado y minimizado que identifique establecimiento, nombre comercial, rubro, ubicación del establecimiento, tipo y estado de patente y periodo de vigencia. Excluir RUT, deudas, teléfonos, personas naturales y domicilios residenciales que no deban publicarse. Distinguir un local abierto al público de una oficina tributaria/virtual: una patente no garantiza presencia de comercio físico.

### Flujos peatonales
Obtener conteos por tramo/punto, intervalo con zona horaria, fecha, metodología, equipo/fuente, cobertura y controles de calidad. Diferenciar personas contadas, pasos y dispositivos; no sumar observaciones incompatibles. No inferir flujo por hora desde cantidad de comercios, población censal, luminarias o densidad de puntos. No necesitamos identificación individual, reconocimiento facial ni trayectorias personales.

### Sistemas municipales
Acordar una API o exportación autorizada, campos permitidos, finalidad, responsabilidad de actualización y controles de acceso. Empezar con solo lectura y un sistema (por ejemplo, mantenimiento de luminarias). Separar el área operacional privada de lo publicable. Las credenciales van en un gestor de secretos, nunca en el navegador, código, registros ni repositorio.

## Contrato técnico disponible

`scripts/validate_municipal_import.py` valida localmente CSV minimizados de `pedestrians`, `assets` o `licenses`; rechaza columnas ajenas al contrato, coordenadas inválidas, fechas incorrectas y duplicados básicos. Requiere confirmación explícita `--authorized`. No conecta con APIs ni publica registros. La validación es estructural, no certificación jurídica o estadística.

Ejemplo de uso, con un archivo que el municipio haya autorizado:

```sh
python scripts/validate_municipal_import.py assets archivo_autorizado.csv --authorized
```

El parámetro `--authorized` no sustituye un convenio ni acredita por sí solo autorización. No incluir archivos privados en GitHub.

## Estados de la plataforma

- `ready`: instantánea geográfica preparada y verificable técnicamente.
- `tabular`: tabla estadística disponible fuera de los filtros del mapa.
- `reference`: documentación de consulta; el análisis geográfico/normativo sigue incompleto.
- `requires_access`: faltan datos o autorizaciones externas, no solo programación.
- `pending` / `unavailable`: todavía no se obtuvo una versión utilizable.

El estado técnico nunca garantiza exhaustividad, actualidad permanente, licencia irrestricta ni aptitud para cualquier decisión.
