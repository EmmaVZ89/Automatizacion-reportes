"""Copia textual de `normalize`, `columns`, `parse_pair` y `load_inputs` de
`legado/descarga_facturas/listado.py` (v6). Es el dorado contra el que se compara
`motor.cargar_listados`; no importar el legado directo porque arrastra `facturas.py` (pdfplumber)."""
import re
import unicodedata
from contextlib import closing

import openpyxl

ALIASES = {
    'cuit': {'cuit', 'cuitcliente', 'cuitdelcliente', 'identificacionfiscal', 'nif'},
    'numero': {'numerofactura', 'nrofactura', 'nrodefactura', 'numerodefactura', 'factura', 'comprobante', 'numerocomprobante', 'numerodecomprobante'},
}


def normalize(value):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().lower())


def columns(row):
    result = {}
    for key, aliases in ALIASES.items():
        matches = [i for i, value in enumerate(row) if normalize(value) in aliases]
        if len(matches) > 1:
            raise ValueError('Hay varias columnas posibles para ' + key + '; dejá un solo encabezado inequívoco.')
        if matches:
            result[key] = matches[0]
    return result if len(result) == 2 else None


def parse_pair(cuit, number):
    if isinstance(cuit, (int, float)):
        if cuit != int(cuit):
            raise ValueError('CUIT numérico con decimales')
        cuit = str(int(cuit))
    cuit = re.sub(r'[\s-]', '', str(cuit or ''))
    if not re.fullmatch(r'\d{11}', cuit):
        raise ValueError('CUIT ausente o inválido; se requieren 11 dígitos')
    number = re.sub(r'\s+', '', str(number or '')).upper()
    if number.endswith('.PDF'):
        number = number[:-4]
    if not re.fullmatch(r'(?:FC|NC|ND)-[A-Z]\d{12,13}', number):
        raise ValueError('Número de comprobante ausente o no reconocido; ejemplo FC-A002100588517')
    return cuit, number


def load_inputs(paths):
    tasks, issues, seen = [], [], set()
    duplicates = 0
    for path in paths:
        matched = False
        with closing(openpyxl.load_workbook(path, read_only=True, data_only=True)) as book:
            for sheet in book:
                mapping = None
                for rowno, row in enumerate(sheet.iter_rows(values_only=True), 1):
                    if mapping is None:
                        if rowno > 100:
                            break
                        mapping = columns(row)
                        if mapping:
                            matched = True
                        continue
                    if not any(v is not None and str(v).strip() for v in row):
                        continue
                    # A repeated header inside the report is not an invoice.
                    if normalize(row[mapping['cuit']]) in ALIASES['cuit'] and normalize(row[mapping['numero']]) in ALIASES['numero']:
                        continue
                    try:
                        pair = parse_pair(row[mapping['cuit']], row[mapping['numero']])
                        if pair in seen:
                            duplicates += 1
                            continue
                        seen.add(pair)
                        tasks.append((*pair, f'{path.name} / {sheet.title} / fila {rowno}'))
                    except Exception as exc:
                        issues.append([path.name, sheet.title, rowno, str(exc)])
        if not matched:
            issues.append([path.name, '', '', 'No se encontró una hoja con columnas CUIT y NumeroFactura en las primeras 100 filas'])
    return tasks, issues, duplicates
