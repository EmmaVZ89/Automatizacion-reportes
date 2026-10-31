# Reportes de cierre: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Una herramienta local única (server Python en 127.0.0.1 + interfaz web) que corre los cinco reportes del cierre mensual con el mismo resultado que los scripts originales, los guía por pasos, permite revisar cada salida y guarda historial por cierre.

**Architecture:** Server HTTP de biblioteca estándar que sirve una página vainilla y una API JSON; dominio en JSON (`almacen.py`), tablas de resultado en un sqlite por ejecución (`tablas.py`); cada reporte corre como subproceso con un protocolo de líneas JSON (`trabajos.py` ↔ `reportes/_comun/protocolo.py`); los motores son los scripts originales con cambios mínimos, verificados contra salidas doradas del legado.

**Tech Stack:** Python 3.10+ (stdlib: `http.server`, `sqlite3`, `json`, `subprocess`, `threading`, `unittest`), openpyxl 3.1.5 + et_xmlfile 2.0.0 vendorizados, HTML/CSS/JS sin framework. Facturas: Playwright + pdfplumber en `.venv` opcional.

**Spec:** `docs/superpowers/specs/2026-10-31-herramienta-cierre-design.md`

## Global Constraints

- Python mínimo **3.10**; nada fuera de stdlib salvo `vendor/` (openpyxl 3.1.5, et_xmlfile 2.0.0) y el `.venv` opcional de facturas.
- **Resultado idéntico** al legado con un solo archivo por entrada y parámetros default: la regresión (`herramientas/regresion_legado.py`) tiene que dar "sin diferencias" para Conciliación, Controles SGA, Mora y Cheques sobre los archivos reales.
- Interfaz y mensajes en castellano, lenguaje llano, sin jerga (nada de job, token, JSON, sqlite, puerto en pantalla). Nombres de reportes: *Conciliación general*, *Controles SGA*, *Control de Mora*, *Control de cheques*, *Descarga de facturas*.
- Repo público: ni URL de SharePoint, ni nombres de organización o personas, ni archivos de datos en el código, `legado/` ni `docs/`.
- `datos/` por defecto en `%LOCALAPPDATA%\ReportesDeCierre\datos`; nunca dentro del programa salvo variable `REPORTES_DATOS`.
- Server sólo en `127.0.0.1`, puerto 7310 a 7320; token por arranque; cabeceras CSP/nosniff/no-referrer; `/api/*` con `Cache-Control: no-store`.
- Escritura de JSON atómica (tmp + rename) con backup en `datos/backup/`.
- Cada entrada acepta **uno o más tramos**; con un solo archivo la salida no cambia; con varios se agrega la columna `Archivo` a la derecha de la fila de origen.
- Sin commits automáticos: ningún paso de este plan commitea; el usuario revisa y commitea.
- Tests con `python -m unittest discover -s tests -v` desde la raíz; fixtures sintéticos, nunca datos reales en el repo.

## Review Focus

1. Un Excel con celdas de fórmula sin valor guardado o con tipo de error (`t="e"`) en una columna requerida: debe cortar con mensaje claro, nunca dar un resultado parcial (test en Task 8 y Task 9).
2. Un segundo doble clic en el BAT con el server ya corriendo: debe abrir el navegador contra la instancia viva, nunca una segunda instancia sobre los mismos datos (test en Task 18).
3. Cerrar la pestaña del navegador con un trabajo corriendo y volver a abrirla: el trabajo sigue, la consola se recupera desde el registro (test en Task 16).
4. Un archivo de 64 MB subido por el navegador: el server lo recibe por streaming a disco sin cargarlo entero en memoria y rechaza más de 200 MB con mensaje (test en Task 15).
5. Marcas de revisión de una versión anterior cuyas filas ya no existen: se informa el conteo de "sin destino" y no se pierde nada de `triage.json` (test en Task 5).

---

## Estructura de archivos

```
Automatizacion-reportes/
  AGENTS.md  CLAUDE.md  GEMINI.md  LEEME.md  .gitignore  requirements-facturas.txt
  Reportes de cierre.bat                 doble clic: levanta o reusa el server y abre el navegador
  Reportes de cierre - consola.bat       mismo arranque con ventana; `pruebas` corre los tests
  Instalar descarga de facturas.bat      crea .venv con playwright + pdfplumber
  app/
    __init__.py  version.py              VERSION = '2026.10.31'
    arranque.py                          sys.path (vendor), carpeta datos, instancia única, abrir navegador
    servidor.py                          ThreadingHTTPServer, rutas, estáticos, SSE
    rutas_api.py                         handlers de /api/* (usa dominio, trabajos, tablas, exportar)
    seguridad.py                         token, cookie, Origin, cabeceras, nombres y rutas seguras
    almacen.py                           JSON atómico + backup
    dominio.py                           cierres, archivos del cierre, ejecuciones, versiones
    trabajos.py                          subprocesos, protocolo lado server, estados, eventos
    eventos.py                           bus de eventos para SSE
    tablas.py                            sqlite por ejecución: cargar, consultar, triage, trasladar
    exportar.py                          xlsx trabajado y zip de cierre
    catalogo.py                          registro de reportes y disponibilidad (stdlib / venv)
    web/ index.html  app.js  estilos.css
    reportes/
      _comun/ protocolo.py  entradas.py  salidas.py  xlsx_escritura.py
      conciliacion_general/ reporte.py  motor.py  excel.py  ejecutar.py
      controles_sga/        reporte.py  motor.py  excel.py  ejecutar.py
      control_mora/         reporte.py  motor.py  ejecutar.py
      control_cheques/      reporte.py  motor.py  ejecutar.py
      descarga_facturas/    reporte.py  motor.py  sharepoint.py  ejecutar.py
  vendor/ openpyxl/  et_xmlfile/  VERSIONES.md
  legado/ conciliacion_general/  controles_sga/  control_mora/  control_cheques/  descarga_facturas/  (sólo .py, .txt, .bat, docx)
  herramientas/ regresion_legado.py  empaquetar.py
  tests/ fixtures.py  test_*.py  dorados/<reporte>/...
  docs/ reglas/*.md  pendientes.md  regresion.md  superpowers/
  .claude/rules/reportes/*.md   .agent/rules/*.md
```

---

## Fase 0: base del repositorio

### Task 1: Esqueleto, vendor y legado

**Files:**
- Create: `.gitignore`, `app/__init__.py`, `app/version.py`, `vendor/VERSIONES.md`, `requirements-facturas.txt`, `tests/__init__.py`, `tests/fixtures.py`, `docs/pendientes.md`, `docs/regresion.md`
- Copy: `vendor/openpyxl/`, `vendor/et_xmlfile/` desde los wheels (ya descargados y verificados: openpyxl `5282c12b…9de2`, et_xmlfile `7a91720b…2caa`)
- Copy: `legado/<reporte>/` con los `.py`, `.txt`, `.bat`, `.docx` de `D:\Desarrollo\Programacion\Automatizacion` (sin `entradas/`, `Entrada/`, `resultados/`, `SALIDA/`, `.venv`, `__pycache__`, `configuracion.json`, `ERROR_ULTIMA_EJECUCION.txt`)

**Interfaces:**
- Produces: `tests/fixtures.py` con `xlsx_sintetico(path, hojas: list[tuple[str, list[list]]])` (el generador de `pruebas_general.py`, celdas `inlineStr` sin atributo `r`) y `xlsx_openpyxl(path, hojas)` (mismo contrato, escrito con el openpyxl vendorizado, para los motores que leen con openpyxl); `carpeta_temporal()` context manager.
- Produces: `app/version.py` → `VERSION = '2026.10.31'`.

- [ ] **Step 1:** `git init` en `D:\Desarrollo\Programacion\Automatizacion-reportes`, rama `main`, remoto `origin` = `https://github.com/EmmaVZ89/Automatizacion-reportes` (sin push).
- [ ] **Step 2:** `.gitignore`: `datos/`, `.venv/`, `__pycache__/`, `*.pyc`, `*.sqlite`, `sesion_chrome/`, `dist/`, `tests/_tmp/`.
- [ ] **Step 3:** Copiar vendor y legado como se indica; `vendor/VERSIONES.md` con nombre, versión, licencia, origen (PyPI) y SHA-256 de cada wheel.
- [ ] **Step 4:** Escribir `tests/fixtures.py` y el test `tests/test_fixtures.py::test_xlsx_sintetico_se_lee_con_openpyxl` (crea un libro con dos hojas, lo abre con `vendor` openpyxl y compara valores).
- [ ] **Step 5:** Run `python -m unittest tests.test_fixtures -v` → PASS (con `vendor/` agregado al path desde `tests/__init__.py`).

---

## Fase 1: núcleo del server (sin reportes)

### Task 2: Almacén JSON atómico con backup

**Files:**
- Create: `app/almacen.py`, `tests/test_almacen.py`

**Interfaces:**
- Produces: `class Almacen(ruta: Path, ahora=time.time, max_backups=30, minutos_entre_backups=10)` con `.datos: dict` (`{'version': 1, 'entradas': []}` si no existe), `.guardar()`, `.recargar()`, `.solo_lectura: bool`, `.motivo: str|None`; `class AlmacenCorrupto(Exception)`.
- Produces: `escribir_json_atomico(ruta: Path, objeto) -> None` y `leer_json(ruta: Path, default)`.

- [ ] **Step 1:** Tests: `test_guardar_escribe_tmp_y_renombra` (no queda `.tmp`), `test_json_invalido_pasa_a_solo_lectura_y_guardar_lanza`, `test_backup_fechado_en_subcarpeta_backup_y_poda_a_max`, `test_dos_guardados_en_menos_de_n_minutos_un_solo_backup`.
- [ ] **Step 2:** Run → FAIL (módulo inexistente).
- [ ] **Step 3:** Implementar `app/almacen.py` (backup `backup/<base>-AAAAMMDD-HHMMSS.json`, poda por nombre ordenado).
- [ ] **Step 4:** Run → PASS.

### Task 3: Seguridad: token, cookie, Origin, nombres y rutas

**Files:**
- Create: `app/seguridad.py`, `tests/test_seguridad.py`

**Interfaces:**
- Produces: `nuevo_token() -> str` (`secrets.token_urlsafe(32)`); `cookie_de_token(token) -> str` (`reportes_token=<t>; Path=/; HttpOnly; SameSite=Strict`); `token_de_peticion(headers, query) -> str|None` (query `t` o cookie); `peticion_autorizada(headers, query, token, modifica: bool, host: str) -> tuple[bool, str]` (modifica ⇒ `Origin` ausente o igual a `http://<host>`, y `Sec-Fetch-Site` ∈ {`same-origin`, `none`} si viene); `CABECERAS_BASE: dict` (CSP `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`); `nombre_seguro(nombre: str) -> str` (sólo nombre base, letras/números/`._ -()`, máx 120, extensión en minúsculas); `ruta_confinada(base: Path, relativa: str) -> Path` (lanza `ValueError` si sale de `base`); `EXT_ENTRADA = {'.xlsx', '.xlsm'}`.

- [ ] **Step 1:** Tests: `test_cookie_httponly_samesite_strict`, `test_peticion_que_modifica_con_origin_ajeno_se_rechaza`, `test_peticion_get_sin_origin_se_acepta`, `test_nombre_seguro_quita_carpetas_y_caracteres`, `test_ruta_confinada_rechaza_punto_punto_y_unidad`, `test_token_desde_query_o_cookie`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS.

### Task 4: Protocolo motor ↔ server y corredor de trabajos

**Files:**
- Create: `app/reportes/__init__.py`, `app/reportes/_comun/__init__.py`, `app/reportes/_comun/protocolo.py`, `app/eventos.py`, `app/trabajos.py`, `tests/test_protocolo.py`, `tests/test_trabajos.py`, `tests/motor_falso.py`

**Interfaces:**
- Produces (lado motor, `protocolo.py`, sin dependencias): `log(m)`, `paso(m)`, `progreso(v: float, m='')`, `tabla(nombre, filas: int)`, `resumen(datos: dict)`, `error(m)`, `esperar(id, mensaje, boton='Continuar') -> None` (escribe la línea `esperar`, bloquea leyendo stdin hasta `{"t":"continuar","id":id}`; `{"t":"cancelar"}` lanza `Cancelado`), `class Cancelado(Exception)`. Todas escriben una línea JSON en stdout con `flush`. Si stdout no es el server (`REPORTES_PROTOCOLO` ausente), `log` imprime texto plano y `esperar` usa `input()` (así cada `ejecutar.py` sirve también por consola).
- Produces (`eventos.py`): `class Bus` con `suscribir() -> queue.Queue`, `desuscribir(q)`, `emitir(tipo: str, datos: dict)`.
- Produces (`trabajos.py`): `class Trabajos(archivo: Path, bus: Bus, ahora=time.time)` con `listar() -> list[dict]`, `obtener(id) -> dict|None`, `activos() -> list[dict]`, `lanzar(ejecucion_id: str, comando: list[str], cwd: Path, env: dict, registro: Path) -> dict` (un trabajo por ejecución: lanza `ValueError('Ya hay un trabajo corriendo para esta ejecución')`), `continuar(id, espera_id) -> bool`, `cancelar(id) -> bool`, `al_terminar(fn(trabajo))`. Estados: `corriendo`, `esperando`, `ok`, `error`, `cancelado`, `interrumpido` (los que estaban activos al arrancar). Trabajo: `{id, ejecucionId, estado, paso, progreso, lineas: [...] (máx 400, el resto sólo en registro.log), espera: {id, mensaje, boton}|None, tablas: {nombre: filas}, resumen: dict|None, inicio, fin, error}`. Persiste en `trabajos.json` con debounce de 200 ms. Lee stdout del subproceso en un hilo: línea JSON válida ⇒ evento; otra ⇒ `log`. stderr ⇒ registro.log y, al terminar con código ≠ 0 sin `error` previo, `error = última línea de stderr` en lenguaje llano ("El reporte terminó con un error; ver el registro").

- [ ] **Step 1:** `tests/motor_falso.py`: script que emite `paso`, `log`, `progreso`, `tabla`, `esperar('login', ...)`, `resumen`; con `--fallar` escribe a stderr y sale 1; con `--lento` duerme 10 s. Tests: `test_motor_falso_llega_a_esperando_y_continua_hasta_ok`, `test_cancelar_mata_el_proceso_y_queda_cancelado`, `test_salida_no_json_se_registra_como_log`, `test_codigo_distinto_de_cero_queda_error_con_mensaje_llano`, `test_al_arrancar_los_activos_quedan_interrumpidos`, `test_lineas_se_acotan_a_400_y_registro_log_las_tiene_todas`, `test_protocolo_sin_server_usa_input` (monkeypatch `input`).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS (timeouts de test ≤ 20 s).

### Task 5: Tablas de resultado en sqlite, triage y traslado

**Files:**
- Create: `app/tablas.py`, `app/reportes/_comun/salidas.py`, `tests/test_tablas.py`

**Interfaces:**
- Produces (`salidas.py`, lado motor): `class Volcador(ruta_sqlite: Path)` con `tabla(nombre: str, columnas: list[str], filas: Iterable[list], clave: list[str], marcas: Iterable[tuple[int, str]] = ())` (crea tabla `t_<nombre>` con columnas `_fila INTEGER PRIMARY KEY`, `_clave TEXT`, `_estado TEXT DEFAULT 'pendiente'`, `_obs TEXT DEFAULT ''`, `_marcas TEXT` (JSON de columnas resaltadas) + una columna TEXT por columna original (nombre saneado, mapa guardado en tabla `_columnas(tabla, posicion, nombre, columna)`); `_clave` = valores de `clave` unidos por `\x1f`; inserta por lotes de 5000; emite `protocolo.tabla` al cerrar), `cerrar()`.
- Produces (`tablas.py`, lado server): `class Tablas(ruta_sqlite: Path)` con `listar() -> list[{tabla, titulo?, columnas, filas, estados: {pendiente, revisada, omitida}}]`, `consultar(tabla, desde=0, cantidad=100, orden: str|None, descendente=False, filtro: str='', estado: str|None, columna_filtro: str|None) -> {filas: [dict], total: int}` (filtro `LIKE` escapado sobre todas las columnas o una; `orden` validado contra `_columnas`), `marcar(tabla, filas: list[int], estado, obs: str|None) -> int`, `triage() -> dict` (`{tabla: {clave: {estado, obs, fecha, origen}}}` de lo no pendiente), `aplicar_triage(triage: dict, origen: str) -> {aplicadas, sin_destino}`, `filas_completas(tabla, incluir_omitidas=True) -> Iterable[dict]`.
- Produces: `app/dominio.py` usa `Tablas.triage()` para escribir `triage.json` tras cada `marcar` (Task 6).

- [ ] **Step 1:** Tests: `test_volcar_y_listar_conserva_orden_y_nombres_de_columnas`, `test_consultar_pagina_filtra_y_ordena`, `test_marcar_cambia_estado_y_conteos`, `test_triage_y_aplicar_triage_por_clave_con_sin_destino` (Review Focus 5: tres claves, una no existe ⇒ `sin_destino == 1`, las otras aplicadas con `origen='version'`), `test_orden_por_columna_inexistente_lanza_valueerror`, `test_filtro_con_porcentaje_y_guion_bajo_se_escapa`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS.

### Task 6: Dominio: cierres, archivos del cierre, ejecuciones y versiones

**Files:**
- Create: `app/dominio.py`, `tests/test_dominio.py`

**Interfaces:**
- Consumes: `Almacen`, `escribir_json_atomico`, `nombre_seguro`, `Tablas`.
- Produces: `class Dominio(dir_datos: Path, ahora=...)` con:
  - `crear_cierre(periodo: 'AAAA-MM', corte: 'AAAA-MM-DD', nombre='') -> dict` (periodo único; `ValueError` si repetido o formato inválido), `listar_cierres()`, `obtener_cierre(id)`, `editar_cierre(id, **campos)`, `borrar_cierre(id)` (sólo sin ejecuciones finales; borra `datos/cierres/<id>` y sus ejecuciones).
  - `agregar_archivo(cierre_id, nombre, origen: Path|None, bytes_iter=None) -> dict` (copia a `datos/cierres/<id>/archivos/<sha8>-<nombre>`; SHA-256 calculado al copiar; mismo SHA ⇒ devuelve el existente sin duplicar), `archivos_de(cierre_id) -> list`, `quitar_archivo(cierre_id, archivo_id)` (`ValueError` si lo referencia una ejecución).
  - `crear_ejecucion(cierre_id, reporte: str) -> dict` (versión = máx + 1 por cierre+reporte; carpeta `datos/ejecuciones/<id>/`), `listar_ejecuciones(cierre_id=None, reporte=None)`, `obtener_ejecucion(id)`, `asignar_entradas(id, entradas: {clave: [archivo_ids]})`, `asignar_parametros(id, parametros: dict)`, `actualizar_estado(id, estado, **campos)`, `marcar_final(id)` (desmarca las otras versiones), `borrar_ejecucion(id)` (`ValueError` si es final y no `forzar=True`).
  - `version_anterior(id) -> dict|None`, `trasladar_revision(id) -> {aplicadas, sin_destino}` (lee `triage.json` de la versión anterior del mismo cierre y lo aplica con `origen='version'`), `traer_revision_cierre_anterior(id) -> {...}` (sólo `omitida`, `origen='cierre'`).
  - `guardar_triage(id)` (de `Tablas.triage()` a `triage.json`), `resumen_revision(id) -> {pendientes, revisadas, omitidas}`.
  - `rutas(id) -> {carpeta, parametros, resumen, triage, registro, salidas, sqlite}`.
- Produces: `datos/configuracion.json` vía `leer_configuracion() -> dict` / `guardar_configuracion(dict)` con defaults `{'tema': 'claro', 'limiteMB': 200, 'reportes': {}}`.

- [ ] **Step 1:** Tests: `test_crear_cierre_periodo_unico_y_formato`, `test_agregar_archivo_dedup_por_sha256`, `test_quitar_archivo_referenciado_falla`, `test_version_incrementa_por_cierre_y_reporte`, `test_marcar_final_desmarca_anteriores`, `test_trasladar_revision_usa_version_anterior_y_cuenta_sin_destino`, `test_traer_revision_cierre_anterior_solo_omitidas`, `test_borrar_cierre_con_final_falla`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS.

### Task 7: Entradas comunes (detección y tramos) y catálogo de reportes

**Files:**
- Create: `app/reportes/_comun/entradas.py`, `app/reportes/_comun/xlsx_escritura.py`, `app/catalogo.py`, `tests/test_entradas.py`, `tests/test_catalogo.py`

**Interfaces:**
- Produces (`entradas.py`): `encabezados_xlsx(path, max_filas=30) -> list[(hoja, fila, [encabezados])]` (lector stdlib, primera fila con ≥ 3 celdas no vacías por hoja); `detectar(path, detectores: dict[str, callable]) -> str|None` (`detector(hojas) -> bool`; dos positivos ⇒ `ValueError('El archivo mezcla dos tipos')`); `ordenar_tramos(paths) -> list[Path]` (por nombre, natural: `_1` antes de `_10`); `aviso_recorte(filas: int) -> str|None` (450000 exacto, o 453000–455000); `OrigenFila = namedtuple('OrigenFila', 'archivo hoja fila')`; `filas_sga_sintetico` NO (los fixtures son de tests).
- Produces (`xlsx_escritura.py`): `escribir_libro(path, hojas: list[{nombre, columnas, filas, formatos?, anchos?, nota?, resaltadas?}])`: escritor genérico stdlib, generalización del de `excel_sga.py`, usado por `exportar.py` (los motores conservan sus propios escritores).
- Produces (`catalogo.py`): `REPORTES: dict[str, dict]` cargado de `app/reportes/*/reporte.py` (`REPORTE` con `codigo, nombre, descripcion, entradas, parametros, salidas, requiere, pausas`); `disponibilidad(codigo, raiz) -> {disponible: bool, motivo: str}` (`requiere == 'venv_facturas'` ⇒ existe `.venv/Scripts/python.exe` y `import playwright, pdfplumber` responde 0 en ese intérprete); `interprete(codigo, raiz) -> list[str]` (`[sys.executable, '-I']` o el del venv); `parametros_default(codigo, configuracion) -> dict` (defaults de la definición pisados por `configuracion['reportes'][codigo]['parametros']`); `validar_parametros(codigo, valores) -> dict` (tipos: `fecha`, `texto`, `opcion`, `lista`, `booleano`, `tabla` (lista de dicts con columnas), `ruta`).

- [ ] **Step 1:** Tests: `test_encabezados_detecta_primera_fila_con_datos`, `test_detectar_rechaza_dos_tipos`, `test_ordenar_tramos_natural`, `test_aviso_recorte`, `test_catalogo_carga_cinco_reportes_con_campos_obligatorios`, `test_validar_parametros_fecha_invalida`, `test_escribir_libro_se_abre_con_openpyxl_y_conserva_tipos`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar (las definiciones `reporte.py` mínimas de los cinco reportes van en esta tarea con `entradas`, `parametros` y `salidas` según la sección 3 del spec; los motores llegan en la Fase 2). **Step 4:** Run → PASS.

---

## Fase 2: motores (cada uno: refactor mínimo + dorados + regresión)

Patrón común de cada tarea de motor:
1. Generar **dorados sintéticos**: correr el script de `legado/` sobre fixtures chicos (con `py -3.12` para los que usan openpyxl del sistema, o con `vendor` en el path) y guardar sus salidas en `tests/dorados/<reporte>/` (CSV/JSON/XLSX leído a CSV con openpyxl; sin sellos de tiempo ni rutas).
2. Refactorizar a `motor.py`: misma lógica, funciones con parámetros explícitos, sin `input()`, constantes como parámetros con default igual al actual, origen de fila `(archivo, hoja, fila)`, tramos.
3. `ejecutar.py`: lee `parametros.json` y `entradas.json` del `--trabajo`, llama al motor, escribe salidas originales en `salidas/`, vuelca tablas con `Volcador`, emite `resumen`.
4. Test que compara el motor nuevo contra los dorados en los fixtures; test de tramos (dos archivos que concatenados dan el mismo resultado que uno, más la columna `Archivo`).
5. `herramientas/regresion_legado.py <reporte>` sobre los archivos reales: "sin diferencias" (sección 12 del spec). Los dorados reales ya generados están en el scratchpad de la sesión (`dorado_real/`); la herramienta debe poder regenerarlos desde `legado/`.

### Task 8: Conciliación general

**Files:**
- Create: `app/reportes/conciliacion_general/{motor.py, excel.py, ejecutar.py}`, `tests/test_conciliacion_general.py`, `tests/dorados/conciliacion_general/`
- Modify: `app/reportes/conciliacion_general/reporte.py` (entradas: `sga` (1+ tramos, detector SGA), `erp` (1 a 3 archivos o tramos, detector ERP); parámetros: `alcance` opción {abiertos, completo} sin default (obligatorio), `corte` fecha (default: corte del cierre), `fondo` texto default `Fondo de Riesgo General`; salidas: `resumen` (Resumen, clave `[Control]`), `general` (Conciliación general, clave `[Tipo, Cliente, Comprobante]`))

**Interfaces:**
- Produces: `motor.run(entradas: dict[str, list[Path]], salida: Path, alcance: str, corte: str|None, fondo: str, informar=protocolo) -> dict` (devuelve el `summary` que hoy va a `Resumen.json`); `motor.detectar_tipo(path) -> 'SGA'|'ERP'|None`.
- Tramos: `xlsx_rows` se itera por cada tramo del mismo lado; `origin` = `nombre [hoja]`; manifiesto con una entrada por archivo; el control "Tipo repetido en dos archivos" se mantiene salvo que ambos estén en el mismo grupo de tramos de la entrada.

- [ ] **Step 1:** Dorados sintéticos con `legado/conciliacion_general/conciliar.py` (fixtures de `pruebas_general.setup`, unificado y separado).
- [ ] **Step 2:** Tests: `test_igual_a_dorado_unificado`, `test_igual_a_dorado_separado`, `test_dos_tramos_sga_equivalen_a_uno_y_agregan_archivo`, `test_celda_error_en_columna_requerida_corta` (Review Focus 1), `test_ejecutar_vuelca_dos_tablas_y_resumen`. Run → FAIL.
- [ ] **Step 3:** Implementar `motor.py` (copia de `conciliar.py` con los cambios del patrón), `excel.py` (= `excel_general.py`), `ejecutar.py`.
- [ ] **Step 4:** Run → PASS. **Step 5:** `python herramientas/regresion_legado.py conciliacion_general --entradas "D:\Desarrollo\Programacion\Automatizacion\Automatizacion_General\entradas" --alcance abiertos --corte 2026-10-31` → `SIN DIFERENCIAS` (compara `Conciliacion_general.csv`, `Resumen.json` sin `fuentes[].fecha_descarga` ni rutas, y las dos hojas del XLSX celda a celda).

### Task 9: Controles SGA

**Files:**
- Create: `app/reportes/controles_sga/{motor.py, excel.py, ejecutar.py}`, `tests/test_controles_sga.py`, `tests/dorados/controles_sga/`
- Modify: `reporte.py` (entrada `sga` 1+ tramos; parámetros: `corte` fecha, `inicio_regla_mensual` fecha default `2026-10-01`, `documentos_excluidos` lista default `['CH-20190722105522839']`, `conceptos_exentos` lista (default `EXEMPT_CONCEPTS`), `conceptos_con_aporte` lista default `['SERV. ADMINIST. FRG - 1º', 'SERV. ADMINIST. FRG - 2º', 'DEUDA POR APORTE VENCIDO GTZ']`, `imputacion_condicional` tabla default `CONDITIONAL_IMPUTATION`, `imputacion_distinta_permitida` lista default `['DEUDA POR APORTE NO VIGENTE - RDO. EJ.']`, `facturas_oficiales` lista default `['FC-A','FC-B','FE-A']`, `tolerancia` texto default `0.02`, `salidas_a_generar` lista de las 6 (default todas), `reglas` tabla (concepto, datos, datos_confirmados, agrupador, agrupador_confirmado; default vacía ⇒ propuesta estadística); salidas: una tabla por solapa: `netos_mora`, `netos_mes`, `netos_historico`, `datos_anio`, `datos_historico`, `servicios_anio`, `servicios_historico`, `saldo_mora`, `abiertos`, `agrupador_anio`, `agrupador_historico`; claves: netos `[FondoDeRiesgo, CodigoEmpresa, NumeroFactura, NumeroComprobanteImputacion, Fila SGA]`, datos/agrupador `[FondoDeRiesgo, CodigoEmpresa, NumeroFactura, NumeroComprobanteImputacion, Control]`, servicios `[FondoDeRiesgo, CodigoEmpresa, NumeroDeAporte, Control]`, abiertos `[FondoDeRiesgo, CodigoEmpresa, Comprobante]`, saldo_mora `[FondoDeRiesgo]`)

**Interfaces:**
- Produces: `motor.ejecutar(tramos: list[Path], salida: Path, corte: date, parametros: dict, informar=protocolo) -> (reports, rules, summary)`; `motor.read_xlsx(path)` agrega `r['_archivo']`; `idx` en `excel.build_reports` pasa a `(archivo, fila)`; `FilaOrigen`/`Fila SGA` conservan el número; columna `Archivo` sólo si `len(tramos) > 1`.
- Produces: `reglas_propuestas` se emite en `resumen['reglas_propuestas']` además de escribirse en `salidas/reglas_propuestas.json` (el sub-paso Reglas de la UI la lee de ahí).

- [ ] **Step 1:** Dorados sintéticos: fixture SGA con los 22 `FIELDS` + `CodigoSocio, TipoLinea, Linea, Canal` y ~30 filas que cubran: factura con imputaciones, NC, servicio 1º/2º, MORA, OPX pendiente, FI-P recíproco, factura oficial FC-A, documento excluido. Correr `legado/controles_sga/control_sga.py` con `--corte 2026-10-31`.
- [ ] **Step 2:** Tests: `test_igual_a_dorado_seis_libros` (cada solapa celda a celda vía openpyxl), `test_reglas_confirmadas_cambian_estado_a_error`, `test_dos_tramos_equivalen_y_agregan_archivo`, `test_formula_sin_valor_corta` (Review Focus 1), `test_salidas_a_generar_omite_libros`. Run → FAIL.
- [ ] **Step 3:** Implementar. **Step 4:** Run → PASS. **Step 5:** Regresión real: `regresion_legado.py controles_sga --entradas "...\Control SGA\ENTRADA" --corte 2026-10-31` → `SIN DIFERENCIAS` en los 6 XLSX, `reglas_propuestas.json` y `ejecucion.json` (sin `archivo`).

### Task 10: Control de Mora

**Files:**
- Create: `app/reportes/control_mora/{motor.py, ejecutar.py}`, `tests/test_control_mora.py`, `tests/dorados/control_mora/`
- Modify: `reporte.py` (entradas `erp` 1+ (detector: columnas `MainAccount, BusinessUnit, Saldo de cierre`), `sga` 1+ (detector: `GrupoConceptoFacturacion, FondoDeRiesgo, Importe`); parámetros: `cuentas` lista default `['113601','113602','113603','113604','113605']`, `unidad_negocio` texto default `FRG`, `fondo` texto default `Fondo de Riesgo General`, `grupo` texto default `Mora`; salidas: `resultado` (clave `[Concepto]`), `respaldo_erp` (clave `[ArchivoOrigen, HojaOrigen, FilaOrigen]`), `respaldo_sga` (ídem))

**Interfaces:**
- Produces: `motor.ejecutar(erp: list[Path], sga: list[Path], salida: Path, parametros: dict, informar=protocolo) -> dict` (resumen con totales como texto Decimal). La detección por prefijo de nombre se reemplaza por la del `reporte.py` (columnas); el cálculo no cambia. `ArchivoOrigen` ya existe en los respaldos, por lo que con tramos no se agrega columna.

- [ ] **Step 1:** Dorados con `legado/control_mora/control_mora.py` (`py -3.12`, fixtures openpyxl con fechas y floats). **Step 2:** Tests `test_igual_a_dorado`, `test_tramos_sga_suman`, `test_faltan_cuentas_corta`. Run → FAIL. **Step 3:** Implementar. **Step 4:** PASS. **Step 5:** Regresión real → `SIN DIFERENCIAS` (`Resultado_Control_Mora.csv` sin `Archivo ERP/SGA`, respaldos completos, `PROCESO_COMPLETO.txt`).

### Task 11: Control de cheques

**Files:**
- Create: `app/reportes/control_cheques/{motor.py, ejecutar.py}`, `tests/test_control_cheques.py`, `tests/dorados/control_cheques/`
- Modify: `reporte.py` (entradas `sga` 1+ (`IdCheque, Estado`), `erp` 1+ (`Id de Transacción, Estado, Pagado a`); parámetros: `prefijos_historicos` lista default `['563']`, `prefijo_sga` texto `10000`, `prefijo_erp` texto `gtz-`, `equivalencias` tabla default `[{erp:'rechazado',sga:'rechazado'},{erp:'depositado',sga:'depositado'},{erp:'en cartera',sga:'acreditado'}]`, `estados_proveedores` lista `['debitado','entregado']`, `estados_validos` lista `['canjeado']`; salidas: `revisar` (clave `[ID SGA, Motivo]`), `resumen` (clave `[Concepto]`))

- [ ] **Step 1:** Dorados (`py -3.12`). **Step 2:** Tests `test_igual_a_dorado`, `test_tramos_erp_se_indexan_juntos`, `test_importe_numerico_con_coma`. **Step 3:** Implementar (`Resumen.txt` además se vuelca como tabla `resumen` de dos columnas). **Step 4:** PASS. **Step 5:** Regresión real → `SIN DIFERENCIAS` (`Cheques_para_revisar.csv`; `Resumen.txt` sin las líneas `SGA:`/`ERP:` de ruta).

### Task 12: Descarga de facturas

**Files:**
- Create: `app/reportes/descarga_facturas/{motor.py, sharepoint.py, ejecutar.py}`, `tests/test_descarga_facturas.py`, `Instalar descarga de facturas.bat`, `requirements-facturas.txt` (`playwright>=1.50,<2`, `pdfplumber>=0.11.9,<0.12`)
- Modify: `reporte.py` (entrada `listado` 1+ (detector: alguna hoja con un alias de CUIT y uno de número en las primeras 100 filas); parámetros: `desde` fecha opcional, `hasta` fecha opcional, `concepto` texto, `destino` ruta (obligatoria; se guarda en configuración), `origen_sharepoint` texto (URL base, obligatoria, en configuración), `ruta_biblioteca` texto (`/sites/.../Comprobantes`, en configuración); `requiere: 'venv_facturas'`; `pausas: ['login']`; salidas: `descarga` (clave `[CUIT, Factura]`), `entrada_a_revisar` (clave `[Archivo, Hoja, Fila]`))

**Interfaces:**
- Produces: `motor.cargar_listados(paths) -> (tasks, issues, duplicates)` (= `load_inputs`, sin cambios); `motor.ejecutar(listados, salida, parametros, informar=protocolo)`: `informar.esperar('login', 'Iniciá sesión en Chrome. Cuando veas la biblioteca Comprobantes, volvé acá y apretá Continuar.')` en lugar de `input()`; `sharepoint.py` = `facturas.py` sin `DEST`, `ORIGIN`, `SITE`, `ROOT` fijos (se reciben por parámetro; `check_url` compara contra el origen recibido) y sin `main()`. `sesion_chrome` en `datos/sesion_chrome/`.
- `ejecutar.py` corre con el intérprete del venv (`catalogo.interprete`); con `--simular` (tests) usa un `contexto` falso que devuelve PDFs de fixture.

- [ ] **Step 1:** Tests: `test_cargar_listados_igual_que_legado` (alias, duplicados, inválidos: dorado de `legado/.../listado.load_inputs` sobre un fixture), `test_ejecutar_simulado_clasifica_en_anio_mes_concepto_y_conflicto` (PDF de fixture generado con texto fijo: se requiere pdfplumber ⇒ el test se salta si no está instalado), `test_sin_venv_disponibilidad_false_con_motivo_llano`. **Step 2:** FAIL. **Step 3:** Implementar + BAT (`py -3 -m venv .venv`, `pip install -r requirements-facturas.txt`, `playwright install chrome` no: usa `channel='chrome'` del sistema; mensaje final en castellano). **Step 4:** PASS (el de PDF se salta si falta pdfplumber; se corre en el venv al final de la Fase 5).

### Task 13: Herramienta de regresión contra el legado

**Files:**
- Create: `herramientas/regresion_legado.py`, `tests/test_regresion_legado.py`

**Interfaces:**
- Produces: CLI `regresion_legado.py <reporte> --entradas <carpeta> [--corte] [--alcance] [--salida <carpeta>]`: corre el legado (con `py -3.12` si el reporte usa openpyxl y `vendor` no alcanza; si no, `sys.executable`) y el motor nuevo (`ejecutar.py` con un `--trabajo` armado al vuelo), y compara: CSV/TXT/JSON byte a byte tras normalizar (quitar sellos `AAAAMMDD_HHMMSS`, rutas absolutas, `fecha_descarga`), XLSX celda a celda por hoja (valores y, en SGA, las celdas resaltadas). Imprime `SIN DIFERENCIAS` o la primera diferencia de cada archivo (archivo, hoja, celda, esperado, obtenido) y sale 0/1. Función reutilizable `comparar_carpetas(a: Path, b: Path) -> list[str]`.
- `docs/regresion.md`: tabla por reporte con fecha, archivos (nombre, SHA-256, filas), parámetros y resultado; sin importes.

- [ ] **Step 1:** `test_comparar_carpetas_detecta_celda_distinta_y_normaliza_sellos`. **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS. **Step 5:** Correr los cuatro reportes reales y completar `docs/regresion.md`.

---

## Fase 3: API del server

### Task 14: Servidor, estáticos, token, estado, cierres y ejecuciones

**Files:**
- Create: `app/servidor.py`, `app/rutas_api.py`, `tests/test_servidor.py`, `tests/cliente.py` (helper `http.client` con token)

**Interfaces:**
- Produces: `crear_servidor(dir_datos: Path, raiz: Path, puerto_inicial=7310, intentos=11, token=None, abrir_navegador=False) -> Servidor` con `.puerto`, `.token`, `.servir_en_hilo()`, `.cerrar()`; `ThreadingHTTPServer` ligado a `127.0.0.1`; `GET /` sin token válido ⇒ 403 con página en castellano "Abrí la herramienta desde su acceso directo"; con `?t=` válido ⇒ setea cookie y redirige a `/`; estáticos sólo de `app/web/` con tipos fijos; `GET /api/estado` ⇒ `{version, puerto, reportes: [{codigo, nombre, descripcion, disponible, motivo}], trabajosActivos, datos: ruta, python}`; CRUD de cierres y ejecuciones como la sección 8 del spec; errores `{error: 'mensaje llano'}` con 400/404/409; 500 ⇒ `{error: 'Ocurrió un error inesperado; quedó en el registro'}` y traza en `datos/servidor.log`.

- [ ] **Step 1:** Tests: `test_sin_token_api_403`, `test_query_t_setea_cookie_y_redirige`, `test_cabeceras_csp_nosniff_en_pagina_y_no_store_en_api`, `test_post_con_origin_ajeno_403`, `test_crud_cierres_y_ejecuciones`, `test_estado_lista_cinco_reportes`, `test_error_inesperado_no_filtra_traza` (ruta de prueba que lanza), `test_estatico_fuera_de_web_404`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS.

### Task 15: Archivos del cierre: subida por streaming y carpeta local

**Files:**
- Modify: `app/rutas_api.py`; Create: `tests/test_archivos.py`

**Interfaces:**
- Produces: `POST /api/cierres/<id>/archivos` con cabeceras `X-Nombre` (URL-encoded) y `Content-Length`: el cuerpo se escribe por bloques de 1 MB a un `.parcial` y luego `Dominio.agregar_archivo`; `Content-Length` > `limiteMB` ⇒ 413 `{error: 'El archivo supera los 200 MB'}` antes de leer; extensión fuera de `EXT_ENTRADA` ⇒ 400. `POST /api/cierres/<id>/archivos/carpeta {ruta}`: lista `.xlsx/.xlsm` (sin `~$`) de esa carpeta, devuelve `[{nombre, bytes}]`; `POST .../archivos/desde-carpeta {ruta, nombres: [...]}` copia los elegidos (sólo lectura del origen). `GET /api/cierres/<id>/archivos` devuelve además `tipo` detectado por reporte: `{archivoId: {conciliacion_general: 'sga', control_mora: 'sga', ...}}` calculado con `catalogo` + `entradas.detectar` al subir y cacheado en el archivo del cierre. `DELETE /api/cierres/<id>/archivos/<archivoId>`.

- [ ] **Step 1:** Tests: `test_subida_de_70mb_no_carga_en_memoria` (Review Focus 4: cuerpo generado por bloques; se mide `tracemalloc` pico < 20 MB en el hilo del server, o se verifica que el `.parcial` crece durante la subida), `test_mas_de_limite_413_sin_leer`, `test_extension_invalida_400`, `test_desde_carpeta_copia_y_detecta_tipo`, `test_nombre_con_ruta_se_sanea`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS.

### Task 16: Ejecutar, trabajos, continuar, cancelar y eventos SSE

**Files:**
- Modify: `app/rutas_api.py`, `app/servidor.py`; Create: `tests/test_ejecutar.py`

**Interfaces:**
- Produces: `POST /api/ejecuciones/<id>/ejecutar {entradas: {clave: [archivoIds]}, parametros}` ⇒ valida (`catalogo.validar_parametros`, entradas completas y de tipo correcto, cantidad), escribe `parametros.json` y `entradas.json` (`{clave: [{ruta, nombre, sha256}]}`) en la carpeta de la ejecución, lanza `Trabajos.lanzar` con `catalogo.interprete` + `ejecutar.py --trabajo <carpeta>` y `env` con `REPORTES_PROTOCOLO=1`, `PYTHONPATH=<raiz>;<raiz>/vendor`; estado de la ejecución sigue al trabajo (`al_terminar` ⇒ `ok`: guarda `resumen.json`, `salidas` desde `Tablas.listar()`, `trasladar_revision` si hay versión anterior y guarda el resultado en `resumen.traslado`; `error`/`cancelado`). `GET /api/trabajos`, `GET /api/trabajos/<id>` (con `lineas`), `POST /api/trabajos/<id>/continuar {espera}`, `POST /api/trabajos/<id>/cancelar`. `GET /api/eventos` SSE (`event: trabajo`, `event: ejecucion`, keepalive cada 15 s). Al arrancar el server, las ejecuciones en `corriendo`/`esperando` pasan a `error` con mensaje "Se cerró la herramienta mientras corría".

- [ ] **Step 1:** Tests con un reporte falso registrado sólo en tests (`catalogo.registrar_para_pruebas('falso', REPORTE_FALSO, interprete=[sys.executable, 'tests/motor_falso.py'])`): `test_ejecutar_llega_a_esperando_continuar_y_ok_con_tablas`, `test_entradas_incompletas_400_llano`, `test_sse_recibe_evento_trabajo`, `test_pestana_cerrada_y_reabierta_recupera_lineas` (Review Focus 3: la segunda conexión obtiene las líneas por `GET /api/trabajos/<id>`), `test_segunda_version_traslada_revision`, `test_arranque_marca_interrumpidas`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS.

### Task 17: Tablas, triage, exportación y archivos de salida

**Files:**
- Modify: `app/rutas_api.py`; Create: `app/exportar.py`, `tests/test_exportar.py`

**Interfaces:**
- Produces: `GET /api/ejecuciones/<id>/tablas` ⇒ `Tablas.listar()` + títulos del `reporte.py`; `GET .../tablas/<tabla>?desde&cantidad(≤500)&orden&desc&filtro&columna&estado`; `POST .../triage {tabla, filas: [...], estado, obs}` (⇒ `marcar`, `guardar_triage`, evento `ejecucion`); `POST .../traer-revision-anterior`; `GET .../archivos/<nombre>` sirve `salidas/<nombre>` (ruta confinada, `Content-Disposition: attachment`); `GET .../exportar?tabla=<t>&incluirOmitidas=0|1` ⇒ XLSX de esa tabla con columnas originales + `Estado revisión` + `Observaciones` (resaltadas de `_marcas` en anaranjado); `GET .../exportar?libro=<nombre>` ⇒ para Controles SGA, el libro original con sus solapas y las dos columnas agregadas; para Conciliación general, `Conciliacion_general.xlsx` con `Estado revision`/`Observaciones` completados en la hoja de detalle. `exportar.exportar_tabla(tablas, tabla, definicion, incluir_omitidas) -> bytes`, `exportar.exportar_libro(...)`, `exportar.exportar_cierre(dominio, cierre_id) -> bytes` (ZIP: por ejecución final `resumen.json`, `triage.json`, exportados trabajados; sin entradas), `importar_cierre(dominio, zip_bytes)` (crea cierre en modo `importado: True`, sin sqlite: las tablas se cargan desde los XLSX del ZIP a un sqlite nuevo, sólo lectura).

- [ ] **Step 1:** Tests: `test_exportar_tabla_agrega_dos_columnas_y_excluye_omitidas`, `test_exportar_libro_conciliacion_completa_estado_y_observaciones`, `test_descarga_de_salida_original_intacta_por_sha`, `test_exportar_e_importar_cierre_round_trip`, `test_cantidad_mayor_a_500_se_acota`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS.

### Task 18: Configuración, instancia única, cierre y apagado por inactividad

**Files:**
- Create: `app/arranque.py`, `tests/test_arranque.py`; Modify: `app/rutas_api.py`, `app/servidor.py`

**Interfaces:**
- Produces: `GET/PATCH /api/configuracion` (tema, limiteMB, `reportes.<codigo>.parametros`, `reportes.<codigo>.reglas`, `carpetaDatos` sólo lectura); `POST /api/cerrar` ⇒ si hay trabajos activos 409 `{error: 'Hay un reporte corriendo; esperá a que termine o cancelalo'}`, si no, responde `{ok: true}` y apaga en 0,5 s. `arranque.dir_datos() -> Path` (`REPORTES_DATOS` o `%LOCALAPPDATA%\ReportesDeCierre\datos`); `arranque.instancia_viva(dir_datos) -> dict|None` (lee `.servidor.json`, hace `GET /api/estado` con el token; responde ⇒ la devuelve); `arranque.main(argv)`: si hay instancia viva ⇒ abre `http://127.0.0.1:<p>/?t=<token>` y sale 0; si no ⇒ crea server, escribe `.servidor.json` `{pid, puerto, token, inicio}`, abre navegador, sirve; `--sin-navegador`, `--puerto`; hilo de inactividad: sin peticiones en 3 h y sin trabajos ⇒ apaga; al salir borra `.servidor.json`.

- [ ] **Step 1:** Tests: `test_segundo_arranque_reusa_instancia_y_no_abre_otro_puerto` (Review Focus 2: `main` con `abrir=lambda url: capturas.append(url)`), `test_servidor_json_se_borra_al_cerrar`, `test_cerrar_con_trabajo_activo_409`, `test_patch_configuracion_guarda_parametros_por_reporte`, `test_inactividad_apaga` (umbral inyectado de 1 s).
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS.

---

## Fase 4: interfaz

Criterios transversales: una sola página; estado en `window.app`; `esc()` para todo texto de datos; sin `innerHTML` con datos sin escapar; tema por `data-tema` en `<html>` (`claro`/`oscuro`, inicial de `prefers-color-scheme`, conmutador en la barra, persistido en configuración); variables de color definidas en los dos temas con contraste ≥ 4,5:1 (verificado con una tabla en `estilos.css` como comentario); foco visible; navegación por teclado en la grilla; textos de ayuda bajo cada campo; nada de jerga.

### Task 19: Esqueleto, temas, barra y pantalla de cierres

**Files:**
- Create: `app/web/index.html`, `app/web/estilos.css`, `app/web/app.js`, `tests/test_web_estatico.py`

**Interfaces:**
- Produces: vistas `#/cierres` (tarjetas por período: estado por reporte, botón "Nuevo cierre" con período y fecha de corte), `#/cierre/<id>` (cinco tarjetas de reporte: Disponible / Necesita instalación con el porqué; última versión: estado, pendientes/revisadas/omitidas; botones "Empezar" / "Continuar" / "Ver resultados"), `#/historial`, `#/configuracion`, `#/trabajos` (panel lateral con los trabajos activos y su consola, visible desde cualquier vista). `app.js` expone `api(metodo, ruta, cuerpo)` (fetch con `credentials: 'same-origin'`, errores ⇒ aviso rojo con el `error` del server), `esc(texto)`, `ruta()` por hash, `conectarEventos()` (EventSource con reconexión).
- Test estático: `test_index_tiene_dos_temas_y_variables_iguales` (cada `--variable` de `[data-tema=claro]` existe en `[data-tema=oscuro]`), `test_no_hay_innerhtml_con_interpolacion_sin_esc` (regex sobre `app.js`), `test_contraste_minimo` (calcula contraste WCAG de los pares texto/fondo declarados en el comentario-tabla de `estilos.css`, ≥ 4,5).

- [ ] **Step 1:** Tests estáticos. **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS + prueba manual con el server (copia de datos, puerto 7319) en ambos temas, captura adjunta a las notas de seguimiento.

### Task 20: Asistente: pasos Archivos, Opciones y Ejecución

**Files:**
- Modify: `app/web/app.js`, `app/web/estilos.css`, `app/web/index.html`

**Interfaces:**
- Produces: vista `#/ejecucion/<id>` con barra de pasos (1 Archivos · 2 Opciones · 3 Ejecución · 4 Resultados · 5 Exportar) y estado por paso. **Archivos**: por cada entrada del reporte, zona para arrastrar/elegir (varios archivos = tramos) y lista de archivos del cierre ya reconocidos de ese tipo con "Usar"; botón "Elegir una carpeta de la PC" (pide la ruta, muestra lo que hay y permite marcar); cada archivo muestra "Reconocí: <tipo>, hoja <hoja>, <n> filas" o el error llano; aviso de posible descarga recortada; "Siguiente" sólo con todas las entradas completas. **Opciones**: formulario generado de `parametros` (tipos fecha/texto/opción/lista editable/booleano/tabla/ruta) con ayuda; "Guardar como valores para los próximos cierres" (PATCH configuración); para Controles SGA, sección "Reglas confirmadas" con la tabla editable. **Ejecución**: consola en vivo (paso actual, barra de progreso, últimas 400 líneas), botón Cancelar, bloque de espera (mensaje + botón del motor) cuando el trabajo está `esperando`; al terminar `ok` pasa solo a Resultados; en `error` muestra el mensaje y "Ver registro".

- [ ] **Step 1:** Prueba manual guiada con el reporte falso (`REPORTES_FALSO=1` registra el motor de pruebas en el catálogo del server) y con Control de cheques real sobre fixtures: pausa, continuar, cancelar, error. **Step 2:** Capturas de los tres estados a la Nota. **Step 3:** Corregir lo que salga.

### Task 21: Resultados: grilla, filtros y revisión

**Files:**
- Modify: `app/web/app.js`, `app/web/estilos.css`, `app/web/index.html`

**Interfaces:**
- Produces: pestañas por tabla con conteo; grilla paginada (100 por página, selector 100/250/500), orden por columna, búsqueda global y por columna, filtro por estado (Todas / Pendientes / Revisadas / Omitidas), selección por casilla y Shift, acciones sobre la selección (Revisada / Omitir / Pendiente / Observación...), edición de observación por fila, celdas resaltadas con el mismo anaranjado de los Excel, importes alineados a la derecha, encabezado fijo. Botón "Traer la revisión del cierre anterior" con el resumen de lo aplicado. Resumen del motor (totales, alertas) arriba de las pestañas para Conciliación y Mora.

- [ ] **Step 1:** Prueba manual con una ejecución real de Control de cheques y una de Conciliación general (237k filas: paginar, filtrar, marcar 500 filas, recargar la página y verificar que las marcas persisten). **Step 2:** Capturas a la Nota. **Step 3:** Corregir.

### Task 22: Exportar, historial y configuración

**Files:**
- Modify: `app/web/app.js`, `app/web/estilos.css`, `app/web/index.html`

**Interfaces:**
- Produces: paso **Exportar**: descargas del original y del trabajado (por tabla y por libro), casilla "Sin las omitidas", "Marcar como resultado final del cierre", "Exportar cierre" (ZIP). **Historial**: tabla de ejecuciones (cierre, reporte, versión, fecha, estado, pendientes/revisadas/omitidas, final), filtros, abrir, borrar con confirmación (doble para una final). **Configuración**: tema, límite de tamaño, dónde están los datos (sólo lectura + "Abrir carpeta"), valores por defecto por reporte (reutiliza el formulario de Opciones), limpieza de archivos no referenciados, "Cerrar la herramienta", versión.

- [ ] **Step 1:** Prueba manual completa de un cierre de principio a fin con fixtures; abrir los XLSX exportados en Excel (o LibreOffice) y verificar columnas agregadas. **Step 2:** Capturas a la Nota. **Step 3:** Corregir.

---

## Fase 5: arranque, empaquetado y documentación

### Task 23: BATs, empaquetado y prueba de instalación limpia

**Files:**
- Create: `Reportes de cierre.bat`, `Reportes de cierre - consola.bat`, `herramientas/empaquetar.py`

**Interfaces:**
- Produces: `Reportes de cierre.bat`: busca `py -3` o `python`; si no hay, muestra en castellano cómo instalar Python (enlace oficial, "marcar Add to PATH") y pausa; si hay, `start "" /B pythonw -m app.arranque` (sin ventana) — `arranque.main` reusa la instancia si existe. `- consola.bat`: `python -m app.arranque --consola`; con argumento `pruebas` ⇒ `python -m unittest discover -s tests -v`. `empaquetar.py` ⇒ `dist/Reportes-de-cierre-<version>.zip` con todo salvo `datos/`, `.venv/`, `tests/`, `legado/`, `docs/superpowers/`, `.git/`, `__pycache__/`.

- [ ] **Step 1:** Extraer el ZIP en una carpeta temporal con nombre con espacios y acentos, doble clic en el BAT, verificar que abre, que un segundo doble clic no duplica, y que `Instalar descarga de facturas.bat` deja el reporte Disponible. **Step 2:** Correr el test de PDF de Task 12 dentro del venv. **Step 3:** Corregir.

### Task 24: Documentación para usuarias y para agentes

**Files:**
- Create: `LEEME.md`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `docs/reglas/{conciliacion_general, controles_sga, control_mora, control_cheques, descarga_facturas}.md`, `.claude/rules/reportes/<reporte>.md` (frontmatter `description` + `paths: ["**/reportes/<reporte>/**"]`), `.agent/rules/<reporte>.md` (frontmatter `trigger: glob`, `globs: ["app/reportes/<reporte>/**"]`), `docs/pendientes.md` (completar), `CHANGELOG.md`

**Interfaces:**
- `docs/reglas/*.md`: redactados desde los LEEME/NOTA/HISTORIAL/DOCX de `legado/`, sin nombres de personas ni de organización; con "Fuente: LEEME v1.5 (22/10/2026)"; secciones: qué hace, entradas, reglas, estados/resultados, limitaciones, parámetros y sus defaults, salidas y claves de revisión.
- `AGENTS.md`: arquitectura (estructura de archivos de este plan), cómo correr y probar, reglas: (1) no cambiar la matemática de un motor sin correr `regresion_legado.py` y anotar en `docs/regresion.md`; (2) `datos/` nunca al repo; (3) lenguaje llano en la interfaz, lista de palabras prohibidas; (4) repo público: sin URLs, nombres ni datos reales; (5) todo color es una variable en los dos temas; (6) tests con fixtures sintéticos; (7) un reporte nuevo = carpeta con `reporte.py` + `motor.py` + `ejecutar.py` + `docs/reglas/` + rule; (8) commits los hace el dueño del repo. `CLAUDE.md` = `@AGENTS.md` + skills útiles. `GEMINI.md` = "Leer AGENTS.md" + lo mismo resumido.
- `docs/pendientes.md`: lo observado en el análisis (sección 3 del spec) como lista con reporte, descripción, impacto y cómo verificarlo.

- [ ] **Step 1:** Escribir. **Step 2:** `python herramientas/revisar_docs.py` (chequeo simple en `tests/test_docs.py`: cada reporte tiene `docs/reglas`, `.claude/rules`, `.agent/rules`; ninguno de `AGENTS.md`, `LEEME.md`, `docs/` contiene `sharepoint.com`, nombres propios listados en `tests/palabras_prohibidas.txt` (archivo ignorado por git, local)). **Step 3:** PASS.

### Task 25: Regresión final y cierre del hito

- [ ] **Step 1:** `python -m unittest discover -s tests -v` → todo PASS.
- [ ] **Step 2:** `herramientas/regresion_legado.py` para los cuatro reportes sobre los archivos reales → `SIN DIFERENCIAS`; `docs/regresion.md` completo.
- [ ] **Step 3:** Prueba manual del flujo completo con los archivos reales en un cierre `2026-10` (tiempos de cada reporte anotados en `docs/regresion.md`).
- [ ] **Step 4:** `git status` limpio de datos; resumen de decisiones y pendientes al usuario; handoff en las notas de seguimiento. Sin commit.
