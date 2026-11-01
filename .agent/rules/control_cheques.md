---
trigger: glob
globs: ["app/reportes/control_cheques/**"]
---

# Control de cheques (`app/reportes/control_cheques/`)

- Antes de tocar el motor, leer `docs/reglas/control_cheques.md`: ahí están las reglas de negocio, los estados y sus textos, las claves de cruce y lo que no cambia sin regresión.
- `motor.py` viene del legado (`legado/control_cheques/`). Cualquier cambio de cálculo, de texto de estado o de orden de filas exige correr `python herramientas/regresion_legado.py control_cheques` sobre los archivos reales y anotar el resultado en `docs/regresion.md`. Sin regresión anotada, el cambio no se da por bueno.
- El orden de evaluación (histórico → sin ID → no encontrado → duplicado → proveedores → válidos → cancelado → sin regla → comparación) es parte del contrato.
- Las correcciones detectadas y no aplicadas se anotan en `docs/pendientes.md`, no se corrigen de paso.

## Archivos de la carpeta

- `reporte.py`: definición `REPORTE` (entradas `sga`/`erp`, parámetros de prefijos, equivalencias y exclusiones, salidas `revisar`, `pedido_sistemas` (informativa) y `resumen`).
- `motor.py`: copia de `legado/control_cheques/control_cheques.py` con parámetros y tramos; usa openpyxl de `vendor/`. Agrega las columnas opcionales `Fecha` y `Fecha de depósito` (se buscan por alias normalizado; si faltan, salen vacías) y `Pedido_a_sistemas.csv` (motivo `Diferencia de estado`). La regresión compara el CSV sin esas dos columnas.
- `ejecutar.py`: punto de entrada del subproceso; convierte `Resumen.txt` en la tabla `resumen` y `Pedido_a_sistemas.csv` en `pedido_sistemas`.

## Contrato de `ejecutar.py`

- Se invoca como subproceso: `python -I app/reportes/control_cheques/ejecutar.py --trabajo <carpeta>`.
- Lee de `<carpeta>` `parametros.json` (valores del paso Opciones) y `entradas.json` (`{clave: [{ruta, nombre}]}`, uno o más tramos por entrada; el nombre original se pasa aparte porque en el server el archivo se guarda como `archivos/<sha8>/<nombre>` y el nombre puede repetirse entre cierres).
- Escribe `<carpeta>/salidas/` (los archivos originales del reporte) y `<carpeta>/resultados.sqlite` (una tabla por salida, vía `_comun/salidas.Volcador`), y habla con el server por el protocolo de líneas JSON de `_comun/protocolo.py` (`log`, `paso`, `progreso`, `tabla`, `esperar`, `resumen`, `error`).
