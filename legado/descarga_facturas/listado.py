"""Descarga directa desde listados Excel, sin enumerar la biblioteca."""
import csv
import re
import sys
import unicodedata
from contextlib import closing
from datetime import datetime
from pathlib import Path

import openpyxl
import facturas as core

BASE = Path(__file__).resolve().parent
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


def date_input(label):
    while True:
        value = input(label + ' (dd/mm/aaaa; vacío = sin límite): ').strip()
        if not value:
            return None
        try:
            return datetime.strptime(value, '%d/%m/%Y').date()
        except ValueError:
            print('Fecha inválida. Ejemplo: 12/10/2026.')


def main():
    from playwright.sync_api import sync_playwright
    print('DESCARGA POR LISTADO EXCEL - VERSION 6', flush=True)
    entry = BASE / 'Entrada'
    entry.mkdir(exist_ok=True)
    paths = sorted(p for p in entry.iterdir() if p.suffix.lower() in {'.xlsx', '.xlsm'} and not p.name.startswith('~$'))
    if not paths:
        raise ValueError('Pegá tu listado Excel en la carpeta Entrada y volvé a abrir EJECUTAR.')
    tasks, issues, duplicates = load_inputs(paths)
    logs = BASE / 'resultados'
    logs.mkdir(exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    issue_path = logs / ('entrada_a_revisar_' + stamp + '.csv')
    if issues:
        with issue_path.open('w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Archivo', 'Hoja', 'Fila', 'Motivo'])
            writer.writerows(issues)
    print(f'Facturas únicas: {len(tasks)}. Repeticiones omitidas: {duplicates}. Filas/archivos para revisar: {len(issues)}.')
    if issues:
        print('Revisá: ' + str(issue_path))
    if not tasks:
        raise ValueError('No hay facturas válidas para descargar.')
    start = date_input('Emisión desde')
    end = date_input('Emisión hasta')
    if start and end and start > end:
        raise ValueError('Desde no puede ser posterior a hasta.')
    concept_filter = input('Concepto (vacío = todos): ').strip()
    dest_text = input('Carpeta destino (Enter = ' + str(core.DEST) + '): ').strip().strip('"')
    dest = Path(dest_text) if dest_text else core.DEST
    if not dest.is_dir():
        raise ValueError('La carpeta destino no existe. Creala o copiá su ruta correcta.')
    report = logs / ('descarga_' + stamp + '.csv')
    counts = {}
    with report.open('w', newline='', encoding='utf-8-sig') as f, sync_playwright() as p:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['CUIT', 'Factura', 'FechaEmisionPDF', 'ConceptosPDF', 'Estado', 'Detalle', 'FilaOrigen'])
        context = p.chromium.launch_persistent_context(str(BASE / 'sesion_chrome'), channel='chrome', headless=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(core.VIEW, wait_until='domcontentloaded', timeout=120000)
            input('Cuando veas Comprobantes en Chrome, volvé acá y presioná SOLO ENTER. ')
            web = core.wait_for_library(page)
            if web:
                core.SITE = core.check_url(web).rstrip('/')
            for index, (cuit, number, source_row) in enumerate(tasks, 1):
                emitted, concepts = None, []
                print(f'[{index}/{len(tasks)}] {number}', flush=True)
                try:
                    source = core.ROOT + '/' + cuit + '/' + number + '.pdf'
                    response = core.get_response(context, core.ORIGIN + core.quote(source, safe='/'))
                    data = response.body()
                    if b'%PDF-' not in data[:1024]:
                        raise ValueError('La respuesta no es un PDF; revisar sesión o ubicación')
                    emitted, concepts = core.read_pdf(data)
                    # Check that SharePoint returned the requested document.
                    with core.pdfplumber.open(core.io.BytesIO(data)) as pdf:
                        text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
                    if number not in re.sub(r'\s+', '', text).upper():
                        raise ValueError('No se pudo confirmar el número de factura dentro del PDF')
                    if (start and emitted < start) or (end and emitted > end):
                        status, detail = 'Fuera del período', ''
                    elif concept_filter and concepts and not any(normalize(concept_filter) in normalize(c) for c in concepts):
                        status, detail = 'Otro concepto', ''
                    else:
                        category = concepts[0] if len(concepts) == 1 else ('Varios conceptos' if concepts else 'Para revisar')
                        target = dest / emitted.strftime('%Y-%m') / core.safe_name(category) / (number + '.pdf')
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if target.exists():
                            status = 'Ya existía' if target.read_bytes() == data else 'CONFLICTO: no se reemplazó'
                        else:
                            with target.open('xb') as out:
                                out.write(data)
                            status = 'Copiada' if concepts else 'REVISAR: concepto no identificado'
                        detail = str(target)
                except Exception as exc:
                    status, detail = 'ERROR', str(exc)
                counts[status] = counts.get(status, 0) + 1
                writer.writerow([cuit, number, emitted.strftime('%d/%m/%Y') if emitted else '', ' | '.join(concepts), status, detail, source_row])
                f.flush()
                print('  ' + status, flush=True)
        finally:
            context.close()
    print('\nFinalizó la lectura del listado.')
    for status, count in counts.items():
        print(f'{status}: {count}')
    print('Resultado: ' + str(report))
    print('Revisá los errores, conflictos y filas de entrada inválidas antes de dar la descarga por completa.')
    print('OneDrive debe estar sincronizando la carpeta destino para subir las copias a SharePoint.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nInterrumpido. Consultá el resultado parcial y volvé a ejecutar cuando quieras.')
        sys.exit(1)
    except Exception as exc:
        print('\nNo se completó: ' + str(exc))
        sys.exit(1)
