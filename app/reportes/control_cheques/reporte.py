"""Definición del reporte Control de cheques (estados de cheques SGA contra ERP)."""
from .._comun import detectores

REPORTE = {
    'codigo': 'control_cheques',
    'ambito': 'cierre',
    'icono': 'cheque',
    'orden': 4,
    'nombre': 'Control de cheques',
    'descripcion': 'Compara el estado de cada cheque de SGA con el registrado en los valores de tesorería de ERP, que es la referencia, y lista los casos a revisar.',
    'ayuda': 'Necesita el Excel de cheques de SGA y el de Valores registrados de tesorería de ERP.',
    'requiere': 'stdlib',
    'pausas': [],
    'entradas': [
        {'clave': 'sga', 'titulo': 'Cheques (SGA)', 'tipo': 'cheques_sga', 'detectar': detectores.cheques_sga, 'minimo': 1, 'maximo': 3},
        {'clave': 'erp', 'titulo': 'Valores registrados de tesorería (ERP)', 'tipo': 'tesoreria_erp', 'detectar': detectores.tesoreria_erp, 'minimo': 1, 'maximo': 3},
    ],
    'parametros': [
        {'clave': 'prefijos_historicos', 'titulo': 'Prefijos de ID históricos válidos (sin cruce con ERP)', 'tipo': 'lista', 'default': ['563']},
        {'clave': 'prefijo_sga', 'titulo': 'Prefijo del ID en SGA', 'tipo': 'texto', 'default': '10000', 'obligatorio': True},
        {'clave': 'prefijo_erp', 'titulo': 'Prefijo equivalente en ERP', 'tipo': 'texto', 'default': 'gtz-', 'obligatorio': True,
         'ayuda': 'El ID de SGA que empieza con el prefijo SGA se compara con el de ERP reemplazándolo por este.'},
        {'clave': 'equivalencias', 'titulo': 'Equivalencias de estado (ERP → SGA)', 'tipo': 'tabla',
         'default': [{'erp': 'rechazado', 'sga': 'rechazado'}, {'erp': 'depositado', 'sga': 'depositado'}, {'erp': 'en cartera', 'sga': 'acreditado'}],
         'columnas': [{'clave': 'erp', 'titulo': 'Estado en ERP', 'tipo': 'texto'}, {'clave': 'sga', 'titulo': 'Estado esperado en SGA', 'tipo': 'texto'}]},
        {'clave': 'estados_proveedores', 'titulo': 'Estados de ERP que se excluyen (pago a proveedores)', 'tipo': 'lista', 'default': ['debitado', 'entregado'],
         'ayuda': 'También se excluye todo cheque con "Pagado a" informado.'},
        {'clave': 'estados_validos', 'titulo': 'Estados de ERP válidos sin comparar', 'tipo': 'lista', 'default': ['canjeado']},
    ],
    'salidas': [
        {'tabla': 'revisar', 'titulo': 'Cheques para revisar', 'archivo': 'Cheques_para_revisar.csv', 'clave': ['ID SGA', 'Motivo'], 'principal': True},
        {'tabla': 'resumen', 'titulo': 'Resumen', 'archivo': 'Resumen.txt', 'clave': ['Concepto'], 'revisable': False},
    ],
    'archivos': ['Cheques_para_revisar.csv', 'Resumen.txt'],
}
