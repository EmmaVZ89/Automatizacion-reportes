# Interfaz (`app/web/`)

Cómo está armada la pantalla y las prácticas que se siguen al cambiarla. La usan personas administrativas no
técnicas: cada decisión de pantalla se toma pensando en ellas. Lo que dice "lo controla un test" está en
`tests/test_web_estatico.py` y no se negocia.

## Cómo está armada

- `index.html`, `estilos.css` y `app.js`. JS vainilla, sin build. Todo se construye con `el()`.
- Configuración es una ventana (`abrirConfiguracion(seccion)`; `#/configuracion` la abre sobre Inicio).
- El encabezado fijo del reporte, achicado, conserva su alto con margen (`fijarCabecera`): si la página se acortara,
  el navegador corregiría el desplazamiento y la pantalla temblaría.
- Dos temas por variables CSS (`[data-tema]`), **claro por defecto**.
- Íconos: sprite SVG en `index.html` (`icono('i-…')`), nunca imágenes ni fuentes externas.

## Piezas comunes

Se usan éstas; no se arma otra versión de lo mismo.

- `dialogo()`: confirmaciones con tono. Las clases de tono llevan prefijo (`tono-aviso`): no reusar nombres de clase
  de otros componentes (`.aviso` es la notificación).
- `abrirModal()`, `abrirMenu()` / `botonMenu()`.
- `aviso()`: avisos con barra de tiempo.
- `abrirAyuda(clave)`: cajón de ayuda (`AYUDA_PASOS`, `AYUDA_GENERAL`). `bienvenida()`: guía de inicio
  (`configuracion.bienvenida` recuerda que ya se vio).
- `tareas`: visor de tareas. **Todo lo que tarda** pasa por `tareas.correr({clave, titulo})`, que avisa si la misma
  clave ya está en curso; las descargas, por `descargar(ruta, titulo)`. Los reportes y el Excel de origen llegan por
  los eventos `trabajo` y `origen`.
- `btn()`: si su acción devuelve una promesa, el botón se marca solo como ocupado.
- `enSilencio()`: los redibujos que llegan por eventos van sin animaciones de entrada.

## Lo que no se negocia

- Nada de `innerHTML`, `eval` ni recursos externos (CSP `default-src 'self'`). Lo controla un test.
- Todo color es una variable definida en los dos temas, y cada par texto/fondo nuevo se agrega a la lista de
  `test_contraste_minimo_en_los_pares_declarados` (contraste ≥ 4,5:1). Lo controlan dos tests.
- Lenguaje llano. Prohibidas en pantalla: token, JSON, sqlite, puerto, servidor, subproceso, API, backend, endpoint,
  stdout, localhost, debug. Lo controla un test.
- Las animaciones van siempre, también con "reducir movimiento" del sistema: es una decisión del dueño del
  repositorio. Lo controla un test.
- Sin saltos de maquetado (abajo). Lo controla un test.

## Sin saltos de maquetado

Un cambio de tabla, de filtro o de paso no puede mover lo que está alrededor.

- Un bloque que se vuelve a armar con datos que llegan después conserva su alto (`conservarAlto`, lo usa `grilla`).
- La vista toma su ancho al pintarse (`pantallaNueva`), no al cambiar la dirección.
- `html` reserva la barra de desplazamiento (`scrollbar-gutter: stable`).
- La grilla tiene alto fijo; también Configuración y la vista previa de Nuevo cierre.
- Los estados elegidos no cambian el grosor de letra: la tabla elegida se marca con una barrita, no en negrita.
- Los `<details>` se animan con `::details-content` e `interpolate-size`; los avisos entran y salen animando el alto.
- Para medir: un PerformanceObserver de `layout-shift` en Playwright, con la herramienta abierta sobre datos de
  prueba (ver "Cómo probar"). `test_sin_saltos_al_cambiar_de_contenido` fija los arreglos.

## Criterios de pantalla

Decisiones tomadas con quien usa la herramienta; un cambio que las contradiga se consulta antes.

- **Columnas estables.** Una tabla tiene las mismas columnas todos los meses, y no hay columnas que cambien de
  contenido según el caso: así los filtros y el Excel no cambian de lugar. Por eso la conciliación tiene siempre
  *Fecha SGA* y *Fecha ERP*, en lugar de una sola fecha (01/11/2026).
- **Se valida donde se elige.** El aviso va en el paso donde se toma la decisión, con la salida a mano. El fondo de
  riesgo se elige en Opciones: ahí se avisa si el ERP es de otro fondo, se ofrece "Usar <ese fondo>" o "Elegir otro
  ERP" y no se deja correr; Archivos sólo muestra el fondo como dato (01/11/2026).
- **Filtros de encabezado como en Excel**, en todas las columnas: en texto, la lista de valores con búsqueda (hasta
  2.000), recalculada con los demás filtros; en importes, condiciones (distinto de cero, igual, mayor, menor, entre).
- **Errores**: dicen qué pasó y qué hacer, en la voz de la herramienta, sin trazas (la traza va al registro).
- **Una acción se llama igual** en todas las pantallas donde aparece (por ejemplo, "Descargar el registro" en
  Ejecución y en Historial).
- **Esqueletos de carga**: todavía no. Si se agregan, sólo donde la carga real pase ~200 ms (primera apertura de una
  tabla grande, entrada a Resultados de una corrida pesada, lista de valores del filtro, cuenta de filas de
  Exportar): aparecen con 200 ms de demora, duran al menos 300 ms y tienen las medidas del contenido final. Antes se
  miden los tiempos con datos reales (pendiente del 01/11/2026).

## Cómo probar

- Nunca con los datos reales: `REPORTES_DATOS=<carpeta temporal> py -m app.arranque --consola --puerto 7319 --sin-navegador`
  y la URL con token que imprime. Al terminar se apaga (`POST /api/cerrar` o matando el proceso): no quedan
  herramientas abiertas.
- Las pantallas se revisan con Playwright sin ventana (capturas y mediciones) contra esa instancia.
- Un cambio que afecte volumen (grilla, filtros, exportación) se prueba con datos sintéticos grandes y se miden los
  tiempos. Referencia del 02/11/2026, con 1.060.000 comprobantes (ERP en tres tramos): la primera página de la
  grilla sale al instante, la grilla filtrada en *Para revisar* en 0,5 s y la lista de valores de un filtro en 0,8 s.
