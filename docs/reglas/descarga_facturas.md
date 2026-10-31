# Descarga de facturas (por listado Excel)

Fuente: `legado/descarga_facturas/LEEME.txt` ("Descarga directa por listado Excel — versión 6") y
`legado/descarga_facturas/listado.py` (v6) + `facturas.py` (v5, sólo las funciones de apoyo: lectura del
PDF, nombre seguro, espera de la biblioteca, pedido con sesión). Mismo comportamiento que
`app/reportes/descarga_facturas/motor.py` y `sharepoint.py`.

## Qué hace

A partir de uno o más listados Excel con CUIT y número de factura, descarga el PDF de cada factura desde
la biblioteca de comprobantes de la organización (SharePoint, con la sesión de Chrome de la usuaria) y lo
guarda en una carpeta local organizada por mes de emisión y concepto, ambos leídos **dentro del PDF**.
No recorre la biblioteca: construye la dirección directa de cada archivo con el CUIT y el número. Si una
factura no está en esa ubicación, lo informa y sigue con las demás.

No es parte del cierre mensual: en la herramienta tiene su propia sección, **Facturas** (`ambito: 'herramienta'`
en `reporte.py`), y sus corridas se guardan en un espacio propio, fuera de la lista de cierres.

Este reporte necesita una instalación aparte (`Instalar descarga de facturas.bat`: control de Chrome y
lectura de PDF) y una pausa durante la ejecución para iniciar sesión en Chrome.

## Entradas

| Entrada | Cómo se reconoce | Tramos |
|---|---|---|
| Listado de facturas (Excel con CUIT y número) | Una hoja con, en las primeras 100 filas, una columna CUIT y una columna de número de factura; los encabezados pueden tener variantes y estar en cualquier posición. Un histórico de SGA o un listado de cheques no cuenta como listado aunque tenga esas columnas | 1 a 10 archivos; todos se leen y se juntan |

- Formatos `.xlsx` y `.xlsm`; no `.xls`.
- Se leen **todas** las hojas que tengan encabezados reconocidos, incluso ocultas. En cada hoja, el
  encabezado es la primera fila (dentro de las primeras 100) donde aparecen las dos columnas.
- Variantes aceptadas (sin acentos, espacios ni signos, sin distinguir mayúsculas): CUIT = `cuit`,
  `cuit cliente`, `cuit del cliente`, `identificacion fiscal`, `nif`; número = `numero factura`,
  `nro factura`, `nro de factura`, `numero de factura`, `factura`, `comprobante`,
  `numero comprobante`, `numero de comprobante`.
- Si en una fila hay **dos** columnas posibles para el mismo dato, corta: "Hay varias columnas posibles
  para …; dejá un solo encabezado inequívoco."
- Un archivo sin ninguna hoja reconocida genera una fila en `entrada_a_revisar` ("No se encontró una
  hoja con columnas CUIT y NumeroFactura en las primeras 100 filas").

## Reglas de negocio

### Lectura del listado

- Filas vacías se saltan. Una fila que repite el encabezado dentro del reporte no es una factura.
- **CUIT:** si es numérico debe ser entero; se quitan espacios y guiones; debe quedar de exactamente 11
  dígitos. No se inventan dígitos faltantes. Si no cumple → `entrada_a_revisar` ("CUIT ausente o
  inválido; se requieren 11 dígitos").
- **Número:** se quitan espacios, se pasa a mayúsculas y se quita un `.PDF` final; debe tener la forma
  `FC-`, `NC-` o `ND-` + una letra + 12 o 13 dígitos (ejemplo `FC-A002100588517`). Si no →
  `entrada_a_revisar` ("Número de comprobante ausente o no reconocido; …").
- Una misma combinación CUIT + número se descarga **una sola vez** por ejecución; las repeticiones se
  cuentan como "Repeticiones omitidas".
- Cada factura conserva su origen `archivo / hoja / fila N` (`FilaOrigen`).
- Si no queda ninguna factura válida, corta: "No hay facturas válidas para descargar."
- Las fechas `desde` / `hasta` son opcionales; `desde` posterior a `hasta` corta. La carpeta destino
  debe existir (se valida después de leer el listado).

### Descarga

- Dirección de cada PDF: `<origen><biblioteca>/<CUIT>/<número>.pdf`, pedida con la sesión de Chrome.
  Sólo se aceptan direcciones del origen configurado.
- Antes de descargar, la herramienta abre la vista de la biblioteca y espera a que la usuaria inicie
  sesión y apriete **Continuar**; después espera hasta 90 segundos a que la biblioteca responda.
- La respuesta tiene que ser un PDF (`%PDF-` en el primer kilobyte) y el número de factura tiene que
  aparecer dentro del texto del PDF (sin espacios, en mayúsculas); si no, la fila queda en `ERROR`
  ("La respuesta no es un PDF; revisar sesión o ubicación" / "No se pudo confirmar el número de factura
  dentro del PDF").
- Del PDF se leen la **fecha de emisión** (tiene que haber exactamente una "Fecha de Emisión") y los
  **conceptos**. Ni la fecha ni el concepto se toman del Excel.

### Filtros y destino

| Situación | Estado | Detalle |
|---|---|---|
| Emisión anterior a `desde` o posterior a `hasta` | `Fuera del período` | vacío |
| Hay `concepto` y ningún concepto del PDF lo contiene (comparación normalizada) | `Otro concepto` | vacío |
| Guardada por primera vez, con concepto | `Copiada` | ruta del archivo |
| Guardada por primera vez, sin concepto en el PDF | `REVISAR: concepto no identificado` | ruta (carpeta `Para revisar`) |
| Ya existía un archivo con el mismo nombre y el mismo contenido | `Ya existía` | ruta |
| Ya existía con **otro** contenido | `CONFLICTO: no se reemplazó` | ruta (no se sobrescribe) |
| Cualquier error (no está en la biblioteca, no es PDF, fecha no identificable, sin sesión…) | `ERROR` | mensaje |

- Destino: `<destino>/AAAA-MM/<concepto>/<número>.pdf`, con `AAAA-MM` del mes de emisión. Si el PDF
  tiene más de un concepto, la carpeta es `Varios conceptos`; si no tiene ninguno, `Para revisar`. El
  nombre de carpeta se sanea (caracteres no válidos reemplazados).
- Los originales no se modifican. La subida a la biblioteca de destino la hace OneDrive si está
  sincronizando esa carpeta; la herramienta no sube nada.

## Parámetros

| Clave | Título | Default | Qué cambia |
|---|---|---|---|
| `origen` | Dirección de SharePoint de la organización | (obligatorio; se pide la primera vez y se guarda en la configuración local) | Origen de todas las direcciones; sólo se aceptan pedidos a ese origen |
| `sitio` | Ruta del sitio | `/sites/DynamicsERP` | No interviene en la descarga (herencia de la v5; se devuelve en el resultado) |
| `biblioteca` | Ruta de la biblioteca Comprobantes | `/sites/DynamicsERP/GTZ/Comprobantes` | Carpeta base: `<biblioteca>/<CUIT>/<número>.pdf` |
| `destino` | Carpeta destino en esta PC | (obligatorio; se guarda) | Dónde se crean `AAAA-MM/concepto/` |
| `desde` | Emisión desde | vacío (no se persiste) | Filtro por fecha de emisión leída del PDF |
| `hasta` | Emisión hasta | vacío (no se persiste) | Ídem |
| `concepto` | Concepto a buscar | vacío = todos (no se persiste) | Filtro por concepto leído del PDF |

La sesión de Chrome se guarda en la carpeta de datos de la herramienta (`sesion_chrome`) y es de la
usuaria: nunca se comparte ni va al repositorio.

## Salidas

| Archivo | Tabla | Columnas | Clave de revisión |
|---|---|---|---|
| `descarga.csv` | `descarga` | `CUIT`, `Factura`, `FechaEmisionPDF` (dd/mm/aaaa), `ConceptosPDF` (separados por ` \| `), `Estado`, `Detalle`, `FilaOrigen` | `CUIT` + `Factura` |
| `entrada_a_revisar.csv` | `entrada_a_revisar` | `Archivo`, `Hoja`, `Fila`, `Motivo` | `Archivo` + `Hoja` + `Fila` |

- `descarga.csv` se escribe fila por fila a medida que avanza, en el orden del listado; si se cancela,
  queda lo descargado hasta ese momento.
- `entrada_a_revisar.csv` se escribe siempre (vacío con encabezado si no hay nada).
- Resumen de la ejecución: facturas únicas, repeticiones omitidas, filas a revisar y cantidad por
  estado.

## Limitaciones y advertencias

- Si hay errores, la descarga queda incompleta y el CSV identifica cada factura pendiente; conviene
  revisar errores, conflictos y filas inválidas antes de darla por completa.
- Requiere Chrome instalado, la instalación aparte y conexión a la organización; la sesión expira y
  hay que volver a iniciarla.
- Si al apretar Continuar Chrome todavía está en la pantalla de inicio de sesión, la espera de 90
  segundos termina en error y hay que volver a ejecutar.
- Un PDF cuya fecha de emisión no se identifique de forma única queda en `ERROR`.
- `Fuera del período` no informa en qué mes cayó; `FechaEmisionPDF` sí lo trae.
- No se afirma que todas las facturas de un listado estén disponibles en la biblioteca.

## Qué NO cambia nunca sin regresión

- Las reglas de lectura del listado: alias de columnas, 100 filas de búsqueda, hojas ocultas incluidas,
  normalización de CUIT (11 dígitos, sin inventar) y de número (expresión `(FC|NC|ND)-[A-Z]\d{12,13}`),
  deduplicación por CUIT + número.
- La construcción de la dirección del PDF y las dos verificaciones (es PDF; el número está en el texto).
- Los textos de `Estado` y de `Motivo`, el criterio de carpeta (`AAAA-MM` / concepto / `Varios
  conceptos` / `Para revisar`), y que nunca se sobrescribe un archivo distinto.
- Las columnas y el orden de los dos CSV.

Cualquier cambio en esto exige correr `herramientas/regresion_legado.py descarga_facturas` (con el
navegador simulado sobre una carpeta de PDFs) y anotar el resultado en `docs/regresion.md`.
