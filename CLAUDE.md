# CLAUDE.md — Reportes de cierre

@AGENTS.md

## Propio de Claude Code

- Las reglas por reporte se cargan solas al tocar `app/reportes/<reporte>/` (`.claude/rules/reportes/*.md`, con
  `paths`). Antes de cambiar un motor, leer `docs/reglas/<reporte>.md` y `docs/pendientes.md`. Las de la interfaz
  (`.claude/rules/web.md`) y del servidor (`.claude/rules/servidor.md`) se cargan al tocar `app/web/`, o `app/*.py`,
  `app/reportes/_comun/` y `herramientas/`, y remiten a `docs/interfaz.md` y `docs/servidor.md`.
- Nunca correr los motores sobre `datos/` reales desde una sesión; para probar la interfaz usar `REPORTES_DATOS`
  apuntando a una carpeta temporal y un puerto 7319–7320, y apagar el server al terminar (`POST /api/cerrar` o matar
  el proceso): no dejar servers corriendo.
- Los archivos reales de prueba (64 MB) viven fuera del repo; la regresión se corre con `--entradas` apuntando a esa
  carpeta y sólo se anota en `docs/regresion.md` el SHA-256 y la cantidad de filas, nunca importes.
- Los PDF reales que manda quien usa la herramienta (una factura que cayó mal) se copian a una carpeta propia fuera
  del repo y se leen con `python -I`. En `docs/regresion.md` van su SHA-256 abreviado y sus hojas, nunca el concepto:
  el del legado puede traer el importe en letras, que también es una cifra.
- Commit y push, sólo cuando el dueño del repositorio lo pide (regla 9 de `AGENTS.md`); nunca por iniciativa propia.
