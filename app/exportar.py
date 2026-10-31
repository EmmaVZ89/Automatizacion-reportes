"""Exportación de resultados trabajados (XLSX con Estado revisión y Observaciones), y exportación e
importación de un cierre completo (ZIP) para compartirlo con otra persona."""
import io
import json
import re
import tempfile
import zipfile
from pathlib import Path

from . import catalogo
from .almacen import leer_json
from .reportes._comun.salidas import Volcador
from .reportes._comun.xlsx_escritura import escribir_libro
from .tablas import Tablas

COL_ESTADO = 'Estado revisión'
COL_OBS = 'Observaciones'
TEXTO_ESTADO = {'pendiente': '', 'revisada': 'Revisada', 'omitida': 'Omitida'}


def _definiciones(e):
    try:
        d = catalogo.obtener(e['reporte'])
    except KeyError:
        return {}, {}
    return {s['tabla']: s for s in d['salidas']}, d


def _hoja_de_tabla(tablas, info, definicion, incluir_omitidas, nombre_hoja=None):
    columnas = list(info['columnas'])
    tipos = list(info['tipos'])
    rev = (definicion or {}).get('revision_en_libro') or {}
    i_estado = columnas.index(rev['estado']) if rev.get('estado') in columnas else None
    i_obs = columnas.index(rev['obs']) if rev.get('obs') in columnas else None
    if i_estado is None:
        columnas.append(COL_ESTADO)
        tipos.append('texto')
        i_estado = len(columnas) - 1
    if i_obs is None:
        columnas.append(COL_OBS)
        tipos.append('texto')
        i_obs = len(columnas) - 1
    resaltadas = set()
    filas = []
    for n, f in enumerate(tablas.filas_completas(info['tabla'], incluir_omitidas)):
        valores = list(f['valores'])
        while len(valores) < len(columnas):
            valores.append('')
        valores[i_estado] = TEXTO_ESTADO.get(f['_estado'], f['_estado'])
        valores[i_obs] = f['_obs']
        for col in f['_marcas']:
            if col in columnas:
                resaltadas.add((n, columnas.index(col)))
        filas.append(valores)
    titulo = (definicion or {}).get('titulo') or info['titulo']
    return {'nombre': (nombre_hoja or (definicion or {}).get('hoja') or titulo)[:31], 'titulo': titulo, 'columnas': columnas, 'tipos': tipos,
            'filas': filas, 'nota': 'Estado revisión y Observaciones se cargaron en la herramienta Reportes de cierre.' + ('' if incluir_omitidas else ' Las filas omitidas no se incluyen.'),
            'resaltadas': resaltadas}


def _bytes_de_libro(hojas):
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / 'salida.xlsx'
        escribir_libro(ruta, hojas)
        return ruta.read_bytes()


def exportar_tabla(dominio, e, tabla, incluir_omitidas=True):
    tablas = dominio.tablas(e['id'])
    info = next((t for t in tablas.listar() if t['tabla'] == tabla), None)
    if not info:
        raise ValueError('No existe esa tabla en los resultados.')
    defs, _ = _definiciones(e)
    hoja = _hoja_de_tabla(tablas, info, defs.get(tabla), incluir_omitidas)
    return _bytes_de_libro([hoja]), (defs.get(tabla, {}).get('archivo') or tabla + '.xlsx')


def exportar_libro(dominio, e, libro, incluir_omitidas=True):
    tablas = dominio.tablas(e['id'])
    defs, _ = _definiciones(e)
    lista = tablas.listar()
    hojas = []
    for s in defs.values():
        if s.get('archivo') != libro:
            continue
        info = next((t for t in lista if t['tabla'] == s['tabla']), None)
        if info:
            hojas.append(_hoja_de_tabla(tablas, info, s, incluir_omitidas))
    if not hojas:
        raise ValueError('Ese libro no tiene tablas en los resultados.')
    return _bytes_de_libro(hojas), libro


def exportar_cierre(dominio, cierre_id):
    """ZIP con el cierre, sus ejecuciones terminadas (la final de cada reporte, o la última), sus
    resúmenes, revisión y tablas trabajadas. Sin archivos de entrada ni sesiones."""
    c = dominio.obtener_cierre(cierre_id)
    if not c:
        raise ValueError('No existe ese cierre.')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        publico = {k: v for k, v in c.items() if k != 'archivos'}
        publico['archivos'] = [{k: a.get(k) for k in ('nombre', 'bytes', 'sha256', 'tipo', 'hoja', 'filas')} for a in c['archivos']]
        z.writestr('cierre.json', json.dumps(publico, ensure_ascii=False, indent=2))
        elegidas = {}
        for e in dominio.listar_ejecuciones(cierre_id):
            if e['estado'] != 'ok':
                continue
            actual = elegidas.get(e['reporte'])
            if actual is None or (e.get('final') and not actual.get('final')) or (e.get('final') == actual.get('final') and e['version'] > actual['version']):
                elegidas[e['reporte']] = e
        for e in elegidas.values():
            base = f'ejecuciones/{e["reporte"]}/'
            z.writestr(base + 'ejecucion.json', json.dumps(e, ensure_ascii=False, indent=2))
            rutas = dominio.rutas(e['id'])
            for clave in ('resumen', 'triage', 'parametros'):
                if rutas[clave].exists():
                    z.write(rutas[clave], base + rutas[clave].name)
            if rutas['registro'].exists():
                z.write(rutas['registro'], base + 'registro.log')
            tablas = dominio.tablas(e['id'])
            if tablas.existe():
                defs, _ = _definiciones(e)
                for info in tablas.listar():
                    hoja = _hoja_de_tabla(tablas, info, defs.get(info['tabla']), True, nombre_hoja=info['tabla'])
                    z.writestr(base + f'tablas/{info["tabla"]}.xlsx', _bytes_de_libro([hoja]))
    return buffer.getvalue()


def _leer_tabla_exportada(datos):
    import openpyxl
    libro = openpyxl.load_workbook(io.BytesIO(datos), read_only=True)
    hoja = libro.worksheets[0]
    filas = hoja.iter_rows(min_row=4, values_only=True)
    encabezado = [str(v) if v is not None else '' for v in next(filas)]
    cuerpo = [(['' if v is None else v for v in f] + [''] * len(encabezado))[:len(encabezado)] for f in filas if any(v is not None for v in f)]
    libro.close()
    return encabezado, cuerpo


def importar_cierre(dominio, datos_zip):
    try:
        z = zipfile.ZipFile(io.BytesIO(datos_zip))
        publico = json.loads(z.read('cierre.json').decode('utf-8'))
    except (zipfile.BadZipFile, KeyError, ValueError):
        raise ValueError('El archivo no es un cierre exportado por la herramienta.')
    periodo = str(publico.get('periodo', ''))
    c = dominio.crear_cierre(periodo, publico.get('corte', ''), publico.get('nombre', ''))
    dominio.editar_cierre(c['id'], notas=publico.get('notas', ''))
    with dominio._lock:
        cierre = dominio._buscar_cierre(c['id'])
        cierre['importado'] = True
        cierre['archivos'] = [{**a, 'id': f'imp_{i}', 'ruta': '', 'subido': publico.get('creado'), 'aviso': None, 'error': None} for i, a in enumerate(publico.get('archivos', []))]
        dominio._cierres.guardar()
    nombres = z.namelist()
    reportes = sorted({n.split('/')[1] for n in nombres if n.startswith('ejecuciones/') and n.count('/') >= 2})
    for reporte in reportes:
        base = f'ejecuciones/{reporte}/'
        try:
            original = json.loads(z.read(base + 'ejecucion.json').decode('utf-8'))
        except (KeyError, ValueError):
            continue
        e = dominio.crear_ejecucion(c['id'], reporte)
        rutas = dominio.rutas(e['id'])
        parametros = json.loads(z.read(base + 'parametros.json').decode('utf-8')) if base + 'parametros.json' in nombres else original.get('parametros', {})
        dominio.asignar_parametros(e['id'], parametros)
        resumen = json.loads(z.read(base + 'resumen.json').decode('utf-8')) if base + 'resumen.json' in nombres else original.get('resumen')
        if base + 'registro.log' in nombres:
            rutas['registro'].write_bytes(z.read(base + 'registro.log'))
        defs, _ = _definiciones({'reporte': reporte})
        tablas_zip = [n for n in nombres if n.startswith(base + 'tablas/') and n.endswith('.xlsx')]
        v = Volcador(rutas['sqlite'])
        marcas_pendientes = []
        for n in sorted(tablas_zip, key=lambda x: [s['tabla'] for s in defs.values()].index(Path(x).stem) if Path(x).stem in defs else 999):
            nombre = Path(n).stem
            if not re.match(r'^[a-z][a-z0-9_]*$', nombre):
                continue
            encabezado, cuerpo = _leer_tabla_exportada(z.read(n))
            d = defs.get(nombre, {})
            rev = d.get('revision_en_libro') or {}
            col_estado = rev.get('estado') if rev.get('estado') in encabezado else COL_ESTADO
            col_obs = rev.get('obs') if rev.get('obs') in encabezado else COL_OBS
            i_estado = encabezado.index(col_estado) if col_estado in encabezado else None
            i_obs = encabezado.index(col_obs) if col_obs in encabezado else None
            quitar = {i for i in (i_estado, i_obs) if i is not None and encabezado[i] in (COL_ESTADO, COL_OBS)}
            columnas = [h for i, h in enumerate(encabezado) if i not in quitar]
            filas = [[x for i, x in enumerate(f) if i not in quitar] for f in cuerpo]
            clave = [k for k in d.get('clave', []) if k in columnas] or columnas[:1]
            v.tabla(nombre, columnas, filas, clave, titulo=d.get('titulo', nombre))
            for idx, f in enumerate(cuerpo):
                estado = str(f[i_estado]).strip().casefold() if i_estado is not None else ''
                obs = str(f[i_obs]) if i_obs is not None else ''
                if estado or obs:
                    marcas_pendientes.append((nombre, idx, {'revisada': 'revisada', 'omitida': 'omitida'}.get(estado, 'pendiente'), obs))
        v.cerrar()
        t = Tablas(rutas['sqlite'])
        por_tabla = {}
        for nombre, idx, estado, obs in marcas_pendientes:
            por_tabla.setdefault((nombre, estado, obs), []).append(idx)
        for (nombre, estado, obs), idxs in por_tabla.items():
            t.marcar(nombre, idxs, estado, obs, origen='importado')
        dominio.actualizar_estado(e['id'], 'ok', resumen=resumen, salidas=[{k: val for k, val in s.items() if k != 'tipos'} for s in t.listar()], error=None)
        dominio.guardar_triage(e['id'])
        if original.get('final'):
            dominio.marcar_final(e['id'])
    return dominio.obtener_cierre(c['id'])
