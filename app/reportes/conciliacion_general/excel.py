"""Presentación XLSX sin dependencias. No calcula ni cambia claves o saldos.

Copia de legado/conciliacion_general/excel_general.py. Los lectores del CSV (`filas_resumen`,
`filas_detalle`) se exponen aparte para que ejecutar.py vuelque las mismas filas a sqlite."""
import csv
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape
import re

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
LABELS = {
    'SIN COINCIDENCIA - ERP SOLO ABIERTOS': 'SOLO EN SGA — REVISAR EN ERP',
    'SOLO ERP - REVISAR': 'SOLO EN ERP — REVISAR EN SGA',
    'REVISAR IDENTIFICACION - SGA': 'SIN COMPROBANTE EN SGA — REVISAR',
}
COLUMNAS_RESUMEN = ['Control', 'Saldo SGA', 'Saldo ERP', 'Diferencia', 'Resultado / cantidad', 'Detalle']

def label(value):
    return LABELS.get(value, value)

def column(i):
    result = ''
    while i:
        i, rem = divmod(i-1, 26)
        result = chr(65+rem)+result
    return result

def clean(value):
    # XML 1.0 no admite caracteres de control. Texto explícito: nunca fórmula.
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value))[:32767]

def sheet(z, name, rows, numeric, widths, filter_rows=False):
    with z.open(name, 'w') as stream:
        def write(s): stream.write(s.encode('utf-8'))
        write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
        write(f'<worksheet xmlns="{NS}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>')
        for i, width in enumerate(widths, 1):
            write(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>')
        write('</cols><sheetData>')
        count = 0
        for count, row in enumerate(rows, 1):
            if count > 1048576: raise ValueError('El detalle supera el máximo de filas de Excel.')
            write(f'<row r="{count}">')
            for i, value in enumerate(row, 1):
                if value == '' or value is None: continue
                ref = column(i)+str(count)
                if count > 1 and i in numeric:
                    # Únicamente columnas generadas por el cálculo; no inferir IDs.
                    if not re.fullmatch(r'-?\d+(?:\.\d+)?', str(value)):
                        raise ValueError(f'Número inválido en {name} {ref}')
                    write(f'<c r="{ref}" s="{2 if (not filter_rows or i in (6,7,8)) else 3}" t="n"><v>{value}</v></c>')
                else:
                    style = 1 if count == 1 else 0
                    write(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(clean(value))}</t></is></c>')
            write('</row>')
        write('</sheetData>')
        if filter_rows and count:
            write(f'<autoFilter ref="A1:{column(len(widths))}{count}"/>')
        write('</worksheet>')
    return count

def filas_resumen(csv_path):
    """Filas CONTROL del CSV como filas de la hoja Resumen (sin encabezado; ver COLUMNAS_RESUMEN)."""
    controls = []
    with Path(csv_path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f, delimiter=';'); next(reader)
        for row in reader:
            if row[0] == 'CONTROL':
                concept = row[2]
                for old, new in LABELS.items(): concept = concept.replace(old, new)
                controls.append([concept,row[5],row[6],row[7],label(row[8]),row[14]])
    return controls

def filas_detalle(csv_path):
    """Encabezado y filas de datos del CSV (sin CONTROL) con los estados con etiqueta. Desde la v1.5 el CSV ya
    trae el Tipo visible (RC-X, OP-X, PENDIENTE...): no se reemplaza."""
    with Path(csv_path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f, delimiter=';')
        yield next(reader)
        for row in reader:
            if row[0] == 'CONTROL': continue
            row[8] = label(row[8])
            yield row

def export_excel(csv_path, output):
    """Separar controles v1.3 del detalle; compatible con resultados anteriores."""
    csv_path, output = Path(csv_path), Path(output)
    summary = [list(COLUMNAS_RESUMEN)] + filas_resumen(csv_path)
    temporary = output.with_suffix('.temporal.xlsx')
    try:
        with ZipFile(temporary, 'w', ZIP_DEFLATED, compresslevel=6) as z:
            z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in (1,2))+'</Types>')
            z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
            z.writestr('xl/workbook.xml', f'<workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Resumen" sheetId="1" r:id="r1"/><sheet name="Conciliación general" sheetId="2" r:id="r2"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="r{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in (1,2))+'<Relationship Id="styles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
            z.writestr('xl/styles.xml', f'<styleSheet xmlns="{NS}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF24476A"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="4"><xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0"/><xf numFmtId="4" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
            # Resumen: texto explícito para alcances/estados, importes numéricos.
            sheet(z,'xl/worksheets/sheet1.xml',summary,{2,3,4},[48,24,24,24,48,100])
            n = sheet(z,'xl/worksheets/sheet2.xml',filas_detalle(csv_path),{6,7,8,10,11},[20,14,30,18,45,24,24,26,48,12,12,55,55,25,65,30,55],True)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return n-1
