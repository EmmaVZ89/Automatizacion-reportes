# Conciliación general (SGA contra ERP)

Fuente: `legado/conciliacion_general/LEEME.txt`, `NOTA_VERSION_1_4.txt`, `HISTORIAL_VERSIONES.txt` y
`VALIDACION_1_4.txt` — versión 1.4 del 16/10/2026 — más los cambios de la **versión 1.5** (31/10/2026,
pedido de la responsable funcional). Las claves de cruce y la lista completa de estados salen de
`legado/conciliacion_general/conciliar.py` y `app/reportes/conciliacion_general/motor.py`.

## Cambios de la versión 1.5 (31/10/2026)

Pedido de la responsable funcional sobre resultados de la 1.4. Son los únicos puntos en que la salida difiere
del legado; `herramientas/cambios_conciliacion.py` los verifica fila por fila contra la salida del legado.

1. **ERP de saldos abiertos: ausente en ERP = saldo ERP cero.** Si un comprobante de SGA no figura en el ERP
   de abiertos, se compara contra 0,00: con saldo SGA cero da `COINCIDE`; con saldo distinto de cero da
   `DIFERENCIA`, con `Saldo ERP` 0,00 y la diferencia informada. Observación: "No figura en el ERP de saldos
   abiertos: se toma saldo ERP 0,00." Dejan de aparecer `SOLO EN SGA — REVISAR EN ERP` y `NO EVALUADO` para
   comprobantes de SGA. Lo que está sólo en ERP no cambia. El alcance `completo` no cambia.
2. **Movimientos pendientes referidos a una factura, en fila aparte.** Una línea de "Movimientos Pendientes"
   sin subrecibo cuyo `NumeroComprobanteImputacion` empieza con `FI-`, `FC-` o `ND-` ya no se suma al saldo de
   ese comprobante: sale en su propia fila, con Tipo `PENDIENTE` y el mismo Comprobante. Motivo: en el
   cierre de octubre dos FI-P de Aportes (cruce recíproco con otro FI-P) tenían un pendiente del importe
   opuesto y la suma daba cero, cuando el saldo real del comprobante en SGA no era cero. La fila PENDIENTE
   se compara como cualquier otra (en abiertos, contra ERP 0,00).
3. **Tipo del subrecibo = tipo del comprobante principal.** Para los subrecibos (`SR-`) la columna Tipo muestra
   el prefijo del comprobante principal: `RC-X`, `RC-R`, `RC-O` (recibos) u `OP-X` (orden de pago). Se toma de
   `Número de Recibo global` en ERP y de `NumeroComprobanteImputacion` en las líneas pendientes con subrecibo de
   SGA. Si no se conoce, `SUBRECIBO` (con observación); si aparecen dos tipos distintos, ambos separados por
   " / " (con observación). **El cruce sigue siendo por cliente y subrecibo**: sólo cambia lo que se muestra.
   Antes todos se mostraban como `OP-X`, aunque la mayoría eran recibos.

## Qué hace

Primera conciliación general de **todos** los movimientos recibidos de un fondo de riesgo (el Fondo de Riesgo
General o, desde el 01/11/2026, FERF Prov. Santa Fe; ver "Fondos de riesgo" más abajo): compara,
comprobante por comprobante, el saldo que surge del histórico de cuenta corriente de SGA con el saldo que
surge de las transacciones del cliente de ERP. Agrupa por cliente, tipo interno y comprobante, suma con
aritmética decimal exacta y recién después redondea a dos decimales. Las ausencias no se reemplazan por
cero (si un lado no tiene el comprobante, su saldo y la diferencia quedan vacíos), salvo el caso del ERP de
saldos abiertos descripto en el cambio 1 de la versión 1.5. Incluye los asientos REH
y los movimientos sin identificación, sin emparejarlos por importe. No incorpora los demás controles del
cierre (eso es Controles SGA).

## Entradas

| Entrada | Cómo se reconoce | Tramos |
|---|---|---|
| Histórico de cuenta corriente (SGA) | Una hoja cuyo encabezado contiene `FondoDeRiesgo`, `CodigoEmpresa`, `NumeroFactura`, `Importe`, `GrupoConceptoFacturacion`, `Subrecibo`, `NumeroComprobanteImputacion`, `CUIT`, `RazonSocial` | 1 a 6 archivos del mismo tipo; se leen en orden de nombre como uno solo |
| Transacciones del cliente (ERP) | Una hoja cuyo encabezado contiene `Saldo2`, `Cuenta de cliente`, `Factura`, `Número de recibo`, `Número de Recibo global`, `Asiento`, `Tipo de transacción` | 1 a 6 archivos: un ERP unificado, o hasta tres separados por tipo de transacción (`Cliente`, `Pago`, `Diario general`), más los tramos de cada uno |

- Los nombres de archivo son libres: la fuente y la hoja original se identifican por los encabezados
  (se buscan en las primeras 10 filas de cada hoja). Las hojas de resumen o tablas dinámicas no se toman
  como fuente porque no tienen el encabezado completo.
- Cada libro debe tener **una sola** hoja de datos original. Una hoja que cumple a la vez el esquema SGA
  y el ERP es "esquema ambiguo" y se rechaza. Un archivo de ERP puesto como SGA (o al revés) se rechaza.
- Archivos idénticos por contenido (mismo SHA-256) se rechazan ("Archivo duplicado por contenido").
- `Tipo de transacción` vacío o distinto de `Cliente`, `Pago`, `Diario general` o `Liquidación` corta la ejecución.
  `Liquidación` la traen los ERP de FERF Prov. Santa Fe (decisión del 01/11/2026): lleva número de `Factura` y se
  clasifica y cruza con las mismas reglas que el resto (en la práctica, como las de tipo `Cliente`).
- Varios archivos ERP con el mismo tipo de transacción se aceptan como tramos de una misma descarga y
  generan la alerta "Tramos del mismo tipo de transacción: … Verificar que sean partes de una misma
  descarga". Un ERP con exactamente 450.000 filas genera la alerta "Posible descarga recortada".
- Si falta alguno de los tres tipos de transacción en el ERP se informa en el Resumen ("Sin filas de
  estos tipos: …").
- Columnas requeridas faltantes, encabezados duplicados, importe vacío o inválido, cliente vacío o una
  celda de error de Excel en una columna requerida cortan la ejecución con un mensaje; nunca se asume cero.

## Reglas de negocio

### Filtro y lectura

- De SGA se toman **sólo** las filas cuyo `FondoDeRiesgo` es igual al parámetro `fondo`. El ERP no se
  filtra por fondo: tiene que ser el ERP de ese fondo (ver "Fondos de riesgo").
- Importe de SGA: columna `Importe`. Importe de ERP: columna `Saldo2`, conservando el signo.
- Los importes se leen como decimales exactos (hasta 80 dígitos de precisión) y se suman antes de
  redondear. El redondeo a dos decimales es "mitad hacia arriba" (`ROUND_HALF_UP`).
- En alcance `abiertos`, las filas de ERP con `Saldo2` cero se conservan y se cuentan en la alerta
  "Modo abiertos: filas con Saldo2 cero".

### Tipo interno y comprobante de cada fila de SGA

| Situación | Tipo interno | Comprobante |
|---|---|---|
| `GrupoConceptoFacturacion` = "Movimientos pendientes" y tiene `Subrecibo` **y** `NumeroComprobanteImputacion` que empieza con `NC-` | `AMBIGUO` | `archivo:fila:N` (alerta "NC y subrecibo simultáneos") |
| Movimiento pendiente con `NumeroComprobanteImputacion` que empieza con `NC-` | `NC` | ese número |
| Movimiento pendiente con `Subrecibo` | `SR` | el subrecibo (el comprobante principal, `NumeroComprobanteImputacion`, define el Tipo visible) |
| Movimiento pendiente sin lo anterior, con `NumeroComprobanteImputacion` que empieza con `FI-`, `FC-`, `ND-` | `MP` (Tipo visible `PENDIENTE`; en la 1.4 era `FACTURA` y se sumaba al comprobante) | ese número |
| Movimiento pendiente con `NumeroComprobanteImputacion` que empieza con `REH` | `REH` | ese número |
| Otro movimiento pendiente | `MP_OTRO` | `NumeroComprobanteImputacion` o `archivo:fila:N` (alerta "Movimiento sin cruce automático") |
| Con `NumeroFactura` que empieza con `NC-` | `NC` | la factura |
| Con `NumeroFactura` (cualquier otro prefijo, incluido `ND-`) | `FACTURA` | la factura |
| Sin `NumeroFactura` | `SIN_FACTURA` | `archivo:fila:N` (alerta "Movimiento sin cruce automático") |

ND se mantiene dentro de FACTURA conservando el prefijo `ND` en el comprobante: no se aprobó un cambio
de clasificación para ND.

### Tipo interno y comprobante de cada fila de ERP

| Situación (en este orden) | Tipo interno | Comprobante |
|---|---|---|
| `Número de Recibo global` empieza con `OP-X` y `Número de recibo` empieza con `SR-` | `SR` | el subrecibo |
| `Número de Recibo global` empieza con `OP-X` sin subrecibo | `OPX` | el identificador OP-X (no se inventa un cruce) |
| `Asiento` empieza con `REH` | `REH` | el asiento |
| `Factura` que empieza con `NC-` | `NC` | la factura |
| `Factura` (otro prefijo) | `FACTURA` | la factura |
| `Número de recibo` empieza con `SR-` | `SR` | el subrecibo |
| Resto | `OTRO` | el asiento o `archivo:fila:N`; si el importe no es cero, alerta "Saldo sin identificador de conciliación" |

Una OP-X que además trae `Factura` genera la alerta "OPX también tiene factura: revisar prioridad".

### Clave de cruce

`(tipo interno, cliente, comprobante)`, donde cliente es `CodigoEmpresa` en SGA y `Cuenta de cliente` en
ERP. Cada lado se agrupa por esa clave y se suma; después se unen las claves de ambos lados. Las
prioridades de cruce son las de la versión 1.3 y no cambiaron en 1.4.

- La columna Tipo de `SR` y `OPX` muestra el tipo del comprobante principal (`RC-X`, `RC-R`, `RC-O`, `OP-X`;
  ver cambio 3 de la versión 1.5); la clave interna sigue usando cliente y subrecibo cuando existe, y
  Comprobante muestra el subrecibo usado. No se agrupa por número de recibo ni de OP-X.
- Una OPX se incluye una sola vez; si hay subrecibo, el cruce se hace por ese identificador.

### Estados (columna Resultado)

| Estado visible | Cuándo |
|---|---|
| `COINCIDE` | Ambos lados tienen el comprobante y los saldos redondeados son iguales |
| `DIFERENCIA` | Ambos lados lo tienen y los saldos difieren |
| `COINCIDE` / `DIFERENCIA` (abiertos) | Alcance `abiertos`: sólo SGA; se compara contra ERP 0,00 (versión 1.5; en la 1.4 era `SOLO EN SGA — REVISAR EN ERP` o `NO EVALUADO`) |
| `SOLO EN ERP — REVISAR EN SGA` | Sólo ERP, con saldo distinto de cero, en cualquier alcance (interno: `SOLO ERP - REVISAR`) |
| `NO EVALUADO - ERP SOLO ABIERTOS` | Alcance `abiertos`: sólo ERP con saldo cero |
| `PENDIENTE NUEVA DESCARGA ERP` | Alcance `completo`: sólo SGA con saldo distinto de cero |
| `SOLO SGA SALDO CERO - REVISAR` | Alcance `completo`: sólo SGA con saldo cero |
| `SOLO ERP SALDO CERO - VERIFICAR ANTIGUEDAD` | Alcance `completo`: sólo ERP con saldo cero, tipo FACTURA |
| `SOLO ERP SALDO CERO - REVISAR` | Alcance `completo`: sólo ERP con saldo cero, otros tipos |
| `SIN COMPROBANTE EN SGA — REVISAR` | Tipo no identificado (`SIN_FACTURA`, `MP_OTRO`, `AMBIGUO`) del lado SGA (interno: `REVISAR IDENTIFICACION - SGA`) |
| `REVISAR IDENTIFICACION - ERP` | Tipo no identificado (`OTRO`) del lado ERP |

Los tres renombres (`LABELS` en `excel.py`) se aplican tanto al Excel como al CSV de respaldo; el resto
de los estados conserva su texto interno. `SIN_ID_MP` está declarado como no identificado pero ninguna
rama lo produce.

### Observaciones generadas por el motor

La columna Observaciones viene con notas fijas cuando corresponde (la revisión de la usuaria se agrega
en la herramienta, no las reemplaza):

- Tipos no identificados: "No se asigna una contraparte automáticamente; se conserva el movimiento y su fila de origen."
- `REH`: "Asiento REH incluido en el saldo general; no se concilia por importe ni por estado de cheque."
- Fila `PENDIENTE`: "Movimiento pendiente de imputación de SGA referido a este comprobante: se informa en una fila aparte y no se suma al saldo del comprobante."
- Clave que incluye otro `MP_OTRO` (referido a `REH`): "Incluye movimiento pendiente identificado por comprobante; revisar su clasificación por separado."
- Clave con OPX en alguno de los lados: "OPX incluida una sola vez; si hay subrecibo, el cruce se hace por ese identificador."
- Subrecibo sin comprobante principal conocido: "No se identificó el comprobante principal (recibo u orden de pago) del subrecibo."
- Subrecibo con dos tipos de comprobante principal: "El subrecibo figura con comprobantes principales de distinto tipo: revisar."
- Abiertos, ausente en ERP: "No figura en el ERP de saldos abiertos: se toma saldo ERP 0,00."

Las notas se unen con un espacio, en el orden de esta lista.

### Controles de cobertura (aserciones)

Al terminar, el motor verifica que la suma exacta y la cantidad de filas incluidas en la salida sean
iguales a las de las fuentes, por lado. Si no coinciden corta con "La salida general no cubre todos los
movimientos de …". También verifica que el Excel tenga tantas filas de datos como claves conciliadas.

### Fecha de corte

Es declarativa: se escribe en el Resumen y en `Resumen.json`. No filtra filas ni reconstruye saldos a
esa fecha.

## Parámetros

| Clave | Título | Default | Qué cambia |
|---|---|---|---|
| `alcance` | Alcance del reporte ERP | (obligatorio, no se persiste) `abiertos` o `completo` | Qué estado reciben los comprobantes presentes en un solo lado (ver tabla de estados) y si se cuenta la alerta de filas con `Saldo2` cero |
| `corte` | Fecha de corte | La del cierre (no se persiste) | Sólo se declara en Resumen / `Resumen.json`; con fecha inválida corta |
| `fondo` | Fondo de riesgo | La variante de la versión (`Fondo de Riesgo General` o `FERF Prov. Santa Fe`; desplegable, no se persiste) | Filtro de filas de SGA; se escribe en la columna Fondo de cada fila y define la variante (serie de versiones) |

## Fondos de riesgo

Pedido del 01/11/2026. La conciliación se hace por fondo: **Fondo de Riesgo General** y **FERF Prov. Santa Fe**.
El histórico de SGA es el mismo para los dos (se filtra por `FondoDeRiesgo`); el ERP es una descarga por fondo.

- **Variante.** El fondo es una variante del reporte (`REPORTE['variantes']`): cada fondo tiene su serie de versiones
  (v1, v2… por fondo), su resultado final, su traslado de marcas entre versiones y su "traer la revisión del cierre
  anterior". En el cierre son dos ítems obligatorios (Conciliación general · Fondo General y · FERF Prov. Santa Fe).
  Las versiones de antes de este cambio son del Fondo General (su parámetro `fondo`).
- **Opciones.** El fondo es un desplegable que arranca con el de la versión; cambiarlo en una versión que todavía no
  corrió la pasa a la serie del otro fondo. Una versión que ya corrió no cambia de fondo.
- **El ERP de cada fondo.** El ERP no trae una columna de fondo: se reconoce por el prefijo de sus asientos
  (`SaFe…`: FERF Prov. Santa Fe; `Ventas-…`: Fondo General). Al agregar un ERP al cierre se guarda de qué fondo es
  (por una muestra de las primeras filas) y Archivos lo muestra como dato ("ERP de …"). La validación va en Opciones,
  donde se elige el fondo: si el ERP elegido es de otro fondo (o mezcla los dos), un aviso lo dice, ofrece "Usar
  <ese fondo>" o "Elegir otro ERP", y no deja correr. Al correr, el servidor también rechaza un ERP de otro fondo. El motor revisa el archivo entero: corta si las transacciones mezclan los dos
  fondos o si son de un fondo distinto del de la corrida, y si el histórico de SGA no tiene filas de ese fondo.
- Con los archivos de octubre: el histórico tiene 339 filas de FERF Prov. Santa Fe (y 450.687 del Fondo General); el
  ERP de Santa Fe tiene 1.065 filas (354 Cliente, 480 Liquidación, 118 Pago, 113 Diario general), de las que 924 tienen
  `Saldo2` cero: es una descarga **completa**. Con alcance completo: 593 comprobantes, 227 COINCIDE, 1 DIFERENCIA.

## Salidas

| Archivo | Tabla / solapa | Columnas principales | Clave de revisión |
|---|---|---|---|
| `Conciliacion_general.xlsx` | `Resumen` | `Control`, `Saldo SGA`, `Saldo ERP`, `Diferencia`, `Resultado / cantidad`, `Detalle` | `Control` |
| `Conciliacion_general.xlsx` | `Conciliación general` | `Tipo`, `Cliente`, `Fecha SGA`, `Fecha ERP`, `Comprobante`, `CUIT`, `Razon social`, `Saldo SGA`, `Saldo ERP`, `Diferencia SGA menos ERP`, `Resultado`, `Filas SGA`, `Filas ERP`, `Origen SGA (primeras 5)`, `Origen ERP (primeras 5)`, `Estado revision`, `Observaciones` | `Tipo` + `Cliente` + `Comprobante`; la revisión se escribe en `Estado revision` y `Observaciones` |
| `Respaldo_tecnico/Conciliacion_general.csv` | — | Las mismas columnas más `Fondo` y `Detalle identificacion` (alias: subrecibo y recibo global); al final filas con `Tipo = CONTROL` | — |
| `Respaldo_tecnico/Resumen.json` | — | versión, alcance, corte, fondo, conteos por estado, cobertura por lado, fuentes (archivo, hoja, SHA-256, filas, total exacto, tipos), tipos ERP ausentes, alertas | — |
| `Respaldo_tecnico/trazabilidad.sqlite`, `Respaldo_tecnico/COMPLETADO.txt` | — | Fila por fila de ambas fuentes con su clasificación; constancia de fin | — |

- En la solapa Conciliación general los importes son números; CUIT, cliente y comprobante son texto.
- **Más comprobantes de los que entran en una hoja** (02/11/2026, con el ERP completo cortado por fechas). Una hoja
  de Excel lleva 1.048.576 filas con el encabezado. Si el detalle no entra, sigue en `Conciliación general (2)`,
  `(3)`…, cada una con el encabezado y el filtro; lo mismo el `Resumen` (`Resumen (2)`…), que lleva una fila por
  alerta. El legado (y la herramienta hasta la 2026.11.01) cortaba la corrida al final con «El detalle supera el
  máximo de filas de Excel.»; el cálculo no cambió. La grilla y el CSV de respaldo no tienen ese límite.
- `Fecha SGA` y `Fecha ERP` (pedido de quien usa el reporte, 01/11/2026) son la fecha del comprobante en cada
  sistema, a la izquierda de `Comprobante`. En SGA se toma `FechaFactura`, salvo que el comprobante de la fila sea
  de imputación (subrecibo, recibo, pendiente o NC imputada: `NumeroComprobanteImputacion` o `Subrecibo`), que
  toma `FechaComprobanteImputacion`. En ERP, sólo `Fecha`. Con varias filas para el mismo comprobante va la más
  antigua (la emisión). Vacía si ese sistema no tiene el comprobante o no trae la fecha. Sólo informan: no
  intervienen en el cruce, los saldos ni el resultado. En el CSV van como `aaaa-mm-dd`; en el Excel, como
  fechas. En la grilla, cuando el comprobante está en los dos sistemas con fechas distintas, las dos se pintan
  de anaranjado (en el cierre de octubre: 27 de 87.518 comprobantes con las dos fechas).
  Los controles no se mezclan con el detalle: van sólo en Resumen.
- Filas `CONTROL` del respaldo (y contenido del Resumen), en este orden: `TOTAL GENERAL POR COMPROBANTE`,
  `TOTAL FUENTES RECIBIDAS`, `DIFERENCIA DE REDONDEO`, `COBERTURA DE MOVIMIENTOS`, `ALCANCE Y CORTE`,
  una `CANTIDAD: <estado>` por estado (orden alfabético), una `ALERTA` por alerta, una `FUENTE SGA` /
  `FUENTE ERP` por archivo.
- `Origen SGA/ERP (primeras 5)` lista hasta cinco `archivo [hoja]:fila`. Con un solo tramo el nombre es
  el del archivo recibido.
- `Resumen.json` lleva `"version": "1.5"`.

## En la herramienta

- **Filas para revisar.** Las filas con `Resultado = COINCIDE` no cuentan como pendientes (`revisar` en
  `reporte.py`). Se ven en la grilla con el filtro Todas, marcadas "No requiere", y se pueden marcar igual.
- **Vista por defecto.** `Resultado` va primero, al lado de la revisión. `Filas SGA`, `Filas ERP`, `Origen SGA
  (primeras 5)`, `Origen ERP (primeras 5)`, `Estado revision` y `Fondo` arrancan ocultas; los datos siguen en la
  fila y en las exportaciones con "todas las columnas".
- **Excel de origen de una fila** (`origen.py`). Toma de `trazabilidad.sqlite` todas las filas de SGA y de ERP con
  la clave de la fila: mismo `Cliente` y `Comprobante`, y tipo interno según el `Tipo` visible (`PENDIENTE` es
  `MP`; `RC-X`, `RC-R`, `RC-O`, `OP-X`, `SUBRECIBO` o una combinación con " / " son `SR` u `OPX`; el resto, el
  mismo tipo). Arma una hoja con el encabezado y las filas de cada archivo de SGA, dos filas libres y el
  encabezado y las filas de cada archivo de ERP, con los valores, formatos de número y anchos del original. Un
  lado sin filas no aparece. A diferencia de `Origen SGA/ERP (primeras 5)`, trae todas las filas. Con varios tramos,
  cada archivo es un bloque con su propio encabezado.
- **Detalle de la lectura** (`ejecutar.informar_lectura`). Al terminar, bien o con error, el registro de la corrida
  lleva por archivo las filas que se tomaron (y las del archivo, si se llegó a `Resumen.json`), su rango de fechas
  (de `trazabilidad.sqlite`) y los tipos de transacción del ERP; después, la cantidad de comprobantes y cuántos hay
  de cada resultado. Sirve para ver si dos tramos del ERP se superponen. Antes de correr se borran el
  `trazabilidad.sqlite` y el `Resumen.json` que haya dejado otra corrida en la misma carpeta.

## Limitaciones y advertencias

- En alcance `abiertos`, que un documento no figure en ERP se toma como saldo ERP cero (cambio 1 de la 1.5):
  si la descarga de abiertos vino incompleta, esos comprobantes aparecen como `DIFERENCIA`. La integridad de
  la descarga ERP se verifica aparte: el Resumen lo deja escrito como "Integridad ERP no confirmada".
- El corte declarado no reconstruye saldos a esa fecha.
- Excel guarda números con hasta 15 dígitos significativos; el cálculo exacto está en
  `trazabilidad.sqlite` y `Resumen.json`. No usar Excel para recalcular el motor.
- Las validaciones manuales de la responsable funcional confirman los casos revisados del cierre; no
  certifican por sí mismas la integridad del ERP ni la resolución contable.
- Los controles automáticos no sustituyen la revisión del cierre.
- Un comprobante que aparece en más de un archivo ERP muestra en `Origen ERP (primeras 5)` el orden en
  que se leyeron los tramos (orden natural de nombre).

## Qué NO cambia nunca sin regresión

- La clasificación de tipo interno y comprobante (las dos tablas de arriba, en ese orden de evaluación)
  y la clave `(tipo, cliente, comprobante)`.
- La suma en decimal exacto antes de redondear, `ROUND_HALF_UP` a dos decimales, y que un importe
  ausente nunca se reemplaza por cero (salvo la regla de abiertos de la 1.5, que sólo afecta la comparación).
- Los textos de los estados internos y los tres renombres visibles, las notas de Observaciones y los
  textos de las filas `CONTROL`.
- El orden de las filas: claves ordenadas como texto por `(tipo, cliente, comprobante)`; los controles al
  final, en el orden indicado.
- Las columnas y su orden (`HEAD` + `Fondo` + `Detalle identificacion`; desde el 01/11/2026 con `Fecha SGA` y
  `Fecha ERP`, que la regresión compara aparte porque el legado no las tiene), el separador `;`, UTF-8 con BOM y
  la protección contra fórmulas (`'` delante de `=`, `+`, `-`, `@`) en el CSV.
- Las aserciones de cobertura.

Cualquier cambio en esto exige correr `herramientas/regresion_legado.py conciliacion_general` y anotar
el resultado en `docs/regresion.md`. Desde la 1.5 esa regresión no exige igualdad con el legado: exige que
toda diferencia esté explicada por los cambios de la 1.5 (`herramientas/cambios_conciliacion.py`). Un cambio
de reglas nuevo se agrega ahí, con su motivo en este documento, y se regeneran los dorados
(`tests/dorados/conciliacion_general/generar.py`).
