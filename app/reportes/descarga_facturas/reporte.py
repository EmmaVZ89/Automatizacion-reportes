"""Definición del reporte Descarga de facturas (PDF desde la biblioteca de comprobantes, por listado Excel)."""
from .._comun import detectores

REPORTE = {
    'codigo': 'descarga_facturas',
    'orden': 5,
    # No es un control del cierre: tiene su sección propia (Facturas) y no aparece dentro de cada cierre.
    'ambito': 'herramienta',
    'icono': 'factura',
    'nombre': 'Descarga de facturas',
    'descripcion': 'Descarga los PDF de las facturas de un listado Excel (CUIT y número) desde la biblioteca de comprobantes y los guarda por concepto en la carpeta destino.',
    'ayuda': 'Necesita una instalación aparte (Chrome y componentes de lectura de PDF). Durante la ejecución hay que iniciar sesión en Chrome y después apretar Continuar.',
    'requiere': 'venv_facturas',
    'pausas': ['login'],
    'entradas': [
        {'clave': 'listado', 'titulo': 'Listado de facturas (Excel con CUIT y número)', 'tipo': 'listado_facturas', 'detectar': detectores.listado_facturas,
         'minimo': 1, 'maximo': 10, 'ayuda': 'Uno o más Excel. Las columnas CUIT y NumeroFactura pueden tener otros nombres parecidos y estar en cualquier posición.'},
    ],
    'parametros': [
        {'clave': 'origen', 'titulo': 'Dirección de SharePoint de la organización', 'tipo': 'texto', 'obligatorio': True,
         'ayuda': 'Por ejemplo https://organizacion.sharepoint.com (sin nada después). Se guarda para la próxima vez.'},
        {'clave': 'sitio', 'titulo': 'Ruta del sitio', 'tipo': 'texto', 'obligatorio': True, 'default': '/sites/DynamicsERP',
         'ayuda': 'La parte de la dirección después del dominio hasta el nombre del sitio.'},
        {'clave': 'biblioteca', 'titulo': 'Ruta de la biblioteca Comprobantes', 'tipo': 'texto', 'obligatorio': True, 'default': '/sites/DynamicsERP/GTZ/Comprobantes',
         'ayuda': 'Dentro de la biblioteca cada factura está en la carpeta de su CUIT: <biblioteca>/<CUIT>/<número>.pdf.'},
        {'clave': 'destino', 'titulo': 'Carpeta destino en esta PC', 'tipo': 'ruta', 'obligatorio': True,
         'ayuda': 'Carpeta existente (por ejemplo la sincronizada con OneDrive). Se crea una carpeta por concepto, con las facturas de todos los meses.'},
        {'clave': 'desde', 'titulo': 'Emisión desde', 'tipo': 'fecha', 'no_persistir': True, 'ayuda': 'Opcional. Se compara con la fecha de emisión leída dentro del PDF.'},
        {'clave': 'hasta', 'titulo': 'Emisión hasta', 'tipo': 'fecha', 'no_persistir': True, 'ayuda': 'Opcional.'},
        {'clave': 'concepto', 'titulo': 'Concepto a buscar', 'tipo': 'texto', 'no_persistir': True, 'ayuda': 'Opcional. Vacío = todos los conceptos.'},
    ],
    'salidas': [
        {'tabla': 'descarga', 'titulo': 'Resultado de la descarga', 'archivo': 'descarga.csv', 'clave': ['CUIT', 'Factura'], 'principal': True},
        {'tabla': 'entrada_a_revisar', 'titulo': 'Filas del listado a revisar', 'archivo': 'entrada_a_revisar.csv', 'clave': ['Archivo', 'Hoja', 'Fila']},
    ],
    'archivos': ['descarga.csv', 'entrada_a_revisar.csv'],
}
