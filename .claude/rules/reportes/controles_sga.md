---
description: "Reglas del reporte Controles SGA (seis controles sobre el histórico de cuenta corriente): motor del legado 1.5, reglas propuestas, regresión obligatoria."
paths: ["**/reportes/controles_sga/**"]
---

# Controles SGA (`app/reportes/controles_sga/`)

- Antes de tocar el motor, leer `docs/reglas/controles_sga.md`: ahí están las reglas de negocio, los estados y sus textos, las claves de cruce y lo que no cambia sin regresión.
- `motor.py` viene del legado (`legado/controles_sga/`). Cualquier cambio de cálculo, de texto de estado o de orden de filas exige correr `python herramientas/regresion_legado.py controles_sga` sobre los archivos reales y anotar el resultado en `docs/regresion.md`. Sin regresión anotada, el cambio no se da por bueno.
- Las reglas confirmadas (`parametros["reglas"]`) equivalen al `--reglas` del legado; exentos y aporte del programa prevalecen siempre.
- Las correcciones detectadas y no aplicadas se anotan en `docs/pendientes.md`, no se corrigen de paso.

## Archivos de la carpeta

- `reporte.py`: definición `REPORTE`: listas de conceptos (exentos, con aporte, imputación condicional), `SALIDAS` (doce tablas, una por solapa, con `CLAVES` por control) y los parámetros, incluida la tabla `reglas`. Las tres de netos declaran `origen`; servicios y abiertos, `seccion`. `SALIDAS_ANTERIORES` guarda `servicios_anio` (versiones de antes de los servicios por mes) para mostrar esas corridas y trasladar sus marcas.
- `motor.py`: copia de `legado/controles_sga/control_sga.py` (v1.5): lectura, `default_rules`, `controls`, `open_documents`, consolidación de netos. Devuelve los libros, las reglas propuestas y el resumen.
- `excel.py`: copia de `excel_sga.py`: arma los seis libros con solapas, celdas anaranjadas y bloque original de SGA. Servicios se parte por mes (`mensual_servicios`; solapas en orden Mes en curso / No exigibles / Histórico), no por año.
- `origen.py`: Excel de origen de netos: la fila del histórico de SGA (`Fila SGA`, `Archivo`) con las columnas de `_marcas` que son del bloque original pintadas de anaranjado. Contrato en `app/origenes.py`; no cambia la matemática.
- `ejecutar.py`: punto de entrada del subproceso; vuelca sólo las tablas de `salidas_a_generar` y emite `reglas_propuestas` en el resumen.

## Contrato de `ejecutar.py`

- Se invoca como subproceso: `python -I app/reportes/controles_sga/ejecutar.py --trabajo <carpeta>`.
- Lee de `<carpeta>` `parametros.json` (valores del paso Opciones) y `entradas.json` (`{clave: [{ruta, nombre}]}`, uno o más tramos por entrada; el nombre original se pasa aparte porque en el server el archivo se guarda como `archivos/<sha8>/<nombre>` y el nombre puede repetirse entre cierres).
- Escribe `<carpeta>/salidas/` (los archivos originales del reporte) y `<carpeta>/resultados.sqlite` (una tabla por salida, vía `_comun/salidas.Volcador`), y habla con el server por el protocolo de líneas JSON de `_comun/protocolo.py` (`log`, `paso`, `progreso`, `tabla`, `esperar`, `resumen`, `error`).
