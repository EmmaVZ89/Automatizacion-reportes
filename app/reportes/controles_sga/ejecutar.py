"""Punto de entrada del subproceso: `python -I ejecutar.py --trabajo <carpeta>`.
Lee parametros.json y entradas.json de la carpeta, corre el motor, escribe las salidas originales en
salidas/, vuelca una tabla por solapa a resultados.sqlite y emite el resumen por el protocolo."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
for _ruta in (RAIZ, RAIZ / 'vendor'):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

import argparse  # noqa: E402
import json  # noqa: E402
import zipfile  # noqa: E402
from datetime import date  # noqa: E402
from xml.etree import ElementTree as ET  # noqa: E402

from app.reportes._comun import protocolo  # noqa: E402
from app.reportes._comun.entradas import ordenar_tramos  # noqa: E402
from app.reportes._comun.salidas import Volcador  # noqa: E402
from app.reportes.controles_sga import motor  # noqa: E402
from app.reportes.controles_sga.reporte import LIBROS, SALIDAS  # noqa: E402

ERRORES_ESPERABLES = (ValueError, zipfile.BadZipFile, ET.ParseError, FileNotFoundError, PermissionError)


def tramos_ordenados(lista):
    """[(ruta, nombre)] ordenados por nombre original (en el server la ruta es <sha8>-<nombre>)."""
    por_nombre = {}
    for e in lista:
        por_nombre.setdefault(str(e['nombre']), []).append(Path(e['ruta']))
    salida = []
    for nombre in ordenar_tramos(list(por_nombre)):
        for ruta in por_nombre[nombre.name]:
            salida.append((ruta, nombre.name))
    return salida


def valor_mostrado(v, formato):
    """El valor tal como se ve en el Excel: fechas en texto ISO, importes como número, texto como texto."""
    if v is None:
        return None
    if formato == 'date' and isinstance(v, (int, float)) and not isinstance(v, bool):
        return motor.date(1899, 12, 30) + motor.timedelta(days=int(v))
    return v


def volcar(reports, parametros, ruta_sqlite):
    pedidas = parametros.get('salidas_a_generar') or list(LIBROS)
    libros = {r['name']: r for r in reports}
    with Volcador(ruta_sqlite) as v:
        for s in SALIDAS:
            if s['libro'] not in pedidas:
                continue
            hoja = next(h for h in libros[s['libro']]['sheets'] if h['name'] == s['hoja'])
            columnas = hoja['columns']
            filas = ([valor_mostrado(x, f) for x, f in zip(fila, hoja['formats'])] for fila in hoja['rows'])
            marcas = [(i, columnas[ci]) for i, ci in hoja['orange']]
            v.tabla(s['tabla'], columnas, filas, s['clave'], marcas, s['titulo'])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--trabajo', required=True)
    args = ap.parse_args(argv)
    trabajo = Path(args.trabajo)
    parametros = json.loads((trabajo / 'parametros.json').read_text(encoding='utf-8'))
    entradas = json.loads((trabajo / 'entradas.json').read_text(encoding='utf-8'))
    tramos = tramos_ordenados(entradas.get('sga') or [])
    if not tramos:
        protocolo.error('Falta el histórico de cuenta corriente de SGA.')
        return 1
    corte = parametros.get('corte')
    if not corte:
        protocolo.error('Falta la fecha de corte.')
        return 1
    try:
        corte = date.fromisoformat(str(corte)[:10])
    except ValueError:
        protocolo.error(f'La fecha de corte no es válida: {corte}')
        return 1
    salidas = trabajo / 'salidas'
    try:
        reports, rules, summary = motor.ejecutar([r for r, _ in tramos], salidas, corte, parametros, protocolo, nombres=[n for _, n in tramos])
        protocolo.paso('Volcando tablas de resultado')
        volcar(reports, parametros, trabajo / 'resultados.sqlite')
    except ERRORES_ESPERABLES as e:
        protocolo.error(str(e))
        return 1
    protocolo.resumen(summary | {'reglas_propuestas': rules})
    return 0


if __name__ == '__main__':
    sys.exit(main())
