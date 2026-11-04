# GEMINI.md — Reportes de cierre (Antigravity)

Leé `AGENTS.md`: ahí están la arquitectura, las reglas de trabajo y los comandos. Las reglas por reporte se activan
solas al tocar `app/reportes/<reporte>/` (`.agent/rules/*.md`) y remiten a `docs/reglas/<reporte>.md`. Las de la
interfaz (`.agent/rules/web.md`) y del servidor (`.agent/rules/servidor.md`) remiten a `docs/interfaz.md` y
`docs/servidor.md`.

Resumen de lo innegociable:

- Los motores (`app/reportes/*/motor.py`) vienen del legado: ningún cambio de cálculo sin correr
  `py herramientas/regresion_legado.py <reporte> --entradas <carpeta>` y anotar en `docs/regresion.md` (la Descarga
  de facturas, con `.venv\Scripts\python.exe herramientas/regresion_facturas.py --pdfs <carpeta>`).
- `datos/` y `sesion_chrome/` nunca al repositorio. Repositorio público: sin nombres de personas u organizaciones,
  sin URLs reales, sin datos reales.
- Interfaz y LEEME en castellano llano, sin jerga técnica; sin `innerHTML` ni recursos externos.
- Tests: `py -m unittest discover -s tests -t . -v`, y con `.venv\Scripts\python.exe` los que leen PDF. Commit y
  push, sólo cuando lo pide el dueño del repositorio.
