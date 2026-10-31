"""Definición del reporte Controles SGA (seis controles internos sobre el histórico de cuenta corriente)."""
from .._comun import detectores

CONCEPTOS_EXENTOS = [
    'VENTA BIENES DE USO', 'VENTA DE BIENES DE USO', 'PUBLICIDAD GRAFICA',
    'DEVOLUCION DE COBRANZA', 'CHEQUE A CANJEAR - FRG',
    'COMISION POR CUENTA DE TERCEROS', 'DEVOLUCION A LOS FONDOS ESPECIFICOS',
    'DIFERENCIA DE CAMBIO', 'GASTOS DE ESTUDIO', 'GASTOS ESCRIBANIA',
    'IMPORTES A RECUPERAR CON IVA', 'OTROS INGRESOS', 'REINTEGRO DE GASTOS',
    'RESCATE AVAL POR CGTIA', 'SINIESTROS A COBRAR', 'DEUDAS DIVERSAS',
    'SERVICIOS ADMINISTRATIVOS', 'CHEQUE RECHAZADO',
]
CONCEPTOS_CON_APORTE = ['SERV. ADMINIST. FRG - 1º', 'SERV. ADMINIST. FRG - 2º', 'DEUDA POR APORTE VENCIDO GTZ']
IMPUTACION_CONDICIONAL = [
    {'concepto': 'COMISION POR CUENTA DE TERCEROS', 'agrupador': 'COMISIONES'},
    {'concepto': 'INCOBRABLES PARTICIPES - GTZ', 'agrupador': 'COMISIONES'},
    {'concepto': 'INCOBRABLES PARTICIPES - FRG', 'agrupador': 'MORA'},
    {'concepto': 'INCOBRABLES QUITA', 'agrupador': 'MORA'},
]
SALIDAS = [
    {'tabla': 'netos_mora', 'libro': 'Control_Netos_Impuestos', 'hoja': 'MORA', 'titulo': 'Netos e impuestos · MORA'},
    {'tabla': 'netos_mes', 'libro': 'Control_Netos_Impuestos', 'hoja': 'Mes en curso', 'titulo': 'Netos e impuestos · Mes en curso'},
    {'tabla': 'netos_historico', 'libro': 'Control_Netos_Impuestos', 'hoja': 'Histórico', 'titulo': 'Netos e impuestos · Histórico'},
    {'tabla': 'datos_anio', 'libro': 'Control_Datos_Obligatorios', 'hoja': 'Año en curso', 'titulo': 'Datos obligatorios · Año en curso'},
    {'tabla': 'datos_historico', 'libro': 'Control_Datos_Obligatorios', 'hoja': 'Histórico', 'titulo': 'Datos obligatorios · Histórico'},
    {'tabla': 'agrupador_anio', 'libro': 'Control_Concepto_Agrupador', 'hoja': 'Año en curso', 'titulo': 'Concepto y agrupador · Año en curso'},
    {'tabla': 'agrupador_historico', 'libro': 'Control_Concepto_Agrupador', 'hoja': 'Histórico', 'titulo': 'Concepto y agrupador · Histórico'},
    {'tabla': 'servicios_anio', 'libro': 'Control_Servicios_Administrativos', 'hoja': 'Año en curso', 'titulo': 'Servicios administrativos · Año en curso'},
    {'tabla': 'servicios_historico', 'libro': 'Control_Servicios_Administrativos', 'hoja': 'Histórico', 'titulo': 'Servicios administrativos · Histórico'},
    {'tabla': 'abiertos', 'libro': 'Comprobantes_Abiertos', 'hoja': 'Comprobantes abiertos', 'titulo': 'Comprobantes abiertos'},
    {'tabla': 'saldo_mora', 'libro': 'Saldo_MORA', 'hoja': 'Saldo por fondo', 'titulo': 'Saldo MORA'},
]
CLAVES = {
    'netos': ['FondoDeRiesgo', 'CodigoEmpresa', 'NumeroFactura', 'NumeroComprobanteImputacion', 'Fila SGA'],
    'datos': ['FondoDeRiesgo', 'CodigoEmpresa', 'NumeroFactura', 'NumeroComprobanteImputacion', 'Control'],
    'agrupador': ['FondoDeRiesgo', 'CodigoEmpresa', 'NumeroFactura', 'NumeroComprobanteImputacion', 'Control'],
    'servicios': ['FondoDeRiesgo', 'CodigoEmpresa', 'NumeroDeAporte', 'Control'],
    'abiertos': ['FondoDeRiesgo', 'CodigoEmpresa', 'Comprobante'],
    'saldo': ['FondoDeRiesgo'],
}
LIBROS = ['Control_Netos_Impuestos', 'Control_Datos_Obligatorios', 'Control_Servicios_Administrativos', 'Saldo_MORA', 'Comprobantes_Abiertos', 'Control_Concepto_Agrupador']

for s in SALIDAS:
    s['archivo'] = s['libro'] + '.xlsx'
    s['clave'] = CLAVES[s['tabla'].split('_')[0]]
    if s['tabla'] == 'saldo_mora':
        s['revisable'] = False  # dos filas de saldo por fondo: información, no se revisa fila por fila

REPORTE = {
    'codigo': 'controles_sga',
    'ambito': 'cierre',
    'icono': 'lista',
    'orden': 2,
    'nombre': 'Controles SGA',
    'descripcion': 'Seis controles internos sobre el histórico de cuenta corriente de SGA: netos e impuestos, datos obligatorios, servicios administrativos, saldo MORA, comprobantes abiertos y concepto/agrupador.',
    'ayuda': 'Necesita el reporte histórico completo de SGA (todos los tramos si vino cortado). La primera corrida propone reglas por concepto; podés confirmarlas y volver a correr.',
    'requiere': 'stdlib',
    'pausas': [],
    'entradas': [
        {'clave': 'sga', 'titulo': 'Histórico de cuenta corriente (SGA)', 'tipo': 'historico_sga', 'detectar': detectores.historico_sga,
         'minimo': 1, 'maximo': 6, 'ayuda': 'El reporte completo descargado de SGA. Si vino cortado, agregá todos los tramos.'},
    ],
    'parametros': [
        {'clave': 'corte', 'titulo': 'Fecha de corte', 'tipo': 'fecha', 'obligatorio': True, 'default_cierre': 'corte', 'no_persistir': True,
         'ayuda': 'Define el año y mes en curso, la exigibilidad del segundo servicio y las anulaciones.'},
        {'clave': 'salidas_a_generar', 'titulo': 'Controles a generar', 'tipo': 'lista', 'default': list(LIBROS),
         'opciones': [{'valor': l, 'titulo': l.replace('_', ' ')} for l in LIBROS], 'ayuda': 'Desmarcá los que no necesites este mes.'},
        {'clave': 'inicio_regla_mensual', 'titulo': 'Desde cuándo el segundo servicio debe ir en el mes exacto', 'tipo': 'fecha', 'default': '2026-10-01',
         'ayuda': 'Antes de esta fecha, un segundo servicio desfasado se acepta como histórico.'},
        {'clave': 'documentos_excluidos', 'titulo': 'Comprobantes excluidos de todos los controles', 'tipo': 'lista', 'default': ['CH-20190722105522839'],
         'ayuda': 'Números exactos de comprobante que no se controlan.'},
        {'clave': 'conceptos_exentos', 'titulo': 'Conceptos exentos de datos obligatorios', 'tipo': 'lista', 'default': list(CONCEPTOS_EXENTOS),
         'ayuda': 'Además, todo concepto que empiece con "ACCIONES " queda exento.'},
        {'clave': 'conceptos_con_aporte', 'titulo': 'Conceptos que exigen número de aporte', 'tipo': 'lista', 'default': list(CONCEPTOS_CON_APORTE)},
        {'clave': 'imputacion_condicional', 'titulo': 'Conceptos de imputación válidos sólo para un agrupador', 'tipo': 'tabla', 'default': list(IMPUTACION_CONDICIONAL),
         'columnas': [{'clave': 'concepto', 'titulo': 'Concepto de imputación', 'tipo': 'texto'}, {'clave': 'agrupador', 'titulo': 'Agrupador de la factura', 'tipo': 'texto'}]},
        {'clave': 'imputacion_distinta_permitida', 'titulo': 'Conceptos de imputación distintos permitidos', 'tipo': 'lista', 'default': ['DEUDA POR APORTE NO VIGENTE - RDO. EJ.']},
        {'clave': 'facturas_oficiales', 'titulo': 'Prefijos de facturas oficiales (fuera de comprobantes abiertos)', 'tipo': 'lista', 'default': ['FC-A', 'FC-B', 'FE-A'],
         'ayuda': 'Además se excluye toda la serie Y.'},
        {'clave': 'tolerancia', 'titulo': 'Margen de redondeo por línea ($)', 'tipo': 'decimal', 'default': '0.02'},
        {'clave': 'reglas', 'titulo': 'Reglas confirmadas por concepto', 'tipo': 'tabla', 'default': [],
         'columnas': [{'clave': 'concepto', 'titulo': 'Concepto', 'tipo': 'texto'},
                      {'clave': 'datos', 'titulo': 'Datos exigidos', 'tipo': 'opcion', 'opciones': ['APORTE', 'EXP_OP', 'EXENTO', 'SIN_DEFINIR', 'REQUIERE_DATO_SIN_DEFINIR']},
                      {'clave': 'datos_confirmados', 'titulo': 'Datos confirmados', 'tipo': 'booleano'},
                      {'clave': 'agrupador', 'titulo': 'Agrupador esperado', 'tipo': 'texto'},
                      {'clave': 'agrupador_confirmado', 'titulo': 'Agrupador confirmado', 'tipo': 'booleano'}],
         'ayuda': 'Vacío: se usa la propuesta estadística del reporte. Después de la primera corrida podés confirmar las reglas propuestas acá.'},
    ],
    'salidas': SALIDAS,
    'archivos': [l + '.xlsx' for l in LIBROS] + ['reglas_propuestas.json', 'ejecucion.json'],
}
