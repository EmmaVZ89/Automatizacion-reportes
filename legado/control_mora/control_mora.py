from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime
from collections import Counter
import csv
import unicodedata
import sys

CUENTAS = {'113601', '113602', '113603', '113604', '113605'}
BASE = Path(__file__).resolve().parent

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

def archivo(entrada, prefijo):
    candidatos = [p for p in entrada.iterdir() if p.suffix.lower() == '.xlsx' and not p.name.startswith('~$') and normal(p.stem).startswith(normal(prefijo))]
    if len(candidatos) != 1:
        raise ValueError(f'Debe haber UN archivo {prefijo}*.xlsx en entrada; encontrados: {len(candidatos)}. Retirá las descargas anteriores.')
    return candidatos[0]

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

def ejecutar(entrada=None, salida=None):
    import openpyxl
    entrada = Path(entrada) if entrada else BASE / 'entrada'
    salida = Path(salida) if salida else BASE / 'salida'
    entrada.mkdir(parents=True, exist_ok=True)
    erp = archivo(entrada, 'Saldo de comprobación')
    sga = archivo(entrada, 'ReporteHistoricoDeCuentaCorriente')
    destino = salida / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    destino.mkdir(parents=True)
    total_erp = Decimal(0)
    total_sga = Decimal(0)
    cuentas = Counter()
    cantidad = 0
    print('Leyendo ERP...', flush=True)
    wb = openpyxl.load_workbook(erp, read_only=True, data_only=True)
    try:
        ws, inicio, headers, idx = hoja(wb, ['MainAccount', 'BusinessUnit', 'Saldo de cierre'])
        erp_hoja = ws.title
        f, out = escritor(destino / 'Respaldo_ERP.csv', ['ArchivoOrigen', 'HojaOrigen', 'FilaOrigen'] + headers)
        with f:
            for n, row in enumerate(ws.iter_rows(min_row=inicio+1, values_only=True), inicio+1):
                cuenta = codigo(row[idx[normal('MainAccount')]])
                if cuenta in CUENTAS and normal(row[idx[normal('BusinessUnit')]]) == 'frg':
                    total_erp += importe(row[idx[normal('Saldo de cierre')]])
                    cuentas[cuenta] += 1
                    out.writerow([erp.name, ws.title, n] + [celda(v) for v in row])
        if set(cuentas) != CUENTAS or any(v != 1 for v in cuentas.values()):
            raise ValueError(f'Faltan cuentas FRG o hay cuentas duplicadas. Cantidades: {dict(cuentas)}')
    finally:
        wb.close()
    print('Leyendo SGA completo; puede demorar varios minutos...', flush=True)
    wb = openpyxl.load_workbook(sga, read_only=True, data_only=True)
    try:
        ws, inicio, headers, idx = hoja(wb, ['GrupoConceptoFacturacion', 'FondoDeRiesgo', 'Importe'])
        sga_hoja = ws.title
        f, out = escritor(destino / 'Respaldo_SGA_Mora.csv', ['ArchivoOrigen', 'HojaOrigen', 'FilaOrigen'] + headers)
        with f:
            for n, row in enumerate(ws.iter_rows(min_row=inicio+1, values_only=True), inicio+1):
                if normal(row[idx[normal('GrupoConceptoFacturacion')]]) == 'mora' and normal(row[idx[normal('FondoDeRiesgo')]]) == 'fondo de riesgo general':
                    valor = importe(row[idx[normal('Importe')]])
                    total_sga += valor
                    valores = list(row)
                    valores[idx[normal('Importe')]] = valor
                    out.writerow([sga.name, ws.title, n] + [celda(v) for v in valores])
                    cantidad += 1
                if n % 100000 == 0:
                    print(f'  {n:,} filas revisadas...', flush=True)
        if cantidad == 0:
            raise ValueError('No se encontraron movimientos de Mora del Fondo de Riesgo General.')
    finally:
        wb.close()
    diferencia = total_erp - total_sga
    estado = 'SIN DIFERENCIAS' if diferencia.quantize(Decimal('0.01')) == 0 else 'REVISAR DIFERENCIA'
    resumen = [
        ['Estado', estado], ['Saldo ERP FRG', total_erp], ['Saldo SGA Mora FRG', total_sga],
        ['Diferencia ERP menos SGA', diferencia], ['Filas ERP', sum(cuentas.values())],
        ['Filas SGA', cantidad], ['Archivo ERP', erp.name], ['Hoja ERP', erp_hoja],
        ['Archivo SGA', sga.name], ['Hoja SGA', sga_hoja],
        ['Cuentas ERP (una vez cada una)', ', '.join(sorted(CUENTAS))],
        ['Criterio SGA', 'Suma de Importe con sus signos: facturas e imputaciones; sin filtrar fechas ni excluir saldos cancelados.'],
        ['Fecha de corte', 'La de las exportaciones. Verificar que ambos archivos correspondan al mismo corte.'],
    ]
    f, out = escritor(destino / 'Resultado_Control_Mora.csv', ['Concepto', 'Valor'])
    with f:
        out.writerows([[a, celda(b)] for a, b in resumen])
    (destino / 'PROCESO_COMPLETO.txt').write_text(f'{estado}\nERP: {total_erp:,.2f}\nSGA: {total_sga:,.2f}\nDiferencia ERP - SGA: {diferencia:,.2f}\nFilas SGA: {cantidad}\n', encoding='utf-8')
    print((destino / 'PROCESO_COMPLETO.txt').read_text(encoding='utf-8'))
    print(f'Resultados: {destino}')
    return destino

if __name__ == '__main__':
    try:
        ejecutar()
    except Exception as e:
        print(f'ERROR: {e}\nEl control no terminó. Solo es válido un resultado con PROCESO_COMPLETO.txt.', file=sys.stderr)
        sys.exit(1)
