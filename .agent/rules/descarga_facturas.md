---
trigger: glob
globs: ["app/reportes/descarga_facturas/**"]
---

# Descarga de facturas (`app/reportes/descarga_facturas/`)

- Antes de tocar el motor, leer `docs/reglas/descarga_facturas.md`: ahí están las reglas de negocio, los estados y sus textos, las claves de cruce y lo que no cambia sin regresión.
- `motor.py` viene del legado (`legado/descarga_facturas/`). Cualquier cambio de cálculo, de texto de estado o de orden de filas exige correr `python herramientas/regresion_legado.py descarga_facturas` sobre los archivos reales y anotar el resultado en `docs/regresion.md`. Sin regresión anotada, el cambio no se da por bueno.
- Nunca escribir la dirección real de SharePoint, nombres de la organización ni rutas de la usuaria en código, docs o tests: viven en `datos/configuracion.json`. La carpeta `sesion_chrome` tampoco va al repo.
- Las correcciones detectadas y no aplicadas se anotan en `docs/pendientes.md`, no se corrigen de paso.

## Archivos de la carpeta

- `reporte.py`: definición `REPORTE` (`requiere: venv_facturas`, pausa `login`, entrada `listado`, parámetros `origen`, `sitio`, `biblioteca`, `destino`, `desde`, `hasta`, `concepto`).
- `motor.py`: copia de `legado/descarga_facturas/listado.py` (v6): lectura del listado, descarga, estados; incluye `navegador_simulado` para pruebas sin Playwright.
- `sharepoint.py`: funciones de apoyo portadas de `facturas.py` (v5): `read_pdf`, `texto_pdf`, `safe_name`, `check_url`, `get_response`, `wait_for_library`.
- `ejecutar.py`: punto de entrada del subproceso; corre con el intérprete de `.venv` (playwright + pdfplumber).

## Contrato de `ejecutar.py`

- Se invoca como subproceso: `python -I app/reportes/descarga_facturas/ejecutar.py --trabajo <carpeta>`.
- Lee de `<carpeta>` `parametros.json` (valores del paso Opciones) y `entradas.json` (`{clave: [{ruta, nombre}]}`, uno o más tramos por entrada; el nombre original se pasa aparte porque en el server el archivo se guarda como `archivos/<sha8>/<nombre>` y el nombre puede repetirse entre cierres).
- Escribe `<carpeta>/salidas/` (los archivos originales del reporte) y `<carpeta>/resultados.sqlite` (una tabla por salida, vía `_comun/salidas.Volcador`), y habla con el server por el protocolo de líneas JSON de `_comun/protocolo.py` (`log`, `paso`, `progreso`, `tabla`, `esperar`, `resumen`, `error`).
