# Reportes de cierre

## Qué es

Es la herramienta con la que se hacen los reportes del cierre mensual: **Conciliación general**,
**Controles SGA**, **Control de Mora** y **Control de cheques**. Trae además, en su propia sección
**Facturas**, la **Descarga de facturas**, que no es parte del cierre. Reemplaza a los
cinco programas sueltos que había antes (cada uno con su carpeta, su ventana negra y su forma de usarse)
por una sola pantalla que se abre en el navegador, con los mismos pasos para los cinco. Los cálculos son
los mismos de siempre: lo que cambió es cómo se usan.

Funciona entera en tu PC. No manda nada a internet (salvo la descarga de facturas, que entra a la
biblioteca de comprobantes con tu usuario, como lo hacías hasta ahora).

## Instalación

1. Extraé el ZIP en una carpeta de tu PC **fuera de OneDrive y de SharePoint**. Por ejemplo,
   `C:\Reportes de cierre`. Si la dejás dentro de una carpeta sincronizada, los archivos grandes se
   suben solos y la herramienta se vuelve lenta o falla.
2. Hacé doble clic en **`Reportes de cierre.bat`**. Se abre el navegador con la herramienta. La
   primera vez crea sola el acceso directo **Reportes de cierre**, con su ícono, en el Escritorio y en la
   carpeta de la herramienta: desde ahí en adelante abrila con ese acceso directo (no muestra la ventana
   negra). Si lo borraste, en Configuración está **Crear el acceso directo en el Escritorio**. Si movés la
   carpeta de la herramienta, abrila una vez con el `.bat` y el acceso directo se corrige solo.
3. Si al abrirla te dice que falta Python (o no abre nada), instalalo desde
   [python.org/downloads](https://www.python.org/downloads/). En la primera pantalla del instalador
   marcá la casilla **"Add Python to PATH"** antes de apretar Install. Después volvé a hacer doble clic
   en `Reportes de cierre.bat` (o en el acceso directo, que te avisa lo mismo con un mensaje).
4. Sólo para **Descarga de facturas** hace falta un paso más, una única vez: doble clic en
   **`Instalar descarga de facturas.bat`**. Tarda entre 2 y 5 minutos y necesita internet. Hasta que lo
   hagas, la sección **Facturas** te avisa que todavía no está instalada; los reportes del cierre
   funcionan igual.

No hace falta instalar nada más ni tener Excel abierto.

## Cómo se usa

### La primera vez

Al abrirla por primera vez aparece una **guía de inicio** corta. Se vuelve a ver cuando quieras desde
**Ayuda**, arriba a la derecha. Ahí también están los cinco pasos explicados, qué significa cada
resultado de la conciliación, preguntas frecuentes y qué hacer si algo sale mal. Dentro de un reporte,
el botón **¿Cómo sigo?** abre la ayuda del paso en el que estás.

La herramienta arranca con el tema claro. El botón de la luna, arriba a la derecha, la pasa a oscuro y
queda así para la próxima vez. También se cambia en Configuración.

### Crear el cierre del mes

Al abrir la herramienta ves la pantalla de **Inicio**: el cierre en curso y, debajo, todos los cierres. A
esa pantalla volvés desde **Inicio**, en la barra de arriba, o tocando el logo con el nombre de la
herramienta; **Cierres** muestra sólo la lista de cierres. Con **Nuevo cierre** elegís el mes en un
calendario; la fecha de corte se propone como el último día del mes y se puede cambiar. Esa fecha queda
propuesta en todos los reportes de ese cierre. Cada cierre muestra el estado de sus reportes (la
Conciliación general cuenta dos veces: una por cada fondo de riesgo): sin correr, en curso, terminado con
tantas filas pendientes, o resultado final.

### Cada reporte en cinco pasos

1. **Archivos.** Arrastrá o elegí los Excel que pide el reporte. La herramienta reconoce sola qué es
   cada archivo (por sus columnas, no por el nombre) y te lo dice en palabras: por ejemplo "Reconocí el
   histórico de cuenta corriente, hoja Datos, 458.658 filas". Si falta uno, hay dos iguales o no
   reconoce alguno, no te deja seguir y te dice qué corregir. Si en este cierre ya subiste el mismo
   histórico para otro reporte, te lo ofrece para no volver a subirlo. El tacho al lado de cada archivo
   lo quita del cierre (el original de tu PC no se toca); los que no reconoce, como un Excel exportado que
   se subió por error, aparecen aparte en *Archivos del cierre que no reconocí* y también se pueden quitar.
   Un archivo que usa alguna versión del cierre no se puede quitar.
2. **Opciones.** Fecha de corte, alcance y las listas que antes estaban fijas en el programa (cuentas,
   conceptos, prefijos). Cada campo tiene su ayuda. Normalmente no hay que tocar nada: los valores son
   los de siempre. Si cambiás algo, podés guardarlo "para los próximos cierres".
3. **Ejecución.** Se ve el avance en lenguaje llano y hay un botón para cancelar. Si el reporte necesita
   que hagas algo (en facturas: iniciar sesión en Chrome), te lo pide y espera a que aprietes
   **Continuar**.
4. **Resultados.** A la izquierda, las tablas de resultado, agrupadas bajo el título de su Excel (por
   ejemplo, *Control Netos Impuestos* con MORA, Mes en curso e Histórico): tocá el título para abrirlas o
   cerrarlas. A la derecha, la tabla elegida con búsqueda, filtros y orden. Si la versión se corrió
   antes de un cambio del reporte, un aviso naranja arriba lo dice: **Correr una versión nueva** la corre
   con los mismos archivos y opciones, y lo que ya revisaste pasa solo. Marcás cada fila como **Revisada** u **Omitir**, o le anotás una
   **Observación**. Arriba ves cuántas quedan pendientes. Las tablas de totales o de respaldo (por
   ejemplo *Resumen*) aparecen aparte, bajo **Información**: se consultan, pero no se revisan fila por
   fila ni cuentan como pendientes.
   - Sólo cuentan las filas que hay que revisar: en la conciliación, las que no dan COINCIDE. El filtro
     **Para revisar** muestra ésas. **Todas** muestra también las que coinciden, con la marca *No requiere*.
   - El embudo de cada título filtra como en Excel. En las columnas de texto tildás los valores: la
     lista muestra lo que queda con los otros filtros y se busca escribiendo. En los importes elegís una
     condición: distinto de cero, igual, mayor, menor o entre dos valores. Los filtros activos se ven
     arriba de la tabla y se quitan con la cruz; se limpian al cambiar de tabla.
   - **Columnas** elige qué columnas ver y en qué orden; también podés arrastrar el título de una columna.
     La vista queda guardada para ese reporte.
   - **Exportar**, en la barra de la tabla, baja un Excel con todas las filas del filtro elegido, no sólo la página, con
     tus columnas en tu orden.
   - En la conciliación, el botón verde de cada fila baja un Excel con las filas de SGA y de ERP que la
     forman, con las columnas del archivo original: primero las de SGA, dos filas libres y después las de
     ERP. En *Control Netos Impuestos* (Controles SGA) baja la fila del histórico de SGA con las celdas a
     completar o corregir en anaranjado, como en pantalla, para pedir la corrección. Para eso la
     herramienta pasa los Excel de entrada a un formato de consulta rápida: lo hace sola al terminar la
     corrida y tarda alrededor de un minuto por cada 60 MB.
5. **Exportar.** Armás el Excel que necesitás en lugar de bajar todo: qué filas (las que hay que
   revisar, todas, o algunos valores del resultado), qué estado de revisión (y si querés sólo las que
   tienen observación) y qué columnas (las de tu vista o todas), con la hoja Resumen al principio si
   querés. Antes de bajarlo te dice cuántas filas va a tener. Más abajo sigue estando el libro completo
   del reporte, con todas sus solapas y tu revisión. Acá también marcás la ejecución como **resultado
   final** del cierre.

### Tareas: lo que tarda

Arriba a la derecha, al lado de Ayuda, está el botón de **Tareas**. Muestra lo que tarda: los reportes que
corren, los Excel que se arman y los archivos que se suben, cada uno con su avance, cuánto tardó y su
resultado. Lo que pedís aparece además en una tarjeta abajo a la derecha que, al terminar, se guarda en
Tareas. Si pedís de nuevo algo que ya está en curso, por ejemplo el mismo Excel, la herramienta te avisa
en lugar de repetirlo. Mientras una acción trabaja, su botón muestra que está ocupado.

### Revisada, omitida, pendiente

- **Pendiente**: todavía no la miraste. Todas las filas nacen así.
- **Revisada**: la miraste y está resuelta o entendida para este mes.
- **Omitida**: es un caso conocido que no corresponde revisar (por ejemplo, una diferencia histórica
  que ya está justificada). La observación explica por qué.

Lo que marcás se guarda solo. Si volvés a correr el mismo reporte en el mismo cierre (una **versión**
nueva), las marcas pasan automáticamente a las filas que siguen apareciendo, y la herramienta te dice
cuántas se trasladaron. Entre un mes y el siguiente no es automático: en Resultados tenés el botón
**"Traer la revisión del cierre anterior"**, que marca como omitidas (con su observación) las filas que
el mes pasado omitiste y que este mes siguen apareciendo. Las revisadas no se traen, porque son de ese
mes.

### Versiones y resultado final

Cada vez que ejecutás un reporte dentro de un cierre se crea una versión nueva (1, 2, 3…); las
anteriores quedan en **Historial** y se pueden borrar. La que marcás como **resultado final** es la que
el cierre muestra como terminada. Podés volver a cualquier paso de una ejecución; si cambiás archivos u
opciones y volvés a ejecutar, se crea otra versión.

## Cada reporte en un párrafo

**Conciliación general.** Se hace por fondo de riesgo: **Fondo de Riesgo General** y **FERF Prov. Santa Fe**,
cada uno con su tarjeta en el cierre, sus versiones y su resultado final. Pide el histórico de cuenta corriente
de SGA (el mismo para los dos fondos: se toman sólo las filas del fondo) y el reporte de transacciones del
cliente de ERP **de ese fondo** (uno unificado, o separados por tipo: Cliente, Pago, Diario general y, en Santa
Fe, Liquidación). En Archivos cada ERP dice de qué fondo es. El fondo se elige con el desplegable de Opciones
(mientras la versión no corrió) y ahí mismo se valida: si el ERP elegido es del otro fondo, un aviso te ofrece
usar ese fondo o volver a elegir el ERP, y no deja correr hasta resolverlo. El fondo se ve en todos los pasos. En Opciones
elegís si el ERP se bajó con *sólo saldos abiertos* o *completo*: cambia qué dice el resultado cuando un
comprobante está de un solo lado. Devuelve un Excel con dos solapas: *Resumen* (totales, cantidades por
estado, alertas y archivos usados) y *Conciliación general* (una fila por comprobante con saldo SGA,
saldo ERP, diferencia y estado: COINCIDE, DIFERENCIA, SOLO EN SGA — REVISAR EN ERP, etc.). Con *sólo
saldos abiertos*, un comprobante de SGA que no figura en el ERP se compara contra cero: da COINCIDE si su
saldo en SGA es cero y DIFERENCIA si no. Un movimiento pendiente de imputación de SGA que se refiere a una
factura sale en su propia fila, con tipo PENDIENTE, y no se suma al saldo de esa factura. En los
subrecibos, la columna Tipo muestra el comprobante principal al que pertenecen (RC-X para recibos, OP-X
para órdenes de pago); la comparación sigue siendo por subrecibo. A la izquierda de Comprobante están
**Fecha SGA** y **Fecha ERP**, la fecha de ese comprobante en cada sistema (en SGA, la de la factura, o la del
comprobante de imputación cuando la fila es de un recibo, subrecibo o pendiente); una vacía quiere decir que
ese sistema no tiene el comprobante o no trae la fecha. Si las dos fechas son distintas, se pintan de
anaranjado.

**Controles SGA.** Pide sólo el histórico completo de SGA y la fecha de corte. Devuelve los seis
controles de siempre, cada uno en su Excel: netos e impuestos, datos obligatorios, servicios
administrativos, saldo MORA, comprobantes abiertos y concepto/agrupador, separando General y Santa Fe.
La primera vez que lo corrés en un cierre, al terminar te muestra las **reglas propuestas** por concepto
(qué datos exige, qué agrupador suele tener). Las que validás las marcás como confirmadas y volvés a
correr: así los faltantes con regla confirmada salen como ERROR en vez de REVISAR. Las reglas confirmadas
quedan guardadas para los cierres siguientes. En Resultados, *Control de servicios administrativos* tiene
tres solapas: *Mes en curso* (lo facturado o pendiente del mes de la fecha de corte), *No exigibles* (los
casos cuyo mes de facturación todavía no comenzó) e *Histórico* (todo lo anterior, también los meses
anteriores de este año). *Comprobantes abiertos* tiene su propia sección. Una versión corrida antes de
este cambio muestra un aviso: corré una versión nueva para verla así (lo que ya revisaste pasa solo).

**Control de Mora.** Pide el Saldo de comprobación de ERP y el histórico de SGA, bajados al mismo
corte. Compara el saldo de las cinco cuentas de mora del fondo general con la suma de los movimientos
de Mora en SGA y devuelve los dos saldos, la diferencia y el estado (SIN DIFERENCIAS o REVISAR
DIFERENCIA), más los respaldos con las filas que entraron en cada suma.

**Control de cheques.** Pide el Excel de cheques de SGA y el de Valores registrados de tesorería de
ERP. Compara el estado de cada cheque tomando ERP como referencia y devuelve la lista de cheques para
revisar, con el motivo (diferencia de estado, ID no encontrado, duplicado…), la fecha y la fecha de
depósito, y un resumen con las cantidades. Además arma el *Pedido a sistemas*: el ID de SGA y la fecha de
depósito de cada cheque con diferencia de estado, para pedir que corrijan el estado.

**Descarga de facturas** (sección **Facturas**, aparte del cierre). Pide uno o más listados Excel con CUIT y número de factura (las columnas
pueden llamarse de distintas maneras y estar en cualquier lugar). En Opciones, la primera vez, cargás
la dirección de la biblioteca de comprobantes y la carpeta de tu PC donde van los PDF; después quedan
guardadas. Durante la ejecución se abre Chrome: iniciá sesión, esperá a ver la biblioteca
Comprobantes, volvé a la herramienta y apretá **Continuar**. Los PDF se guardan por mes y concepto
(leídos de adentro de cada factura). Devuelve una tabla con el resultado de cada factura (Copiada, Ya
existía, ERROR, Fuera del período…) y otra con las filas del listado que no se pudieron usar. Cada
descarga queda registrada en la sección Facturas.

## Archivos cortados en dos (tramos)

Cuando un reporte es muy largo, el sistema de origen lo corta cerca de las 454.000 filas y te da dos
archivos (o más) con los mismos encabezados: uno es la continuación del otro. En el paso Archivos
podés agregar los dos juntos en la misma entrada: la herramienta ve que son del mismo tipo, los ordena
por nombre y los lee como si fueran uno. Si un archivo tiene justo 450.000 filas o entre 453.000 y
455.000, te avisa "posible descarga recortada" para que te fijes si falta el segundo. En los resultados,
cuando hubo más de un archivo, aparece la columna *Archivo* al lado de la fila de origen para que
encuentres la línea en el Excel correcto.

## Dónde quedan los datos

Los cierres, los archivos que subiste, los resultados y tus marcas se guardan en una carpeta de tu PC
(`ReportesDeCierre\datos`, dentro de los datos locales de tu usuario de Windows; la ruta exacta se ve en
**Configuración**). Esa carpeta **no se comparte ni se copia a OneDrive o SharePoint**: tiene archivos
muy grandes, la base de trabajo se rompe si se sincroniza, y además guarda tu sesión de Chrome para la
descarga de facturas.

Para pasarle un cierre a otra persona usá **Exportar cierre** (en la pantalla del cierre): arma un único
archivo con los resultados trabajados, el resumen y las observaciones, sin los Excel de entrada ni tu
sesión. La otra persona lo abre con **Importar un cierre** y lo ve tal cual, sin poder volver a
ejecutarlo. Es una herramienta de una persona por PC; lo que se comparte es el resultado.

En Configuración también está **Limpieza**: borra los Excel de entrada que ninguna versión final usa
(son los que ocupan lugar); los resultados y las revisiones se conservan.

En esa carpeta queda también el **registro** de la herramienta: anota cada vez que se abre y se cierra
(con el motivo: desde la pantalla, para reiniciarse o por inactividad), si la vez anterior terminó sin
cerrarse bien, los errores, las caídas del programa y cuánto tardó cada Excel de origen. Se descarga en un solo archivo desde Configuración → La herramienta →
**Reportar un problema**.

## Problemas frecuentes

| Qué ves | Qué hacer |
|---|---|
| Hacés doble clic y no se abre nada, o se cierra una ventana negra enseguida | Falta Python o se instaló sin "Add Python to PATH". Instalalo de nuevo desde python.org marcando esa casilla. Si sigue igual, abrí `Reportes de cierre - consola.bat`: deja la ventana abierta con el mensaje, y ese mensaje es lo que hay que mandar. |
| La página dice "Abrí la herramienta desde su acceso directo" | Entraste a la dirección guardada en el navegador de otra vez. Cerrá esa pestaña y volvé a hacer doble clic en `Reportes de cierre.bat` (o en su acceso directo). |
| Una franja dice que la herramienta se actualizó | Se instaló una versión nueva con la herramienta abierta. Tocá **Reiniciar la herramienta** en la franja: se cierra y se vuelve a abrir sola en unos segundos. |
| Una franja roja dice "Se perdió la conexión con la herramienta", o "No se pudo hablar con la herramienta" | La herramienta se cerró: se apagó o suspendió la PC, se cerró el proceso o falló. Volvé a abrirla desde el acceso directo; lo que tenías guardado sigue ahí. Los reportes y Excel de origen que estaban en curso aparecen como interrumpidos en Tareas: volvé a pedirlos. Si te pasa seguido, en Configuración → La herramienta tocá **Reportar un problema** y mandá el archivo a quien te da soporte. |
| Una franja dice que la herramienta "se volvió a abrir en otra pestaña" | La abriste de nuevo (o se reinició) y esta pestaña quedó vieja. Seguí en la pestaña nueva y cerrá ésta. |
| "No reconocí qué reporte es" | El archivo no tiene las columnas del reporte original. Fijate que sea el Excel descargado del sistema, sin editar, y que la hoja de datos esté entera (no un resumen). Si es un formato nuevo, avisá a quien te dio la herramienta. |
| "Hay dos archivos de …; dejá uno solo" o "Archivo duplicado por contenido" | Subiste dos veces el mismo archivo, o dos del mismo tipo que no son tramos. Sacá uno. Si son las dos partes de un reporte cortado, agregalos los dos en la misma entrada. |
| "El archivo supera los … MB permitidos" | El límite se sube en Configuración. Antes fijate que sea el archivo correcto: un histórico de SGA pesa unas decenas de MB. |
| "Posible descarga recortada" | Es un aviso, no un error. Fijate si el sistema te dio un segundo archivo y agregalo como tramo. |
| El reporte terminó con error | Abrí **"Ver el registro completo"** en el paso Ejecución. Si el mensaje te dice qué corregir (una columna que falta, un importe vacío), corregí el archivo de origen y volvé a correr. Si no, mandá el registro a quien te dio la herramienta: el botón lo descarga como archivo de texto; podés adjuntarlo a un mail. |
| "Se cerró la herramienta mientras el reporte corría" | Se apagó la PC o se cerró la herramienta con un reporte en marcha. Volvé a ejecutar esa versión; no quedó nada a medias en tus marcas. |
| Excel de origen: "Ya no está el archivo de entrada…" | La **Limpieza** de Configuración borró un Excel que usó esa versión. Agregalo de nuevo en el paso Archivos y corré una versión nueva. |
| Facturas: "Todavía no está instalada" | Hacé doble clic en `Instalar descarga de facturas.bat`, esperá a que diga Listo y volvé a abrir la herramienta. |
| Descarga de facturas: error de sesión o "La respuesta no es un PDF" | Chrome no estaba con la sesión iniciada cuando apretaste Continuar. Volvé a ejecutar, iniciá sesión, esperá a ver la biblioteca y recién ahí apretá Continuar. |

## Cerrar la herramienta

En el menú de los tres puntos, arriba a la derecha, está **Cerrar la herramienta** (también en
Configuración). Si hay un reporte corriendo te
avisa para que esperes o lo canceles. Mientras la tengas abierta en el navegador no se apaga, aunque no
la uses. Cerrar la pestaña tampoco la apaga en el momento: sigue trabajando y se apaga sola tres horas
después de cerrar la última pestaña. Para volver a abrirla, doble clic en `Reportes de cierre.bat`
o en su acceso directo: si ya estaba abierta, simplemente te lleva a la pantalla.

En el mismo menú está **Reiniciar la herramienta**: la cierra y la vuelve a abrir sola en unos segundos,
en la misma pantalla. Sirve si algo quedó trabado o después de instalar una versión nueva. Lo que tenés
guardado no se pierde; si hay un reporte corriendo, te pide que esperes o lo canceles.
