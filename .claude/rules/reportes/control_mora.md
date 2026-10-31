---
description: "Reglas del reporte Control de Mora (cuentas de mora en ERP contra agrupador MORA en SGA): motor del legado, regresión obligatoria."
paths: ["**/reportes/control_mora/**"]
---

# Control de Mora (`app/reportes/control_mora/`)

- Antes de tocar el motor, leer `docs/reglas/control_mora.md`: ahí están las reglas de negocio, los estados y sus textos, las claves de cruce y lo que no cambia sin regresión.
- `motor.py` viene del legado (`legado/control_mora/`). Cualquier cambio de cálculo, de texto de estado o de orden de filas exige correr `python herramientas/regresion_legado.py control_mora` sobre los archivos reales y anotar el resultado en `docs/regresion.md`. Sin regresión anotada, el cambio no se da por bueno.
- Compara dos totales, no movimientos; la fecha de corte la garantiza la usuaria al descargar ambos reportes.
- Las correcciones detectadas y no aplicadas se anotan en `docs/pendientes.md`, no se corrigen de paso.

## Archivos de la carpeta

- `reporte.py`: definición `REPORTE` (entradas `erp`/`sga`, parámetros `cuentas`, `unidad_negocio`, `fondo`, `grupo`, tres salidas CSV).
- `motor.py`: copia de `legado/control_mora/control_mora.py` con detección por columnas, parámetros y tramos; usa openpyxl de `vendor/`.
- `ejecutar.py`: punto de entrada del subproceso; vuelca los CSV a sqlite leyéndolos en streaming.

## Contrato de `ejecutar.py`

- Se invoca como subproceso: `python -I app/reportes/control_mora/ejecutar.py --trabajo <carpeta>`.
- Lee de `<carpeta>` `parametros.json` (valores del paso Opciones) y `entradas.json` (`{clave: [{ruta, nombre}]}`, uno o más tramos por entrada; el nombre original se pasa aparte porque en el server el archivo se guarda como `archivos/<sha8>/<nombre>` y el nombre puede repetirse entre cierres).
- Escribe `<carpeta>/salidas/` (los archivos originales del reporte) y `<carpeta>/resultados.sqlite` (una tabla por salida, vía `_comun/salidas.Volcador`), y habla con el server por el protocolo de líneas JSON de `_comun/protocolo.py` (`log`, `paso`, `progreso`, `tabla`, `esperar`, `resumen`, `error`).
