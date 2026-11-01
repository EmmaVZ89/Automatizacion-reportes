"""Filas de origen de una fila de la Conciliación general, para el Excel de origen.

El motor deja en Respaldo_tecnico/trazabilidad.sqlite cada fila de SGA y de ERP que entró al resultado, con su
clave (tipo interno, cliente, comprobante), el archivo con su hoja ("nombre [hoja]") y el número de fila del Excel.
Acá se traduce una fila del resultado (con el Tipo visible) a esas filas. El contrato está en app/origenes.py.
"""
import re
import sqlite3
from pathlib import Path

from .motor import COLUMNAS_ERP, COLUMNAS_SGA

LADOS = ('SGA', 'ERP')
# Tipos internos que se muestran tal cual; el resto de los Tipo visibles (RC-X, OP-X, "RC-X / OP-X", SUBRECIBO)
# son subrecibos u órdenes de pago, y PENDIENTE es el movimiento pendiente referido a una factura.
TIPOS_DIRECTOS = {'FACTURA', 'NC', 'REH', 'SIN_FACTURA', 'MP_OTRO', 'AMBIGUO', 'OTRO', 'SIN_ID_MP'}
_RE_ARCHIVO = re.compile(r'^(.*) \[(.*)\]$')


def trazabilidad(salidas):
    return Path(salidas) / 'Respaldo_tecnico' / 'trazabilidad.sqlite'


def _archivo_y_hoja(texto):
    m = _RE_ARCHIVO.match(texto or '')
    return (m.group(1), m.group(2)) if m else (texto, '')


def _con(traz):
    return sqlite3.connect(f'file:{Path(traz).as_posix()}?mode=ro', uri=True)


def _traz(ctx):
    traz = trazabilidad(ctx['salidas'])
    if not traz.exists():
        raise FileNotFoundError(traz)
    return traz


def fuentes(ctx):
    con = _con(_traz(ctx))
    try:
        filas = con.execute('SELECT DISTINCT sistema, archivo FROM filas').fetchall()
    finally:
        con.close()
    return sorted((lado, *_archivo_y_hoja(archivo)) for lado, archivo in filas)


def tipos_internos(tipo_visible):
    if tipo_visible == 'PENDIENTE':
        return ['MP']
    if tipo_visible in TIPOS_DIRECTOS:
        return [tipo_visible]
    return ['SR', 'OPX']


def filas_de(ctx, fila):
    """[(lado, archivo, hoja, [filas])] de una fila del resultado ({columna: valor}), SGA primero."""
    tipos = tipos_internos(fila.get('Tipo') or '')
    con = _con(_traz(ctx))
    try:
        cur = con.execute(f'SELECT sistema, archivo, fila FROM filas WHERE sistema IN (?, ?) AND tipo IN ({",".join("?" * len(tipos))}) '
                          'AND cliente=? AND comprobante=? ORDER BY fila', (*LADOS, *tipos, fila.get('Cliente') or '', fila.get('Comprobante') or ''))
        grupos = {}
        for lado, archivo, n in cur:
            grupos.setdefault((lado, archivo), []).append(int(n))
    finally:
        con.close()
    return [(lado, *_archivo_y_hoja(archivo), numeros)
            for (lado, archivo), numeros in sorted(grupos.items(), key=lambda par: (LADOS.index(par[0][0]), par[0][1]))]


def nombre(fila):
    return fila.get('Comprobante')


def es_encabezado(lado, textos):
    return (COLUMNAS_SGA if lado == 'SGA' else COLUMNAS_ERP) <= set(textos)
