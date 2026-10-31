# Pendientes (correcciones menores y de salida detectadas, no aplicadas)

Lo que se vio al refactorizar los motores y al analizar los programas originales, y que **no se cambió** para que el
resultado siga siendo idéntico al legado. Cada punto se corrige como un cambio aparte, acordado con quien usa el
reporte, y con su regresión. Las secciones son por reporte; esta primera es transversal.

## General (de la etapa de análisis)

- El BAT original de Conciliación general no declaraba la fecha de corte y la elección 1/2 por consola era frágil
  (el último error real registrado fue por eso). Resuelto por diseño en la herramienta: el corte y el alcance se
  eligen en Opciones.
- `configuracion.json` del legado traía nombres de archivo que ya no se usaban. La herramienta no lo lee.
- Las columnas `Estado revision` y `Observaciones` de la conciliación existían vacías: ahora las completa la revisión.
- La detección de archivos por prefijo de nombre (Control de Mora) se reemplazó por detección por columnas, igual que
  en los otros reportes; el cálculo no cambió.
- El aviso de "posible descarga recortada" existía sólo en Conciliación general para exactamente 450.000 filas; la
  herramienta lo generaliza a todos los archivos (450.000 exacto o entre 453.000 y 455.000 filas) como aviso.

## Control de cheques

Detectado al refactorizar el legado a `app/reportes/control_cheques/motor.py`; no se aplicó nada de esto (la salida es idéntica al legado).

- Las etiquetas del resumen `Validos: ID historico 563`, `Validos: Canjeado historico` y `Excluidos: Pago a Proveedores` son fijas aunque
  los parámetros `prefijos_historicos`, `estados_validos` y `estados_proveedores` cambien: con otros prefijos o estados el texto deja de
  describir lo que cuenta.
- La exclusión por pago a proveedores (estado `debitado`/`entregado` o `Pagado a` informado) sólo se mira cuando el ID cruza con un
  único registro ERP: con ID duplicado se informa el duplicado aunque todos sus registros sean pagos a proveedores (legado, conservado).
- El estado `cancelado` de ERP está escrito en el código (motivo `Cancelado en ERP presente en SGA`) y no es parámetro.
- `Importe SGA` se formatea con dos decimales y coma sólo cuando la celda es numérica; si la celda viene como texto se copia tal cual
  (p. ej. `1.600,00`), así que la columna mezcla formatos según cómo exporte SGA.
- Con `prefijo_sga` vacío todos los ID de SGA recibirían el `prefijo_erp` adelante (la definición lo marca obligatorio; conviene que el
  server lo valide como no vacío). Un prefijo histórico vacío se ignora.
- La línea de alcance de `Resumen.txt` ("tras reemplazar el prefijo 10000 por gtz-") se interpola con los parámetros; con los defaults
  queda igual al legado.

## Control de Mora

Observaciones del refactor a `app/reportes/control_mora/` (Task 10). Ninguna se aplicó: el motor da byte a byte lo mismo que el legado.

- `celda()` formatea los floats con `str()` y cambia el punto por coma: un valor chico sale en notación científica (`1e-05`),
  y por eso en `resultados.sqlite` columnas como `ImporteNetoGravado` quedan detectadas como texto. `Importe` no lo sufre porque
  se escribe como `Decimal`.
- `importe()` hace `Decimal(str(float))`: suma sobre la representación corta del float que trae openpyxl, no sobre el binario.
  Es lo que siempre hizo; conviene saberlo si alguna vez se compara contra una suma hecha en Excel.
- Los textos de error (`Faltan cuentas FRG...`, `No se encontraron movimientos de Mora del Fondo de Riesgo General.`) y el texto
  fijo de `Cuentas ERP (una vez cada una)` nombran FRG / Mora aunque la unidad de negocio, el fondo y el agrupador ahora sean
  parámetros. Se dejaron tal cual para no cambiar textos.
- El aviso `N filas revisadas...` usa separador de miles inglés (`100,000`) y, con tramos, el contador arranca de nuevo en cada archivo.
- Decisión propia para tramos: en `Resultado_Control_Mora.csv` las filas `Archivo ERP`, `Hoja ERP`, `Archivo SGA` y `Hoja SGA` listan
  los nombres (u hojas distintas) separados por `, `. Con un solo archivo el resultado es idéntico al legado. Los respaldos ya traían
  `ArchivoOrigen`, así que no se agregó ninguna columna.
- Por corrida, `Respaldo_SGA_Mora.csv` pesa 49 MB y `resultados.sqlite` 76 MB (128.677 filas por 39 columnas): la misma tabla queda
  guardada dos veces. Evaluar si la tabla `respaldo_sga` en sqlite hace falta entera o si alcanza con el CSV.
- `detectores.historico_sga` exige `CodigoEmpresa` y `NumeroFactura`, que este motor no usa: un histórico sin esas columnas no se
  reconoce como entrada aunque el motor podría procesarlo. Está en `_comun/`, no se tocó.
- `hoja()` mira sólo las primeras 20 filas de cada hoja y exige exactamente una hoja con las columnas por archivo (igual que el legado;
  con tramos se evalúa archivo por archivo).
- `ejecutar.py` vuelca las tres tablas leyendo los CSV recién escritos (streaming, sin acumular las 128k filas en memoria): los valores
  en sqlite son el texto del CSV (coma decimal, `'` delante de `=+@`), no el valor crudo de Excel.

## Descarga de facturas

Lo que se vio al portar `legado/descarga_facturas/listado.py` (v6) y `facturas.py` (v5) a `motor.py` y `sharepoint.py`.
Nada de esto se corrigió: el motor hace lo mismo que el legado.

- `facturas.py` v5 (recorrido completo de la biblioteca: `inventory`, `selected_files`, `list_items`, `endpoint`, `main`,
  `ask_date`, caché `cache_pdf/`) ya no se usa como flujo. Sólo se portaron `read_pdf`, `safe_name`, `check_url`,
  `get_response` y `wait_for_library`. Si en algún momento hace falta el recorrido completo, se porta desde `legado/`.
- `DEST`, `ORIGIN`, `SITE` y `ROOT` eran constantes fijas (con la carpeta de OneDrive de la usuaria y la URL de la
  organización). Pasaron a los parámetros `destino`, `origen`, `sitio` y `biblioteca`.
- El parámetro `sitio` no interviene en la descarga: la v6 arma la dirección del PDF con `origen + biblioteca + /CUIT/numero.pdf`
  y sólo actualizaba `SITE` con lo que devuelve la página (`webAbsoluteUrl`) por herencia de la v5, donde lo usaba `endpoint()`.
  El motor conserva ese comportamiento (lo devuelve como `sitio` en el resultado) pero podría sacarse de la pantalla de Opciones.
- La verificación del número de factura dentro del PDF abre el PDF dos veces con pdfplumber (una en `read_pdf` para fecha y
  conceptos, otra para el texto completo). Con muchas facturas duplica el tiempo de lectura. Se podría leer una sola vez.
- `read_pdf` exige exactamente una "Fecha de Emisión" en todo el PDF; un comprobante de varias páginas que la repita en cada
  página da "No se pudo identificar una única fecha de emisión" (es el mismo dato, pero el conjunto tiene un solo valor, así
  que en la práctica sólo falla si las fechas difieren o si no está).
- La fila "Otro concepto" se decide con `normalize` (sin acentos ni espacios) en la v6, mientras que la v5 usaba `casefold`
  sobre el texto crudo. Se mantuvo la v6.
- El estado `Fuera del período` deja `Detalle` vacío y no informa en qué mes cayó; el CSV sí trae `FechaEmisionPDF`.
- `wait_for_library` espera hasta 90 segundos después de que la usuaria aprieta Continuar; si Chrome todavía está en la
  pantalla de inicio de sesión, el mensaje de error pide volver a ejecutar. Podría volver a pedir la pausa en vez de cortar.
- El legado sólo escribía `entrada_a_revisar_<stamp>.csv` cuando había filas para revisar; el motor lo escribe siempre
  (vacío con encabezado) para que la tabla exista en la interfaz. `descarga.csv` y `entrada_a_revisar.csv` van sin sello de
  tiempo porque cada ejecución tiene su carpeta.
- `get_response` manda `Accept: application/json;odata=nometadata` también al pedir el PDF (herencia de la v5); SharePoint
  igual devuelve el archivo. Queda así.
- La carpeta destino se valida después de leer el listado (orden del legado). Si no existe, el `entrada_a_revisar.csv` ya
  quedó escrito y `descarga.csv` no se crea.
- Al cancelar durante la pausa de login, `descarga.csv` queda sólo con el encabezado y no se vuelca a la tabla.
- La sesión de Chrome (`sesion_chrome`) la define el server por parámetro; si no la pasa, el motor la crea al lado de
  `salidas/` dentro de la carpeta del trabajo, con lo que la usuaria tendría que iniciar sesión en cada corrida.

## Conciliación general (Task 8)

Detectado al refactorizar `legado/conciliacion_general/conciliar.py` a `app/reportes/conciliacion_general/motor.py`. Nada de esto se corrigió: el motor reproduce al legado (regresión real sin diferencias).

- **Nombre de archivo en las salidas.** El motor usa `p.name` para el origen de cada fila, las alertas, las filas `FUENTE` y `fuentes[].archivo`. En el server el archivo se guarda como `<sha8>-<nombre>`, así que la usuaria va a ver ese prefijo en el Excel. Hace falta que el motor reciba el nombre original junto con la ruta (hoy `run()` recibe sólo rutas, por contrato del brief).
- **Orden de los archivos ERP.** El legado ordenaba los ERP por nombre con orden de cadena; ahora llegan en el orden de `ordenar_tramos` (natural: `descarga_2` antes que `descarga_10`). Sólo cambia el orden de las filas `FUENTE`/`fuentes` y de "Origen ERP (primeras 5)" cuando un mismo comprobante aparece en más de un archivo.
- **Aviso de 450.000 filas.** El legado sólo lo emite para ERP y sólo con exactamente 450.000 filas (`count==450000`); los tramos SGA no avisan. El aviso general por rango (453.000-455.000) vive en la interfaz (`entradas.aviso_recorte`), no en el motor.
- **Celda de error de Excel (`t="e"`) en columna no requerida** pasa en silencio (p. ej. `CUIT` en ERP no es requerida y no se lee; en SGA todas las columnas usadas son requeridas). En columnas requeridas corta con `ValueError`.
- **Estado `SIN_ID_MP`** figura en `unidentified` pero ninguna rama lo produce. `special=[]` se declara y nunca se usa.
- **`getcontext().prec = 80`** se fija al importar el módulo (contexto global de `decimal` del proceso). En el subproceso no afecta a nadie; en tests en proceso tampoco rompe nada.
- **`COMPLETADO.txt` y `trazabilidad.sqlite`** se siguen escribiendo en `Respaldo_tecnico/` pero `reporte.py['archivos']` sólo lista el XLSX, el CSV y `Resumen.json` (decisión de catálogo, no del motor).
- **Textos de error que cambiaron** (no son estados ni motivos de la salida): "Se requiere exactamente un archivo de SGA" → "Se requiere al menos un archivo de SGA."; "hasta tres reportes ERP separados, sin superposiciones de tipos" → "un ERP unificado, reportes ERP separados por tipo o sus tramos"; se agregó "<archivo>: es un archivo de ERP y se lo indicó como SGA." y "<archivo>: no es un libro de Excel (.xlsx) o está dañado." (antes explotaba con `BadZipFile`).
- **`Resumen.json` conserva `version: "1.4"`** del legado aunque el motor ya no es ese script.

## Controles SGA (`app/reportes/controles_sga/`)

Detectado al portar `legado/controles_sga/control_sga.py` v1.5 + `excel_sga.py`. Nada de esto se corrigió: el motor
reproduce el legado tal cual (regresión real sin diferencias).

- `apply_confirmed_rules` del legado recorre `EXEMPT_CONCEPTS` como **set**: los conceptos exentos que no aparecen en
  el reporte se agregan al final de `reglas_propuestas.json` en orden de hash (cambia de proceso a proceso). El motor
  recorre la lista de parámetros en su orden, así que el JSON es determinístico; sólo se nota cuando faltan dos o más
  conceptos exentos en los datos (en el reporte real falta uno solo, por eso el byte a byte coincide).
- `default_rules` cuenta también las líneas de los **documentos excluidos** (`documentos_excluidos`) en la estadística
  por concepto: la línea `CH-…` aporta a la regla de `CHEQUE RECHAZADO` aunque después no se controle.
- En `controls` se construye `sub_concepts` (conceptos por subrecibo) y nunca se usa; hay un segundo
  `if pending(r): continue` muerto dentro del bucle principal. `REQUIRES_UNDEFINED_DATA` es un set vacío fijo (no es
  parámetro). `write_csv` quedó en `motor.py` sin uso (el legado tampoco lo llamaba).
- `ejecucion.json`: `salidas` y `solapas` cuentan los seis libros aunque `salidas_a_generar` no los escriba (el
  cálculo se hace igual; sólo se omite el archivo y la tabla).
- `ejecucion.json`: se agregó la clave `archivos` (lista de nombres de los tramos) y `archivo` pasa a ser los nombres
  unidos con ` | ` (con un tramo queda igual que el legado).
- Reglas confirmadas (`parametros['reglas']`): el motor pasa `datos` y `agrupador` tal cual (como el `--reglas` del
  legado); un `datos` fuera de las cinco opciones no se valida acá sino en la interfaz. `''`/`None` en los booleanos
  cuentan como `False`.
- `excel.consolidate_data` agrupa por `(fondo, empresa, factura, archivo, fila)`: dos líneas idénticas en tramos
  distintos nunca se funden (correcto), pero el texto `fila N` de `DetalleValidaciones` (no se exporta) no nombra el
  archivo.
- Con más de un tramo, los mensajes de error de preparación dicen `Fila N de <archivo>`; con uno solo siguen
  siendo `Fila N: …` como el legado.
- La columna `Archivo` usa ancho 30 (no existe en el legado; sólo aparece con varios tramos).
