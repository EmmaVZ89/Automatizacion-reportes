"""Punto de entrada del subproceso: python -I ejecutar.py --trabajo <carpeta>."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
for _ruta in (RAIZ, RAIZ / 'vendor'):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

import argparse  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402

from app.reportes._comun import protocolo  # noqa: E402
from app.reportes._comun.entradas import ordenar_tramos  # noqa: E402
from app.reportes._comun.salidas import Volcador  # noqa: E402
from app.reportes.control_cheques import motor  # noqa: E402
from app.reportes.control_cheques.reporte import REPORTE  # noqa: E402

SALIDAS = {s['tabla']: s for s in REPORTE['salidas']}


def _tramos(entradas, clave):
    """Rutas de los tramos de una entrada, ordenadas por el nombre original (no por la ruta guardada)."""
    por_nombre = {}
    for a in entradas.get(clave) or []:
        ruta = Path(a['ruta'])
        por_nombre.setdefault(a.get('nombre') or ruta.name, []).append(ruta)
    return [por_nombre[p.name].pop(0) for p in ordenar_tramos(n for n, rutas in por_nombre.items() for _ in rutas)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=REPORTE['descripcion'])
    parser.add_argument('--trabajo', type=Path, required=True)
    args = parser.parse_args(argv)
    trabajo = args.trabajo.resolve()
    with (trabajo / 'parametros.json').open(encoding='utf-8') as f:
        parametros = json.load(f)
    with (trabajo / 'entradas.json').open(encoding='utf-8') as f:
        entradas = json.load(f)
    sga = _tramos(entradas, 'sga')
    erp = _tramos(entradas, 'erp')
    if not sga or not erp:
        protocolo.error('Faltan archivos: hace falta al menos un Excel de cheques de SGA y uno de valores de tesorería de ERP.')
        return 1
    for ruta in sga + erp:
        if not ruta.is_file():
            protocolo.error(f'No se encuentra el archivo {ruta.name}.')
            return 1
    destino = trabajo / 'salidas'
    try:
        resumen = motor.controlar(sga, erp, destino, parametros, informar=protocolo)
    except ValueError as error:
        protocolo.error(f'No se pudo completar el control: {error}')
        return 1

    with (destino / SALIDAS['revisar']['archivo']).open(encoding='utf-8-sig', newline='') as f:
        lector = csv.reader(f, delimiter=';')
        columnas = next(lector)
        filas_revisar = [fila for fila in lector]
    with Volcador(trabajo / 'resultados.sqlite') as volcador:
        volcador.tabla('revisar', columnas, filas_revisar, SALIDAS['revisar']['clave'], titulo=SALIDAS['revisar']['titulo'])
        volcador.tabla('resumen', ['Concepto', 'Valor'], [[concepto, valor] for concepto, valor in resumen.items()],
                       SALIDAS['resumen']['clave'], titulo=SALIDAS['resumen']['titulo'])
    protocolo.resumen({
        'reporte': REPORTE['codigo'],
        'sga': [p.name for p in sga],
        'erp': [p.name for p in erp],
        'cantidades': dict(resumen),
        'total_para_revisar': resumen.get('Total para revisar', 0),
    })
    return 0


if __name__ == '__main__':
    sys.exit(main())
