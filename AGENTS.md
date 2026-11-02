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
  con `el()`. Configuración es una ventana (`abrirConfiguracion(seccion)`; `#/configuracion` la abre sobre Inicio). El encabezado fijo del reporte, achicado, conserva su alto con margen (`fijarCabecera`): si la página se acortara, el navegador corregiría el scroll y temblaría. Dos temas por variables CSS (`[data-tema]`, **claro por defecto**), contraste ≥ 4,5:1 verificado por
  test. Íconos: sprite SVG en `index.html` (`icono('i-…')`), nunca imágenes ni fuentes externas. Piezas comunes en
  `app.js`: `dialogo()` (confirmaciones con tono), `abrirModal()`, `abrirMenu()`/`botonMenu()`, `aviso()` (avisos
  con barra de tiempo), `abrirAyuda(clave)` (cajón de ayuda: `AYUDA_PASOS`, `AYUDA_GENERAL`), `bienvenida()` (guía
  de inicio; `configuracion.bienvenida` recuerda que ya se vio) y `tareas` (visor de tareas: todo lo que tarda pasa
  por `tareas.correr({clave, titulo})`, que avisa si la misma clave ya está en curso; las descargas, por
  `descargar(ruta, titulo)`; los reportes y el Excel de origen llegan por los eventos `trabajo` y `origen`). Un `btn()`
  cuya acción devuelve una promesa se marca solo como ocupado. Los redibujos que llegan por eventos van con
  `enSilencio()` (sin animaciones de entrada). Las clases de tono de los diálogos llevan prefijo (`tono-aviso`): no
  reusar nombres de clase de otros componentes (`.aviso` es la notificación). Sin saltos de maquetado: un bloque que se
  vuelve a armar con datos que llegan después conserva su alto (`conservarAlto`, lo usa `grilla`); la vista toma su
  ancho al pintarse (`pantallaNueva`), no al cambiar la dirección; `html` reserva la barra de desplazamiento; la grilla
  tiene alto fijo; los estados elegidos no cambian el grosor de letra; los `<details>` se animan con
  `::details-content`. Para medir, el patrón es un PerformanceObserver de `layout-shift` en Playwright
  (`tests/test_web_estatico.py` fija los arreglos). Si el código de `app/` cambia con la
  herramienta abierta, `/api/estado` devuelve `reiniciar` y la pantalla lo avisa. Inactividad: `_vigilar_inactividad`
  cuenta como uso una pestaña conectada a `/api/eventos` (`bus.suscriptores`) y una copia de origen en curso; sólo
  apaga sin pestañas. Si la pantalla pierde la conexión (`revisarConexion`: error del canal de eventos, un pedido que no
  llega o un 403 de sesión vieja) muestra `#banda-conexion` e interrumpe las tareas de reportes y copias; al volver
  (`reconectada`) las pone al día. Registro (`datos/servidor.log`, rotado): apertura con versión y pid, cierre con
  `motivo_cierre`, sesión anterior sin cerrar (quedó `.servidor.json`), errores sin atrapar (`arranque.registrar_fallas`,
  sólo en `python -m app.arranque`) y caídas del intérprete en `fallas.log` (faulthandler); `GET /api/registro` los
  baja juntos. El aviso de versión nueva ofrece "Reiniciar la herramienta"
  (también en el menú): `POST /api/reiniciar` → `Servidor.reiniciar` lanza `python -m app.arranque --reinicio TOKEN`
  con el mismo token y puerto y se cierra; la instancia nueva espera a que se suelte el puerto, y la pantalla espera
  a que `/api/estado` devuelva otra `instancia` y recarga. En Windows el puerto es exclusivo (`_ServidorHttp`). Las
  animaciones van siempre, también con "reducir movimiento" del sistema: es una decisión del dueño del
  repositorio.

## Reglas de trabajo

1. **La matemática de los motores no se toca sin regresión.** `app/reportes/<reporte>/motor.py` es el script original
   (`legado/`) con cambios mínimos. Cualquier cambio en un motor exige correr
   `py herramientas/regresion_legado.py <reporte> --entradas <carpeta con los archivos reales>` y anotar el resultado
   en `docs/regresion.md`. Con un solo archivo por entrada y parámetros por defecto, la salida tiene que ser
   **idéntica** a la del legado, salvo los cambios de reglas acordados con quien usa el reporte (hoy: Conciliación
   general 1.5), que se documentan en `docs/reglas/<reporte>.md` y se verifican explicando cada diferencia
   (`herramientas/cambios_conciliacion.py`). Las reglas de negocio de cada reporte están en `docs/reglas/<reporte>.md`.
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
   carpetas temporales en `tests/_tmp/`.
9. **Commits y push los hace el dueño del repositorio.** Un agente deja los cambios en el working copy y los
   describe. La versión vive en `app/version.py` (`AAAA.MM.DD`); todo cambio visible suma su línea en `CHANGELOG.md`.
10. Las correcciones pendientes de los motores (cosas raras heredadas del legado que no se arreglan sin acordarlo)
    están en `docs/pendientes.md`: se leen antes de "mejorar" algo.

## Comandos

```
py -m app.arranque --consola                       # abre la herramienta con consola
py -m unittest discover -s tests -t . -v            # tests
py herramientas/regresion_legado.py control_cheques --entradas <carpeta>
py herramientas/empaquetar.py                       # dist/Reportes-de-cierre-<versión>.zip
```

Para probar la interfaz sin tocar los datos reales: `REPORTES_DATOS=<carpeta temporal> py -m app.arranque --consola --puerto 7319 --sin-navegador`
y abrir la URL con token que imprime.
