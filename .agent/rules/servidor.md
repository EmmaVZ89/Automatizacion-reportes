---
trigger: glob
globs: ["app/*.py", "app/reportes/_comun/**", "herramientas/**"]
---

# Servidor y procesos (`app/*.py`, `app/reportes/_comun/`, `herramientas/`)

- Antes de cambiar el servidor, el dominio, los trabajos o lo común a los reportes, leer `docs/servidor.md`. El mapa de módulos está en "Arquitectura" de `AGENTS.md`.
- Cada reporte corre en un subproceso con `python -I` y habla por el protocolo de `_comun/protocolo.py`: para avisarle algo a la pantalla se usa el protocolo, no `print`.
- El estado se escribe con `almacen.escribir_json_atomico`. Las pruebas usan `REPORTES_DATOS` o `tests/_tmp/`, nunca la carpeta de datos real (`%LOCALAPPDATA%\ReportesDeCierre\datos`).
- Un nombre de archivo que llega de la pantalla pasa por `seguridad.nombre_seguro`, y una ruta dentro de una carpeta, por `seguridad.ruta_confinada`.
- Con un candado tomado no se llama a nada que lo vuelva a pedir ni que espere a otro hilo: así se trabó la herramienta entera con `Origenes.estado()`.
- En pantalla, texto llano; la traza, al registro (`datos/servidor.log` o el `registro.log` de la ejecución).
- Una tabla que puede pasar `MAX_FILAS_EXCEL` filas sigue en hojas de continuación. Un cambio que afecte volumen se prueba con datos sintéticos grandes y se miden los tiempos.
- Un error se arregla con un test que lo reproduce primero. Una herramienta nueva de `herramientas/` lleva su test y su comando en "Comandos" de `AGENTS.md`.
