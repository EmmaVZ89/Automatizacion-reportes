"""Motor del Control de Mora: el script original (legado/control_mora/control_mora.py) con los cambios
mínimos del patrón de la herramienta: sin rutas propias, sin detección por prefijo de nombre, constantes
tomadas de los parámetros, entradas en uno o más tramos y avisos por `informar`. El cálculo, el orden
de las filas y el formato de las salidas no cambian."""
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime
from collections import Counter
from zipfile import BadZipFile
import csv
import unicodedata

from .._comun import protocolo

ARCHIVOS = {
    'resultado': 'Resultado_Control_Mora.csv',
    'respaldo_erp': 'Respaldo_ERP.csv',
    'respaldo_sga': 'Respaldo_SGA_Mora.csv',
    'proceso': 'PROCESO_COMPLETO.txt',
}
DEFAULTS = {
    'cuentas': ['113601', '113602', '113603', '113604', '113605'],
    'unidad_negocio': 'FRG',
    'fondo': 'Fondo de Riesgo General',
    'grupo': 'Mora',
}


def normal(v):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(v or '')) if not unicodedata.combining(c)).strip().casefold()


def importe(v):
    if v is None or str(v).strip() == '':
        raise ValueError('Importe vacío: no se puede dar por cero.')
    try:
        n = Decimal(str(v).strip())
        if not n.is_finite():
            raise ValueError('Importe no finito')
        return n
    except InvalidOperation:
        raise ValueError(f'Importe no numérico: {v!r}')


def codigo(v):
    return str(v).strip().removesuffix('.0')


def hoja(wb, obligatorias):
    encontradas = []
    for ws in wb:
        for n, row in enumerate(ws.iter_rows(max_row=20, values_only=True), 1):
            indices = {normal(v): i for i, v in enumerate(row) if v is not None}
            if all(normal(c) in indices for c in obligatorias):
                encontradas.append((ws, n, list(row), indices))
                break
    if len(encontradas) != 1:
        raise ValueError(f'Se esperaba una sola hoja con columnas {obligatorias}; encontradas: {len(encontradas)}.')
    return encontradas[0]


def escritor(path, headers):
    f = path.open('w', newline='', encoding='utf-8-sig')
    w = csv.writer(f, delimiter=';')
    w.writerow(headers)
    return f, w


def celda(v):
    if isinstance(v, (int, float, Decimal)):
        return str(v).replace('.', ',')
    if isinstance(v, datetime):
        return v.isoformat(sep=' ')
    s = '' if v is None else str(v)
    # Conservar texto como texto al abrir CSV en Excel.
    return "'" + s if s.startswith(('=', '+', '@')) else s


def _tramos(rutas, nombres):
    """[(ruta, nombre original)] de una entrada; el nombre original es el que llevan las salidas."""
    nombres = nombres or {}
    return [(Path(r), nombres.get(str(r)) or Path(r).name) for r in rutas]


def _abrir(ruta, nombre):
    import openpyxl
    from openpyxl.utils.exceptions import InvalidFileException
    try:
        return openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError, OSError) as e:
        raise ValueError(f'No se pudo leer {nombre}: no es un libro de Excel (.xlsx) o está dañado.') from e


def ejecutar(erp, sga, salida, parametros=None, informar=protocolo, nombres=None):
    """erp, sga: rutas de los tramos de cada entrada, ya ordenadas. salida: carpeta donde van los
    cuatro archivos (sin subcarpeta). nombres: {ruta: nombre original} cuando el archivo está
    guardado con otro nombre. Devuelve el resumen (totales como texto)."""
    parametros = {**DEFAULTS, **(parametros or {})}
    CUENTAS = {codigo(c) for c in parametros['cuentas'] if str(c).strip()}
    if not CUENTAS:
        raise ValueError('Hay que indicar al menos una cuenta de mora en ERP.')
    unidad = normal(parametros['unidad_negocio'])
    fondo = normal(parametros['fondo'])
    grupo = normal(parametros['grupo'])
    erp = _tramos(erp, nombres)
    sga = _tramos(sga, nombres)
    if not erp or not sga:
        raise ValueError('Faltan archivos: hace falta el Saldo de comprobación de ERP y el histórico de cuenta corriente de SGA.')
    destino = Path(salida)
    destino.mkdir(parents=True, exist_ok=True)
    total_erp = Decimal(0)
    total_sga = Decimal(0)
    cuentas = Counter()
    cantidad = 0
    erp_hojas = []
    sga_hojas = []
    informar.paso('Leyendo ERP...')
    primero = True
    for ruta, nombre in erp:
        wb = _abrir(ruta, nombre)
        try:
            ws, inicio, headers, idx = hoja(wb, ['MainAccount', 'BusinessUnit', 'Saldo de cierre'])
            erp_hojas.append(ws.title)
            if primero:
                f, out = escritor(destino / ARCHIVOS['respaldo_erp'], ['ArchivoOrigen', 'HojaOrigen', 'FilaOrigen'] + headers)
                primero = False
            else:
                f = (destino / ARCHIVOS['respaldo_erp']).open('a', newline='', encoding='utf-8')
                out = csv.writer(f, delimiter=';')
            with f:
                for n, row in enumerate(ws.iter_rows(min_row=inicio + 1, values_only=True), inicio + 1):
                    cuenta = codigo(row[idx[normal('MainAccount')]])
                    if cuenta in CUENTAS and normal(row[idx[normal('BusinessUnit')]]) == unidad:
                        total_erp += importe(row[idx[normal('Saldo de cierre')]])
                        cuentas[cuenta] += 1
                        out.writerow([nombre, ws.title, n] + [celda(v) for v in row])
        finally:
            wb.close()
    if set(cuentas) != CUENTAS or any(v != 1 for v in cuentas.values()):
        raise ValueError(f'Faltan cuentas FRG o hay cuentas duplicadas. Cantidades: {dict(cuentas)}')
    informar.paso('Leyendo SGA completo; puede demorar varios minutos...')
    primero = True
    for ruta, nombre in sga:
        wb = _abrir(ruta, nombre)
        try:
            ws, inicio, headers, idx = hoja(wb, ['GrupoConceptoFacturacion', 'FondoDeRiesgo', 'Importe'])
            sga_hojas.append(ws.title)
            if primero:
                f, out = escritor(destino / ARCHIVOS['respaldo_sga'], ['ArchivoOrigen', 'HojaOrigen', 'FilaOrigen'] + headers)
                primero = False
            else:
                f = (destino / ARCHIVOS['respaldo_sga']).open('a', newline='', encoding='utf-8')
                out = csv.writer(f, delimiter=';')
            with f:
                for n, row in enumerate(ws.iter_rows(min_row=inicio + 1, values_only=True), inicio + 1):
                    if normal(row[idx[normal('GrupoConceptoFacturacion')]]) == grupo and normal(row[idx[normal('FondoDeRiesgo')]]) == fondo:
                        valor = importe(row[idx[normal('Importe')]])
                        total_sga += valor
                        valores = list(row)
                        valores[idx[normal('Importe')]] = valor
                        out.writerow([nombre, ws.title, n] + [celda(v) for v in valores])
                        cantidad += 1
                    if n % 100000 == 0:
                        informar.log(f'  {n:,} filas revisadas...')
        finally:
            wb.close()
    if cantidad == 0:
        raise ValueError('No se encontraron movimientos de Mora del Fondo de Riesgo General.')
    diferencia = total_erp - total_sga
    estado = 'SIN DIFERENCIAS' if diferencia.quantize(Decimal('0.01')) == 0 else 'REVISAR DIFERENCIA'
    archivo_erp = ', '.join(nombre for _, nombre in erp)
    archivo_sga = ', '.join(nombre for _, nombre in sga)
    erp_hoja = ', '.join(dict.fromkeys(erp_hojas))
    sga_hoja = ', '.join(dict.fromkeys(sga_hojas))
    resumen = [
        ['Estado', estado], ['Saldo ERP FRG', total_erp], ['Saldo SGA Mora FRG', total_sga],
        ['Diferencia ERP menos SGA', diferencia], ['Filas ERP', sum(cuentas.values())],
        ['Filas SGA', cantidad], ['Archivo ERP', archivo_erp], ['Hoja ERP', erp_hoja],
        ['Archivo SGA', archivo_sga], ['Hoja SGA', sga_hoja],
        ['Cuentas ERP (una vez cada una)', ', '.join(sorted(CUENTAS))],
        ['Criterio SGA', 'Suma de Importe con sus signos: facturas e imputaciones; sin filtrar fechas ni excluir saldos cancelados.'],
        ['Fecha de corte', 'La de las exportaciones. Verificar que ambos archivos correspondan al mismo corte.'],
    ]
    f, out = escritor(destino / ARCHIVOS['resultado'], ['Concepto', 'Valor'])
    with f:
        out.writerows([[a, celda(b)] for a, b in resumen])
    proceso = f'{estado}\nERP: {total_erp:,.2f}\nSGA: {total_sga:,.2f}\nDiferencia ERP - SGA: {diferencia:,.2f}\nFilas SGA: {cantidad}\n'
    (destino / ARCHIVOS['proceso']).write_text(proceso, encoding='utf-8')
    informar.log(proceso)
    return {
        'estado': estado,
        'saldo_erp': str(total_erp),
        'saldo_sga': str(total_sga),
        'diferencia': str(diferencia),
        'filas_erp': sum(cuentas.values()),
        'filas_sga': cantidad,
        'archivos_erp': [nombre for _, nombre in erp],
        'hojas_erp': erp_hojas,
        'archivos_sga': [nombre for _, nombre in sga],
        'hojas_sga': sga_hojas,
        'cuentas': sorted(CUENTAS),
        'proceso_completo': proceso,
        'salidas': list(ARCHIVOS.values()),
    }
