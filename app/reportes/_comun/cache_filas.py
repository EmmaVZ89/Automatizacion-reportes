"""Copia de consulta rápida de una hoja de Excel, para sacar unas pocas filas de un libro de cientos de miles
sin volver a leerlo entero (lo usa el Excel de origen de una fila de resultado).

Se arma una sola vez por archivo y hoja, en un subproceso:
    python -I cache_filas.py --xlsx <libro> --hoja <hoja> --destino <copia .sqlite>
Imprime líneas JSON {"progreso": 0..1} y termina con código 0. Sólo biblioteca estándar.

Las filas se guardan en bloques de BLOQUE filas, como JSON comprimido {fila: [[columna, valor, formato], ...]}
(sólo celdas con valor). `valor` es
número, texto o booleano tal como está en el libro; `formato` es el índice del formato de número de la celda
(las fechas son números con formato de fecha, como en Excel). También guarda los anchos de columna."""
import argparse
import json
import re
import sqlite3
import sys
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
NS_R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
VERSION = 2
BLOQUE = 128
FORMATOS_INCORPORADOS = {
    0: 'General', 1: '0', 2: '0.00', 3: '#,##0', 4: '#,##0.00', 9: '0%', 10: '0.00%', 11: '0.00E+00', 12: '# ?/?',
    13: '# ??/??', 14: 'dd/mm/yyyy', 15: 'd-mmm-yy', 16: 'd-mmm', 17: 'mmm-yy', 18: 'h:mm AM/PM', 19: 'h:mm:ss AM/PM',
    20: 'h:mm', 21: 'h:mm:ss', 22: 'dd/mm/yyyy h:mm', 37: '#,##0 ;(#,##0)', 38: '#,##0 ;[Red](#,##0)',
    39: '#,##0.00;(#,##0.00)', 40: '#,##0.00;[Red](#,##0.00)', 45: 'mm:ss', 46: '[h]:mm:ss', 47: 'mmss.0',
    48: '##0.0E+0', 49: '@'}
_RE_ULTIMA = re.compile(r'([0-9]+)$')


def _columna(ref):
    col = 0
    for ch in ref:
        if not ch.isalpha():
            break
        col = col * 26 + ord(ch.upper()) - 64
    return col - 1


def _formatos_de_estilo(z):
    """Código de formato de número por índice de estilo de celda (cellXfs)."""
    if 'xl/styles.xml' not in z.namelist():
        return []
    raiz = ET.fromstring(z.read('xl/styles.xml'))
    propios = {}
    nf = raiz.find(NS + 'numFmts')
    if nf is not None:
        for f in nf:
            propios[int(f.get('numFmtId'))] = f.get('formatCode') or 'General'
    xfs = raiz.find(NS + 'cellXfs')
    salida = []
    for xf in (xfs if xfs is not None else []):
        i = int(xf.get('numFmtId') or 0)
        salida.append(propios.get(i) or FORMATOS_INCORPORADOS.get(i, 'General'))
    return salida


def _textos_compartidos(z):
    textos = []
    if 'xl/sharedStrings.xml' in z.namelist():
        with z.open('xl/sharedStrings.xml') as f:
            raiz = None
            for evento, e in ET.iterparse(f, events=('start', 'end')):
                if raiz is None:
                    raiz = e
                if evento == 'end' and e.tag == NS + 'si':
                    textos.append(''.join(x.text or '' for x in e.iter(NS + 't')))
                    raiz.clear()
    return textos


def _ruta_hoja(z, hoja):
    libro = ET.fromstring(z.read('xl/workbook.xml'))
    hojas = libro.find(NS + 'sheets')
    elegida = next((s for s in hojas if s.get('name') == hoja), None) if hojas is not None else None
    if elegida is None:
        raise ValueError(f'El libro no tiene la hoja {hoja}.')
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    destino = next(x.get('Target') for x in rels if x.get('Id') == elegida.get(NS_R))
    return destino.lstrip('/') if destino.startswith('/') else 'xl/' + destino


def _numero(texto):
    try:
        if re.fullmatch(r'-?\d+', texto):
            return int(texto)
        return float(texto)
    except ValueError:
        return texto


def construir(xlsx, hoja, destino, informar=None):
    """Arma la copia de consulta de `hoja` del libro `xlsx` en `destino`. Devuelve la cantidad de filas."""
    xlsx, destino = Path(xlsx), Path(destino)
    temporal = destino.with_name(destino.name + '.tmp')
    temporal.unlink(missing_ok=True)
    con = sqlite3.connect(str(temporal))
    filas = 0
    try:
        con.execute('PRAGMA journal_mode=OFF')
        con.execute('PRAGMA synchronous=OFF')
        con.execute('CREATE TABLE meta(clave TEXT PRIMARY KEY, valor TEXT)')
        con.execute('CREATE TABLE formatos(id INTEGER PRIMARY KEY, codigo TEXT)')
        con.execute('CREATE TABLE bloques(bloque INTEGER PRIMARY KEY, datos BLOB)')
        with ZipFile(xlsx) as z:
            estilos = _formatos_de_estilo(z)
            textos = _textos_compartidos(z)
            ids_formato = {}

            def formato(estilo):
                codigo = estilos[estilo] if 0 <= estilo < len(estilos) else 'General'
                if codigo not in ids_formato:
                    ids_formato[codigo] = len(ids_formato)
                return ids_formato[codigo]

            ultima = 0
            anchos = {}
            lote = []
            actual = {'bloque': None, 'filas': {}}

            def cerrar_bloque():
                if actual['filas']:
                    texto = json.dumps(actual['filas'], ensure_ascii=False, separators=(',', ':')).encode('utf-8')
                    lote.append((actual['bloque'], zlib.compress(texto, 6)))
                actual['filas'] = {}

            with z.open(_ruta_hoja(z, hoja)) as f:
                raiz = None
                for evento, e in ET.iterparse(f, events=('start', 'end')):
                    if raiz is None:
                        raiz = e
                    if evento != 'end':
                        continue
                    if e.tag == NS + 'dimension':
                        m = _RE_ULTIMA.search(e.get('ref', ''))
                        ultima = int(m.group(1)) if m else 0
                    elif e.tag == NS + 'col':
                        try:
                            for c in range(int(e.get('min')), int(e.get('max')) + 1):
                                anchos[c - 1] = float(e.get('width'))
                        except (TypeError, ValueError):
                            pass
                    elif e.tag == NS + 'row':
                        celdas = []
                        siguiente = 0
                        for c in e:
                            if c.tag != NS + 'c':
                                continue
                            ref = c.get('r')
                            col = _columna(ref) if ref else siguiente
                            siguiente = col + 1
                            t = c.get('t')
                            v = c.find(NS + 'v')
                            if t == 'inlineStr':
                                valor = ''.join(x.text or '' for x in c.iter(NS + 't'))
                            elif v is None or v.text is None:
                                continue
                            elif t == 's':
                                valor = textos[int(v.text)]
                            elif t == 'b':
                                valor = v.text == '1'
                            elif t in ('str', 'e'):
                                valor = v.text
                            else:
                                valor = _numero(v.text)
                            if valor == '':
                                continue
                            celdas.append([col, valor, formato(int(c.get('s') or 0))])
                        n = int(e.get('r') or (filas + 1))
                        if n // BLOQUE != actual['bloque']:
                            cerrar_bloque()
                            actual['bloque'] = n // BLOQUE
                        if celdas:
                            actual['filas'][n] = celdas
                        filas += 1
                        if len(lote) >= 50:
                            con.executemany('INSERT OR REPLACE INTO bloques VALUES(?,?)', lote)
                            lote.clear()
                            if informar and ultima:
                                informar(min(0.99, n / ultima))
                        e.clear()
                        raiz.clear()
            cerrar_bloque()
            if lote:
                con.executemany('INSERT OR REPLACE INTO bloques VALUES(?,?)', lote)
            con.executemany('INSERT INTO formatos VALUES(?,?)', [(i, c) for c, i in ids_formato.items()])
            con.executemany('INSERT INTO meta VALUES(?,?)', [('version', str(VERSION)), ('hoja', hoja), ('archivo', xlsx.name),
                                                            ('anchos', json.dumps(anchos)), ('filas', str(filas))])
        con.commit()
    finally:
        con.close()
    temporal.replace(destino)
    if informar:
        informar(1.0)
    return filas


class CacheFilas:
    """Lectura de una copia de consulta armada con `construir`."""

    def __init__(self, ruta):
        self.ruta = Path(ruta)

    def lista(self):
        if not self.ruta.exists():
            return False
        try:
            con = sqlite3.connect(f'file:{self.ruta.as_posix()}?mode=ro', uri=True)
            try:
                v = con.execute("SELECT valor FROM meta WHERE clave='version'").fetchone()
            finally:
                con.close()
        except sqlite3.Error:
            return False
        return bool(v) and v[0] == str(VERSION)

    def _con(self):
        return sqlite3.connect(f'file:{self.ruta.as_posix()}?mode=ro', uri=True)

    def leer(self, numeros):
        """{numero de fila: [(columna, valor, codigo de formato)]} de las filas pedidas que tienen datos."""
        numeros = sorted({int(x) for x in numeros})
        con = self._con()
        try:
            formatos = dict(con.execute('SELECT id, codigo FROM formatos').fetchall())
            pedidas = set(numeros)
            bloques = sorted({n // BLOQUE for n in numeros})
            salida = {}
            for i in range(0, len(bloques), 500):
                lote = bloques[i:i + 500]
                for _, datos in con.execute(f'SELECT bloque, datos FROM bloques WHERE bloque IN ({",".join("?" * len(lote))})', lote):
                    for n, celdas in json.loads(zlib.decompress(datos)).items():
                        if int(n) in pedidas:
                            salida[int(n)] = [(c, v, formatos.get(f, 'General')) for c, v, f in celdas]
            return salida
        finally:
            con.close()

    def primeras(self, cantidad=20):
        """Las primeras filas con datos (para encontrar el encabezado)."""
        con = self._con()
        try:
            datos = con.execute('SELECT datos FROM bloques ORDER BY bloque LIMIT 1').fetchone()
        finally:
            con.close()
        if not datos:
            return []
        filas = sorted((int(n), c) for n, c in json.loads(zlib.decompress(datos[0])).items())[:cantidad]
        leidas = self.leer([n for n, _ in filas])
        return [(n, leidas[n]) for n, _ in filas if n in leidas]

    def anchos(self):
        con = self._con()
        try:
            v = con.execute("SELECT valor FROM meta WHERE clave='anchos'").fetchone()
        finally:
            con.close()
        return {int(k): w for k, w in json.loads(v[0]).items()} if v else {}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--xlsx', required=True, type=Path)
    parser.add_argument('--hoja', required=True)
    parser.add_argument('--destino', required=True, type=Path)
    args = parser.parse_args(argv)

    def informar(p):
        print(json.dumps({'progreso': round(p, 3)}), flush=True)

    try:
        construir(args.xlsx, args.hoja, args.destino, informar)
    except Exception as e:  # el server muestra el mensaje en lenguaje llano
        print(json.dumps({'error': str(e)}, ensure_ascii=False), flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
