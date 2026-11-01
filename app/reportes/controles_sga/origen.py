"""Filas de origen de una fila de Control Netos Impuestos (Controles SGA), para el Excel de origen.

Cada fila de netos viene de una fila del histórico de cuenta corriente de SGA (columna Fila SGA; con varios tramos,
la columna Archivo dice de cuál). El Excel lleva el encabezado y esa fila, con las celdas observadas (las anaranjadas
de la pantalla, que son columnas del histórico) pintadas de anaranjado. Sólo se usa el histórico de SGA. El contrato
está en app/origenes.py."""
from pathlib import Path

from .excel import ORIGINAL

ENCABEZADO_SGA = {'CodigoEmpresa', 'NumeroFactura', 'Importe'}


def _tramos(ctx):
    return [x for x in (ctx['entradas'].get('sga') or [])]


def _hoja(ctx, ruta):
    hoja = ctx['hojas'].get(str(ruta))
    if hoja:
        return hoja
    from ..conciliacion_general.motor import identificar  # la hoja de datos, por sus encabezados
    hojas = [h for lado, h, _ in identificar(Path(ruta)) if lado == 'SGA']
    if not hojas:
        raise FileNotFoundError(ruta)
    return hojas[0]


def fuentes(ctx):
    tramos = _tramos(ctx)
    if not tramos:
        raise FileNotFoundError('sin histórico de SGA')
    return [('SGA', Path(x['ruta']).name, _hoja(ctx, Path(x['ruta']))) for x in tramos]


def filas_de(ctx, fila):
    try:
        numero = int(str(fila.get('Fila SGA') or '').strip())
    except ValueError:
        return []
    tramos = _tramos(ctx)
    archivo = fila.get('Archivo') or (Path(tramos[0]['ruta']).name if len(tramos) == 1 else None)
    hoja = next((h for _, a, h in fuentes(ctx) if a == archivo), None)
    if not archivo or not hoja:
        return []
    observadas = {m for m in fila.get('_marcas') or [] if m in ORIGINAL}
    return [('SGA', archivo, hoja, [numero], {numero: observadas})]


def nombre(fila):
    return fila.get('NumeroFactura') or fila.get('NumeroComprobanteImputacion')


def es_encabezado(lado, textos):
    return ENCABEZADO_SGA <= set(textos)
