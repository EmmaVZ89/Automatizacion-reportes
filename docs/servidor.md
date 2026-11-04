# Servidor y procesos (`app/*.py`, `app/reportes/_comun/`, `herramientas/`)

Prácticas para cambiar lo que corre detrás de la pantalla. El mapa de módulos está en "Arquitectura" de `AGENTS.md`;
los motores de cada reporte tienen sus reglas en `docs/reglas/<reporte>.md`.

## Reportes en subproceso

- Cada corrida es `python -I app/reportes/<reporte>/ejecutar.py --trabajo <carpeta>`. Habla por líneas JSON en la
  salida estándar (`_comun/protocolo.py`: `log`, `paso`, `progreso`, `tabla`, `esperar`, `resumen`, `error`). Lo que
  imprime y no es JSON queda como log: para avisarle algo a la pantalla, se usa el protocolo.
- El subproceso recibe sus archivos por `entradas.json` y sus opciones por `parametros.json`, y escribe sólo en su
  carpeta de trabajo (`salidas/`, `resultados.sqlite`); la Descarga de facturas, además, en la carpeta destino.

## Datos

- Todo estado en JSON, con escritura atómica y backup (`almacen.escribir_json_atomico`, `Almacen`).
- Los datos reales viven en `%LOCALAPPDATA%\ReportesDeCierre\datos` y nunca van al repositorio. Las pruebas usan
  `REPORTES_DATOS=<carpeta temporal>` o `tests/_tmp/` (`tests/fixtures.carpeta_temporal`); nunca la carpeta real.
- Un nombre de archivo que llega de la pantalla pasa por `seguridad.nombre_seguro`, y una ruta pedida dentro de una
  carpeta, por `seguridad.ruta_confinada`. Cada pedido se autoriza con el token del arranque
  (`seguridad.peticion_autorizada`; cookie `HttpOnly; SameSite=Strict`).

## Candados e hilos

- Con un candado tomado no se llama a nada que lo vuelva a pedir ni que espere a otro hilo. `Origenes.estado()`
  llamado con `_lock` tomado trabó la herramienta entera (`/api/estado` y la copia en curso quedaban esperando,
  01/11/2026). El candado pasó a reentrante sólo como resguardo; el arreglo es pedir el estado después de soltarlo.
- Un problema de este tipo se arregla con un test que lo reproduce primero
  (`test_pedir_la_copia_mientras_se_arma_no_traba_la_herramienta`).

## Errores y registro

- La pantalla recibe un texto llano que dice qué pasó y qué hacer. La traza va a `datos/servidor.log` o al
  `registro.log` de la ejecución, que lleva la hora en cada línea (`Trabajos._escribir_registro`).
- Cada corrida deja un registro que se puede descargar para soporte (`app/registro_corrida.py`), termine bien o con
  error. Un reporte que junta varios archivos deja en el registro qué tomó de cada uno (la conciliación, con
  `informar_lectura`: filas, fechas y tipos por archivo y conteos): así se ve, por ejemplo, si dos tramos se superponen.
- `datos/servidor.log` (rotado): apertura con versión y pid, cierre con `motivo_cierre`, sesión anterior sin cerrar
  (quedó `.servidor.json`), errores sin atrapar (`arranque.registrar_fallas`, sólo en `python -m app.arranque`) y
  caídas del intérprete en `fallas.log` (faulthandler). `GET /api/registro` los baja juntos.

## Volumen

- Una hoja de Excel tiene hasta `MAX_FILAS_EXCEL` filas; lo que no entra sigue en "Nombre (2)", "(3)"… con el mismo
  encabezado (`_comun/xlsx_escritura.escribir_libro`, `nombre_de_hoja`), y `importar_cierre` las junta.
- Un cambio que afecte volumen se prueba con datos sintéticos grandes (02/11/2026: 1.060.000 comprobantes, con el
  ERP en tres tramos) y se miden los tiempos de la corrida y de cada exportación.

## La herramienta en marcha

- Si el código de `app/` cambia con la herramienta abierta, `/api/estado` devuelve `reiniciar` y la pantalla lo avisa.
- Inactividad: `_vigilar_inactividad` cuenta como uso una pestaña conectada a `/api/eventos` (`bus.suscriptores`) y
  una copia de origen en curso; sólo apaga sin pestañas.
- Si la pantalla pierde la conexión (`revisarConexion`: error del canal de eventos, un pedido que no llega o un 403
  de sesión vieja) muestra `#banda-conexion` e interrumpe las tareas de reportes y copias; al volver (`reconectada`)
  las pone al día.
- "Reiniciar la herramienta" (aviso de versión nueva y menú): `POST /api/reiniciar` → `Servidor.reiniciar` lanza
  `python -m app.arranque --reinicio TOKEN` con el mismo token y puerto y se cierra; la instancia nueva espera a que
  se suelte el puerto, y la pantalla espera a que `/api/estado` devuelva otra `instancia` y recarga.
- En Windows el puerto es exclusivo (`_ServidorHttp`, sin `allow_reuse_address`): con `SO_REUSEADDR`, la instancia
  nueva escuchaba con la vieja viva y la conexión abierta seguía hablando con la vieja.

## Herramientas (`herramientas/`)

- `regresion_legado.py` (cuatro reportes) y `regresion_facturas.py` (Descarga de facturas) comparan contra el
  legado con archivos reales y salen con 0 o 1; `cambios_conciliacion.py` explica las diferencias acordadas de la
  conciliación; `empaquetar.py` arma el ZIP de entrega (no lleva datos, tests, legado ni el `.venv`).
- Una herramienta nueva lleva su test en `tests/` con datos sintéticos, y su comando en "Comandos" de `AGENTS.md`.
