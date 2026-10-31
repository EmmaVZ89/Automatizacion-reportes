# Controles SGA (seis controles internos sobre el histórico de cuenta corriente)

Fuente: `legado/controles_sga/LEEME.txt` (versión 1.5, actualización 22/10/2026) y el documento
funcional "Controles internos de SGA — Reglas y criterios de revisión" (programa 1.5, documento 0.6,
22/10/2026), escrito por la responsable funcional. Los códigos de control y de estado salen de
`legado/controles_sga/control_sga.py` (mismo código que `app/reportes/controles_sga/motor.py`).

## Qué hace

Sobre el reporte histórico **completo** de cuenta corriente de SGA genera seis salidas independientes:
netos e impuestos, datos obligatorios, servicios administrativos, saldo MORA, comprobantes abiertos y
concepto/agrupador. Todas separan Fondo de Riesgo General y FERF Prov. Santa Fe (el fondo es parte de
cada clave). Conserva las líneas originales de SGA en las salidas, para poder pedir correcciones a
Sistemas. Es un proceso independiente de la conciliación SGA–ERP.

La primera corrida además infiere **reglas propuestas** por concepto (qué datos exige, qué agrupador
suele tener). Las reglas se confirman en la herramienta y se vuelve a correr: un dato faltante con regla
confirmada pasa de REVISAR a ERROR.

## Entradas

| Entrada | Cómo se reconoce | Tramos |
|---|---|---|
| Histórico de cuenta corriente (SGA) | Una hoja cuyo encabezado contiene `FondoDeRiesgo`, `CodigoEmpresa`, `NumeroFactura`, `Importe`, `GrupoConceptoFacturacion`; el motor usa además `CUIT`, `RazonSocial`, `NumeroDeAporte`, `Expediente`, `Operacion`, `Concepto`, `FechaFactura`, `NumeroComprobanteImputacion`, `ConceptoFacturacionImputacion`, `FechaComprobanteImputacion`, `FechaImputacion`, `Subrecibo`, `ImporteNetoGravado`, `ImporteIVA`, `ImporteIIBB` | 1 a 6 archivos del mismo tipo, leídos en orden de nombre como uno solo |

- La hoja se detecta por columnas, no por el nombre de la solapa; el nombre del archivo es libre.
- Con un solo tramo la fila de origen es el número de fila del Excel; con varios, las salidas agregan la
  columna `Archivo` y los mensajes de preparación dicen "Fila N de <archivo>".

### Vocabulario del motor

| Término | Definición |
|---|---|
| Línea de emisión (`base`) | Fila sin `NumeroComprobanteImputacion` |
| Imputación | Fila con `NumeroComprobanteImputacion` |
| Movimiento pendiente | Fila sin `NumeroFactura`, o con el texto "MOVIMIENTOS PENDIENTES" en `NumeroFactura`, `GrupoConceptoFacturacion` o `Concepto` |
| Documento excluido | Fila cuyo `NumeroFactura` o `NumeroComprobanteImputacion` está en `documentos_excluidos` (hoy sólo `CH-20190722105522839`); queda fuera de todos los controles |
| Faltante | Vacío, sólo espacios o cero |
| Clave de factura | fondo + `CodigoEmpresa` + `NumeroFactura` |
| Clave de servicio | fondo + `CodigoEmpresa` + `NumeroDeAporte` |
| Clave de OPX pendiente | fondo + `CodigoEmpresa` + `Subrecibo` |
| Cruce FI recíproco | Dos líneas `FI-P…` del mismo fondo y cliente que se referencian mutuamente (`NumeroFactura` de una = `NumeroComprobanteImputacion` de la otra) con importes opuestos dentro de la tolerancia. Se reconoce como referencia real sin inventar una emisión |

Las comparaciones de texto se hacen sin acentos, sin espacios sobrantes y sin distinguir mayúsculas.

## Reglas de negocio

### Reglas por concepto (propuestas y confirmadas)

Para cada concepto, sobre sus líneas de emisión no pendientes, el motor cuenta cuántas tienen
`NumeroDeAporte` y cuántas tienen `Expediente` **y** `Operacion`, y cuál es su agrupador más frecuente.
La regla propuesta (`datos`) es:

1. `EXENTO` si el concepto empieza con "ACCIONES " o está en `conceptos_exentos` (confirmado).
2. `APORTE` si está en `conceptos_con_aporte` (confirmado).
3. Si no, el patrón mayoritario (`APORTE` o `EXP_OP`) cuando cubre al menos el 80 % de las líneas; si
   no llega, `SIN_DEFINIR`.

`datos_confirmados` sólo es verdadero para 1 y 2. `agrupador` es el más frecuente y `agrupador_confirmado`
nace en falso. El resultado se escribe en `reglas_propuestas.json` con las cantidades observadas
(`lineas_emision_observadas`, `con_aporte`, `con_exp_op`).

Las reglas confirmadas (parámetro `reglas`) reemplazan a las propuestas concepto por concepto; los
exentos y los de aporte confirmados en el programa prevalecen siempre sobre cualquier regla cargada.
`REQUIERE_DATO_SIN_DEFINIR` existe como valor pero el programa no lo asigna a ningún concepto por sí solo.

### Excepciones confirmadas de datos obligatorios

Los movimientos pendientes y estos conceptos quedan fuera del control de datos obligatorios, incluidas
las comprobaciones de coincidencia con la factura (la excepción no los saca de las otras salidas):
`ACCIONES CLASE A - PARTICIPES`, `ACCIONES CLASE B - PROTECTORES` (todo concepto que empiece con
"ACCIONES "), `VENTA BIENES DE USO`, `VENTA DE BIENES DE USO`, `PUBLICIDAD GRAFICA`, `DEVOLUCION DE
COBRANZA`, `CHEQUE A CANJEAR - FRG`, `CHEQUE RECHAZADO` (ese concepto exacto, no otros que contengan
esas palabras), `COMISION POR CUENTA DE TERCEROS`, `DEUDAS DIVERSAS`, `DEVOLUCION A LOS FONDOS
ESPECIFICOS`, `DIFERENCIA DE CAMBIO`, `GASTOS DE ESTUDIO`, `GASTOS ESCRIBANIA`, `IMPORTES A RECUPERAR CON
IVA`, `OTROS INGRESOS`, `REINTEGRO DE GASTOS`, `RESCATE AVAL POR CGTIA`, `SERVICIOS ADMINISTRATIVOS`,
`SINIESTROS A COBRAR`.

Requieren número de aporte (confirmado): `SERV. ADMINIST. FRG - 1º`, `SERV. ADMINIST. FRG - 2º`,
`DEUDA POR APORTE VENCIDO GTZ`. El resto de las reglas inferidas del patrón del reporte son propuestas
hasta que se validen.

### 1. Netos e impuestos (`Control_Netos_Impuestos`)

Se excluyen los movimientos pendientes. No se recalculan impuestos con los porcentajes de SGA: sólo se
usan importes registrados.

| Control | Qué verifica | Resultado |
|---|---|---|
| `SUMA_POR_LINEA` | En cada línea, `Importe` = `ImporteNetoGravado` + `ImporteIVA` + `ImporteIIBB` (margen `tolerancia`, $0,02 por línea) | Diferencia, importes de la línea |
| `REPLICA_NETO` / `REPLICA_IVA` / `REPLICA_IIBB` | Cada imputación replica proporcionalmente los componentes de su factura: esperado = importe imputado × componente original ÷ importe total original, redondeado a centavo; se compara con el registrado con margen `tolerancia` | Registrado, esperado, diferencia |
| `REFERENCIA_NO_VERIFICABLE` | La imputación no tiene línea de emisión (ni cruce FI recíproco) o la referencia no permite calcular la proporción | Motivo |
| `SALDO_COMPONENTES` | Por factura: el total está cancelado (|saldo| ≤ tolerancia) pero queda un remanente de neto, IVA o IIBB mayor al margen acumulado (tolerancia × cantidad de líneas) | Saldos por componente, tolerancia acumulada |
| `REPLICA_SALDO_NETO` / `_IVA` / `_IIBB` | Por factura con saldo distinto de cero: el saldo por componente no conserva la proporción de la factura, con el margen acumulado | Registrado, esperado, diferencia |

La referencia de una imputación son las líneas de emisión de su misma clave de factura; si hay varias,
se prefieren las del mismo concepto que `ConceptoFacturacionImputacion`.

**Consolidación:** una fila por línea original observada (factura, imputación y subrecibo). `Control`
reúne los códigos, `Estado` es siempre `REVISAR`, `Motivo` reúne "código: motivo" de cada observación.
Las observaciones de saldo (`SALDO_COMPONENTES`, `REPLICA_SALDO_*`) se agregan como contexto a las filas
ya observadas de esa factura; si no hay ninguna, generan una fila propia. La fila conserva el bloque
original de SGA desde `CodigoEmpresa` hasta `ImporteIIBB`, en el mismo orden y con los mismos valores, y a
la derecha `Importe`, `Neto`, `IVA`, `IIBB`, `DiferenciaSuma` (importe menos neto, IVA e IIBB de esa
línea; no es la suma de las observaciones), `Saldo`, `SaldoNeto`, `SaldoIVA`, `SaldoIIBB` (contexto de la
factura: no sumar entre filas de distintas imputaciones), `CantidadObservaciones`, `FilaOrigen`,
`TipoCaso` (`FACTURA` o `FACTURA E IMPUTACION`), `ToleranciaAcumulada` y la columna "Qué hay que
corregir".

**Celdas observadas:** se colorea en anaranjado la celda original del componente cuya imputación difiere
de lo esperado, sin modificar su valor (incluidos vacíos y ceros). Si sólo se detecta una suma incorrecta
se marca `Importe`; si sólo hay un remanente por componente se marca el saldo calculado, sin atribuir el
error a una celda no identificada. No se marcan ceros de impuestos que no corresponden. Mensajes:
"Completar Neto", "Completar IVA", "Completar IIBB", "Completar Neto + IVA + IIBB" cuando falta el
importe; "Corregir …" cuando existe pero es incorrecto; "Revisar suma Neto + IVA + IIBB" o "Revisar
saldo Neto + impuestos" cuando no se identifica un componente concreto.

**Solapas:** `MORA` (todas las diferencias del agrupador MORA, sin límite de año), `Mes en curso`
(los demás agrupadores en facturas con alguna imputación en el mes y año de la fecha de corte, aunque la
factura sea antigua) e `Histórico` (el resto).

### 2. Datos obligatorios (`Control_Datos_Obligatorios`)

Se aplica a líneas no pendientes y no excluidas, según la regla del concepto (`datos`):

| Control | Cuándo | Estado |
|---|---|---|
| `REGLA_SIN_DEFINIR` | El concepto tiene regla `SIN_DEFINIR` | `REVISAR` |
| `DATO_EXIGIDO_POR_PRECISAR` | Regla `REQUIERE_DATO_SIN_DEFINIR` | `REVISAR` |
| `DATO_FALTANTE` | Falta `NumeroDeAporte` (regla `APORTE`) o `Expediente` / `Operacion` (regla `EXP_OP`) | `ERROR` si la regla está confirmada; `REVISAR` (motivo con "Regla propuesta por el patrón del reporte; pendiente de confirmar") si no |
| `REFERENCIA_NO_VINCULADA` | Imputación (concepto no exento) sin línea de emisión con el mismo fondo, cliente y comprobante | `REVISAR`. **No afirma que la factura no exista en SGA** |
| `DATOS_NO_COINCIDEN` | `NumeroDeAporte`, `Expediente` u `Operacion` de la imputación distinto del único valor de su factura (incluido el caso de registrado vacío) | `ERROR` (columnas `Campo`, `Esperado`, `Registrado`) |
| `REFERENCIA_AMBIGUA` | La factura tiene varios valores para ese campo | `REVISAR` |

Una fila por línea original (factura e imputaciones separadas); los motivos de la línea se reúnen en
`Motivo` (por ejemplo "Completar Expediente + Operación"). No se agrupan importes ni se repite la fila
por cada campo faltante. Solapas `Año en curso` e `Histórico` según `FechaFactura` (fechas no
disponibles van a Histórico).

### 3. Servicios administrativos (`Control_Servicios_Administrativos`)

Se relacionan únicamente los conceptos `SERV. ADMINIST. FRG - 1º` y `SERV. ADMINIST. FRG - 2º` por
clave de servicio (fondo + cliente + aporte), sobre líneas de emisión no pendientes. Sólo cuentan
documentos `FC…` / `FE…` con importe no negativo. El concepto antiguo `SERVICIOS ADMINISTRATIVOS` queda
fuera del control anual.

El segundo servicio corresponde siempre y debe emitirse en el **mismo mes del año siguiente** al primero
(`MesEsperado`):

| Período esperado | Regla |
|---|---|
| Anterior a `inicio_regla_mensual` (octubre de 2026) | Si existe el segundo (emitido hasta el corte): `OK_HISTORICO` aunque esté desfasado. Si falta: `FALTANTE_HISTORICO` |
| Desde `inicio_regla_mensual` | Debe facturarse en el mes correspondiente: `OK` si coincide el mes, `FUERA_DE_TERMINO` si no |
| Mes esperado posterior al corte | `NO_EXIGIBLE` (se omite de las solapas; se cuenta en `ejecucion.json`) |
| Mes esperado en curso al corte | `PENDIENTE_EN_PLAZO` si falta el segundo |
| Mes esperado terminado al corte, sin segundo | `FALTANTE_VENCIDO` |

Otros resultados del mismo libro:

| Control | Estado | Significado |
|---|---|---|
| `SEGUNDO_SERVICIO` | los de la tabla anterior, o `REVISAR` si la fecha del segundo es inválida | Resultado del par |
| `FACTURA_ANULADA` | `ANULADA POR NC` | Factura anulada totalmente por NC/NE aplicadas; no cuenta como servicio vigente ni como duplicado; se conserva para trazabilidad (`NotasCredito`, `ImporteNC`) |
| `NC_REFACTURACION` | `REVISAR` | Sólo hay NC u otros documentos, sin factura vigente identificable |
| `DUPLICADO` | `REVISAR` | Más de una factura vigente para el mismo aporte y servicio |
| `SIN_PRIMER_VIGENTE` | `REVISAR` | El primer servicio visible fue anulado por NC |
| `SIN_ANTECEDENTE` | `SIN PRIMER SERVICIO VISIBLE` | Existe el segundo pero no se ve el primero (el reporte puede omitir facturas antiguas canceladas) |
| `FECHA_INVALIDA` | `REVISAR` | No se puede determinar el mes esperado |
| `VINCULACION` | `REVISAR` | Falta número de aporte; no se puede vincular |

**Anulación por NC:** se buscan, en la misma clave de factura, imputaciones `NC-`/`NE-` cuyo concepto (o
concepto de imputación) coincida con el emitido, aplicadas hasta la fecha de corte (`FechaImputacion` o,
si falta, `FechaComprobanteImputacion`; sin fecha se toman). Hay anulación total si los signos son
opuestos y la suma queda dentro de la tolerancia. Una NC parcial no anula; un cobro que cancela la
factura no equivale a una anulación; no se atribuye una NC a una factura por compartir sólo el aporte.

Solapas `Año en curso` e `Histórico` según el año esperado del segundo servicio (si el primero no es
visible, el año de emisión del segundo).

### 4. Saldo MORA (`Saldo_MORA`)

Por fondo, suma de `Importe` con su signo de todas las líneas (no excluidas) cuyo
`GrupoConceptoFacturacion` es `MORA`: facturas, imputaciones y notas de crédito, sobre todo el histórico
recibido. Columnas `FondoDeRiesgo`, `SaldoMORA`, `LineasIncluidas`, `Alcance`.

### 5. Comprobantes abiertos (`Comprobantes_Abiertos`)

Incluye OPX, notas de crédito, notas de débito, recibos y cualquier otro comprobante interno con saldo
distinto de cero, positivo o negativo, incluidos los centavos. **Sin tolerancia.** Se excluyen las
facturas oficiales (`facturas_oficiales`: `FC-A`, `FC-B`, `FE-A`) y toda la serie Y.

- Movimientos pendientes: se agrupan por fondo + cliente + `Subrecibo` (`CriterioAgrupacion` "Fondo +
  cliente + subrecibo") o, sin subrecibo, por fondo + cliente + `NumeroComprobanteImputacion`. Sin ninguno
  de los dos: `SIN_IDENTIFICADOR`, clasificación `SIN IDENTIFICAR`, estado `REVISAR`. El saldo es el
  remanente del reporte; los conceptos ya imputados son referencia.
- Resto: se agrupa por clave de factura. Un documento ya representado por su remanente pendiente no se
  repite. Un cruce FI recíproco sin emisión independiente y con contraparte cancelada no genera fila.
- `Estado`: `ABIERTO` cuando el grupo tiene una emisión visible (o una sola clasificación, en pendientes);
  `REVISAR` cuando el saldo sale sólo de imputaciones ("Sin emisión independiente visible…") o las
  clasificaciones son mixtas.
- `Clasificacion` según el documento controlado: `OPX` (OPX / OP-X), `NOTAS DE CRÉDITO` (NC, NE),
  `NOTAS DE DÉBITO` (ND, DE), `RECIBOS` (RC, RCX, RC-X), `FACTURAS INTERNAS` (resto identificado),
  `SIN IDENTIFICAR`.
- `Comprobante` / `ComprobanteControlado` es el documento cuyo saldo se controla; los recibos u OPX
  aplicados a una factura interna aparecen en `ComprobantesRelacionados`.
- `FechaComprobante` es la emisión del documento controlado: `FechaFactura` si fue emitido, o
  `FechaComprobanteImputacion` cuando aparece como imputación, buscando mismo fondo, cliente y número.
  Nunca se reemplaza por la fecha de la factura vinculada ni por `FechaImputacion`. `ControlFecha`: `OK`,
  "Fecha no disponible en origen" o "Fechas de emision diferentes; revisar origen" (celda coloreada).

### 6. Concepto y agrupador (`Control_Concepto_Agrupador`)

| Control | Cuándo | Estado |
|---|---|---|
| `AGRUPADOR` | `GrupoConceptoFacturacion` distinto del agrupador de la regla del concepto | `ERROR` si `agrupador_confirmado`; `REVISAR` si es propuesto |
| `REFERENCIA_NO_VINCULADA` | Imputación sin emisión de referencia (ni cruce FI recíproco) | `REVISAR`. No confirma que falte la factura |
| `IMPUTACION_FUERA_DE_AGRUPADOR` | El concepto de imputación está en `imputacion_condicional` y la factura no tiene exactamente el agrupador exigido | `REVISAR` (`AgrupadorRequerido`, `AgrupadorFactura`) |
| `CONCEPTO_IMPUTACION` | Concepto de imputación vacío o distinto de los conceptos emitidos, sin excepción | `REVISAR` (`ConceptosFactura`) |

Excepciones de imputación válidas sólo para el agrupador indicado: `COMISION POR CUENTA DE TERCEROS` →
`COMISIONES`; `INCOBRABLES PARTICIPES - GTZ` → `COMISIONES`; `INCOBRABLES PARTICIPES - FRG` → `MORA`;
`INCOBRABLES QUITA` → `MORA`. `DEUDA POR APORTE NO VIGENTE - RDO. EJ.` conserva la excepción anterior
(concepto de imputación distinto permitido). Las excepciones no eliminan el control entre concepto
emitido y agrupador. Solapas `Año en curso` e `Histórico` según `FechaFactura`.

### Año y mes en curso

Se determinan por la **fecha de corte**, no por el reloj de la PC. La fecha de corte se usa para
servicios, anulaciones y separación de solapas; las demás salidas leen el reporte completo según las
exclusiones de cada control.

## Parámetros

| Clave | Título | Default | Qué cambia |
|---|---|---|---|
| `corte` | Fecha de corte | La del cierre (obligatoria, no se persiste) | Año/mes en curso, exigibilidad del segundo servicio, anulaciones hasta esa fecha, solapas |
| `salidas_a_generar` | Controles a generar | Los seis libros | Qué libros y tablas se escriben (el cálculo se hace igual) |
| `inicio_regla_mensual` | Desde cuándo el segundo servicio debe ir en el mes exacto | `2026-10-01` | Frontera entre `OK_HISTORICO`/`FALTANTE_HISTORICO` y `OK`/`FUERA_DE_TERMINO`/`FALTANTE_VENCIDO` |
| `documentos_excluidos` | Comprobantes excluidos de todos los controles | `CH-20190722105522839` | Números exactos que no se controlan |
| `conceptos_exentos` | Conceptos exentos de datos obligatorios | Lista de la sección "Excepciones confirmadas" (más todo "ACCIONES …") | Regla `EXENTO` confirmada |
| `conceptos_con_aporte` | Conceptos que exigen número de aporte | `SERV. ADMINIST. FRG - 1º`, `SERV. ADMINIST. FRG - 2º`, `DEUDA POR APORTE VENCIDO GTZ` | Regla `APORTE` confirmada |
| `imputacion_condicional` | Conceptos de imputación válidos sólo para un agrupador | Las cuatro excepciones de la sección 6 | Control `IMPUTACION_FUERA_DE_AGRUPADOR` |
| `imputacion_distinta_permitida` | Conceptos de imputación distintos permitidos | `DEUDA POR APORTE NO VIGENTE - RDO. EJ.` | Excepción de `CONCEPTO_IMPUTACION` |
| `facturas_oficiales` | Prefijos de facturas oficiales | `FC-A`, `FC-B`, `FE-A` | Exclusión de comprobantes abiertos (la serie Y se excluye siempre) |
| `tolerancia` | Margen de redondeo por línea ($) | `0.02` | Margen de netos, réplicas, saldos (× cantidad de líneas), anulación por NC y cruce FI recíproco. No aplica a comprobantes abiertos |
| `reglas` | Reglas confirmadas por concepto | vacío (se usa la propuesta estadística) | Equivale al `--reglas reglas.json` del legado: `datos` (`APORTE`, `EXP_OP`, `EXENTO`, `SIN_DEFINIR`, `REQUIERE_DATO_SIN_DEFINIR`), `datos_confirmados`, `agrupador`, `agrupador_confirmado` |

## Salidas

Seis libros `.xlsx` con filtros, encabezados inmovilizados, importes como números, fechas como fechas e
identificadores como texto. Control, Estado y Motivo van al principio (en abiertos, `Clasificacion`).

| Archivo | Solapas (tabla) | Clave de revisión |
|---|---|---|
| `Control_Netos_Impuestos.xlsx` | `MORA` (`netos_mora`), `Mes en curso` (`netos_mes`), `Histórico` (`netos_historico`) | `FondoDeRiesgo` + `CodigoEmpresa` + `NumeroFactura` + `NumeroComprobanteImputacion` + `Fila SGA` |
| `Control_Datos_Obligatorios.xlsx` | `Año en curso` (`datos_anio`), `Histórico` (`datos_historico`) | `FondoDeRiesgo` + `CodigoEmpresa` + `NumeroFactura` + `NumeroComprobanteImputacion` + `Control` |
| `Control_Concepto_Agrupador.xlsx` | `Año en curso` (`agrupador_anio`), `Histórico` (`agrupador_historico`) | ídem datos obligatorios |
| `Control_Servicios_Administrativos.xlsx` | `Año en curso` (`servicios_anio`), `Histórico` (`servicios_historico`) | `FondoDeRiesgo` + `CodigoEmpresa` + `NumeroDeAporte` + `Control` |
| `Comprobantes_Abiertos.xlsx` | `Comprobantes abiertos` (`abiertos`) | `FondoDeRiesgo` + `CodigoEmpresa` + `Comprobante` |
| `Saldo_MORA.xlsx` | `Saldo por fondo` (`saldo_mora`) | `FondoDeRiesgo` |
| `reglas_propuestas.json` | — | Propuestas de datos y agrupador por concepto, con cantidades |
| `ejecucion.json` | — | Versión, parámetros, archivos, cantidades por salida y solapa, servicios futuros no exigibles |

## Limitaciones y advertencias

- `REFERENCIA_NO_VINCULADA` no confirma que el documento no exista en SGA: el reporte puede omitir
  comprobantes antiguos cancelados. Lo mismo vale para `SIN PRIMER SERVICIO VISIBLE`.
- La cantidad de filas de una salida no representa necesariamente errores distintos.
- El saldo mostrado en Netos es contexto de la factura: no sumar entre filas de distintas imputaciones.
- Los agrupadores propuestos por frecuencia siguen sujetos a validación hasta que se confirman.
- Los saldos de comprobantes abiertos sin emisión visible requieren confirmar la integridad del
  histórico.
- Las fechas faltantes se conservan en Histórico para revisión.
- Las reglas confirmadas en el programa (exentos, aporte) prevalecen sobre configuraciones antiguas.

## Qué NO cambia nunca sin regresión

- Las definiciones de pendiente, línea de emisión, excluido y faltante, y las tres claves (factura,
  servicio, OPX pendiente), siempre con el fondo adelante.
- La aritmética: decimal exacto, esperado = imputado × componente ÷ total redondeado a centavo
  (`ROUND_HALF_UP`), tolerancia por línea y acumulada por cantidad de líneas, sin tolerancia en abiertos.
- La regla de propuestas (umbral 80 %, prevalencia de exentos y aporte) y el orden de evaluación de las
  reglas confirmadas.
- Los códigos de `Control`, los textos de `Estado` (`REVISAR`, `ERROR`, `ABIERTO`, `OK`, `OK_HISTORICO`,
  `FUERA_DE_TERMINO`, `NO_EXIGIBLE`, `PENDIENTE_EN_PLAZO`, `FALTANTE_HISTORICO`, `FALTANTE_VENCIDO`,
  `ANULADA POR NC`, `SIN PRIMER SERVICIO VISIBLE`), los textos de `Motivo`, los mensajes "Completar /
  Corregir / Revisar" y las clasificaciones de abiertos.
- La consolidación de netos (una fila por línea original; saldos como contexto), el bloque original
  `CodigoEmpresa`…`ImporteIIBB` intacto y las celdas anaranjadas.
- El criterio de solapas (MORA / Mes en curso / Histórico; Año en curso / Histórico) y el orden de las
  filas dentro de cada una.

Cualquier cambio en esto exige correr `herramientas/regresion_legado.py controles_sga` y anotar el
resultado en `docs/regresion.md`.
