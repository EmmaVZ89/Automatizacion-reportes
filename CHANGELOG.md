# Novedades

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
- Una versión corrida antes de un cambio del reporte avisa que conviene correr una nueva. Las marcas pasan a la
  nueva versión aunque la fila haya cambiado de solapa (por ejemplo, de Mes en curso a Histórico).
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
