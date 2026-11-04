---
trigger: glob
globs: ["app/reportes/descarga_facturas/**"]
---

# Descarga de facturas (`app/reportes/descarga_facturas/`)

- Antes de tocar el motor, leer `docs/reglas/descarga_facturas.md`: ahí están las reglas de negocio, los estados y sus textos, las claves de cruce y lo que no cambia sin regresión.
- `motor.py` y `sharepoint.py` vienen del legado (`legado/descarga_facturas/`). Cualquier cambio de cálculo, de lectura del PDF, de texto de estado o de orden de filas exige correr `.venv\Scripts\python.exe herramientas/regresion_facturas.py --pdfs <carpeta>` sobre PDF reales y anotar el resultado en `docs/regresion.md` (SHA-256 abreviado y hojas de cada PDF, nunca conceptos ni importes). Sin regresión anotada, el cambio no se da por bueno. `regresion_legado.py` no tiene este reporte.
- Los PDF reales que manda quien usa la herramienta van a una carpeta propia fuera del repo y se leen con `python -I`. Cada uno se llama como el número de la factura (como en la biblioteca): la descarga simulada confirma que el número esté dentro del PDF.
- Nunca escribir la dirección real de SharePoint, nombres de la organización ni rutas de la usuaria en código, docs o tests: viven en `datos/configuracion.json`. La carpeta `sesion_chrome` tampoco va al repo.
- Las correcciones detectadas y no aplicadas se anotan en `docs/pendientes.md`, no se corrigen de paso.

## Archivos de la carpeta

- `reporte.py`: definición `REPORTE` (`requiere: venv_facturas`, pausa `login`, entrada `listado`, parámetros `origen`, `sitio`, `biblioteca`, `destino`, `desde`, `hasta`, `concepto`).
- `motor.py`: copia de `legado/descarga_facturas/listado.py` (v6): lectura del listado, descarga, estados; incluye `navegador_simulado` para pruebas sin Playwright.
- `sharepoint.py`: funciones de apoyo portadas de `facturas.py` (v5): `read_pdf`, `texto_pdf`, `safe_name`, `check_url`, `get_response`, `wait_for_library`.
- `ejecutar.py`: punto de entrada del subproceso; corre con el intérprete de `.venv` (playwright + pdfplumber).
- Fuera de la carpeta: `herramientas/regresion_facturas.py` (regresión con PDF reales contra el legado y descarga simulada; tests en `tests/test_regresion_facturas.py`).

## Formas de factura que lee `read_pdf`

Todo cambio en `read_pdf` se prueba con las cuatro formas: cada una tiene su test sintético en `tests/test_descarga_facturas.py` (`LecturaDelConcepto`) y, en la regresión, va al menos un PDF real de cada forma que haya. La 2026.11.03 mandó a `Para revisar` las facturas de varias hojas porque sólo se había comparado con facturas de una hoja.

- **A**: los ítems cierran con `SubTotal:` (`_factura`).
- **B**: no tiene `SubTotal:`; cierra con `TOTAL:` y debajo vienen la percepción, las notas y el importe en letras (`***…***`) (`_factura_b`).
- **Varias hojas**: con muchos ítems, `SubTotal:` y `TOTAL:` pasan a la hoja siguiente, que no repite los encabezados `Concepto` y `Operación`; el último ítem de la hoja termina al pie (`_factura_dos_hojas`; PDF de varias hojas con `_pdf_hojas`).
- **Sin rótulo** en ninguna hoja: no se sabe dónde termina el último ítem; la factura queda sin concepto y va a `Para revisar` (`_factura_b([])`, `_factura_dos_hojas([])`).

Los tests que leen PDF necesitan pdfplumber: con `py` se omiten. Se corren con `.venv\Scripts\python.exe -m unittest discover -s tests -t .`.

## Contrato de `ejecutar.py`

- Se invoca como subproceso: `python -I app/reportes/descarga_facturas/ejecutar.py --trabajo <carpeta>`.
- Lee de `<carpeta>` `parametros.json` (valores del paso Opciones) y `entradas.json` (`{clave: [{ruta, nombre}]}`, uno o más tramos por entrada; el nombre original se pasa aparte porque en el server el archivo se guarda como `archivos/<sha8>/<nombre>` y el nombre puede repetirse entre cierres).
- Escribe `<carpeta>/salidas/` (los archivos originales del reporte) y `<carpeta>/resultados.sqlite` (una tabla por salida, vía `_comun/salidas.Volcador`), y habla con el server por el protocolo de líneas JSON de `_comun/protocolo.py` (`log`, `paso`, `progreso`, `tabla`, `esperar`, `resumen`, `error`).
