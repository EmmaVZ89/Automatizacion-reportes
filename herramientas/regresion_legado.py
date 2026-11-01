"""Regresión contra el legado: corre el script original (legado/) y el motor nuevo (app/reportes/) sobre
los mismos archivos de entrada y compara las salidas. Imprime SIN DIFERENCIAS o la primera diferencia
de cada archivo, y sale con 0 o 1.

    py herramientas/regresion_legado.py conciliacion_general --entradas <carpeta> --alcance abiertos --corte 2026-10-31
    py herramientas/regresion_legado.py controles_sga --entradas <carpeta> --corte 2026-10-31
    py herramientas/regresion_legado.py control_mora --entradas <carpeta>
    py herramientas/regresion_legado.py control_cheques --entradas <carpeta>
    py herramientas/regresion_legado.py <reporte> --solo-comparar <carpeta_legado> <carpeta_nuevo>

Los archivos de entrada se reconocen por sus encabezados (igual que en la herramienta). Las salidas van a
--salida (por defecto una carpeta temporal) y se conservan para mirarlas."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'vendor'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import catalogo  # noqa: E402
from app.reportes._comun import detectores  # noqa: E402
from app.reportes._comun.entradas import ordenar_tramos  # noqa: E402

LEGADO = RAIZ / 'legado'
RE_SELLO = re.compile(r'\d{8}_\d{6}(?:_\d{6})?')
IGNORAR_JSON = {'conciliacion_general': {'fecha_descarga', 'archivo', 'version'}, 'controles_sga': {'archivo', 'archivos'}}
IGNORAR_LINEAS = {'control_cheques': ('SGA:', 'ERP:')}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def clasificar(carpeta):
    """{tipo: [rutas]} de los .xlsx de la carpeta, por encabezados."""
    tipos = {}
    for p in sorted(Path(carpeta).iterdir()):
        if p.suffix.lower() not in ('.xlsx', '.xlsm') or p.name.startswith('~$'):
            continue
        t = detectores.reconocer(p)
        if t:
            tipos.setdefault(t, []).append(p)
    return tipos


def entradas_para(codigo, tipos):
    d = catalogo.obtener(codigo)
    salida = {}
    for e in d['entradas']:
        rutas = tipos.get(e['tipo'], [])
        if len(rutas) < e.get('minimo', 1):
            raise SystemExit(f'Falta un archivo de tipo {e["tipo"]} para {e["titulo"]} en la carpeta de entradas.')
        salida[e['clave']] = [str(p) for p in ordenar_tramos(rutas)]
    return salida


def correr(comando, cwd, env=None, entrada=None):
    e = dict(os.environ)
    e['PYTHONPATH'] = str(RAIZ / 'vendor') + os.pathsep + str(RAIZ)
    e['PYTHONIOENCODING'] = 'utf-8'
    e.pop('REPORTES_PROTOCOLO', None)
    e.update(env or {})
    t = time.time()
    r = subprocess.run(comando, cwd=str(cwd), env=e, input=entrada, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        raise SystemExit(f'Falló: {" ".join(str(c) for c in comando)}')
    return time.time() - t


def unica_subcarpeta(base):
    sub = [p for p in Path(base).iterdir() if p.is_dir()]
    return sub[0] if len(sub) == 1 else Path(base)


def correr_legado(codigo, entradas, parametros, salida):
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    if codigo == 'conciliacion_general':
        base = salida / 'base'
        base.mkdir(exist_ok=True)
        (base / 'configuracion.json').write_text(json.dumps({'fondo': parametros['fondo']}), encoding='utf-8')
        fuentes = salida / 'fuentes'
        fuentes.mkdir(exist_ok=True)
        for rutas in entradas.values():
            for r in rutas:
                destino = fuentes / Path(r).name
                if not destino.exists():
                    os.link(r, destino) if Path(r).drive == destino.drive else shutil.copy2(r, destino)
        seg = correr([py, str(LEGADO / 'conciliacion_general' / 'conciliar.py'), '--base', str(base), '--fuentes', str(fuentes), '--alcance', parametros['alcance'], '--corte', parametros['corte']], LEGADO / 'conciliacion_general')
        return unica_subcarpeta(base / 'resultados'), seg
    if codigo == 'controles_sga':
        if len(entradas['sga']) != 1:
            raise SystemExit('El legado de Controles SGA admite un solo archivo.')
        seg = correr([py, str(LEGADO / 'controles_sga' / 'control_sga.py'), entradas['sga'][0], '--corte', parametros['corte'], '--salida', str(salida / 'sal')], LEGADO / 'controles_sga')
        return unica_subcarpeta(salida / 'sal'), seg
    if codigo == 'control_mora':
        ent = salida / 'entrada'
        ent.mkdir(exist_ok=True)
        for clave, prefijo in (('erp', 'Saldo de comprobación'), ('sga', 'ReporteHistoricoDeCuentaCorriente')):
            if len(entradas[clave]) != 1:
                raise SystemExit('El legado de Control de Mora admite un solo archivo por lado.')
            origen = Path(entradas[clave][0])
            nombre = origen.name if origen.name.startswith(prefijo) else prefijo + ' ' + origen.name
            shutil.copy2(origen, ent / nombre)
        guion = f"import sys; sys.path.insert(0, r'{LEGADO / 'control_mora'}'); import control_mora; control_mora.ejecutar(r'{ent}', r'{salida / 'sal'}')"
        seg = correr([py, '-c', guion], LEGADO / 'control_mora')
        return unica_subcarpeta(salida / 'sal'), seg
    if codigo == 'control_cheques':
        if len(entradas['sga']) != 1 or len(entradas['erp']) != 1:
            raise SystemExit('El legado de Control de cheques admite un solo archivo por lado.')
        seg = correr([py, str(LEGADO / 'control_cheques' / 'control_cheques.py'), '--sga', entradas['sga'][0], '--erp', entradas['erp'][0], '--salida', str(salida / 'sal')], LEGADO / 'control_cheques')
        return unica_subcarpeta(salida / 'sal'), seg
    raise SystemExit('Ese reporte no tiene regresión contra el legado.')


def correr_nuevo(codigo, entradas, parametros, salida):
    trabajo = Path(salida) / 'trabajo'
    trabajo.mkdir(parents=True, exist_ok=True)
    (trabajo / 'parametros.json').write_text(json.dumps(parametros, ensure_ascii=False, indent=2), encoding='utf-8')
    (trabajo / 'entradas.json').write_text(json.dumps({k: [{'ruta': r, 'nombre': Path(r).name, 'sha256': sha(r)} for r in v] for k, v in entradas.items()}, ensure_ascii=False, indent=2), encoding='utf-8')
    (trabajo / 'salidas').mkdir(exist_ok=True)
    seg = correr(catalogo.interprete(codigo, RAIZ) + ['--trabajo', str(trabajo)], RAIZ, env={'REPORTES_PROTOCOLO': '1'})
    return trabajo / 'salidas', seg


def _normalizar_texto(texto, codigo):
    lineas = []
    for l in texto.replace('\r\n', '\n').split('\n'):
        if any(l.startswith(p) for p in IGNORAR_LINEAS.get(codigo, ())):
            continue
        lineas.append(RE_SELLO.sub('<sello>', l))
    return '\n'.join(lineas)


def _normalizar_json(obj, ignorar):
    if isinstance(obj, dict):
        return {k: _normalizar_json(v, ignorar) for k, v in obj.items() if k not in ignorar}
    if isinstance(obj, list):
        return [_normalizar_json(v, ignorar) for v in obj]
    return obj


def _comparar_xlsx(a, b):
    import openpyxl
    la = openpyxl.load_workbook(a, read_only=True)
    lb = openpyxl.load_workbook(b, read_only=True)
    try:
        if la.sheetnames != lb.sheetnames:
            return [f'hojas distintas: {la.sheetnames} vs {lb.sheetnames}']
        for nombre in la.sheetnames:
            fa = la[nombre].iter_rows(values_only=True)
            fb = lb[nombre].iter_rows(values_only=True)
            n = 0
            while True:
                ra = next(fa, None)
                rb = next(fb, None)
                n += 1
                if ra is None and rb is None:
                    break
                ra = tuple(v for v in (ra or ())) or ()
                rb = tuple(v for v in (rb or ())) or ()
                if (ra or None) != (rb or None):
                    ra_, rb_ = list(ra) + [None] * (len(rb) - len(ra)), list(rb) + [None] * (len(ra) - len(rb))
                    for i, (x, y) in enumerate(zip(ra_, rb_)):
                        if x != y:
                            return [f'hoja {nombre} fila {n} columna {i + 1}: {x!r} vs {y!r}']
        return []
    finally:
        la.close()
        lb.close()


SERVICIOS = 'Control_Servicios_Administrativos'
# Cambios acordados con quien usa los reportes (31/10/2026); se verifican explicando cada diferencia.
COLUMNAS_NUEVAS_CHEQUES = ('Fecha', 'Fecha de depósito')


def _filas_xlsx(ruta, hojas, desde=6):
    import openpyxl
    libro = openpyxl.load_workbook(ruta, read_only=True)
    try:
        return {h: [tuple(f) for f in libro[h].iter_rows(min_row=desde, values_only=True) if any(v is not None for v in f)]
                for h in hojas if h in libro.sheetnames}, list(libro.sheetnames)
    finally:
        libro.close()


def _comparar_servicios(a, b):
    """Servicios administrativos por mes: toda fila del legado (Año en curso + Histórico) está una vez en las solapas
    nuevas, y las de más (las futuras, que el legado omitía) están en No exigibles."""
    viejas, _ = _filas_xlsx(a, ('Año en curso', 'Histórico'))
    nuevas, hojas = _filas_xlsx(b, ('Mes en curso', 'No exigibles', 'Histórico'))
    if hojas != ['Mes en curso', 'No exigibles', 'Histórico']:
        return [f'hojas esperadas Mes en curso / No exigibles / Histórico; hay {hojas}']
    legado = [f for filas in viejas.values() for f in filas]
    todas = [f for filas in nuevas.values() for f in filas]
    diferencias = [f'fila del legado ausente o repetida: {f}' for f in set(legado) if todas.count(f) != legado.count(f)]
    diferencias += [f'fila nueva fuera de No exigibles: {f}' for f in todas if f not in legado and f not in nuevas['No exigibles']]
    return diferencias[:20]


def _comparar_cheques(a, b):
    """Cheques para revisar: igual al legado sin las columnas nuevas Fecha y Fecha de depósito."""
    import csv
    def leer(ruta, quitar=()):
        with Path(ruta).open(encoding='utf-8-sig', newline='') as f:
            filas = list(csv.reader(f, delimiter=';'))
        if not filas:
            return filas
        quedan = [i for i, c in enumerate(filas[0]) if c not in quitar]
        return [[f[i] if i < len(f) else '' for i in quedan] for f in filas]
    va, vb = leer(a), leer(b, COLUMNAS_NUEVAS_CHEQUES)
    if va == vb:
        return []
    for n, (x, y) in enumerate(zip(va, vb), 1):
        if x != y:
            return [f'fila {n}: {x} vs {y}']
    return [f'cantidad de filas: {len(va)} vs {len(vb)}']


def comparar_conciliacion(a, b, alcance):
    """Conciliación general v1.5: las diferencias con el legado tienen que estar explicadas por los cambios
    acordados (herramientas/cambios_conciliacion.py). Devuelve (no_explicadas, explicadas)."""
    import cambios_conciliacion as cc
    a, b = Path(a), Path(b)
    csv_l = next(a.rglob('Conciliacion_general.csv'))
    csv_n = next(b.rglob('Conciliacion_general.csv'))
    no_explicadas, explicadas = cc.explicar(csv_l, csv_n, alcance or 'abiertos')
    datos_n, _ = cc.leer_csv(csv_n)
    pendientes = sum(1 for r in datos_n if r['Tipo'] == 'PENDIENTE')
    no_explicadas += cc.explicar_resumen(next(a.rglob('Resumen.json')), next(b.rglob('Resumen.json')), pendientes, datos_n)
    no_explicadas += cc.xlsx_consistente(next(b.rglob('Conciliacion_general.xlsx')), csv_n)
    return no_explicadas, explicadas


def comparar_carpetas(a, b, codigo='', alcance=None):
    a, b = Path(a), Path(b)
    if codigo == 'conciliacion_general':
        no_explicadas, explicadas = comparar_conciliacion(a, b, alcance)
        if explicadas:
            print('Cambios v1.5 explicados por las reglas nuevas:')
            for k, v in sorted(explicadas.items()):
                print(f'  {k}: {v}')
        return no_explicadas
    diferencias = []
    archivos_a = sorted(p for p in a.rglob('*') if p.is_file() and p.suffix.lower() not in ('.sqlite',) and p.name != 'COMPLETADO.txt')
    for pa in archivos_a:
        rel = pa.relative_to(a)
        candidatos = [b / rel] + list(b.rglob(pa.name))
        pb = next((c for c in candidatos if c.is_file()), None)
        if pb is None:
            diferencias.append(f'{rel}: no existe en {b}')
            continue
        if codigo == 'controles_sga' and pa.name == SERVICIOS + '.xlsx':
            diferencias.extend(f'{rel}: {d}' for d in _comparar_servicios(pa, pb))
        elif codigo == 'control_cheques' and pa.name == 'Cheques_para_revisar.csv':
            diferencias.extend(f'{rel}: {d}' for d in _comparar_cheques(pa, pb))
        elif pa.suffix.lower() == '.xlsx':
            diferencias.extend(f'{rel}: {d}' for d in _comparar_xlsx(pa, pb))
        elif pa.suffix.lower() == '.json':
            ignorar = IGNORAR_JSON.get(codigo, set())
            ja = _normalizar_json(json.loads(pa.read_text(encoding='utf-8-sig')), ignorar)
            jb = _normalizar_json(json.loads(pb.read_text(encoding='utf-8-sig')), ignorar)
            if codigo == 'controles_sga' and pa.name == 'ejecucion.json':
                # Servicios por mes: cambian sus cantidades por solapa y ya no hay futuros omitidos.
                for j in (ja, jb):
                    for clave in ('salidas', 'solapas', 'futuros_no_exigibles_omitidos'):
                        if isinstance(j.get(clave), dict):
                            j[clave].pop(SERVICIOS, None)
            if ja != jb:
                diferencias.append(f'{rel}: JSON distinto')
        else:
            ta = _normalizar_texto(pa.read_text(encoding='utf-8-sig', errors='replace'), codigo)
            tb = _normalizar_texto(pb.read_text(encoding='utf-8-sig', errors='replace'), codigo)
            if ta != tb:
                la, lb = ta.split('\n'), tb.split('\n')
                for i, (x, y) in enumerate(zip(la, lb), 1):
                    if x != y:
                        diferencias.append(f'{rel}: línea {i}: {x[:120]!r} vs {y[:120]!r}')
                        break
                else:
                    diferencias.append(f'{rel}: distinta cantidad de líneas ({len(la)} vs {len(lb)})')
    return diferencias


def main(argv=None):
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description='Regresión contra el legado')
    p.add_argument('reporte', choices=['conciliacion_general', 'controles_sga', 'control_mora', 'control_cheques'])
    p.add_argument('--entradas', help='Carpeta con los archivos de entrada (se reconocen por encabezados)')
    p.add_argument('--corte')
    p.add_argument('--alcance', choices=['abiertos', 'completo'])
    p.add_argument('--salida', help='Carpeta donde dejar las corridas (default: temporal)')
    p.add_argument('--solo-comparar', nargs=2, metavar=('LEGADO', 'NUEVO'))
    args = p.parse_args(argv)
    catalogo.cargar()
    if args.solo_comparar:
        dif = comparar_carpetas(args.solo_comparar[0], args.solo_comparar[1], args.reporte, args.alcance)
    else:
        if not args.entradas:
            p.error('Indicá --entradas o --solo-comparar.')
        tipos = clasificar(args.entradas)
        entradas = entradas_para(args.reporte, tipos)
        parametros = catalogo.parametros_default(args.reporte, {})
        if args.corte:
            parametros['corte'] = args.corte
        if args.alcance:
            parametros['alcance'] = args.alcance
        parametros = catalogo.validar_parametros(args.reporte, parametros)
        salida = Path(args.salida) if args.salida else Path(tempfile.mkdtemp(prefix='regresion_'))
        print('Entradas:')
        for clave, rutas in entradas.items():
            for r in rutas:
                print(f'  {clave}: {Path(r).name}  sha256={sha(r)[:16]}...')
        print('Corriendo el legado...', flush=True)
        dir_legado, seg_legado = correr_legado(args.reporte, entradas, parametros, salida / 'legado')
        print(f'  {seg_legado:.0f} s -> {dir_legado}')
        print('Corriendo el motor nuevo...', flush=True)
        dir_nuevo, seg_nuevo = correr_nuevo(args.reporte, entradas, parametros, salida / 'nuevo')
        print(f'  {seg_nuevo:.0f} s -> {dir_nuevo}')
        dif = comparar_carpetas(dir_legado, dir_nuevo, args.reporte, parametros.get('alcance'))
    if dif:
        print('DIFERENCIAS:')
        for d in dif:
            print('  ' + d)
        return 1
    print('SIN DIFERENCIAS NO EXPLICADAS' if args.reporte == 'conciliacion_general' else 'SIN DIFERENCIAS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
