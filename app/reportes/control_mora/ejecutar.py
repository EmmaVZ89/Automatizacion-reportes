"""Punto de entrada del subproceso del Control de Mora: `python -I ejecutar.py --trabajo <carpeta>`.

La carpeta trae parametros.json y entradas.json; acá quedan salidas/ (los cuatro archivos de siempre)
y resultados.sqlite (una tabla por salida). El resumen sale por el protocolo."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
for _ruta in (RAIZ / 'vendor', RAIZ):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

import argparse  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402

from app.reportes._comun import protocolo  # noqa: E402
from app.reportes._comun.entradas import ordenar_tramos  # noqa: E402
from app.reportes._comun.salidas import Volcador  # noqa: E402
from app.reportes.control_mora import motor  # noqa: E402
from app.reportes.control_mora.reporte import REPORTE  # noqa: E402


def tramos_de(entradas, clave):
    """[(ruta, nombre)] de una entrada, ordenados por el nombre original (en el server el archivo
    se guarda como <sha8>-<nombre>)."""
    items = entradas.get(clave) or []
    orden = {p.name: i for i, p in enumerate(ordenar_tramos([e['nombre'] for e in items]))}
    return [(Path(e['ruta']), e['nombre']) for e in sorted(items, key=lambda e: orden[e['nombre']])]


def filas_csv(ruta):
    """(columnas, generador de filas) de un CSV de salida (`;`, UTF-8 con BOM)."""
    with ruta.open('r', newline='', encoding='utf-8-sig') as f:
        lector = csv.reader(f, delimiter=';')
        columnas = next(lector, [])
        yield columnas
        for fila in lector:
            yield fila


def volcar(trabajo, salidas):
    with Volcador(trabajo / 'resultados.sqlite') as v:
        for s in REPORTE['salidas']:
            lector = filas_csv(salidas / s['archivo'])
            columnas = next(lector)
            v.tabla(s['tabla'], columnas, lector, clave=s['clave'], titulo=s['titulo'])


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--trabajo', required=True)
    args = parser.parse_args(argv)
    trabajo = Path(args.trabajo).resolve()
    parametros = json.loads((trabajo / 'parametros.json').read_text(encoding='utf-8'))
    entradas = json.loads((trabajo / 'entradas.json').read_text(encoding='utf-8'))
    erp = tramos_de(entradas, 'erp')
    sga = tramos_de(entradas, 'sga')
    nombres = {str(ruta): nombre for ruta, nombre in erp + sga}
    salidas = trabajo / 'salidas'
    salidas.mkdir(parents=True, exist_ok=True)
    try:
        resumen = motor.ejecutar([r for r, _ in erp], [r for r, _ in sga], salidas, parametros, informar=protocolo, nombres=nombres)
    except ValueError as e:
        protocolo.error(str(e))
        return 1
    protocolo.paso('Preparando las tablas de resultados')
    volcar(trabajo, salidas)
    protocolo.resumen(resumen)
    return 0


if __name__ == '__main__':
    sys.exit(main())
