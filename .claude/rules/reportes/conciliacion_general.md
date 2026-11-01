---
description: "Reglas del reporte Conciliación general (SGA contra ERP): motor 1.5 (legado 1.4 + tres cambios acordados), regresión explicada obligatoria ante cambios de cálculo."
paths: ["**/reportes/conciliacion_general/**"]
---

# Conciliación general (`app/reportes/conciliacion_general/`)

- Antes de tocar el motor, leer `docs/reglas/conciliacion_general.md`: ahí están las reglas de negocio, los estados y sus textos, las claves de cruce y lo que no cambia sin regresión.
- `motor.py` viene del legado (`legado/conciliacion_general/`). Cualquier cambio de cálculo, de texto de estado o de orden de filas exige correr `python herramientas/regresion_legado.py conciliacion_general` sobre los archivos reales y anotar el resultado en `docs/regresion.md`. Sin regresión anotada, el cambio no se da por bueno.
- El estado de cada comprobante depende del parámetro `alcance` (abiertos/completo): no asumir uno.
- Desde la versión 1.5 la salida difiere del legado en tres puntos acordados (abiertos contra ERP 0,00; pendientes de facturas en fila PENDIENTE; Tipo por comprobante principal). La regresión ya no exige igualdad: `herramientas/cambios_conciliacion.py` tiene que explicar cada diferencia. Un cambio de reglas nuevo se agrega ahí y en `docs/reglas/conciliacion_general.md`, y se regeneran los dorados con `tests/dorados/conciliacion_general/generar.py`.
- Las correcciones detectadas y no aplicadas se anotan en `docs/pendientes.md`, no se corrigen de paso.

## Archivos de la carpeta

- `reporte.py`: definición `REPORTE` (entradas `sga`/`erp`, parámetros `alcance`, `corte`, `fondo`, salidas `resumen` y `general` con sus claves de revisión).
- `motor.py`: copia de `legado/conciliacion_general/conciliar.py` (v1.4) con parámetros explícitos, tramos y los cambios de la 1.5; escribe el CSV de respaldo, `Resumen.json`, `trazabilidad.sqlite`.
- `excel.py`: escritor XLSX propio (sin openpyxl) que arma `Conciliacion_general.xlsx` con las solapas Resumen y Conciliación general; `LABELS` renombra tres estados.
- `ejecutar.py`: punto de entrada del subproceso.
- Fondos (01/11/2026): `fondo` es un desplegable y la variante del reporte (`REPORTE['variantes']`). El motor acepta `Liquidación` como tipo de transacción, corta si el ERP es de otro fondo o mezcla fondos (prefijos de asiento en `_comun/detectores.PREFIJOS_FONDO`) y si SGA no tiene filas del fondo. Ver "Fondos de riesgo" en `docs/reglas/conciliacion_general.md`.
- `Fecha SGA` / `Fecha ERP` (informativas, 01/11/2026): `fecha_iso` por fila (SGA: `FechaFactura`, o `FechaComprobanteImputacion` si el comprobante es de imputación; ERP: `Fecha`), la más antigua por clave. Van antes de `Comprobante`: `excel.py` ubica las columnas por nombre, y la regresión (`cambios_conciliacion.leer_csv`) y los dorados las comparan aparte.
- `origen.py`: filas de origen de una fila del resultado, leídas de `Respaldo_tecnico/trazabilidad.sqlite` (el `Tipo` visible se traduce al tipo interno: `PENDIENTE` → `MP`; `RC-X`, `OP-X`, `SUBRECIBO`… → `SR`/`OPX`). Lo usa `app/origenes.py` para el Excel de origen; no cambia la matemática.
- En `reporte.py`, la salida `general` declara `revisar` (las filas `COINCIDE` no cuentan como pendientes), `vista` (Resultado primero; columnas técnicas ocultas) y `origen`.

## Contrato de `ejecutar.py`

- Se invoca como subproceso: `python -I app/reportes/conciliacion_general/ejecutar.py --trabajo <carpeta>`.
- Lee de `<carpeta>` `parametros.json` (valores del paso Opciones) y `entradas.json` (`{clave: [{ruta, nombre}]}`, uno o más tramos por entrada; el nombre original se pasa aparte porque en el server el archivo se guarda como `archivos/<sha8>/<nombre>` y el nombre puede repetirse entre cierres).
- Escribe `<carpeta>/salidas/` (los archivos originales del reporte) y `<carpeta>/resultados.sqlite` (una tabla por salida, vía `_comun/salidas.Volcador`), y habla con el server por el protocolo de líneas JSON de `_comun/protocolo.py` (`log`, `paso`, `progreso`, `tabla`, `esperar`, `resumen`, `error`).
