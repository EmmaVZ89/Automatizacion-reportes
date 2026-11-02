"""Punto de entrada del subproceso de Conciliación general: `python -I ejecutar.py --trabajo <carpeta>`.

Lee <carpeta>/parametros.json y <carpeta>/entradas.json, corre el motor, deja las salidas originales en
<carpeta>/salidas/ y vuelca las dos tablas (resumen y general) a <carpeta>/resultados.sqlite."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
for _ruta in (RAIZ, RAIZ / 'vendor'):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

import argparse  # noqa: E402
import json  # noqa: E402
import sqlite3  # noqa: E402

from app.reportes._comun import protocolo  # noqa: E402
from app.reportes._comun.entradas import ordenar_tramos  # noqa: E402
from app.reportes._comun.salidas import Volcador  # noqa: E402
from app.reportes.conciliacion_general import excel, motor  # noqa: E402
from app.reportes.conciliacion_general.reporte import REPORTE  # noqa: E402


def tramos(lista):
    """Rutas de una entrada ordenadas por el nombre original (en el server el archivo se guarda como <sha8>-<nombre>)."""
    nombres = [e.get('nombre') or Path(e['ruta']).name for e in lista]
    orden = {str(p): i for i, p in enumerate(ordenar_tramos(nombres))}
    return [Path(e['ruta']) for _, e in sorted(zip(nombres, lista), key=lambda par: orden.get(par[0], len(orden)))]


def fechas_distintas(csv_path):
    """(fila, columna) de las fechas a pintar de anaranjado: el comprobante está en los dos sistemas con fechas
    distintas (en el cierre de octubre, 27 de 87.518)."""
    detalle = excel.filas_detalle(csv_path)
    cabecera = next(detalle)
    if 'Fecha SGA' not in cabecera:
        return []
    s, e = cabecera.index('Fecha SGA'), cabecera.index('Fecha ERP')
    return [(i, c) for i, fila in enumerate(detalle) if fila[s] and fila[e] and fila[s] != fila[e] for c in ('Fecha SGA', 'Fecha ERP')]


def _miles(n):
    return f'{n:,}'.replace(',', '.')


def _filas(n):
    return f'{_miles(n)} fila' + ('' if n == 1 else 's')


def informar_lectura(salidas):
    """Para el registro de la corrida, termine bien o con error: las filas que se tomaron de cada archivo con su
    rango de fechas (así se ve si dos tramos se superponen) y cuántos comprobantes salieron. Nunca corta la corrida."""
    respaldo = Path(salidas) / 'Respaldo_tecnico'
    try:
        por_archivo = []
        traza = respaldo / 'trazabilidad.sqlite'
        if traza.exists():
            con = sqlite3.connect(traza)
            try:
                por_archivo = con.execute("SELECT sistema, archivo, COUNT(*), MIN(NULLIF(fecha, '')), MAX(NULLIF(fecha, '')) FROM filas "
                                          'GROUP BY sistema, archivo ORDER BY MIN(rowid)').fetchall()
            finally:
                con.close()
        resumen = json.loads((respaldo / 'Resumen.json').read_text(encoding='utf-8')) if (respaldo / 'Resumen.json').exists() else {}
        fuentes = {f"{f.get('archivo')} [{f.get('hoja')}]": f for f in resumen.get('fuentes') or []}
        if not por_archivo and not resumen:
            return
        protocolo.log('Detalle de la lectura:')
        for sistema, archivo, filas, desde, hasta in por_archivo:
            f = fuentes.get(archivo) or {}
            texto = f'  {sistema} {archivo}: '
            if f.get('filas_archivo') is not None and f.get('filas_archivo') != filas:
                texto += f"{_filas(f['filas_archivo'])}, {_miles(filas)} tomada" + ('' if filas == 1 else 's')
            else:
                texto += _filas(filas) + (' tomada' if filas == 1 else ' tomadas')
            texto += f', fechas del {desde} al {hasta}' if desde else ', sin fechas'
            if f.get('tipos'):
                texto += ' (' + ', '.join(f'{t} {_miles(c)}' for t, c in f['tipos'].items()) + ')'
            protocolo.log(texto)
        if resumen.get('registros_datos') is not None:
            cantidad, capacidad = resumen['registros_datos'], excel.MAX_FILAS - 1
            protocolo.log(f'  Comprobantes de la conciliación: {_miles(cantidad)}' + (
                f'. No entran en una hoja de Excel (entran {_miles(capacidad)}): el detalle sigue en {-(-cantidad // capacidad)} hojas'
                if cantidad > capacidad else ''))
        for clave, cantidad in sorted((resumen.get('conteos') or {}).items()):
            protocolo.log(f'  Resultado {clave}: {_miles(cantidad)}')
    except (OSError, ValueError, sqlite3.Error) as e:
        protocolo.log(f'No se pudo armar el detalle de la lectura: {e}')


def volcar(salidas, ruta_sqlite):
    """Las mismas filas que van a las dos hojas del XLSX, leídas del CSV de respaldo."""
    csv_path = Path(salidas) / 'Respaldo_tecnico' / 'Conciliacion_general.csv'
    definiciones = {s['tabla']: s for s in REPORTE['salidas']}
    with Volcador(ruta_sqlite) as volcador:
        resumen = definiciones['resumen']
        volcador.tabla('resumen', excel.COLUMNAS_RESUMEN, excel.filas_resumen(csv_path), resumen['clave'], titulo=resumen['titulo'])
        general = definiciones['general']
        detalle = excel.filas_detalle(csv_path)
        columnas = next(detalle)
        volcador.tabla('general', columnas, detalle, general['clave'], marcas=fechas_distintas(csv_path), titulo=general['titulo'])


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--trabajo', required=True, type=Path)
    args = parser.parse_args(argv)
    trabajo = args.trabajo.resolve()
    parametros = json.loads((trabajo / 'parametros.json').read_text(encoding='utf-8-sig'))
    entradas = json.loads((trabajo / 'entradas.json').read_text(encoding='utf-8-sig'))
    defaults = {p['clave']: p.get('default') for p in REPORTE['parametros']}
    rutas = {clave: tramos(lista or []) for clave, lista in entradas.items()}
    salidas = trabajo / 'salidas'
    # Lo que haya dejado una corrida anterior en esta carpeta no entra en el detalle de ésta.
    for viejo in ('trazabilidad.sqlite', 'Resumen.json'):
        (salidas / 'Respaldo_tecnico' / viejo).unlink(missing_ok=True)
    try:
        try:
            resumen = motor.run(rutas, salidas, parametros.get('alcance'), parametros.get('corte') or None,
                                parametros.get('fondo') or defaults['fondo'], informar=protocolo)
        finally:
            informar_lectura(salidas)
    except ValueError as e:
        protocolo.error(str(e))
        return 1
    volcar(salidas, trabajo / 'resultados.sqlite')
    protocolo.resumen(resumen)
    return 0


if __name__ == '__main__':
    sys.exit(main())
