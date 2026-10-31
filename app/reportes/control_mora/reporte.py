"""Definición del reporte Control de Mora (saldo de cuentas de mora en ERP contra agrupador MORA en SGA)."""
from .._comun import detectores

REPORTE = {
    'codigo': 'control_mora',
    'ambito': 'cierre',
    'icono': 'reloj',
    'orden': 3,
    'nombre': 'Control de Mora',
    'descripcion': 'Compara el saldo de las cuentas de mora del Fondo de Riesgo General en ERP con la suma de los movimientos del agrupador MORA en SGA.',
    'ayuda': 'Necesita el Saldo de comprobación de ERP y el histórico de cuenta corriente de SGA, descargados al mismo corte.',
    'requiere': 'stdlib',
    'pausas': [],
    'entradas': [
        {'clave': 'erp', 'titulo': 'Saldo de comprobación (ERP)', 'tipo': 'saldo_comprobacion', 'detectar': detectores.saldo_comprobacion, 'minimo': 1, 'maximo': 3},
        {'clave': 'sga', 'titulo': 'Histórico de cuenta corriente (SGA)', 'tipo': 'historico_sga', 'detectar': detectores.historico_sga, 'minimo': 1, 'maximo': 6,
         'ayuda': 'El reporte completo descargado de SGA. Si vino cortado, agregá todos los tramos.'},
    ],
    'parametros': [
        {'clave': 'cuentas', 'titulo': 'Cuentas de mora en ERP', 'tipo': 'lista', 'default': ['113601', '113602', '113603', '113604', '113605'],
         'ayuda': 'Cada cuenta tiene que aparecer exactamente una vez en el saldo de comprobación.'},
        {'clave': 'unidad_negocio', 'titulo': 'Unidad de negocio (BusinessUnit)', 'tipo': 'texto', 'default': 'FRG', 'obligatorio': True},
        {'clave': 'fondo', 'titulo': 'Fondo de riesgo en SGA', 'tipo': 'texto', 'default': 'Fondo de Riesgo General', 'obligatorio': True},
        {'clave': 'grupo', 'titulo': 'Agrupador de SGA', 'tipo': 'texto', 'default': 'Mora', 'obligatorio': True},
    ],
    'salidas': [
        {'tabla': 'resultado', 'titulo': 'Resultado', 'archivo': 'Resultado_Control_Mora.csv', 'clave': ['Concepto'], 'revisable': False, 'principal': True},
        {'tabla': 'respaldo_erp', 'titulo': 'Respaldo ERP (cuentas de mora)', 'archivo': 'Respaldo_ERP.csv', 'clave': ['ArchivoOrigen', 'HojaOrigen', 'FilaOrigen'], 'revisable': False},
        {'tabla': 'respaldo_sga', 'titulo': 'Respaldo SGA (líneas de MORA)', 'archivo': 'Respaldo_SGA_Mora.csv', 'clave': ['ArchivoOrigen', 'HojaOrigen', 'FilaOrigen'], 'revisable': False},
    ],
    'archivos': ['Resultado_Control_Mora.csv', 'Respaldo_ERP.csv', 'Respaldo_SGA_Mora.csv', 'PROCESO_COMPLETO.txt'],
}
