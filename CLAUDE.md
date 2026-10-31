# CLAUDE.md — Reportes de cierre

@AGENTS.md

## Propio de Claude Code

- Las reglas por reporte se cargan solas al tocar `app/reportes/<reporte>/` (`.claude/rules/reportes/*.md`, con
  `paths`). Antes de cambiar un motor, leer `docs/reglas/<reporte>.md` y `docs/pendientes.md`.
- Nunca correr los motores sobre `datos/` reales desde una sesión; para probar la interfaz usar `REPORTES_DATOS`
  apuntando a una carpeta temporal y un puerto 7319–7320, y apagar el server al terminar (`POST /api/cerrar` o matar
  el proceso): no dejar servers corriendo.
- Los archivos reales de prueba (64 MB) viven fuera del repo; la regresión se corre con `--entradas` apuntando a esa
  carpeta y sólo se anota en `docs/regresion.md` el SHA-256 y la cantidad de filas, nunca importes.
- Sin commits ni push automáticos: el dueño del repositorio revisa y commitea.
