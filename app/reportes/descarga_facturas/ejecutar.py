"""Punto de entrada del subproceso: python -I ejecutar.py --trabajo <carpeta> [--simular <carpeta de PDF>].

Corre con el intérprete del .venv de facturas (Playwright + pdfplumber); openpyxl se toma de vendor/.
Con --simular (sólo pruebas) no abre Chrome: sirve `<carpeta>/<CUIT>/<numero>.pdf`."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
for _ruta in (RAIZ, RAIZ / 'vendor'):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

import argparse  # noqa: E402
import json  # noqa: E402

from app.reportes._comun import protocolo  # noqa: E402
from app.reportes._comun.entradas import ordenar_tramos  # noqa: E402
from app.reportes._comun.salidas import Volcador  # noqa: E402
from app.reportes.descarga_facturas import motor  # noqa: E402
from app.reportes.descarga_facturas.reporte import REPORTE  # noqa: E402

try:
    from openpyxl.utils.exceptions import InvalidFileException
except ImportError:  # pragma: no cover
    InvalidFileException = ValueError

ESPERABLES = (ValueError, RuntimeError, InvalidFileException)


def _tramos(entradas, clave):
    """Rutas de la entrada ordenadas por el nombre original (en el server se guardan como <sha8>-<nombre>)."""
    lista = list(entradas.get(clave) or [])
    por_nombre = {}
    for e in lista:
        por_nombre.setdefault(e['nombre'], []).append(e)
    ordenadas = [por_nombre[p.name].pop(0) for p in ordenar_tramos([e['nombre'] for e in lista])]
    rutas = [Path(e['ruta']) for e in ordenadas]
    nombres = {Path(e['ruta']): e['nombre'] for e in ordenadas}
    return rutas, nombres


def correr(trabajo, simular=None):
    trabajo = Path(trabajo)
    parametros = json.loads((trabajo / 'parametros.json').read_text(encoding='utf-8'))
    entradas = json.loads((trabajo / 'entradas.json').read_text(encoding='utf-8'))
    listados, nombres = _tramos(entradas, 'listado')
    if not listados:
        raise ValueError('Falta el listado de facturas (Excel con CUIT y número).')
    parametros = dict(parametros)
    parametros.setdefault('sesion_chrome', str(trabajo / 'sesion_chrome'))
    salida = trabajo / 'salidas'
    fabrica = None
    if simular:
        sitio = str(parametros.get('origen', '')).rstrip('/') + '/' + str(parametros.get('sitio', '')).strip('/')
        fabrica = motor.navegador_simulado(simular, sitio)
    resultado = motor.ejecutar(listados, salida, parametros, informar=protocolo, fabrica_navegador=fabrica, nombres=nombres)
    with Volcador(trabajo / 'resultados.sqlite') as volcador:
        for s in REPORTE['salidas']:
            columnas = motor.COLUMNAS_DESCARGA if s['tabla'] == 'descarga' else motor.COLUMNAS_REVISAR
            volcador.tabla(s['tabla'], columnas, resultado[s['tabla']], s['clave'], titulo=s['titulo'])
    protocolo.resumen(resultado['resumen'])
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=REPORTE['nombre'])
    parser.add_argument('--trabajo', required=True)
    parser.add_argument('--simular', default=None)
    args = parser.parse_args(argv)
    try:
        return correr(args.trabajo, args.simular)
    except protocolo.Cancelado:
        protocolo.log('Cancelado por el usuario.')
        return 2
    except ESPERABLES as exc:
        protocolo.error(str(exc))
        return 1


if __name__ == '__main__':
    sys.exit(main())
