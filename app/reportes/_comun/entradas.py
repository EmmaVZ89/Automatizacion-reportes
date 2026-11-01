"""Lectura liviana de libros Excel para reconocer qué es cada archivo (encabezados de las primeras
filas y cantidad aproximada de filas), ordenar tramos y avisar descargas recortadas. Sólo stdlib."""
import posixpath
import re
from collections import namedtuple
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
NS_R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
OrigenFila = namedtuple('OrigenFila', 'archivo hoja fila')
RECORTE_EXACTO = 450000
RECORTE_RANGO = (453000, 455000)


class ArchivoNoLegible(ValueError):
    pass


def _hojas(z):
    try:
        libro = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    except KeyError as e:
        raise ArchivoNoLegible('El archivo no es un libro de Excel (.xlsx).') from e
    destinos = {r.get('Id'): r.get('Target') for r in rels}
    hojas = []
    lista = libro.find(NS + 'sheets')
    for s in (lista if lista is not None else []):
        destino = destinos.get(s.get(NS_R + 'id'), '')
        destino = destino.lstrip('/') if destino.startswith('/') else posixpath.normpath('xl/' + destino)
        hojas.append((s.get('name'), destino))
    return hojas


def _columna(ref):
    col = 0
    for ch in ref:
        if not ch.isalpha():
            break
        col = col * 26 + ord(ch.upper()) - 64
    return col


def _primeras_filas(z, destino, max_filas):
    """[(numero_fila, {indice_columna: (tipo, valor_crudo)})] de las primeras filas con contenido."""
    filas = []
    with z.open(destino) as f:
        raiz = None
        for evento, e in ET.iterparse(f, events=('start', 'end')):
            if raiz is None:
                raiz = e
            if evento != 'end' or e.tag != NS + 'row':
                continue
            celdas = {}
            siguiente = 0
            for c in e:
                if c.tag != NS + 'c':
                    continue
                ref = c.get('r', '')
                idx = _columna(ref) - 1 if ref else siguiente
                siguiente = idx + 1
                tipo = c.get('t')
                if tipo == 'inlineStr':
                    valor = ''.join(x.text or '' for x in c.iter(NS + 't'))
                else:
                    v = c.find(NS + 'v')
                    valor = v.text if v is not None else None
                if valor not in (None, ''):
                    celdas[idx] = (tipo, valor)
            n = int(e.get('r', len(filas) + 1))
            e.clear()
            raiz.clear()
            if celdas:
                filas.append((n, celdas))
            if len(filas) >= max_filas or n > 200:
                break
    return filas


def _cadenas_compartidas(z, hasta):
    """Las primeras `hasta`+1 cadenas compartidas (los encabezados usan índices bajos)."""
    if 'xl/sharedStrings.xml' not in z.namelist() or hasta < 0:
        return []
    cadenas = []
    with z.open('xl/sharedStrings.xml') as f:
        raiz = None
        for evento, e in ET.iterparse(f, events=('start', 'end')):
            if raiz is None:
                raiz = e
            if evento == 'end' and e.tag == NS + 'si':
                cadenas.append(''.join(x.text or '' for x in e.iter(NS + 't')))
                raiz.clear()
                if len(cadenas) > hasta:
                    break
    return cadenas


def _dimension(z, destino):
    with z.open(destino) as f:
        for _, e in ET.iterparse(f, events=('start',)):
            if e.tag == NS + 'dimension':
                m = re.search(r':[A-Z]+(\d+)$', e.get('ref', ''))
                return int(m.group(1)) if m else None
            if e.tag == NS + 'sheetData':
                return None
    return None


def encabezados_xlsx(path, max_filas=30, minimo_celdas=3):
    """[(hoja, fila, [encabezados], filas_aprox)] por hoja: la primera fila con >= minimo_celdas celdas con texto."""
    path = Path(path)
    try:
        with ZipFile(path) as z:
            salida = []
            for nombre, destino in _hojas(z):
                try:
                    filas = _primeras_filas(z, destino, max_filas)
                except (KeyError, ET.ParseError):
                    continue
                maximo = max((int(v) for _, celdas in filas for t, v in celdas.values() if t == 's' and v.isdigit()), default=-1)
                cadenas = _cadenas_compartidas(z, maximo)
                encontrada = None
                for n, celdas in filas:
                    valores = {}
                    for idx, (t, v) in celdas.items():
                        if t == 's':
                            texto = cadenas[int(v)] if v.isdigit() and int(v) < len(cadenas) else ''
                        else:
                            texto = v
                        texto = str(texto or '').strip()
                        if texto:
                            valores[idx] = texto
                    if len(valores) >= minimo_celdas:
                        encontrada = (n, [valores.get(i, '') for i in range(max(valores) + 1)])
                        break
                if encontrada:
                    ultima = _dimension(z, destino)
                    aprox = max(0, ultima - encontrada[0]) if ultima else None
                    salida.append((nombre, encontrada[0], encontrada[1], aprox))
            return salida
    except BadZipFile as e:
        raise ArchivoNoLegible('El archivo no es un libro de Excel (.xlsx) o está dañado.') from e


def detectar(path, detectores):
    """detectores: {tipo: fn(hojas) -> bool}. Devuelve el tipo reconocido o None; dos tipos ⇒ error."""
    hojas = encabezados_xlsx(path)
    positivos = [tipo for tipo, fn in detectores.items() if fn(hojas)]
    if len(positivos) > 1:
        raise ValueError('El archivo mezcla datos de dos tipos distintos (' + ' y '.join(positivos) + '); usá archivos separados.')
    return positivos[0] if positivos else None


def _clave_natural(nombre):
    return [int(p) if p.isdigit() else p.casefold() for p in re.split(r'(\d+)', str(nombre))]


def ordenar_tramos(paths):
    return sorted((Path(p) for p in paths), key=lambda p: _clave_natural(p.name))


def aviso_recorte(filas):
    if filas is None:
        return None
    if filas == RECORTE_EXACTO or RECORTE_RANGO[0] <= filas <= RECORTE_RANGO[1]:
        return f'El archivo tiene {filas:,} filas: puede ser una descarga recortada. Si el reporte sigue en otro archivo, agregalo como segundo tramo.'.replace(',', '.')
    return None


def valores_columna(path, hoja, columna, max_filas=400):
    """Los valores no vacíos de una columna (por su encabezado) en las primeras filas de una hoja: una muestra rápida,
    sin leer el libro entero."""
    with ZipFile(Path(path)) as z:
        destino = next((d for nombre, d in _hojas(z) if nombre == hoja), None)
        if destino is None:
            return []
        filas = _primeras_filas(z, destino, max_filas)
        maximo = max((int(v) for _, celdas in filas for t, v in celdas.values() if t == 's' and v.isdigit()), default=-1)
        cadenas = _cadenas_compartidas(z, maximo)
        indice = None
        salida = []
        for _, celdas in filas:
            valores = {i: str((cadenas[int(v)] if v.isdigit() and int(v) < len(cadenas) else '') if t == 's' else v or '').strip()
                       for i, (t, v) in celdas.items()}
            if indice is None:
                indice = next((i for i, x in valores.items() if x == columna), None)
            elif valores.get(indice):
                salida.append(valores[indice])
        return salida


def resumen_archivo(path, detectores):
    """Lo que la interfaz muestra de un archivo: tipo, hoja, filas aproximadas y aviso."""
    hojas = encabezados_xlsx(path)
    positivos = [tipo for tipo, fn in detectores.items() if fn(hojas)]
    if len(positivos) > 1:
        raise ValueError('El archivo mezcla datos de dos tipos distintos; usá archivos separados.')
    tipo = positivos[0] if positivos else None
    hoja = None
    filas = None
    if tipo:
        for nombre, _, enc, aprox in hojas:
            if detectores[tipo]([(nombre, 0, enc, aprox)]):
                hoja, filas = nombre, aprox
                break
    return {'tipo': tipo, 'hoja': hoja, 'filas': filas, 'aviso': aviso_recorte(filas), 'hojas': [h[0] for h in hojas]}
