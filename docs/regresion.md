# Regresión contra el legado

Cada motor nuevo se comparó con el script original (`legado/`) sobre los archivos reales de un cierre, con
`herramientas/regresion_legado.py`. Se registran los archivos por SHA-256 y cantidad de filas, nunca importes.
Un cambio en un motor exige repetir su fila. Desde la 1.5, la Conciliación general se compara contra el legado con las diferencias explicadas por sus cambios acordados (ver `docs/reglas/conciliacion_general.md`).

| Fecha | Reporte | Entradas (nombre · SHA-256 abreviado · filas) | Parámetros | Legado | Nuevo | Resultado |
|---|---|---|---|---|---|---|
| 2026-10-31 | Conciliación general | SGA histórico `df3cd5b4…` (451.026 líneas) · ERP transacciones `94b8f47f…` | alcance abiertos, corte 2026-10-31, defaults | 83 s | 87 s | **SIN DIFERENCIAS** (CSV byte a byte, Resumen.json, XLSX 2 hojas / 234.519 filas celda a celda) |
| 2026-10-31 | Controles SGA | SGA histórico `5bf2961b…` (451.026 líneas) | corte 2026-10-31, 6 libros, defaults | 139 s | 152 s | **SIN DIFERENCIAS** (6 XLSX / 11 solapas / 678.207 celdas y 46.954 celdas resaltadas, reglas_propuestas.json, ejecucion.json) |
| 2026-10-31 | Control de Mora | Saldo de comprobación `949053a6…` · SGA histórico `86c8bece…` | defaults | 101 s | 103 s | **SIN DIFERENCIAS** (3 CSV byte a byte, PROCESO_COMPLETO.txt) |
| 2026-10-31 | Control de cheques | Cheques SGA `27511e0b…` (76.450 filas) · Tesorería ERP `262292f1…` (82.125 filas) | defaults | 11 s | 12 s | **SIN DIFERENCIAS** (CSV byte a byte; Resumen.txt salvo las líneas de ruta) |
| 2026-10-31 | Conciliación general **1.5** | Mismos archivos que la fila de la 1.4 | alcance abiertos, corte 2026-10-31, defaults | 83 s | 87 s | **SIN DIFERENCIAS NO EXPLICADAS** contra el legado 1.4 (`herramientas/cambios_conciliacion.py`): 146.904 pasan a COINCIDE y 62 a DIFERENCIA por la regla de abiertos; 2 pendientes de FI-P en fila propia (con su DIFERENCIA); Tipo por comprobante principal en 9.081 subrecibos (RC-X 8.977, RC-R 103, RC-O 1); 3 detalles suman el principal de SGA. Totales, cobertura, alertas y fuentes iguales al legado; el Excel coincide con el CSV |
| 2026-10-31 | Descarga de facturas | — (no hay regresión posible sin SharePoint) | — | — | — | Verificado con dobles: `cargar_listados` idéntico al legado sobre fixtures; clasificación de PDF sintéticos; venv real creado con el BAT y tests en verde |
| 2026-11-01 | Control de cheques (Fecha, Fecha de depósito, Pedido a sistemas) | Mismos archivos que la fila del 31/10 | defaults | 12 s | 12 s | **SIN DIFERENCIAS** comparando el CSV sin las dos columnas nuevas (el legado no las tiene). Los archivos de octubre no traen *Fecha de depósito*: la columna sale vacía y el registro lo avisa; *Fecha* sale en las 3 filas a revisar; Pedido a sistemas: 1 fila |
| 2026-11-01 | Controles SGA (servicios por mes, origen de netos) | Mismo histórico que la fila del 31/10 | corte 2026-10-31, 6 libros, defaults | 143 s | 158 s | **SIN DIFERENCIAS** en los otros cinco libros. Servicios: cada fila del legado (Año en curso + Histórico) aparece una sola vez en las solapas nuevas, y las únicas filas de más están en No exigibles (las que el legado dejaba fuera). Solapas: Mes en curso 15, Histórico 703, No exigibles 306. Repetida con el orden final de solapas (Mes en curso / No exigibles / Histórico): **SIN DIFERENCIAS**, 142 s / 154 s |

Tiempos medidos en la PC de desarrollo (Python 3.14). Los dorados sintéticos de cada motor están en
`tests/dorados/<reporte>/` y se verifican en cada corrida de la suite.
