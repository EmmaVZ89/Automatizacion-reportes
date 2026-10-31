"""Generadores de libros Excel sintéticos para las pruebas. Nunca datos reales."""
import contextlib
import shutil
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def _columna(i):
    s = ''
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def xlsx_sintetico(path, hojas, con_referencias=True):
    """Libro mínimo con celdas inlineStr (como las exportaciones de los sistemas de origen).

    hojas: [(nombre, [[valor, ...], ...]), ...]. Con con_referencias=False las celdas no llevan
    atributo r (así vienen algunas exportaciones ERP)."""
    path = Path(path)
    with ZipFile(path, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(hojas) + 1)) + '</Types>')
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="' + NS_REL + '/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml', '<workbook xmlns="' + NS + '" xmlns:r="' + NS_REL + '"><sheets>' + ''.join(f'<sheet name="{escape(nombre)}" sheetId="{i}" r:id="r{i}"/>' for i, (nombre, _) in enumerate(hojas, 1)) + '</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(f'<Relationship Id="r{i}" Type="{NS_REL}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(hojas) + 1)) + '</Relationships>')
        for i, (_, filas) in enumerate(hojas, 1):
            partes = []
            for n, fila in enumerate(filas, 1):
                celdas = []
                for c, v in enumerate(fila, 1):
                    if v is None or v == '':
                        continue
                    ref = f' r="{_columna(c)}{n}"' if con_referencias else ''
                    celdas.append(f'<c{ref} t="inlineStr"><is><t>{escape(str(v))}</t></is></c>')
                partes.append(f'<row r="{n}">' + ''.join(celdas) + '</row>')
            z.writestr(f'xl/worksheets/sheet{i}.xml', '<worksheet xmlns="' + NS + '"><sheetData>' + ''.join(partes) + '</sheetData></worksheet>')
    return path


def xlsx_openpyxl(path, hojas):
    """Libro escrito con openpyxl (valores tipados: números, fechas, texto), para los motores que leen con openpyxl."""
    import openpyxl
    libro = openpyxl.Workbook()
    libro.remove(libro.active)
    for nombre, filas in hojas:
        hoja = libro.create_sheet(nombre)
        for fila in filas:
            hoja.append(fila)
    libro.save(path)
    return Path(path)


@contextlib.contextmanager
def carpeta_temporal():
    base = Path(__file__).resolve().parent / '_tmp'
    base.mkdir(exist_ok=True)
    ruta = Path(tempfile.mkdtemp(dir=base))
    try:
        yield ruta
    finally:
        shutil.rmtree(ruta, ignore_errors=True)
