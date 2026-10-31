"""Escritor XLSX genérico con la biblioteca estándar (derivado del de Controles SGA): encabezado
fijo, filtros, importes como números, texto explícito (nunca fórmulas) y celdas resaltadas."""
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_RE_NUM = re.compile(r'^-?\d+(?:\.\d+)?$')
_RE_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')

ESTILOS = f'''<styleSheet xmlns="{NS}"><numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.00;[Red]-#,##0.00"/></numFmts><fonts count="3"><font><sz val="10"/><name val="Arial"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Arial"/></font><font><b/><sz val="14"/><name val="Arial"/></font></fonts><fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF24445C"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF4B183"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="7"><xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="center"/></xf><xf fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"><alignment vertical="center" horizontal="center" wrapText="1"/></xf><xf fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf fontId="0" fillId="0" borderId="0" numFmtId="164" xfId="0" applyNumberFormat="1"><alignment horizontal="right" vertical="center"/></xf><xf fontId="0" fillId="0" borderId="0" numFmtId="0" xfId="0"><alignment vertical="center"/></xf><xf fontId="0" fillId="3" borderId="0" numFmtId="164" xfId="0" applyFill="1" applyNumberFormat="1"><alignment horizontal="right" vertical="center"/></xf><xf numFmtId="49" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"><alignment vertical="center"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''


def columna(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _texto(v):
    return escape(_RE_CONTROL.sub('', str(v))[:32767])


def _celda(ref, valor, estilo):
    if valor is None or valor == '':
        return f'<c r="{ref}" s="{estilo}"/>' if estilo in (5, 6) else ''
    if estilo in (3, 5) and isinstance(valor, (int, float)):
        return f'<c r="{ref}" s="{estilo}"><v>{valor!r}</v></c>'
    if estilo in (3, 5) and isinstance(valor, str) and _RE_NUM.match(valor):
        return f'<c r="{ref}" s="{estilo}"><v>{valor}</v></c>'
    return f'<c r="{ref}" s="{estilo}" t="inlineStr"><is><t xml:space="preserve">{_texto(valor)}</t></is></c>'


def escribir_libro(path, hojas):
    """hojas: [{nombre, columnas, filas (iterable de listas), tipos (por columna: 'numero'|'texto'|'fecha'),
    anchos?, nota?, resaltadas? (set de (indice_fila, indice_columna))}]. Fila 1: título; fila 2: nota;
    fila 4: encabezados; datos desde la 5. Devuelve filas escritas por hoja."""
    path = Path(path)
    temporal = path.with_suffix('.temporal.xlsx')
    escritas = []
    try:
        with zipfile.ZipFile(temporal, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('_rels/.rels', f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{NS_REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
            z.writestr('xl/styles.xml', ESTILOS)
            sheets, rels, content = [], [], []
            for si, h in enumerate(hojas, 1):
                cols = list(h['columnas'])
                tipos = list(h.get('tipos') or ['texto'] * len(cols))
                anchos = list(h.get('anchos') or [max(12, min(60, len(str(c)) + 4)) for c in cols])
                resaltadas = set(map(tuple, h.get('resaltadas') or ()))
                sheets.append(f'<sheet name={quoteattr(str(h["nombre"])[:31])} sheetId="{si}" r:id="rId{si}"/>')
                rels.append(f'<Relationship Id="rId{si}" Type="{NS_REL}/worksheet" Target="worksheets/sheet{si}.xml"/>')
                content.append(f'<Override PartName="/xl/worksheets/sheet{si}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
                ultima = columna(max(1, len(cols)))
                with z.open(f'xl/worksheets/sheet{si}.xml', 'w') as out:
                    def put(s):
                        out.write(s.encode('utf-8'))
                    put(f'<worksheet xmlns="{NS}"><sheetViews><sheetView workbookViewId="0" showGridLines="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>')
                    for i, w in enumerate(anchos, 1):
                        put(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>')
                    put('</cols><sheetData>')
                    put('<row r="1" ht="24" customHeight="1">' + _celda('A1', h.get('titulo') or h['nombre'], 2) + '</row>')
                    if h.get('nota'):
                        put('<row r="2">' + _celda('A2', h['nota'], 4) + '</row>')
                    put('<row r="4" ht="30" customHeight="1">' + ''.join(_celda(columna(i + 1) + '4', c, 1) for i, c in enumerate(cols)) + '</row>')
                    n = 0
                    for ri, fila in enumerate(h['filas']):
                        rn = ri + 5
                        if rn > 1048576:
                            raise ValueError('La hoja supera el máximo de filas de Excel.')
                        n += 1
                        put(f'<row r="{rn}">')
                        for ci, v in enumerate(fila[:len(cols)]):
                            estilo = 3 if tipos[ci] == 'numero' else 0
                            if (ri, ci) in resaltadas:
                                estilo = 5 if estilo == 3 else 6
                            put(_celda(columna(ci + 1) + str(rn), v, estilo))
                        put('</row>')
                    put(f'</sheetData><autoFilter ref="A4:{ultima}{n + 4}"/></worksheet>')
                escritas.append(n)
            z.writestr('xl/workbook.xml', f'<workbook xmlns="{NS}" xmlns:r="{NS_REL}"><sheets>' + ''.join(sheets) + '</sheets></workbook>')
            rels.append(f'<Relationship Id="rId{len(sheets) + 1}" Type="{NS_REL}/styles" Target="styles.xml"/>')
            z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(rels) + '</Relationships>')
            z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' + ''.join(content) + '</Types>')
        temporal.replace(path)
    finally:
        temporal.unlink(missing_ok=True)
    return escritas
