"""Definición del reporte Conciliación general (SGA contra ERP, Fondo de Riesgo General)."""
from .._comun import detectores

REPORTE = {
    'codigo': 'conciliacion_general',
    'ambito': 'cierre',
    'icono': 'balanza',
    'orden': 1,
    'nombre': 'Conciliación general',
    'descripcion': 'Compara los saldos por comprobante del histórico de cuenta corriente de SGA con las transacciones del cliente de ERP, para el Fondo de Riesgo General.',
    'ayuda': 'Necesita el histórico completo de SGA y el reporte de transacciones de ERP (uno unificado o hasta tres separados por tipo: Cliente, Pago y Diario general). Si un reporte vino cortado en dos archivos, agregá los dos.',
    'requiere': 'stdlib',
    'pausas': [],
    'entradas': [
        {'clave': 'sga', 'titulo': 'Histórico de cuenta corriente (SGA)', 'tipo': 'historico_sga', 'detectar': detectores.historico_sga,
         'minimo': 1, 'maximo': 6, 'ayuda': 'El reporte completo descargado de SGA. Si vino cortado, agregá todos los tramos.'},
        {'clave': 'erp', 'titulo': 'Transacciones del cliente (ERP)', 'tipo': 'erp_transacciones', 'detectar': detectores.erp_transacciones,
         'minimo': 1, 'maximo': 6, 'ayuda': 'Un archivo unificado, o hasta tres separados por tipo de transacción (Cliente, Pago, Diario general), más sus tramos si vinieron cortados.'},
    ],
    'parametros': [
        {'clave': 'alcance', 'titulo': 'Alcance del reporte ERP', 'tipo': 'opcion', 'obligatorio': True, 'no_persistir': True,
         'opciones': [{'valor': 'abiertos', 'titulo': 'Sólo saldos abiertos'}, {'valor': 'completo', 'titulo': 'Reporte completo'}],
         'ayuda': 'Según cómo descargaste el ERP. Con "sólo saldos abiertos", un comprobante de SGA que no figura en el ERP se compara contra saldo cero.'},
        {'clave': 'corte', 'titulo': 'Fecha de corte', 'tipo': 'fecha', 'default_cierre': 'corte', 'no_persistir': True,
         'ayuda': 'Se declara en el resumen; no filtra ni reconstruye saldos a esa fecha.'},
        {'clave': 'fondo', 'titulo': 'Fondo de riesgo', 'tipo': 'texto', 'default': 'Fondo de Riesgo General', 'obligatorio': True,
         'ayuda': 'Sólo se toman las filas de SGA de este fondo.'},
    ],
    'salidas': [
        {'tabla': 'resumen', 'titulo': 'Resumen', 'archivo': 'Conciliacion_general.xlsx', 'hoja': 'Resumen', 'clave': ['Control'], 'revisable': False},
        {'tabla': 'general', 'titulo': 'Conciliación general', 'archivo': 'Conciliacion_general.xlsx', 'hoja': 'Conciliación general', 'principal': True,
         'clave': ['Tipo', 'Cliente', 'Comprobante'], 'revision_en_libro': {'estado': 'Estado revision', 'obs': 'Observaciones'}},
    ],
    'archivos': ['Conciliacion_general.xlsx', 'Respaldo_tecnico/Conciliacion_general.csv', 'Respaldo_tecnico/Resumen.json'],
}
