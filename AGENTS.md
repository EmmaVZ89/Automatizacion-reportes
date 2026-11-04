# AGENTS.md — Reportes de cierre

Guía para quien programa en este repositorio, sea una persona o un agente (Codex lee este archivo; Claude Code lo
carga desde `CLAUDE.md`; Antigravity desde `GEMINI.md`). Lo que ve la usuaria está en `LEEME.md`.

## Qué es

Herramienta local, para personas administrativas **no técnicas**, que corre los cinco reportes del cierre mensual
(Conciliación general, Controles SGA, Control de Mora, Control de cheques, Descarga de facturas) sobre los Excel que
descargan de sus sistemas, guía cada uno por pasos, permite revisar cada tabla de salida (revisada / omitida /
observación) y guarda un historial por cierre. No es un producto de la empresa del autor ni una herramienta interna:
nada de marcas, sistemas o vocabulario internos.

Diseño: `docs/superpowers/specs/2026-10-31-herramienta-cierre-design.md`. Plan: `docs/superpowers/plans/`.

## Arquitectura

- **Python 3.10+, solo biblioteca estándar** + `vendor/` (openpyxl y et_xmlfile, puro Python; ver `vendor/VERSIONES.md`).
  Sin `pip install` para los cuatro controles. La Descarga de facturas necesita un `.venv` (`Instalar descarga de
  facturas.bat`, `requirements-facturas.txt`) con Playwright y pdfplumber, y el Chrome de la PC.
- `app/arranque.py`: carpeta de datos (`%LOCALAPPDATA%\ReportesDeCierre\datos` o `REPORTES_DATOS`), instancia única
  (`datos/.servidor.json`), abre el navegador con el token. `app/servidor.py`: HTTP en `127.0.0.1:7310..7320`,
  estáticos de `app/web`, token por arranque (cookie `HttpOnly; SameSite=Strict`), cabeceras CSP/nosniff, SSE.
  `app/rutas_api.py`: todos los `/api/*`.
- `app/dominio.py`: cierres (período + corte + biblioteca de archivos deduplicada por SHA-256 en
  `datos/cierres/<id>/archivos/<sha8>/<nombre>`), ejecuciones con versiones, revisión y configuración. Todo en JSON
  (`app/almacen.py`: escritura atómica + backup).
- `app/trabajos.py`: cada corrida es un **subproceso** `python -I app/reportes/<reporte>/ejecutar.py --trabajo <carpeta>`
  que habla por líneas JSON (`app/reportes/_comun/protocolo.py`): log, paso, progreso, tabla, resumen, error y
  `esperar` (pausa para una acción manual; el server manda `continuar`/`cancelar` por stdin).
- `app/tablas.py` + `app/reportes/_comun/salidas.py`: cada tabla de salida se vuelca a `resultados.sqlite` de la
  ejecución (paginado, filtro, orden, triage por clave de negocio). `triage.json` es la fuente de verdad de la revisión.
- Consultas de tabla (`Tablas._consulta`, armadas por `Api._consulta_de` desde la URL): búsqueda, estado, `requiere`,
  `filtros` ({columna: [valores]} o {columna: {excluir: [...]}}) y `condiciones` ({columna: {op, a, b}} con op
  `distinto_cero|igual|mayor|menor|entre`). `Tablas.distintos` arma la lista de valores de un filtro de encabezado
  con los demás filtros aplicados (parámetro `valoresDe` en la URL).
- `app/exportar.py`: Excel "trabajado" (columnas Estado revisión y Observaciones), `exportar_vista` (las filas de una
  consulta, sin paginar, con las columnas elegidas; lo usan el botón "Exportar" de la grilla y el armado del paso Exportar),
  exportar/importar cierre (ZIP). Una tabla que no entra en una hoja de Excel sigue en otras con el mismo encabezado
  ("Nombre (2)"…: `xlsx_escritura.escribir_libro`, `MAX_FILAS_EXCEL`, `nombre_de_hoja`); `importar_cierre` las junta.
- `app/registro_corrida.py`: el registro de una corrida para soporte (`GET /api/ejecuciones/<id>/registro/descargar`,
  botón "Descargar el registro" de Ejecución e Historial): reporte, cierre, versión, horario, estado y error,
  opciones con sus títulos, archivos del cierre que usó y el `registro.log` completo. Cada línea del `registro.log`
  lleva la hora (`Trabajos._escribir_registro`).
- `app/acceso_directo.py` + `app/iniciar.vbs`: acceso directo "Reportes de cierre.lnk" (wscript → `iniciar.vbs`, que
  busca Python como el .bat y corre `app.arranque` sin consola). Lo asegura `python -m app.arranque` en un hilo
  (`main(acceso=...)`; las pruebas llaman a `main` sin `acceso` y nunca crean accesos reales): en la carpeta de la
  herramienta siempre, en el Escritorio la primera vez, y los corrige si la carpeta cambió (`datos/acceso_directo.json`).
  El ícono (`datos/reportes-de-cierre.ico`) se dibuja en Python a partir del logo. Los .lnk se escriben con
  WScript.Shell desde PowerShell. `POST /api/acceso-directo` (Configuración) lo vuelve a crear.
- `app/origenes.py` + `app/reportes/_comun/cache_filas.py`: Excel de origen de una fila. Cada hoja de entrada se copia
  una vez, en un subproceso, a `archivos/<sha8>/filas-<hoja>.sqlite` (bloques de filas comprimidos, con formatos de
  número y anchos); la copia se arma al terminar la corrida o al pedirla. El reporte que lo ofrece marca la salida con
  `origen: True` y tiene `origen.py` (contrato en el docstring de `app/origenes.py`; lo implementan
  `conciliacion_general/origen.py` y `controles_sga/origen.py`). `filas_de` puede devolver, por fila, las columnas a
  pintar de anaranjado (`Tablas.fila` trae `_marcas`, las observadas en pantalla). La limpieza borra las copias con
  su archivo.
- Variantes de un reporte (`REPORTE['variantes'] = {parametro, opciones: [{valor, titulo, corto}]}`; hoy, el fondo de
  riesgo de la conciliación): cada variante es una serie aparte (versión, resultado final, `version_anterior`,
  traer del cierre anterior) por `Dominio.variante_de(e)` (las ejecuciones de antes la toman de sus parámetros).
  `crear_ejecucion(..., variante)` arranca los parámetros con ella; cambiar el parámetro en un borrador pasa la versión
  a la otra serie. `_resumen_cierre` agrega `reportes[codigo].variantes[valor]`; la pantalla arma un ítem por variante
  (`itemsCierre`) y muestra el chip `chipVariante`. Los ERP guardan `fondo` al reconocerse (`fondo_por_asientos`);
  Archivos sólo lo muestra y la validación contra el fondo va en Opciones (donde se elige) y en `ejecutar`.
- `Origenes`: no llamar a `estado()` con `_lock` tomado (trababa la herramienta entera: `/api/estado` y la copia en
  curso quedaban esperando). El candado es reentrante como resguardo.
- `app/catalogo.py`: carga `app/reportes/*/reporte.py` (entradas con detector, parámetros con default, salidas con
  clave de revisión, `orden`, `requiere`). En cada salida, además: `revisar` ({columna, salvo}: las filas con esos
valores no cuentan como pendientes; `Tablas` recibe estas reglas desde `Dominio.tablas` y `REVISION_V` recuenta las
corridas guardadas con otra regla), `vista` ({primero, ocultas}: vista por defecto de la grilla; la del usuario se
guarda en `configuracion.json` > `vistas`), `origen` y `seccion` (título de la sección en Resultados; un libro de una
sola tabla con `seccion` también se muestra como sección). En la definición del reporte, `salidas_anteriores` lista
tablas que dejaban versiones anteriores (con su `libro` y `hoja`): esas corridas se muestran agrupadas y con aviso
(`anterior` en `/api/ejecuciones/<id>/tablas`), y `Dominio._hermanas` hace que las marcas que no encuentran su fila
en su tabla se busquen en las otras tablas del mismo libro (`Tablas.aplicar_triage(..., hermanas)`). Campos de presentación: `ambito` (`cierre` o `herramienta`: la Descarga
  de facturas no es del cierre y vive en un espacio propio, `Dominio.espacio_herramienta`, fuera de
  `listar_cierres`; la interfaz la muestra en la sección Facturas) e `icono` (nombre de un `<symbol id="i-…">` del
  sprite de `index.html`). En cada salida: `principal: True` marca la tabla que se abre primero en Resultados y
  `revisable: False` la vuelve informativa (totales, respaldos): se muestra aparte, sin selección ni columna de
  revisión, y no suma pendientes (`Dominio.tablas_informativas`).
- `app/web/`: `index.html`, `estilos.css`, `app.js`. JS vainilla, sin build, **sin `innerHTML`**: todo se construye
  con `el()`. Dos temas por variables CSS (claro por defecto), íconos en un sprite SVG, piezas comunes en `app.js`
  (`dialogo`, `aviso`, `tareas.correr`, `descargar`…) y pantalla sin saltos de maquetado. Cómo está armada, las
  prácticas y los criterios de pantalla: `docs/interfaz.md`.
- La herramienta en marcha (aviso de código nuevo, inactividad, conexión perdida, `datos/servidor.log`, reinicio con
  el mismo token y puerto, puerto exclusivo en Windows) y las prácticas del servidor: `docs/servidor.md`.

## Reglas de trabajo

1. **La matemática de los motores no se toca sin regresión.** `app/reportes/<reporte>/motor.py` es el script original
   (`legado/`) con cambios mínimos. Cualquier cambio en un motor exige correr
   `py herramientas/regresion_legado.py <reporte> --entradas <carpeta con los archivos reales>` y anotar el resultado
   en `docs/regresion.md`. Con un solo archivo por entrada y parámetros por defecto, la salida tiene que ser
   **idéntica** a la del legado, salvo los cambios de reglas acordados con quien usa el reporte (hoy: Conciliación
   general 1.5 y la lectura del concepto de la Descarga de facturas), que se documentan en `docs/reglas/<reporte>.md`
   y se verifican explicando cada diferencia (`herramientas/cambios_conciliacion.py`). La Descarga de facturas no pasa
   por `regresion_legado.py`: se compara con PDF reales con
   `.venv\Scripts\python.exe herramientas/regresion_facturas.py --pdfs <carpeta>`, que lee cada PDF con el legado y
   con el motor nuevo, explica las diferencias acordadas y corre la descarga con el navegador simulado. Las reglas de
   negocio de cada reporte están en `docs/reglas/<reporte>.md`.
2. **`datos/` nunca va al repositorio** (está en `.gitignore`): son datos reales de la usuaria. Tampoco `sesion_chrome/`.
3. **Repositorio público**: ni URLs de SharePoint, ni nombres de personas u organizaciones, ni archivos de datos reales,
   ni cifras reales en `docs/`. Los fixtures de los tests son sintéticos. Lo que es de la organización (URL, carpeta
   destino) se carga en Opciones y vive en `datos/configuracion.json`.
4. **Lenguaje llano en la interfaz y en el LEEME.** Prohibidas en pantalla: token, JSON, sqlite, puerto, servidor,
   subproceso, API, backend, endpoint, stdout, localhost, debug. Los errores dicen qué pasó y qué hacer, sin trazas
   (la traza va a `datos/servidor.log` o al `registro.log` de la ejecución). `tests/test_web_estatico.py` lo controla.
5. **Todo color es una variable definida en los dos temas** de `estilos.css`, y cada par texto/fondo nuevo se agrega
   a la lista de `test_contraste_minimo_en_los_pares_declarados`.
6. **Nada de `innerHTML`, `eval` ni recursos externos** en la web (CSP `default-src 'self'`).
7. **Un reporte nuevo** = carpeta `app/reportes/<codigo>/` con `reporte.py` (definición), `motor.py`, `ejecutar.py`
   (contrato: `--trabajo <carpeta>` con `parametros.json` y `entradas.json`; escribe `salidas/` y `resultados.sqlite`;
   emite `resumen` por el protocolo) + `docs/reglas/<codigo>.md` + `.claude/rules/reportes/<codigo>.md` +
   `.agent/rules/<codigo>.md` + tests con dorados.
8. **Tests**: `py -m unittest discover -s tests -t . -v` desde la raíz (o `Reportes de cierre - consola.bat pruebas`).
   Fixtures sintéticos (`tests/fixtures.py`), nunca datos reales. Los tests del server usan puertos 7390–7440 y
   carpetas temporales en `tests/_tmp/`. Con `py` se omiten (skipped) los tests que leen PDF, porque pdfplumber está
   sólo en el `.venv` de facturas: un cambio en la Descarga de facturas o en `herramientas/regresion_facturas.py` se
   prueba también con `.venv\Scripts\python.exe -m unittest discover -s tests -t .`, que no omite ninguno.
9. **Commit y push, sólo cuando el dueño del repositorio lo pide.** Hasta entonces, un agente deja los cambios en el
   working copy y los describe. El mensaje lleva un título corto y un cuerpo con qué cambió y por qué, la regresión
   y los tests; si lo escribió un agente, termina con `Co-Authored-By`. Antes del push se revisa el diff: el
   repositorio es público (regla 3). La versión vive en `app/version.py` (`AAAA.MM.DD`; una segunda versión del
   mismo día suma `.2`, `.3`…, como `2026.11.03.2`); todo cambio visible suma su línea en `CHANGELOG.md`.
10. Las correcciones pendientes de los motores (cosas raras heredadas del legado que no se arreglan sin acordarlo)
    están en `docs/pendientes.md`: se leen antes de "mejorar" algo.

## Cómo se hace un cambio

1. **Propuesta sin aplicar** cuando el pedido es un análisis o falta definir algo: qué cambiar, dónde y por qué. El
   código no se toca hasta que se decide.
2. **Decisión** del dueño del repositorio o de quien usa el reporte. Si cambia una regla de negocio, va a
   `docs/reglas/<reporte>.md` como cambio sobre el legado, con la fecha.
3. **Test que falla** con el caso, con datos sintéticos, y recién después el cambio.
4. **Suite completa** con `py` y, si toca algo que lee PDF, también con el `.venv` (regla 8).
5. **Regresión** contra el legado si toca un motor, anotada en `docs/regresion.md` (regla 1).
6. **Documentación**: la regla del reporte; `docs/interfaz.md` o `docs/servidor.md` si cambia una práctica;
   `docs/pendientes.md` para lo que se deja igual a propósito; `CHANGELOG.md` y `app/version.py` si se ve (regla 9).
7. **Paquete** con `py herramientas/empaquetar.py` cuando hay que entregarlo.
8. **Commit y push**, sólo cuando se pide (regla 9).

Para editar archivos con un script, cada reemplazo se aplica sólo si el texto viejo aparece exactamente una vez
(`assert texto.count(viejo) == 1`): si no coincide, el script se detiene en lugar de escribir algo roto.

## Comandos

```
py -m app.arranque --consola                       # abre la herramienta con consola
py -m unittest discover -s tests -t . -v            # tests
py herramientas/regresion_legado.py control_cheques --entradas <carpeta>
.venv\Scripts\python.exe -m unittest discover -s tests -t .           # tests, también los que leen PDF
.venv\Scripts\python.exe herramientas/regresion_facturas.py --pdfs <carpeta>
py herramientas/empaquetar.py                       # dist/Reportes-de-cierre-<versión>.zip
```

Para probar la interfaz sin tocar los datos reales: `REPORTES_DATOS=<carpeta temporal> py -m app.arranque --consola --puerto 7319 --sin-navegador`
y abrir la URL con token que imprime.
