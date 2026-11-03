# Novedades

## 2026.11.03.2

- Descarga de facturas: desde la 2026.11.03, las facturas con tantos ítems que el *SubTotal* y el *TOTAL* pasan a la
  hoja siguiente iban a *Para revisar*. Ahora van a la carpeta de su concepto. Si descargaste con la 2026.11.03,
  borrá la carpeta *Para revisar* y volvé a descargar.

## 2026.11.03

- **Descarga de facturas, una carpeta por concepto:** los PDF se guardan en *carpeta destino / concepto*, con las
  facturas de todos los meses juntas. Ya no se crea la carpeta del mes (por ejemplo *2026-10*).
- Descarga de facturas: en las facturas B, que no tienen renglón de *SubTotal*, el concepto se llevaba el importe en
  letras y cada factura quedaba en una carpeta propia (el nombre del concepto seguido de *---* y el importe). Ahora el
  concepto termina en *SubTotal:* o en *TOTAL:*, y una factura que no tenga ninguno de los dos va a *Para revisar*.

## 2026.11.02

- **Conciliación general con el ERP completo de muchos años:** cuando los comprobantes no entran en una hoja de
  Excel (1.048.575), el detalle sigue en *Conciliación general (2)*, *(3)*… con el mismo encabezado, en el Excel
  del reporte y en los que se bajan (trabajado, vista y cierre exportado). Antes la corrida terminaba al final con
  «El detalle supera el máximo de filas de Excel.». El cálculo no cambia.
- **Descargar el registro**, en el paso Ejecución (termine bien o con error) y en el menú de cada versión en
  Historial: un archivo de texto para mandarle a quien te da soporte, con el reporte, el cierre, la versión, el
  horario, qué pasó, las opciones, los archivos y el registro completo, con la hora de cada línea. Reemplaza a
  "Ver el registro completo", que sólo lo mostraba.
- Conciliación general: el registro dice cuántas filas se tomaron de cada archivo, con qué rango de fechas y de qué
  tipos, cuántos comprobantes salieron y cuántos hay de cada resultado. Así se ve, por ejemplo, si dos tramos del
  ERP se superponen.

## 2026.11.01

- **Reiniciar la herramienta**, en el menú de los tres puntos y en la franja que avisa que se actualizó: se cierra
  y se vuelve a abrir sola en unos segundos, en la misma pantalla.
- Archivos: cada archivo se puede quitar del cierre. Los que no se reconocen (por ejemplo, un Excel exportado que se
  subió por error) aparecen aparte y también se pueden quitar.
- Resultados: las tablas de cada Excel van bajo su título, que se abre y se cierra (por ejemplo, Control Netos
  Impuestos con MORA, Mes en curso e Histórico).
- Mejor lista para elegir la columna del buscador, con búsqueda cuando hay muchas columnas.
- Control de cheques: columnas Fecha y Fecha de depósito (opcionales en los archivos) y tabla nueva *Pedido a
  sistemas* con el ID de SGA y la fecha de depósito de los cheques con diferencia de estado.
- Controles SGA: Excel de origen en Control Netos Impuestos (la fila del histórico de SGA con las celdas a completar o
  corregir en anaranjado). Sección **Control de servicios administrativos** con tres solapas: Mes en curso (lo
  facturado o pendiente del mes), No exigibles (el mes de facturación todavía no comenzó) e Histórico (todo lo
  anterior; ya no hay Año en curso). **Comprobantes abiertos** es una sección propia.
- Las marcas pasan a la nueva versión aunque la fila haya cambiado de solapa (por ejemplo, de Mes en curso a
  Histórico).
- Acceso directo **Reportes de cierre** con el ícono de la herramienta, como el de PedidosIA: se crea solo la
  primera vez, en el Escritorio y en la carpeta de la herramienta, y abre sin la ventana negra. Si la carpeta se
  mueve, se corrige al abrirla; en Configuración se puede volver a crear.
- Una versión corrida antes de un cambio del reporte lo avisa en naranja, con **Correr una versión nueva** (mismos
  archivos y opciones, en un clic).
- Los títulos de las secciones de Resultados (y los controles a generar de Controles SGA) llevan mayúscula sólo en
  la primera palabra.
- Botón **Inicio** en la barra: la pantalla inicial, igual que el logo. **Cierres** muestra la lista de cierres y
  queda marcado mientras se trabaja dentro de un cierre.
- **Conciliación general por fondo de riesgo:** Fondo de Riesgo General y FERF Prov. Santa Fe. El fondo se elige con un
  desplegable en Opciones y se ve en todos los pasos, en el cierre, en Inicio y en Historial (que también filtra por
  fondo). Cada fondo tiene su tarjeta en el cierre (los dos cuentan para completarlo), sus versiones, su resultado
  final y su traslado de marcas. El histórico de SGA es el mismo; el ERP, el de cada fondo: la herramienta reconoce
  de qué fondo es cada ERP (por sus asientos) y lo valida en Opciones, donde se elige el fondo (no deja correr con
  el ERP de otro fondo ni mezclarlos). Se aceptan los movimientos de tipo Liquidación del
  ERP de Santa Fe (se cruzan por su factura). Los Excel que se bajan llevan el fondo en el nombre.
- Corregido: la herramienta se trababa (dejaba de responder y la tarea "Preparando el Excel de origen" no
  terminaba) si se entraba a Resultados mientras se armaba el Excel de origen que arranca solo al terminar una
  corrida. Había que volver a abrirla.
- Pantalla más suave, sin saltos: al cambiar de tabla la grilla conserva su alto hasta que llegan los datos (antes se
  vaciaba, la página se achicaba y volvía a crecer, y la barra de desplazamiento aparecía y desaparecía haciendo
  "vibrar" todo); el lugar de esa barra queda siempre reservado; la grilla tiene alto fijo (filtrar o paginar no corre
  lo de abajo); la tabla elegida se marca sin negrita; elegir una fila no corre la tabla; los bloques que se despliegan
  (Resumen de la corrida, opciones avanzadas, ayuda, valores de Exportar) se abren animados; los avisos entran y salen
  deslizándose; la ventana de Configuración y la de Nuevo cierre no cambian de tamaño; al entrar a un reporte, la
  pantalla anterior ya no se estira un instante. Las animaciones se ven siempre, aunque Windows o el navegador tengan
  "reducir movimiento".
- Conciliación general: columnas **Fecha SGA** y **Fecha ERP** a la izquierda de Comprobante, con la fecha del
  comprobante en cada sistema (en SGA, FechaFactura o, si el comprobante es de imputación, FechaComprobanteImputacion;
  en ERP, Fecha). Si son distintas, en la grilla se pintan de anaranjado. En el Excel van como fechas. Los saldos y
  resultados no cambian.
- En la grilla, las columnas de fecha se ven como día/mes/año y su filtro ordena de la más antigua a la más reciente.
- Una columna nueva de un reporte aparece en su lugar aunque hayas guardado tu propio orden de columnas.
- El filtro de encabezado con muchos valores tildados ya no puede fallar por pedir demasiados a la vez.
- Se sacó Historial del menú de los tres puntos (está en la barra de arriba). "Reportar un problema" (antes
  "Descargar el registro") explica qué hace al pasar el mouse.
- **Configuración** se abre en una ventana, como en PedidosIA: el índice de secciones a la izquierda (Apariencia,
  Archivos, Valores por defecto, Dónde están los datos, Acceso directo, La herramienta) y una sección a la vista.
- Corregido: en algunas páginas, al bajar, el encabezado del reporte temblaba entre la versión completa y la achicada.
- La herramienta ya no se apaga sola mientras está abierta en el navegador (antes se apagaba a las tres horas sin
  pedidos aunque la pestaña siguiera abierta). Tampoco mientras prepara un Excel de origen.
- Si se pierde la conexión con la herramienta, una franja roja lo dice y explica cómo volver a abrirla; los reportes y
  Excel de origen en curso pasan a interrumpidos en Tareas. Si la conexión vuelve (la PC se despertó), la franja se va
  sola y las tareas se ponen al día.
- Registro más completo: cada apertura y cierre con su motivo, el aviso de que la vez anterior terminó sin cerrarse,
  los errores sin atrapar, las caídas del programa (`fallas.log`) y la duración de cada Excel de origen. Se descarga
  desde Configuración → La herramienta → **Reportar un problema**.
- Corregido: la ventana de algunos avisos mostraba el texto "null".

## 2026.10.31

- Visor de **Tareas** en la barra: reportes que corren, Excel que se arman y archivos que se suben, con su avance y
  su resultado. Si se pide de nuevo algo que ya está en curso, se avisa en lugar de repetirlo. Los botones muestran
  que están trabajando mientras dura la acción.
- La pantalla avisa con una franja cuando la herramienta se actualizó estando abierta.
- Exportar: las opciones van en un renglón (qué filas, estado de revisión, qué columnas), con tarjetas de la misma
  altura, y elegir una opción ya no redibuja todo.
- Archivos: los bloques de cada entrada quedan parejos con uno o varios archivos de cada lado. En una versión que
  ya corrió se ven sólo los archivos que usó.
- Se quitó el confeti. Los redibujos que llegan solos (un reporte que termina) ya no repiten las animaciones, y la
  grilla conserva el desplazamiento al marcar filas.
- Corregido: el diálogo para cerrar la herramienta se veía desarmado y quedaba visible después de cerrarla.
- Resultados: sólo cuentan como pendientes las filas que hay que revisar. En la conciliación, las que dan
  COINCIDE se ven en "Todas" con la marca "No requiere"; el filtro nuevo "Para revisar" muestra el resto.
- La grilla se puede configurar: qué columnas ver y en qué orden (ventana "Columnas" o arrastrando el título), y la
  vista queda guardada. En la conciliación, Resultado va al lado de la revisión y las columnas técnicas (filas y
  origen de cada lado, fondo) arrancan ocultas.
- Filtro de encabezado como en Excel: en texto, lista de valores (recalculada con los otros filtros y con búsqueda);
  en importes, condiciones (distinto de cero, igual, mayor, menor, entre). Los filtros activos se muestran arriba de la
  tabla.
- "Exportar" (en la barra de la tabla) baja todas las filas del filtro elegido, con las columnas de la vista.
- Excel de origen de cada fila de la conciliación: las filas de SGA y de ERP que la forman, con las columnas del
  archivo original.
- Exportar: se arma el Excel eligiendo filas, estado de revisión y columnas, con la cuenta de filas antes de bajarlo.
  Se quitaron los archivos técnicos del reporte.
- El encabezado de cada reporte (título y pasos) queda fijo al bajar y se achica para dejar lugar a la tabla.
- Archivos: las entradas se muestran lado a lado. Opciones: las principales van en un mismo renglón.
- Corregido: al ordenar una tabla y pasar a otra (por ejemplo, Resumen) aparecía "No existe esa columna".
- Corregido: algunas acciones dejaban la conexión con la herramienta en mal estado y la acción siguiente fallaba.
- Conciliación general 1.5, con los cambios pedidos por quien usa el reporte. Con el ERP de sólo saldos
  abiertos, un comprobante de SGA que no figura en el ERP se compara contra cero: COINCIDE con saldo SGA cero y
  DIFERENCIA si no. Los movimientos pendientes de imputación referidos a una factura salen en su propia fila
  (tipo PENDIENTE) y ya no se suman a su saldo. En los subrecibos, la columna Tipo muestra el comprobante
  principal (RC-X, RC-R, RC-O u OP-X) en lugar de OP-X para todos; el cruce sigue siendo por subrecibo.
- Interfaz nueva: logo, íconos, menús, ventanas y animaciones; el tema claro es el predeterminado.
- Guía de inicio para quien la usa por primera vez y menú **Ayuda** con los pasos, el significado de cada
  resultado, preguntas frecuentes y qué hacer si algo sale mal. En cada paso, "¿Cómo sigo?" abre su ayuda.
- Nuevo cierre con un calendario de meses; la fecha de corte se propone como el último día del mes.
- La Descarga de facturas pasó a su propia sección, **Facturas**: no es parte del cierre mensual.
- Las tablas de totales y de respaldo se muestran aparte, bajo "Información", y no cuentan como pendientes de
  revisar.

- Primera versión de la herramienta única: los cuatro reportes del cierre (Conciliación general, Controles SGA,
  Control de Mora y Control de cheques) y la Descarga de facturas en una sola pantalla, con un cierre por mes.
- Cada reporte se corre en cinco pasos: Archivos, Opciones, Ejecución, Resultados y Exportar. Se puede volver a un
  paso y correr una versión nueva sin perder la anterior.
- Los archivos descargados se reconocen solos (no hace falta renombrarlos) y se pueden agregar en varios tramos cuando
  el sistema cortó la descarga.
- Las listas y reglas que antes estaban fijas en los programas (conceptos exentos, cuentas de mora, equivalencias de
  estados de cheques, comprobantes excluidos, reglas por concepto) se cambian desde Opciones y se pueden guardar para
  los próximos cierres.
- Cada tabla de resultado se revisa dentro de la herramienta: buscar, filtrar, ordenar, marcar filas como revisadas u
  omitidas y anotar observaciones. Lo marcado pasa solo a la versión siguiente del mismo mes y se puede traer del
  cierre anterior.
- Exportar: el Excel original intacto y el "trabajado" con las columnas Estado revisión y Observaciones; y el cierre
  completo en un archivo para compartirlo.
- Historial de todas las corridas, con borrado de versiones viejas.
- Tema claro y oscuro.
- Los resultados son exactamente los mismos que daban los programas anteriores con los mismos archivos, salvo
  los cambios de la Conciliación general 1.5 descriptos arriba.
