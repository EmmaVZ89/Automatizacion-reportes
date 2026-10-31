# Control de cheques (estados SGA contra ERP)

Fuente: `legado/control_cheques/LEEME.txt` y el documento "Procedimiento de control de cheques — Cierre
mensual" (actualizado al 22/10/2026). Los motivos exactos salen de
`legado/control_cheques/control_cheques.py` (mismo código que `app/reportes/control_cheques/motor.py`).

## Qué hace

Compara el estado de cada cheque registrado en SGA con el estado registrado en los valores de tesorería
de ERP, que se toma como **referencia**. Produce un listado con los casos que necesitan revisión y un
resumen con las cantidades procesadas. Controla estados de las filas de SGA: no concilia importes ni
fechas, no filtra por fondo ni por fecha y no exige que todos los cheques de ERP estén en SGA.

## Entradas

| Entrada | Cómo se reconoce | Tramos |
|---|---|---|
| Cheques (SGA) | Una hoja cuya primera fila contiene `IdCheque` y `Estado`; se usan además, si existen, `RazonSocial`, `Cuit`, `NumeroCheque`, `Importe` | 1 a 3 archivos |
| Valores registrados de tesorería (ERP) | Una hoja cuya primera fila contiene `Id de Transacción`, `Estado`, `Pagado a` | 1 a 3 archivos |

- Los nombres de archivo son libres. Puede haber otras solapas, pero cada archivo debe tener **una
  única** hoja con las columnas requeridas (si hay cero o más de una, corta).
- Se leen las filas con algún valor a partir de la segunda. No se modifican los Excel de origen.

## Reglas de negocio

### Clave de cruce

- La clave es `IdCheque` de SGA. Si empieza con `prefijo_sga` (`10000`), ese prefijo se reemplaza por
  `prefijo_erp` (`gtz-`) y el resultado se compara **exactamente** (conservando ceros) con
  `Id de Transacción` de ERP. Un ID que no empieza con el prefijo se compara tal cual.
- No se usa el número de cheque, `IdCheque2` ni las columnas auxiliares de SGA.
- Un valor numérico entero de Excel (por ejemplo `10000123.0`) se toma como `10000123`.
- Las filas de ERP sin `Id de Transacción` no se pueden cruzar y se cuentan aparte
  ("Filas ERP sin ID (no se pueden cruzar)").

### Tratamiento, en este orden, para cada fila de SGA

| Dato o estado | Tratamiento | Cuenta en el resumen |
|---|---|---|
| `IdCheque` que empieza con un prefijo de `prefijos_historicos` (`563`) | Histórico válido; no requiere coincidencia en ERP | `Validos: ID historico 563` |
| Sin ID | Revisar: `Falta ID en SGA` | motivo |
| ID ausente en ERP | Revisar: `ID no encontrado en ERP` | motivo |
| ID con más de un registro en ERP | Revisar: `ID duplicado en ERP: revisar antes de comparar`. Se decide **antes** de aplicar exclusiones, para no elegir una coincidencia arbitraria ni ocultar conflictos | motivo |
| ERP con estado en `estados_proveedores` (`debitado`, `entregado`) **o** con `Pagado a` informado | Excluido por Pago a Proveedores, cualquiera sea el estado | `Excluidos: Pago a Proveedores` |
| ERP con estado en `estados_validos` (`canjeado`) | Histórico válido | `Validos: Canjeado historico` |
| ERP `cancelado` presente en SGA | Revisar: `Cancelado en ERP presente en SGA` (salvo que ya haya salido por proveedores) | motivo |
| ERP con estado sin regla en `equivalencias` | Revisar: `Estado ERP sin regla definida` | motivo |
| ERP con regla y estado SGA distinto del esperado | Revisar: `Diferencia de estado` | motivo |
| ERP con regla y estado SGA igual al esperado | Válido | `Estados coincidentes` |

Equivalencias por defecto (ERP → SGA esperado): `Rechazado` → `Rechazado`; `Depositado` → `Depositado`;
`En Cartera` → `Acreditado`. Todas las comparaciones de estado se hacen sin distinguir mayúsculas.

### Qué se informa como caso a revisar

Las diferencias de estado, los ID de SGA ausentes en ERP, los ID faltantes en SGA, los ID duplicados en
ERP, los estados sin regla y los cancelados en ERP presentes en SGA. `Total para revisar` es la cantidad
de filas del listado; la ausencia de diferencias de estado no descarta otros motivos.

## Parámetros

| Clave | Título | Default | Qué cambia |
|---|---|---|---|
| `prefijos_historicos` | Prefijos de ID históricos válidos (sin cruce con ERP) | `563` | Qué IDs de SGA se aceptan sin buscar en ERP |
| `prefijo_sga` | Prefijo del ID en SGA | `10000` | Parte del ID que se reemplaza (obligatorio; vacío haría que todos los IDs reciban el prefijo ERP) |
| `prefijo_erp` | Prefijo equivalente en ERP | `gtz-` | Con qué se reemplaza |
| `equivalencias` | Equivalencias de estado (ERP → SGA) | rechazado→rechazado, depositado→depositado, en cartera→acreditado | Qué estado de SGA se espera para cada estado de ERP; un estado de ERP fuera de la tabla es "sin regla definida" |
| `estados_proveedores` | Estados de ERP que se excluyen (pago a proveedores) | `debitado`, `entregado` | Exclusión (además de todo cheque con `Pagado a`) |
| `estados_validos` | Estados de ERP válidos sin comparar | `canjeado` | Válidos históricos |

El estado `cancelado` de ERP está escrito en el código y no es parámetro; las etiquetas del resumen son
fijas (ver `docs/pendientes.md`).

## Salidas

| Archivo | Tabla | Columnas | Clave de revisión |
|---|---|---|---|
| `Cheques_para_revisar.csv` | `revisar` | `Motivo`, `ID ERP`, `ID SGA`, `Empresa`, `CUIT`, `Numero cheque`, `Importe SGA`, `Estado SGA`, `Estado ERP`, `Fila SGA`, `Filas ERP`. Con varios tramos se agregan `Archivo SGA` (después de `Fila SGA`) y `Archivos ERP` (después de `Filas ERP`) | `ID SGA` + `Motivo` |
| `Resumen.txt` | `resumen` | Encabezado con los archivos usados; una línea `etiqueta: cantidad` por categoría en el orden en que aparecieron (`Filas ERP`, …, `Total para revisar`); párrafo de alcance | `Concepto` |

- `Cheques_para_revisar.csv` contiene sólo los casos a revisar; si todo es válido tiene únicamente el
  encabezado. Separado por `;`, UTF-8 con BOM.
- `Importe SGA` se muestra sólo como referencia: con dos decimales y coma cuando la celda es numérica;
  si viene como texto se copia tal cual.
- `Estado ERP` y `Filas ERP` listan los valores de todos los registros encontrados separados por ` / `
  (varios sólo en duplicados).
- El orden de las filas es el de lectura de SGA.

## Limitaciones y advertencias

- No compara importes ni fechas; los importes son referencia.
- No aplica filtros por fondo ni por fecha; lee una única hoja con los encabezados requeridos aunque
  existan otras solapas.
- No exige que todos los cheques de ERP estén en SGA.
- La exclusión por pago a proveedores sólo se evalúa cuando el ID cruza con un único registro ERP; con
  ID duplicado se informa el duplicado aunque todos sus registros sean pagos a proveedores.
- La lectura de los Excel puede demorar.

## Qué NO cambia nunca sin regresión

- El orden de evaluación de la tabla de tratamiento (histórico → sin ID → no encontrado → duplicado →
  proveedores → válidos → cancelado → sin regla → comparación).
- La transformación del ID (reemplazo de prefijo, conservación de ceros, comparación exacta) y la
  comparación de estados sin distinguir mayúsculas.
- Los textos de los motivos y de las etiquetas del resumen, y las columnas del CSV en su orden.
- El orden de las filas (el de SGA) y el formato de `Importe SGA`.

Cualquier cambio en esto exige correr `herramientas/regresion_legado.py control_cheques` y anotar el
resultado en `docs/regresion.md`.
