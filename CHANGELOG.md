# Novedades

## 2026.10.31

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
