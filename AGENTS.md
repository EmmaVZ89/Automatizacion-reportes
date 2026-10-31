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

- **Python 3.10+, sólo biblioteca estándar** + `vendor/` (openpyxl y et_xmlfile, puro Python; ver `vendor/VERSIONES.md`).
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
- `app/exportar.py`: Excel "trabajado" (columnas Estado revisión y Observaciones), exportar/importar cierre (ZIP).
- `app/catalogo.py`: carga `app/reportes/*/reporte.py` (entradas con detector, parámetros con default, salidas con
  clave de revisión, `orden`, `requiere`). Campos de presentación: `ambito` (`cierre` o `herramienta`: la Descarga
  de facturas no es del cierre y vive en un espacio propio, `Dominio.espacio_herramienta`, fuera de
  `listar_cierres`; la interfaz la muestra en la sección Facturas) e `icono` (nombre de un `<symbol id="i-…">` del
  sprite de `index.html`). En cada salida: `principal: True` marca la tabla que se abre primero en Resultados y
  `revisable: False` la vuelve informativa (totales, respaldos): se muestra aparte, sin selección ni columna de
  revisión, y no suma pendientes (`Dominio.tablas_informativas`).
- `app/web/`: `index.html`, `estilos.css`, `app.js`. JS vainilla, sin build, **sin `innerHTML`**: todo se construye
  con `el()`. Dos temas por variables CSS (`[data-tema]`, **claro por defecto**), contraste ≥ 4,5:1 verificado por
  test. Íconos: sprite SVG en `index.html` (`icono('i-…')`), nunca imágenes ni fuentes externas. Piezas comunes en
  `app.js`: `dialogo()` (confirmaciones con tono), `abrirModal()`, `abrirMenu()`/`botonMenu()`, `aviso()` (avisos
  con barra de tiempo), `abrirAyuda(clave)` (cajón de ayuda: `AYUDA_PASOS`, `AYUDA_GENERAL`), `bienvenida()` (guía
  de inicio; `configuracion.bienvenida` recuerda que ya se vio) y `fiesta()` (al terminar la revisión). Las
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
