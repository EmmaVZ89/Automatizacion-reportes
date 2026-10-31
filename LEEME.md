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
2. Hacé doble clic en **`Reportes de cierre.bat`**. Se abre el navegador con la herramienta. Podés
   crear un acceso directo a ese archivo en el escritorio para abrirla desde ahí.
3. Si al abrirla te dice que falta Python (o no abre nada), instalalo desde
   [python.org/downloads](https://www.python.org/downloads/). En la primera pantalla del instalador
   marcá la casilla **"Add Python to PATH"** antes de apretar Install. Después volvé a hacer doble clic
   en `Reportes de cierre.bat`.
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

Al abrir la herramienta ves la pantalla **Cierres**. Con **Nuevo cierre** elegís el mes en un
calendario; la fecha de corte se propone como el último día del mes y se puede cambiar. Esa fecha queda
propuesta en todos los reportes de ese cierre. Cada cierre muestra el estado de sus cuatro reportes: sin
correr, en curso, terminado con tantas filas pendientes, o resultado final.

### Cada reporte en cinco pasos

1. **Archivos.** Arrastrá o elegí los Excel que pide el reporte. La herramienta reconoce sola qué es
   cada archivo (por sus columnas, no por el nombre) y te lo dice en palabras: por ejemplo "Reconocí el
   histórico de cuenta corriente, hoja Datos, 458.658 filas". Si falta uno, hay dos iguales o no
   reconoce alguno, no te deja seguir y te dice qué corregir. Si en este cierre ya subiste el mismo
   histórico para otro reporte, te lo ofrece para no volver a subirlo.
2. **Opciones.** Fecha de corte, alcance y las listas que antes estaban fijas en el programa (cuentas,
   conceptos, prefijos). Cada campo tiene su ayuda. Normalmente no hay que tocar nada: los valores son
   los de siempre. Si cambiás algo, podés guardarlo "para los próximos cierres".
3. **Ejecución.** Se ve el avance en lenguaje llano y hay un botón para cancelar. Si el reporte necesita
   que hagas algo (en facturas: iniciar sesión en Chrome), te lo pide y espera a que aprietes
   **Continuar**.
4. **Resultados.** A la izquierda, las tablas de resultado; a la derecha, la tabla elegida con
   búsqueda, filtros y orden. Marcás cada fila como **Revisada** u **Omitir**, o le anotás una
   **Observación**. Arriba ves cuántas quedan pendientes. Las tablas de totales o de respaldo (por
   ejemplo *Resumen*) aparecen aparte, bajo **Información**: se consultan, pero no se revisan fila por
   fila ni cuentan como pendientes.
5. **Exportar.** Bajás el Excel original (tal cual lo genera el reporte) o el **trabajado**: el mismo
   libro con las columnas *Estado revisión* y *Observaciones* completas con lo que marcaste, con opción
   de dejar afuera las omitidas. Acá también marcás la ejecución como **resultado final** del cierre.

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

**Conciliación general.** Pide el histórico de cuenta corriente de SGA y el reporte de transacciones
del cliente de ERP (uno unificado, o hasta tres separados: Cliente, Pago y Diario general). En Opciones
elegís si el ERP se bajó con *sólo saldos abiertos* o *completo*: cambia qué dice el resultado cuando un
comprobante está de un solo lado. Devuelve un Excel con dos solapas: *Resumen* (totales, cantidades por
estado, alertas y archivos usados) y *Conciliación general* (una fila por comprobante con saldo SGA,
saldo ERP, diferencia y estado: COINCIDE, DIFERENCIA, SOLO EN SGA — REVISAR EN ERP, etc.). Con *sólo
saldos abiertos*, un comprobante de SGA que no figura en el ERP se compara contra cero: da COINCIDE si su
saldo en SGA es cero y DIFERENCIA si no. Un movimiento pendiente de imputación de SGA que se refiere a una
factura sale en su propia fila, con tipo PENDIENTE, y no se suma al saldo de esa factura. En los
subrecibos, la columna Tipo muestra el comprobante principal al que pertenecen (RC-X para recibos, OP-X
para órdenes de pago); la comparación sigue siendo por subrecibo.

**Controles SGA.** Pide sólo el histórico completo de SGA y la fecha de corte. Devuelve los seis
controles de siempre, cada uno en su Excel: netos e impuestos, datos obligatorios, servicios
administrativos, saldo MORA, comprobantes abiertos y concepto/agrupador, separando General y Santa Fe.
La primera vez que lo corrés en un cierre, al terminar te muestra las **reglas propuestas** por concepto
(qué datos exige, qué agrupador suele tener). Las que validás las marcás como confirmadas y volvés a
correr: así los faltantes con regla confirmada salen como ERROR en vez de REVISAR. Las reglas confirmadas
quedan guardadas para los cierres siguientes.

**Control de Mora.** Pide el Saldo de comprobación de ERP y el histórico de SGA, bajados al mismo
corte. Compara el saldo de las cinco cuentas de mora del fondo general con la suma de los movimientos
de Mora en SGA y devuelve los dos saldos, la diferencia y el estado (SIN DIFERENCIAS o REVISAR
DIFERENCIA), más los respaldos con las filas que entraron en cada suma.

**Control de cheques.** Pide el Excel de cheques de SGA y el de Valores registrados de tesorería de
ERP. Compara el estado de cada cheque tomando ERP como referencia y devuelve la lista de cheques para
revisar, con el motivo (diferencia de estado, ID no encontrado, duplicado…), y un resumen con las
cantidades.

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

## Problemas frecuentes

| Qué ves | Qué hacer |
|---|---|
| Hacés doble clic y no se abre nada, o se cierra una ventana negra enseguida | Falta Python o se instaló sin "Add Python to PATH". Instalalo de nuevo desde python.org marcando esa casilla. Si sigue igual, abrí `Reportes de cierre - consola.bat`: deja la ventana abierta con el mensaje, y ese mensaje es lo que hay que mandar. |
| La página dice "Abrí la herramienta desde su acceso directo" | Entraste a la dirección guardada en el navegador de otra vez. Cerrá esa pestaña y volvé a hacer doble clic en `Reportes de cierre.bat` (o en su acceso directo). |
| "No se pudo hablar con la herramienta. ¿Se cerró?" | La herramienta se apagó (se apaga sola después de tres horas sin uso). Volvé a abrirla desde el acceso directo; lo que tenías guardado sigue ahí. |
| "No reconocí qué reporte es" | El archivo no tiene las columnas del reporte original. Fijate que sea el Excel descargado del sistema, sin editar, y que la hoja de datos esté entera (no un resumen). Si es un formato nuevo, avisá a quien te dio la herramienta. |
| "Hay dos archivos de …; dejá uno solo" o "Archivo duplicado por contenido" | Subiste dos veces el mismo archivo, o dos del mismo tipo que no son tramos. Sacá uno. Si son las dos partes de un reporte cortado, agregalos los dos en la misma entrada. |
| "El archivo supera los … MB permitidos" | El límite se sube en Configuración. Antes fijate que sea el archivo correcto: un histórico de SGA pesa unas decenas de MB. |
| "Posible descarga recortada" | Es un aviso, no un error. Fijate si el sistema te dio un segundo archivo y agregalo como tramo. |
| El reporte terminó con error | Abrí **"Ver el registro completo"** en el paso Ejecución. Si el mensaje te dice qué corregir (una columna que falta, un importe vacío), corregí el archivo de origen y volvé a correr. Si no, mandá el registro a quien te dio la herramienta: el botón lo descarga como archivo de texto; podés adjuntarlo a un mail. |
| "Se cerró la herramienta mientras el reporte corría" | Se apagó la PC o se cerró la herramienta con un reporte en marcha. Volvé a ejecutar esa versión; no quedó nada a medias en tus marcas. |
| Facturas: "Todavía no está instalada" | Hacé doble clic en `Instalar descarga de facturas.bat`, esperá a que diga Listo y volvé a abrir la herramienta. |
| Descarga de facturas: error de sesión o "La respuesta no es un PDF" | Chrome no estaba con la sesión iniciada cuando apretaste Continuar. Volvé a ejecutar, iniciá sesión, esperá a ver la biblioteca y recién ahí apretá Continuar. |

## Cerrar la herramienta

En el menú de los tres puntos, arriba a la derecha, está **Cerrar la herramienta** (también en
Configuración). Si hay un reporte corriendo te
avisa para que esperes o lo canceles. Cerrar la pestaña del navegador no la apaga: sigue trabajando y
se apaga sola después de tres horas sin uso. Para volver a abrirla, doble clic en `Reportes de cierre.bat`
o en su acceso directo: si ya estaba abierta, simplemente te lleva a la pantalla.
