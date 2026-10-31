"""Reconocimiento de los archivos de entrada por sus encabezados. Cada función recibe la lista que
devuelve entradas.encabezados_xlsx: [(hoja, fila, [encabezados], filas_aprox)]."""
import re
import unicodedata

from .entradas import encabezados_xlsx


def _norm(v):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(v or '')) if not unicodedata.combining(c)).strip().casefold()


def _tiene(hojas, columnas, normalizado=False):
    for _, _, enc, _ in hojas:
        presentes = {(_norm(e) if normalizado else str(e).strip()) for e in enc}
        buscadas = {(_norm(c) if normalizado else c) for c in columnas}
        if buscadas <= presentes:
            return True
    return False


COLUMNAS_HISTORICO_SGA = ['FondoDeRiesgo', 'CodigoEmpresa', 'NumeroFactura', 'Importe', 'GrupoConceptoFacturacion']
COLUMNAS_ERP_TRANSACCIONES = ['Saldo2', 'Cuenta de cliente', 'Factura', 'Tipo de transacción']
COLUMNAS_SALDO_COMPROBACION = ['MainAccount', 'BusinessUnit', 'Saldo de cierre']
COLUMNAS_CHEQUES_SGA = ['IdCheque', 'Estado']
COLUMNAS_TESORERIA_ERP = ['Id de Transacción', 'Estado', 'Pagado a']
ALIAS_LISTADO = {
    'cuit': {'cuit', 'cuitcliente', 'cuitdelcliente', 'identificacionfiscal', 'nif'},
    'numero': {'numerofactura', 'nrofactura', 'nrodefactura', 'numerodefactura', 'factura', 'comprobante', 'numerocomprobante', 'numerodecomprobante'},
}


def historico_sga(hojas):
    return _tiene(hojas, COLUMNAS_HISTORICO_SGA)


def erp_transacciones(hojas):
    return _tiene(hojas, COLUMNAS_ERP_TRANSACCIONES)


def saldo_comprobacion(hojas):
    return _tiene(hojas, COLUMNAS_SALDO_COMPROBACION, normalizado=True)


def cheques_sga(hojas):
    return _tiene(hojas, COLUMNAS_CHEQUES_SGA)


def tesoreria_erp(hojas):
    return _tiene(hojas, COLUMNAS_TESORERIA_ERP)


def _alias(valor):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode().lower())


def listado_facturas(hojas):
    # Un histórico de SGA también tiene CUIT y NumeroFactura: no es un listado.
    if historico_sga(hojas) or cheques_sga(hojas):
        return False
    for _, _, enc, _ in hojas:
        claves = {_alias(e) for e in enc}
        if claves & ALIAS_LISTADO['cuit'] and claves & ALIAS_LISTADO['numero']:
            return True
    return False


TODOS = {
    'historico_sga': historico_sga,
    'erp_transacciones': erp_transacciones,
    'saldo_comprobacion': saldo_comprobacion,
    'cheques_sga': cheques_sga,
    'tesoreria_erp': tesoreria_erp,
    'listado_facturas': listado_facturas,
}

TITULOS = {
    'historico_sga': 'Histórico de cuenta corriente (SGA)',
    'erp_transacciones': 'Transacciones del cliente (ERP)',
    'saldo_comprobacion': 'Saldo de comprobación (ERP)',
    'cheques_sga': 'Cheques (SGA)',
    'tesoreria_erp': 'Valores registrados de tesorería (ERP)',
    'listado_facturas': 'Listado de facturas (Excel con CUIT y número)',
}


def reconocer(path):
    """Tipo global del archivo (independiente del reporte). None si no se reconoce."""
    hojas = encabezados_xlsx(path)
    positivos = [t for t, fn in TODOS.items() if fn(hojas)]
    if len(positivos) > 1:
        raise ValueError('El archivo mezcla datos de dos tipos distintos (' + ' y '.join(TITULOS[p] for p in positivos) + '); usá archivos separados.')
    return positivos[0] if positivos else None
