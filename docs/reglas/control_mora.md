# Control de Mora (ERP contra SGA)

Fuente: `legado/control_mora/LEEME.txt` (sin número de versión; actualizado el 22/10/2026) y
`legado/control_mora/control_mora.py` (mismo cálculo que `app/reportes/control_mora/motor.py`).

## Qué hace

Compara el saldo de las cinco cuentas contables de mora del Fondo de Riesgo General en ERP (saldo de
comprobación) con la suma de todos los movimientos del agrupador `Mora` de ese fondo en el histórico de
cuenta corriente de SGA, al centavo. Devuelve los dos saldos, la diferencia y un estado, más un respaldo
con las filas que intervinieron de cada lado.

## Entradas

| Entrada | Cómo se reconoce | Tramos |
|---|---|---|
| Saldo de comprobación (ERP) | Una hoja cuyo encabezado contiene `MainAccount`, `BusinessUnit`, `Saldo de cierre` (sin distinguir acentos ni mayúsculas); se busca en las primeras 20 filas de cada hoja | 1 a 3 archivos |
| Histórico de cuenta corriente (SGA) | Una hoja cuyo encabezado contiene `GrupoConceptoFacturacion`, `FondoDeRiesgo`, `Importe` (el detector general exige además `CodigoEmpresa` y `NumeroFactura`) | 1 a 6 archivos |

- Las hojas se reconocen por sus columnas, no por el nombre de la solapa ni del archivo. El legado los
  reconocía por el prefijo del nombre (`Saldo de comprobación*.xlsx`,
  `ReporteHistoricoDeCuentaCorriente*.xlsx`); eso ya no es necesario.
- Cada archivo debe tener **exactamente una** hoja con las columnas requeridas; con cero o más de una se
  corta ("Se esperaba una sola hoja con columnas …").
- Ambos reportes deben descargarse **al mismo corte**: el proceso no deduce la fecha de corte de los
  movimientos.
- No se modifican los archivos originales. Se conserva archivo, hoja y fila de origen de cada línea.

## Reglas de negocio

### Lado ERP

- Se toman las filas cuyo `MainAccount` (sin el sufijo `.0` que agrega Excel) está en `cuentas`
  (`113601`, `113602`, `113603`, `113604`, `113605`) **y** cuyo `BusinessUnit` es `unidad_negocio`
  (`FRG`).
- Saldo ERP = suma de `Saldo de cierre` de esas filas.
- Cada cuenta tiene que aparecer **exactamente una vez** (113601 se cuenta una sola vez). Si falta
  alguna o hay repetidas, corta: "Faltan cuentas FRG o hay cuentas duplicadas. Cantidades: {…}".

### Lado SGA

- Se toman las filas cuyo `GrupoConceptoFacturacion` es `grupo` (`Mora`) **y** cuyo `FondoDeRiesgo` es
  `fondo` (`Fondo de Riesgo General`). Comparación sin acentos, sin espacios sobrantes y sin distinguir
  mayúsculas.
- Saldo SGA = suma de `Importe` **con su signo**: incluye facturas, imputaciones y notas de crédito, sin
  filtrar fechas ni excluir saldos cancelados.
- No se suma `ImporteNetoGravado` ni se vuelven a agregar impuestos.
- Si no hay ninguna fila de Mora del fondo, corta: "No se encontraron movimientos de Mora del Fondo de
  Riesgo General.".

### Importes

- Se leen como decimales a partir del texto del valor de Excel. Un importe vacío corta ("Importe vacío:
  no se puede dar por cero."); uno no numérico también. Nunca se reemplaza por cero.

### Resultado

- `Diferencia ERP menos SGA` = saldo ERP − saldo SGA.
- `Estado` = `SIN DIFERENCIAS` si la diferencia redondeada a dos decimales es cero; si no,
  `REVISAR DIFERENCIA`.

## Parámetros

| Clave | Título | Default | Qué cambia |
|---|---|---|---|
| `cuentas` | Cuentas de mora en ERP | `113601`, `113602`, `113603`, `113604`, `113605` | Qué cuentas se suman; cada una debe aparecer exactamente una vez |
| `unidad_negocio` | Unidad de negocio (BusinessUnit) | `FRG` | Filtro de las filas de ERP |
| `fondo` | Fondo de riesgo en SGA | `Fondo de Riesgo General` | Filtro de las filas de SGA |
| `grupo` | Agrupador de SGA | `Mora` | Filtro de las filas de SGA |

Los textos de error y la fila "Cuentas ERP (una vez cada una)" siguen nombrando FRG / Mora aunque los
filtros sean parámetros (ver `docs/pendientes.md`).

## Salidas

Todos los CSV van separados por `;`, en UTF-8 con BOM, con coma decimal y protección contra fórmulas.

| Archivo | Tabla | Columnas | Clave de revisión |
|---|---|---|---|
| `Resultado_Control_Mora.csv` | `resultado` | `Concepto`, `Valor`. Filas, en este orden: `Estado`, `Saldo ERP FRG`, `Saldo SGA Mora FRG`, `Diferencia ERP menos SGA`, `Filas ERP`, `Filas SGA`, `Archivo ERP`, `Hoja ERP`, `Archivo SGA`, `Hoja SGA`, `Cuentas ERP (una vez cada una)`, `Criterio SGA`, `Fecha de corte` | `Concepto` |
| `Respaldo_ERP.csv` | `respaldo_erp` | `ArchivoOrigen`, `HojaOrigen`, `FilaOrigen` + todas las columnas originales de las filas de las cinco cuentas | `ArchivoOrigen` + `HojaOrigen` + `FilaOrigen` |
| `Respaldo_SGA_Mora.csv` | `respaldo_sga` | `ArchivoOrigen`, `HojaOrigen`, `FilaOrigen` + todas las columnas originales de cada fila de Mora del fondo | `ArchivoOrigen` + `HojaOrigen` + `FilaOrigen` |
| `PROCESO_COMPLETO.txt` | — | Estado, ERP, SGA, diferencia y filas SGA. Confirma que terminó bien; si falta o dice ERROR no usar los respaldos parciales de esa ejecución | — |

Con varios tramos, las filas `Archivo ERP` / `Archivo SGA` listan los nombres separados por `, ` y las
filas `Hoja …` las hojas distintas. Con un solo archivo el resultado es idéntico al legado.

## Limitaciones y advertencias

- No concilia movimiento por movimiento: compara dos totales.
- Depende de que la usuaria descargue ambos reportes al mismo corte; la fila `Fecha de corte` del
  resultado lo recuerda ("La de las exportaciones…").
- El histórico de SGA es grande (del orden de 450.000 filas): la lectura demora varios minutos.
- Si Excel abre el CSV en una sola columna, importar desde Datos > Desde texto/CSV con delimitador `;` y
  codificación UTF-8.

## Qué NO cambia nunca sin regresión

- Los filtros (cuenta + unidad de negocio; agrupador + fondo) y la comparación de texto normalizada.
- La suma de `Importe` con signo, sin filtro de fechas ni exclusiones; la suma de `Saldo de cierre`; la
  exigencia de una fila por cuenta.
- Diferencia = ERP − SGA, redondeo a dos decimales para decidir el estado, y los textos
  `SIN DIFERENCIAS` / `REVISAR DIFERENCIA`.
- El orden y los textos de las trece filas de `Resultado_Control_Mora.csv`, el formato de los respaldos
  (tres columnas de origen + columnas originales en su orden) y el contenido de `PROCESO_COMPLETO.txt`.

Cualquier cambio en esto exige correr `herramientas/regresion_legado.py control_mora` y anotar el
resultado en `docs/regresion.md`.
