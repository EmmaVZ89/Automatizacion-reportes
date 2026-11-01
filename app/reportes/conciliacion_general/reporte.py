"""Definición del reporte Conciliación general (SGA contra ERP, Fondo de Riesgo General)."""
from .._comun import detectores
from .._comun.detectores import FONDO_GENERAL, FONDO_SANTA_FE

REPORTE = {
    # Una conciliación por fondo de riesgo (pedido del 01/11/2026): cada fondo con sus versiones y su resultado final.
    'variantes': {'parametro': 'fondo', 'opciones': [{'valor': FONDO_GENERAL, 'titulo': 'Fondo de Riesgo General', 'corto': 'Fondo General'},
                                                    {'valor': FONDO_SANTA_FE, 'titulo': 'FERF Prov. Santa Fe', 'corto': 'FERF Santa Fe'}]},
    'codigo': 'conciliacion_general',
    'ambito': 'cierre',
    'icono': 'balanza',
    'orden': 1,
    'nombre': 'Conciliación general',
    'descripcion': 'Compara los saldos por comprobante del histórico de cuenta corriente de SGA con las transacciones del cliente de ERP, del Fondo de Riesgo General o de FERF Prov. Santa Fe (cada fondo con su propia conciliación).',
    'ayuda': 'Necesita el histórico completo de SGA y el reporte de transacciones de ERP (uno unificado o hasta tres separados por tipo: Cliente, Pago y Diario general). Si un reporte vino cortado en dos archivos, agregá los dos.',
    'requiere': 'stdlib',
    'pausas': [],
    'entradas': [
        {'clave': 'sga', 'titulo': 'Histórico de cuenta corriente (SGA)', 'tipo': 'historico_sga', 'detectar': detectores.historico_sga,
         'minimo': 1, 'maximo': 6, 'ayuda': 'El reporte completo descargado de SGA, el mismo para los dos fondos: se toman sólo las filas del fondo de la corrida. Si vino cortado, agregá todos los tramos.'},
        {'clave': 'erp', 'titulo': 'Transacciones del cliente (ERP)', 'tipo': 'erp_transacciones', 'detectar': detectores.erp_transacciones,
         'minimo': 1, 'maximo': 6, 'ayuda': 'Las del fondo que vas a conciliar: un archivo unificado, o separados por tipo de transacción (Cliente, Pago, Diario general y, en FERF Prov. Santa Fe, Liquidación), más sus tramos si vinieron cortados.'},
    ],
    'parametros': [
        {'clave': 'alcance', 'titulo': 'Alcance del reporte ERP', 'tipo': 'opcion', 'obligatorio': True, 'no_persistir': True,
         'opciones': [{'valor': 'abiertos', 'titulo': 'Sólo saldos abiertos'}, {'valor': 'completo', 'titulo': 'Reporte completo'}],
         'ayuda': 'Según cómo descargaste el ERP. Con "sólo saldos abiertos", un comprobante de SGA que no figura en el ERP se compara contra saldo cero.'},
        {'clave': 'corte', 'titulo': 'Fecha de corte', 'tipo': 'fecha', 'default_cierre': 'corte', 'no_persistir': True,
         'ayuda': 'Se declara en el resumen; no filtra ni reconstruye saldos a esa fecha.'},
        {'clave': 'fondo', 'titulo': 'Fondo de riesgo', 'tipo': 'opcion', 'desplegable': True, 'default': FONDO_GENERAL, 'obligatorio': True,
         'no_persistir': True, 'opciones': [{'valor': FONDO_GENERAL, 'titulo': 'Fondo de Riesgo General'}, {'valor': FONDO_SANTA_FE, 'titulo': 'FERF Prov. Santa Fe'}],
         'ayuda': 'Se toman sólo las filas de SGA de este fondo. El ERP tiene que ser el de ese mismo fondo.'},
    ],
    'salidas': [
        {'tabla': 'resumen', 'titulo': 'Resumen', 'archivo': 'Conciliacion_general.xlsx', 'hoja': 'Resumen', 'clave': ['Control'], 'revisable': False},
        {'tabla': 'general', 'titulo': 'Conciliación general', 'archivo': 'Conciliacion_general.xlsx', 'hoja': 'Conciliación general', 'principal': True,
         'clave': ['Tipo', 'Cliente', 'Comprobante'], 'revision_en_libro': {'estado': 'Estado revision', 'obs': 'Observaciones'},
         # Las filas que coinciden se ven y se pueden marcar, pero no cuentan como pendientes de revisar.
         'revisar': {'columna': 'Resultado', 'salvo': ['COINCIDE']},
         # Vista por defecto de la grilla: Resultado al lado de la revisión; las columnas técnicas, ocultas.
         'vista': {'primero': ['Resultado'], 'ocultas': ['Filas SGA', 'Filas ERP', 'Origen SGA (primeras 5)', 'Origen ERP (primeras 5)', 'Estado revision', 'Fondo']},
         # Cada fila puede bajar un Excel con sus filas de origen de SGA y ERP (ver origen.py).
         'origen': True},
    ],
    'archivos': ['Conciliacion_general.xlsx', 'Respaldo_tecnico/Conciliacion_general.csv', 'Respaldo_tecnico/Resumen.json'],
}
