# Diseño: herramienta única de automatización de reportes (cierre mensual)

Fecha: 2026-10-31. Repositorio destino: https://github.com/EmmaVZ89/Automatizacion-reportes

## 0. Para quién es

La usan **personas administrativas, no técnicas**, de una organización externa (el área de facturación y
cuenta corriente que hoy corre estos scripts). No es un producto ni una herramienta interna de la
empresa del autor: no tiene que parecerse a nada interno, no menciona sistemas propios ni usa sus
colores o nombres. Lo que ven tiene que entenderse sin manual y sin saber qué es Python, una consola o
un JSON. Consecuencias concretas:

- Instalación = extraer un ZIP y hacer doble clic en un acceso directo. Nada de `pip`, consolas ni
  variables de entorno. Si falta Python, la pantalla lo dice en castellano y con el enlace para
  instalarlo.
- Cada paso dice qué hacer en una frase ("Arrastrá acá el reporte de SGA que descargaste") y qué
  encontró ("Reconocí el histórico de cuenta corriente, hoja *Datos*, 458.658 filas").
- Los errores son mensajes para una persona ("Hay dos archivos de SGA; dejá uno solo"), nunca una
  traza. La traza va al registro, por si alguien técnico la pide.
- Los nombres de pantalla son los que usan ellas hoy: *Conciliación general*, *Controles SGA*,
  *Control de Mora*, *Control de cheques*, *Descarga de facturas*; los estados también (COINCIDE,
  REVISAR, ANULADA POR NC...).
- La documentación técnica (para quien programa, humano o agente) va aparte y no aparece en la
  interfaz.

## 1. Intención y por qué

Hoy el cierre mensual (Fondo de Riesgo General) se apoya en cinco programas Python sueltos en
`D:\Desarrollo\Programacion\Automatizacion`, cada uno con su carpeta de entrada, su BAT, su LEEME y su
carpeta de resultados fechada. Funcionan y están validados con datos reales, pero:

- cada uno se opera distinto (consola, `input()`, BAT que no declara fecha, un ZIP por versión);
- la salida de cada uno es el punto de partida de un trabajo manual (revisar, descartar, anotar, pedir
  correcciones a Sistemas) que hoy se hace fuera del programa, sobre el Excel, sin dejar rastro;
- la última ejecución registrada falló por elegir mal una opción en consola (`ERROR_ULTIMA_EJECUCION.txt`);
- no hay historial consolidado por cierre: hay carpetas `AAAAMMDD_HHMMSS` repartidas en cinco lugares.

Se quiere **una sola herramienta local** (server en 127.0.0.1 + interfaz web) que ejecute los mismos
motores, guíe cada reporte como un asistente de pasos con paradas para acciones manuales, permita
**seguir trabajando cada salida** dentro de la herramienta (omitir, tener en cuenta, anotar) y guarde un
historial limpio por cierre. Debe quedar preparada para corregir y agregar reportes en el futuro.

## 2. Objetivos, no objetivos y anti-objetivos

**Objetivos**
1. Los cinco motores dan **exactamente el mismo resultado** que hoy con las mismas entradas y los
   parámetros por defecto (se verifica contra los archivos reales que están en las carpetas de entrada).
2. Un flujo por pasos por reporte: entradas → parámetros y reglas → ejecución (con pausas) → resultados
   trabajables → exportación. Se puede volver a un paso anterior y re-ejecutar; cada corrida queda como
   una versión dentro del cierre.
3. Sobre cada tabla de salida: marcar filas como *revisada*, *omitida* o *pendiente*, anotar
   observaciones, filtrar, buscar y exportar un Excel "trabajado" (el original queda intacto).
4. Qué omitir y qué tener en cuenta **antes** de correr: las listas y constantes que hoy están fijas en
   el código (conceptos exentos, cuentas FRG, equivalencias de estado de cheques, documentos excluidos,
   reglas propuestas de SGA) son editables desde la interfaz, con los valores actuales como default.
5. Historial por cierre (período `AAAA-MM`): qué se corrió, con qué archivos (SHA-256), parámetros,
   resultado, cuántas filas quedaron pendientes/revisadas/omitidas, y las versiones anteriores.
6. Interfaz clara, en castellano, tema claro y oscuro, contraste mínimo 4,5:1, usable sin manual por
   personas no técnicas (sección 0).
7. Todo autocontenido: Python 3.10+ y su biblioteca estándar, openpyxl empaquetado dentro del
   proyecto (`vendor/`). Sin Node, sin build, sin `pip install` para los cuatro controles. La descarga de
   facturas (Playwright + pdfplumber + Chrome) es la única que necesita una instalación aparte, opcional,
   también por doble clic.
8. OWASP Top 10 aplicado a lo que tiene sentido en una herramienta local (sección 9).
9. Documentación para las usuarias (LEEME en lenguaje llano) y para quien programe después, humano o
   agente (CLAUDE.md, AGENTS.md, GEMINI.md, rules por reporte), derivada de los TXT y DOCX actuales.

**No objetivos**
- No se cambia la matemática ni las reglas de negocio de ningún control. Las correcciones "menores y de
  salida" que se detecten se registran en `docs/pendientes.md` y se hacen después, como cambios aparte
  con su propia verificación.
- No hay multiusuario ni acceso por red: una persona, una PC, `127.0.0.1`.
- No se sube nada a SharePoint ni a ningún servicio: la herramienta sólo lee Excel y escribe en disco
  local (la descarga de facturas sigue siendo la excepción, y sólo lee de SharePoint).
- No se reemplaza Excel: los resultados se siguen pudiendo abrir en Excel; la herramienta agrega la
  capa de revisión y el historial.

**Anti-objetivos (lo que haría fracasar el proyecto aunque "funcione")**
- Que un número de una salida difiera del que da el script original con los mismos datos.
- Que una fila de un resultado se pierda por el camino (cobertura: todas las filas, una sola vez).
- Que la usuaria tenga que instalar algo, abrir una consola o editar un archivo a mano para usar los
  cuatro controles.
- Que el historial se vuelva otra pila de carpetas sin sentido.
- Que la interfaz exija vocabulario técnico (job, token, JSON, sqlite, puerto).

## 3. Inventario de lo que existe (análisis de cada programa)

| Programa | Versión | Entradas | Parámetros | Pasos manuales hoy | Salidas | Dependencias |
|---|---|---|---|---|---|---|
| **Conciliación general** (`Automatizacion_General/conciliar.py` + `excel_general.py`) | 1.4 (16/10/2026) | 1 histórico SGA + 1 ERP unificado o hasta 3 ERP separados (Cliente / Pago / Diario general); se detectan por encabezados, nombre libre; rechaza duplicados por SHA-256 y tipos superpuestos | `--alcance abiertos\|completo` (obligatorio), `--corte AAAA-MM-DD` (declarativo), `configuracion.json` (fondo FRG) | Elegir alcance por consola (1/2); el BAT no pide corte | `Conciliacion_general.xlsx` (Resumen + Conciliación general, 237.293 filas en la prueba), `Respaldo_tecnico/` (CSV, `Resumen.json`, `trazabilidad.sqlite`, `COMPLETADO.txt`) | stdlib (lector XML propio, escritor XLSX propio, sqlite) |
| **Controles SGA** (`Control SGA/control_sga.py` + `excel_sga.py`) | 1.5 (22/10/2026) | 1 reporte histórico SGA completo (hoja detectada por columnas) | `--corte` (Enter = hoy), `--reglas reglas.json` (opcional) | Confirmar fecha por consola; revisar `reglas_propuestas.json` y, si se validan, volver a correr con `--reglas` | 6 XLSX con solapas (Netos e impuestos, Datos obligatorios, Servicios administrativos, Saldo MORA, Comprobantes abiertos, Concepto/Agrupador), `reglas_propuestas.json`, `ejecucion.json` | stdlib |
| **Control de Mora** (`Control_Mora/control_mora.py`) | s/n (LEEME 22/10) | `Saldo de comprobación*.xlsx` (ERP) + `ReporteHistoricoDeCuentaCorriente*.xlsx` (SGA), por prefijo de nombre | ninguno (constantes: cuentas 113601-113605, BusinessUnit FRG, fondo FRG, grupo Mora) | ninguno | `Resultado_Control_Mora.csv`, `Respaldo_ERP.csv`, `Respaldo_SGA_Mora.csv`, `PROCESO_COMPLETO.txt` | openpyxl |
| **Control de cheques** (`control_cheques/control_cheques.py`) | s/n (docx 22/10) | Excel cheques SGA (`IdCheque`, `Estado`) + Excel Valores registrados de tesorería ERP (`Id de Transacción`, `Estado`, `Pagado a`), detectados por columnas | `--sga`/`--erp` opcionales | ninguno | `Cheques_para_revisar.csv`, `Resumen.txt` | openpyxl |
| **Facturas por listado** (`Facturas_por_listado/listado.py` + `facturas.py`) | 6 (listado) / 5 (facturas.py, recorrido histórico, ya no se usa como entrada) | 1+ listados Excel con columnas CUIT y NumeroFactura (alias, hojas ocultas, primeras 100 filas) | desde/hasta (emisión, leída del PDF), concepto, carpeta destino | **Login en Chrome** y volver a la consola a apretar Enter; OneDrive sincronizando destino | `descarga_<stamp>.csv`, `entrada_a_revisar_<stamp>.csv`, PDFs en `AAAA-MM/concepto/factura.pdf` | playwright (+ Chrome instalado), pdfplumber, openpyxl, venv propio |

Observaciones del análisis (no se corrigen en esta etapa salvo que sean de integración):
- `conciliar.py`: el BAT no declara `--corte`; la elección 1/2 por consola es frágil (último error
  real). `configuracion.json` trae nombres de archivo viejos que ya no se usan (se detectan por
  encabezado); sólo se lee `fondo` y `alcance_erp`. Columnas `Estado revision` y `Observaciones` ya
  existen vacías en la salida: la herramienta las va a llenar con la revisión.
- `control_sga.py`: `START = date(2026,10,1)` (desde cuándo rige el mes exacto para el segundo servicio)
  y las listas de conceptos son constantes; pasan a configuración con esos defaults. `--reglas` sobre
  `reglas_propuestas.json` es un ciclo manual que la herramienta convierte en un paso.
- `control_mora.py`: usa `openpyxl`; la detección de archivos es por prefijo de nombre (distinto al
  resto, que detecta por columnas). Se mantiene, y además se acepta detección por columnas como
  respaldo para elegir el archivo (sin cambiar qué se calcula).
- `control_cheques.py`: `Importe SGA` se formatea con coma sólo si es numérico; estados comparados en
  casefold. Sin cambios.
- `listado.py`/`facturas.py`: `DEST` apunta a la carpeta de OneDrive de la usuaria (la carpeta de OneDrive de la usuaria);
  `facturas.py` v5 (recorrido de toda la biblioteca) queda como módulo de apoyo (`read_pdf`,
  `get_response`, `wait_for_library`, `safe_name`) pero no como flujo. La carpeta `sesion_chrome`
  contiene la sesión laboral: nunca va al repo.
- Todos escriben CSV con `;`, UTF-8 con BOM y protección contra fórmulas (`'` delante de `=+-@`).
  Los dos escritores XLSX propios (general y SGA) no dependen de openpyxl y se conservan tal cual.

## 4. Decisiones de cómo se hace (tomadas por quien diseña)

| Decisión | Elección | Por qué |
|---|---|---|
| Lenguaje y runtime | **Python 3.10+ únicamente**, biblioteca estándar (`http.server`, `json`, `sqlite3`, `threading`, `subprocess`) | Los motores ya son Python; las PCs de destino ya tienen `py`. Un solo runtime, sin puente Node↔Python. De otra herramienta local del autor se toman ideas (almacén JSON con backup, trabajos con pasos y consola, eventos SSE, variables de tema con contraste medido), no código ni identidad visual. |
| Dependencias | `openpyxl` 3.1.5 + `et_xmlfile` 2.0.0 empaquetados en `vendor/` (puro Python, licencia MIT) y agregados a `sys.path` al arrancar | Lo usan Mora, Cheques y Facturas. Vendorizarlo evita `pip install` y mantiene idéntica la lectura de valores (fechas, floats) que hoy producen esos scripts. |
| Facturas | Módulo **opcional**: `Instalar descarga de facturas.bat` crea `.venv` con `playwright`, `pdfplumber` (versiones fijadas) y usa el Chrome del sistema. El reporte aparece como "Necesita instalación" con el botón/explicación hasta entonces. | Binarios y navegador no se pueden autocontener. |
| Ejecución de motores | Cada corrida es un **subproceso** `python -I app/reportes/<reporte>/ejecutar.py --trabajo <dir>` que habla con el server por un protocolo de líneas JSON (stdout) y recibe órdenes por stdin | Aísla al server de fallos y del consumo de memoria (450k filas), permite cancelar (kill), pausar (el motor espera una línea en stdin) y usar otro intérprete (el venv de facturas). Las `print()` existentes siguen funcionando: toda línea que no es JSON se muestra como log. |
| Persistencia del dominio | **JSON** en `datos/` (por defecto `%LOCALAPPDATA%\ReportesDeCierre\datos`, sección 14.2): `cierres.json`, `ejecuciones.json`, `configuracion.json`, por cierre `datos/cierres/<id>/archivos/` y por ejecución `datos/ejecuciones/<id>/{parametros.json, resumen.json, triage.json, registro.log, salidas/}` | Lo pidió el usuario; es legible, respaldable y diffeable. Escritura atómica (tmp + rename) y backup fechado en `datos/backup/`. |
| Tablas de resultados | Por ejecución, un `resultados.sqlite` con una tabla por salida (columnas originales + `_fila`, `_estado`, `_obs`) **además** de los archivos originales (XLSX/CSV/JSON) tal cual los producen los motores | La conciliación general tiene 237k filas: la interfaz necesita paginar, filtrar y ordenar sin cargar todo. sqlite es stdlib. `triage.json` es la fuente de verdad de la revisión (se vuelca a sqlite al grabar; si falta el sqlite se reconstruye desde las salidas + triage.json). La usuaria nunca ve la palabra sqlite. |
| Interfaz | Una página (`app/web/index.html` + `app.js` + `estilos.css`) en JS vainilla, sin framework ni build | Autocontenido. |
| Puerto | `127.0.0.1:7310`, o el siguiente libre hasta 7320 | Evita choques con otras herramientas locales. |
| Arranque | `Reportes de cierre.bat` (levanta el server sin ventana y abre el navegador con el token) y `Reportes de cierre - consola.bat` para diagnóstico | Doble clic, como hoy. |
| Ubicación del proyecto | `D:\Desarrollo\Programacion\Automatizacion-reportes` (git, remoto GitHub del usuario) | Al lado de los originales; el nombre del repo. |
| Originales | Se copian a `legado/<programa>/` sin datos, sólo para la regresión y como referencia; no se ejecutan desde la herramienta | Permite diffear resultados viejo vs nuevo en cualquier momento. |
| Nombre visible | **Reportes de cierre** | Describe lo que hace, sin marcas. |

## 5. Modelo de dominio

```
Cierre          { id, periodo: "AAAA-MM", corte: "AAAA-MM-DD", nombre, creado, cerrado: null|fecha, notas,
                  archivos: [{id, nombre, bytes, sha256, tipo, hoja, filas, subido}] }   ← biblioteca del cierre (sección 14.4)
Ejecucion       { id, cierreId, reporte, version: n (por cierre+reporte), estado,
                  creado, inicio, fin, parametros: {...}, entradas: [{clave, archivoIds: [...]}],   ← uno o más tramos por entrada
                  resumen: {...del motor...}, salidas: [{tabla, titulo, filas, archivo}],
                  revision: {pendientes, revisadas, omitidas}, trabajoId, final: bool }
Estados         borrador → listo → corriendo → esperando → ok | error | cancelado
Trabajo         { id, ejecucionId, estado, paso, pasos:[{titulo, estado, lineas[]}], progreso, espera: {id, mensaje, boton}|null }
Triage          triage.json: { "<tabla>": { "<clave de negocio>": { estado: pendiente|revisada|omitida, obs, fecha, origen } } }  (sección 14.1)
Configuracion   { tema, reportes: { <reporte>: { parametros: {...defaults...}, reglas: {...} } }, limites }
```

Un reporte dentro de un cierre puede tener varias versiones (re-ejecuciones). La última marcada como
`final` es la que el historial muestra como resultado del cierre. Las anteriores se pueden borrar
desde el historial (con confirmación; se borra la carpeta de la ejecución).

## 6. El asistente de pasos (igual para los cinco, con contenido propio)

1. **Archivos**: arrastrar o elegir archivos (se copian a `entradas/` de la ejecución; también se puede
   elegir una carpeta de la PC para tomarlos sin copiar, guardando ruta y SHA-256). El server detecta el
   tipo de cada archivo con el detector del motor (SGA/ERP/listado...) y muestra qué reconoció en
   palabras; no se avanza con faltantes, duplicados o ambigüedades. Acción manual típica: cambiar un
   archivo.
2. **Opciones**: formulario generado desde la definición del reporte (fecha de corte, alcance, listas
   editables de exclusiones, qué salidas generar, reglas confirmadas), con ayuda en cada campo. Los
   defaults vienen de la configuración del reporte (persistida) y ésta de las constantes actuales. Un
   cambio puede guardarse "para los próximos cierres".
3. **Ejecución**: consola en vivo en lenguaje llano (log, progreso), botón cancelar. Si el motor pide
   una acción manual (p. ej. *Iniciá sesión en Chrome y cuando veas Comprobantes apretá Continuar*), el
   paso muestra el mensaje y el botón; el trabajo queda `esperando`. Para SGA, al terminar la primera
   corrida se ofrece el sub-paso **Reglas propuestas**: tabla editable (concepto → datos exigidos,
   agrupador, confirmado) que se guarda en la configuración y re-ejecuta con esas reglas.
4. **Resultados**: una pestaña por tabla de salida. Grilla paginada (server-side), búsqueda, filtros
   por columna, orden, selección múltiple; acciones: *Revisada*, *Omitir*, *Pendiente*, *Observación*.
   Contadores por estado. Las celdas que el motor marcó (anaranjadas en SGA) se muestran igual.
5. **Exportar y cerrar**: descarga del original (sin tocar) y del **trabajado**: mismo libro, con
   `Estado revisión` y `Observaciones` completos, y opción de excluir omitidas. Marcar la ejecución como
   final del cierre. Volver a cualquier paso crea una versión nueva al re-ejecutar.

## 7. Definición de un reporte (para poder agregar más)

`app/reportes/<codigo>/reporte.py` exporta un diccionario `REPORTE`:

```python
REPORTE = {
  'codigo': 'control_mora', 'nombre': 'Control de Mora', 'descripcion': '...',
  'entradas': [ {'clave':'erp', 'titulo':'Saldo de comprobación (ERP)', 'detectar': fn, 'cantidad': 1},
                {'clave':'sga', 'titulo':'Histórico de cuenta corriente (SGA)', 'detectar': fn, 'cantidad': 1} ],
  'parametros': [ {'clave':'cuentas','tipo':'lista','titulo':'Cuentas ERP FRG','default':[...], 'ayuda': '...'}, ... ],
  'salidas': [ {'tabla':'resultado','titulo':'Resultado','archivo':'Resultado_Control_Mora.csv'}, ... ],
  'requiere': 'stdlib' | 'venv_facturas',
  'pausas': ['login_sharepoint'],   # ids de las esperas que puede pedir
}
```

`ejecutar.py` es el punto de entrada del subproceso: carga `parametros.json`, llama al motor, escribe
las salidas originales en `salidas/`, vuelca cada tabla a `resultados.sqlite` mediante
`app/reportes/_comun/tablas.py` y emite `resumen` por el protocolo. El motor (`motor.py`) es el script
original con cambios mínimos: sin `input()`, sin `print` de rutas propias, parámetros por argumento,
constantes tomadas de los parámetros (con los mismos defaults).

### Protocolo subproceso ↔ server (líneas JSON por stdout; stdin para órdenes)
```
{"t":"log","m":"Leyendo ERP..."}              {"t":"progreso","v":0.42,"m":"120.000 filas"}
{"t":"paso","m":"Leyendo SGA completo"}       {"t":"esperar","id":"login","m":"...","boton":"Continuar"}
{"t":"tabla","tabla":"resultado","filas":123} {"t":"resumen","datos":{...}}
{"t":"error","m":"..."}                       ← stdin: {"t":"continuar","id":"login"} | {"t":"cancelar"}
```

## 8. API del server (JSON, sólo `127.0.0.1`)

```
GET  /                      página (requiere ?t=<token> la primera vez; después cookie SameSite=Strict)
GET  /api/estado            versión, reportes disponibles (instalado/no), trabajos activos, python detectado
GET  /api/cierres  POST /api/cierres  PATCH /api/cierres/<id>  DELETE /api/cierres/<id>
GET  /api/ejecuciones?cierre=  POST /api/ejecuciones {cierre, reporte}  GET/PATCH/DELETE /api/ejecuciones/<id>
POST /api/ejecuciones/<id>/entradas (bytes + cabecera con el nombre)  DELETE .../entradas/<nombre>
POST /api/ejecuciones/<id>/entradas/carpeta {ruta}        (toma archivos de una carpeta local, sólo lectura)
POST /api/ejecuciones/<id>/ejecutar {parametros}          → trabajo
POST /api/trabajos/<id>/continuar {id}   POST /api/trabajos/<id>/cancelar
GET  /api/ejecuciones/<id>/tablas/<tabla>?desde=&cantidad=&orden=&filtro=&estado=
POST /api/ejecuciones/<id>/triage {tabla, filas:[...], estado, obs}
GET  /api/ejecuciones/<id>/exportar?tabla=|libro=&incluirOmitidas=0|1   → xlsx
GET  /api/ejecuciones/<id>/archivos/<nombre>                             → salida original
GET  /api/configuracion  PATCH /api/configuracion
GET  /api/eventos          SSE: trabajos, ejecuciones
```

## 9. Seguridad (OWASP Top 10 aplicado a una herramienta local)

| Riesgo | Qué se hace |
|---|---|
| A01 Control de acceso | Escucha sólo en `127.0.0.1`. Token aleatorio por arranque (`secrets.token_urlsafe`), entregado en la URL que abre el BAT y luego en cookie `HttpOnly; SameSite=Strict`; toda `/api/*` lo exige. Rutas de archivos normalizadas y confinadas a `datos/` (sin `..`, sin unidades). La "carpeta local" de entradas se lee, nunca se escribe. |
| A02 Criptografía | No hay credenciales. La sesión de Chrome de facturas vive en `datos/sesion_chrome/` (ignorado por git) y el LEEME avisa que no se comparta `datos/`. SHA-256 de cada entrada. |
| A03 Inyección | Sin `shell=True`; argumentos como lista. SQL sólo con parámetros; nombres de tabla/columna validados contra la definición del reporte. CSV/XLSX con protección de fórmulas (ya existe). HTML: todo dato pasa por `esc()`; sin `innerHTML` con datos. |
| A04 Diseño inseguro | Acciones destructivas (borrar ejecución/cierre) con confirmación; límites de tamaño (200 MB por archivo, configurable); un solo trabajo por ejecución. |
| A05 Configuración | Cabeceras: `Content-Security-Policy: default-src 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` en la API. Sin listado de directorios. Errores al usuario sin trazas; traza completa en `registro.log`. |
| A06 Componentes | Versiones fijadas (`vendor/VERSIONES.md` con origen y SHA-256 de los wheels; `requirements-facturas.txt` con rangos cerrados). |
| A07 Autenticación | Token + verificación de `Origin`/`Sec-Fetch-Site` en toda petición que modifica (anti-CSRF desde otra pestaña). |
| A08 Integridad | Escritura atómica de JSON, backup antes de grabar, SHA-256 de entradas y de salidas en `resumen.json`. |
| A09 Registro | `registro.log` por ejecución y `datos/servidor.log` rotado; sin datos personales de más que los propios de los reportes. |
| A10 SSRF | El único cliente HTTP (facturas) sólo acepta URLs del origen de SharePoint configurado (`check_url`, ya existe) y lo muestra en Opciones. |

## 10. Historial

- Vista **Cierres**: tarjetas por período con el estado de cada reporte (sin correr / en curso /
  listo con N pendientes / final). Un cierre se crea con período y fecha de corte (que se propone como
  default de los cinco reportes).
- Vista **Historial**: todas las ejecuciones, filtrables por reporte, cierre y estado; cada una abre
  sus resultados y su registro. Versiones anteriores de un mismo reporte se pueden borrar; la final no
  sin confirmación extra.
- **Limpieza**: desde Configuración, borrar los archivos de entrada copiados de ejecuciones no finales
  de cierres anteriores (son los pesados); los resultados y la revisión se conservan.

## 11. Documentación y reglas para agentes

- `LEEME.md`: para las usuarias. Instalación (extraer, doble clic), uso por reporte, qué significa cada
  estado, qué hacer ante errores. Sin jerga.
- `docs/reglas/<reporte>.md`: las reglas de negocio de cada control, redactadas a partir de los TXT y
  DOCX actuales (son la fuente de verdad del "qué calcula"), con la fecha y versión de origen.
- `docs/pendientes.md`: correcciones menores y de salida detectadas, no aplicadas.
- `AGENTS.md` (canónico, lo lee Codex): arquitectura, reglas de trabajo, prohibiciones (no tocar la
  matemática sin regresión, no commitear `datos/`, lenguaje llano en la interfaz, etc.). `CLAUDE.md` =
  `@AGENTS.md` + lo propio de Claude Code. `GEMINI.md` (Antigravity) remite a `AGENTS.md`.
  `.claude/rules/reportes/<reporte>.md` con frontmatter `paths` y `.agent/rules/<reporte>.md`
  (Antigravity) con `trigger: glob`, ambos apuntando a `docs/reglas/<reporte>.md` para no duplicar.

## 12. Pruebas y regresión

- `tests/` con `unittest` (stdlib): fixtures XLSX sintéticos (se reutiliza el generador de
  `pruebas_general.py`), un test por motor que compara con salidas doradas generadas por el script
  original sobre el mismo fixture (`tests/dorados/`), tests del almacén, del protocolo, del server
  (http.client contra un puerto libre y una carpeta temporal) y del triage/exportación.
- `herramientas/regresion_legado.py`: corre el legado y el motor nuevo sobre los archivos reales de una
  carpeta y compara byte a byte los CSV/JSON y celda a celda los XLSX (ignorando sellos de tiempo y
  rutas). Se corre a mano antes de dar por buena una refactorización; su resultado se anota en
  `docs/regresion.md`.
- `Reportes de cierre - consola.bat pruebas` corre todos los tests.

## 13. Entradas en varios archivos (tramos)

Los sistemas de origen cortan la exportación a Excel cerca de las **454.000 filas**. Cuando el reporte es
más largo, la usuaria recibe dos (o más) archivos que se complementan: mismos encabezados, filas
siguientes. La herramienta lo contempla en todos los reportes:

- Cada entrada del asistente acepta **uno o más archivos del mismo tipo** ("tramos"). El detector
  reconoce que son del mismo tipo (mismos encabezados); se ordenan por nombre y se leen como si fueran
  uno solo, en ese orden. Archivos idénticos (mismo SHA-256) se rechazan como hoy.
- Un tramo que tenga exactamente 450.000 filas, o entre 453.000 y 455.000, dispara el aviso
  "posible descarga recortada" (hoy sólo existe en Conciliación general para 450.000; se generaliza
  como **aviso**, nunca como bloqueo).
- Para el motor, el origen de cada fila es `(archivo, hoja, fila)`. Con **un solo archivo** las salidas
  son idénticas a las actuales (la fila de origen sigue siendo el número de fila del Excel). Con más
  de uno, las salidas que informan fila de origen agregan la columna **Archivo** a la derecha de esa
  fila, para que la usuaria encuentre la línea en el Excel correcto. Ninguna clave interna usa el
  número de fila solo: donde hoy se indexa por `_fila` (Controles SGA) pasa a indexarse por
  `(archivo, fila)`.
- Las entradas que hoy exigen "un solo archivo" (Controles SGA, Mora, Cheques) pasan a exigir "uno
  o más del mismo tipo". Conciliación general ya distingue SGA de hasta tres ERP por tipo de
  transacción; los tramos se suman a eso: varios archivos SGA se concatenan; varios ERP del mismo tipo
  de transacción también (hoy eso se rechaza como "tipo repetido": pasa a aceptarse sólo cuando los
  archivos se declaran tramos de la misma descarga, y el aviso de descarga recortada acompaña).

## 14. Decisiones tras la revisión del constructor

Un revisor independiente leyó el diseño y planteó cinco preguntas. Las respuestas son decisiones de
quien diseña (marcadas como tales) y se incorporan al diseño:

1. **La revisión se traslada.** El triage se guarda por **clave de negocio** de cada tabla, definida
   en `REPORTE['salidas'][i]['clave']` (p. ej. Conciliación: Tipo + Cliente + Comprobante; Controles
   SGA: Fondo + CodigoEmpresa + NumeroFactura + NumeroComprobanteImputacion + Control; Cheques: ID SGA
   + Motivo; Mora: Concepto; Facturas: CUIT + Factura). `_fila` queda sólo para paginar. Al crear una
   versión nueva dentro del mismo cierre, las marcas de la anterior se aplican automáticamente a las
   filas con la misma clave (y se informa cuántas se trasladaron y cuántas quedaron sin destino). Entre
   cierres no es automático: en Resultados hay una acción **"Traer la revisión del cierre anterior"**
   que aplica las *omitidas* y sus observaciones del cierre previo (las *revisadas* no, porque son de
   ese mes). `triage.json` guarda `{tabla: {clave: {estado, obs, fecha, origen: "manual"|"version"|"cierre"}}}`.
2. **Los datos viven fuera de carpetas sincronizadas.** `datos/` va por defecto en
   `%LOCALAPPDATA%\ReportesDeCierre\datos` (configurable en Opciones), independientemente de dónde se
   extraiga el programa, porque la instalación actual está dentro de una biblioteca de SharePoint
   sincronizada y ahí sqlite se corrompe, los Excel de 64 MB se subirían y la sesión de Chrome quedaría
   compartida. El LEEME lo explica en una línea. Para compartir un cierre con otra persona hay una
   acción **"Exportar cierre"** (ZIP con resultados trabajados, resumen y observaciones; sin entradas
   ni sesión) y la contraparte **"Importar cierre"** (sólo lectura: se ve, no se re-ejecuta). Sigue
   siendo "una persona, una PC" en tiempo real; lo compartido es el resultado.
3. **El repositorio es público** (verificado: responde sin autenticación). Por lo tanto: la URL de
   SharePoint, el nombre de la organización, los nombres de personas y cualquier dato real **no van
   en el código ni en `docs/`**. Los defaults que hacen falta para dar el mismo resultado y no son
   datos personales (listas de conceptos, cuentas contables, el comprobante excluido) quedan en el
   código como hoy. La URL de SharePoint y la carpeta destino de facturas se piden en Opciones la
   primera vez y viven en `datos/configuracion.json`. `legado/` lleva sólo código (sin `Entrada/`,
   sin `sesion_chrome`, sin `configuracion.json` con nombres de archivos). `docs/regresion.md` registra
   que se comparó y qué archivos (por SHA-256 y cantidad de filas), sin importes.
4. **Biblioteca de archivos por cierre.** Las entradas se guardan una vez por cierre en
   `datos/cierres/<id>/archivos/<sha256 corto>-<nombre>` y las ejecuciones las **referencian**
   (`Ejecucion.entradas[i].archivoId`). Al pedir el histórico SGA en Controles SGA, Mora o
   Conciliación, el paso 1 ofrece los archivos de ese tipo que el cierre ya tiene ("Ya tenés el
   histórico de cuenta corriente de este cierre: ¿lo uso?"). La limpieza borra archivos del cierre que
   ninguna ejecución final referencia.
5. **Una sola instancia y apagado explícito.** Al arrancar, el server escribe
   `datos/.servidor.json` (pid, puerto, token, inicio). El BAT, antes de levantar otro, lee ese archivo
   y prueba `GET /api/estado` con el token: si responde, sólo abre el navegador en esa instancia; si
   no, borra el archivo y levanta una nueva (el rango de puertos existe para cuando el 7310 lo ocupa
   otro programa, no para correr dos copias). En la interfaz hay **"Cerrar la herramienta"** (apaga el
   server si no hay trabajos corriendo; si los hay, avisa). Además, el server se apaga solo tras 3
   horas sin ninguna petición y sin trabajos activos.

## 15. Qué queda a criterio de quien construye

- Diseño visual concreto (tipografía, espaciados, iconografía) dentro de los temas definidos.
- Formato exacto del Excel "trabajado" para los reportes que hoy sacan CSV (se agrega un XLSX con las
  mismas columnas + revisión; el CSV original se conserva).
- Cómo se muestran celdas resaltadas y notas de solapa en la grilla.
- Tamaño de página de la grilla y estrategia de filtros.
- Redacción de los mensajes de error para la usuaria.
