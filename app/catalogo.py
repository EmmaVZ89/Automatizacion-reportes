"""Catálogo de reportes: carga app/reportes/<codigo>/reporte.py, informa disponibilidad (los que
necesitan el .venv de facturas), arma los parámetros por defecto y los valida."""
import importlib
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_REPORTES = Path(__file__).resolve().parent / 'reportes'
TIPOS = ('fecha', 'texto', 'opcion', 'lista', 'booleano', 'tabla', 'ruta', 'decimal')
CAMPOS_OBLIGATORIOS = ('codigo', 'nombre', 'descripcion', 'entradas', 'parametros', 'salidas', 'requiere')
_RE_FECHA = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_RE_DECIMAL = re.compile(r'^-?\d+(?:[.,]\d+)?$')

REPORTES = {}
_INTERPRETES_PRUEBA = {}


def _validar_definicion(d):
    for campo in CAMPOS_OBLIGATORIOS:
        if campo not in d:
            raise ValueError(f'Reporte {d.get("codigo")!r}: falta {campo!r}')
    for e in d['entradas']:
        for campo in ('clave', 'titulo', 'detectar'):
            if campo not in e:
                raise ValueError(f'Reporte {d["codigo"]}: entrada sin {campo!r}')
    for p in d['parametros']:
        if p.get('tipo') not in TIPOS:
            raise ValueError(f'Reporte {d["codigo"]}: parámetro {p.get("clave")!r} con tipo {p.get("tipo")!r}')
    for s in d['salidas']:
        for campo in ('tabla', 'titulo', 'clave'):
            if campo not in s:
                raise ValueError(f'Reporte {d["codigo"]}: salida sin {campo!r}')
    return d


def cargar():
    REPORTES.clear()
    for carpeta in sorted(DIR_REPORTES.iterdir()):
        if not carpeta.is_dir() or carpeta.name.startswith('_') or not (carpeta / 'reporte.py').exists():
            continue
        modulo = importlib.import_module(f'app.reportes.{carpeta.name}.reporte')
        definicion = _validar_definicion(dict(modulo.REPORTE))
        definicion['carpeta'] = carpeta
        REPORTES[definicion['codigo']] = definicion
    ordenados = sorted(REPORTES.values(), key=lambda d: (d.get('orden', 99), d['codigo']))
    REPORTES.clear()
    for d in ordenados:
        REPORTES[d['codigo']] = d
    return REPORTES


def registrar_para_pruebas(codigo, definicion, interprete):
    """Un reporte que sólo existe en los tests (motor falso)."""
    d = _validar_definicion(dict(definicion))
    d['carpeta'] = None
    REPORTES[codigo] = d
    _INTERPRETES_PRUEBA[codigo] = list(interprete)


def obtener(codigo):
    if not REPORTES:
        cargar()
    if codigo not in REPORTES:
        raise KeyError('No existe ese reporte.')
    return REPORTES[codigo]


def ruta_venv(raiz=RAIZ):
    return Path(raiz) / '.venv' / 'Scripts' / 'python.exe'


def disponibilidad(codigo, raiz=RAIZ, probar=True):
    d = obtener(codigo)
    if d['requiere'] != 'venv_facturas':
        return {'disponible': True, 'motivo': ''}
    python = ruta_venv(raiz)
    if not python.exists():
        return {'disponible': False, 'motivo': 'Necesita una instalación aparte: ejecutá "Instalar descarga de facturas.bat" una vez.'}
    if probar:
        try:
            r = subprocess.run([str(python), '-c', 'import playwright, pdfplumber'], capture_output=True, timeout=60,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if r.returncode != 0:
                return {'disponible': False, 'motivo': 'La instalación está incompleta: volvé a ejecutar "Instalar descarga de facturas.bat".'}
        except (OSError, subprocess.TimeoutExpired):
            return {'disponible': False, 'motivo': 'No se pudo comprobar la instalación de la descarga de facturas.'}
    return {'disponible': True, 'motivo': ''}


def interprete(codigo, raiz=RAIZ):
    if codigo in _INTERPRETES_PRUEBA:
        return list(_INTERPRETES_PRUEBA[codigo])
    d = obtener(codigo)
    if d['requiere'] == 'venv_facturas':
        return [str(ruta_venv(raiz)), '-I', str(d['carpeta'] / 'ejecutar.py')]
    return [sys.executable, '-I', str(d['carpeta'] / 'ejecutar.py')]


def parametros_default(codigo, configuracion=None, cierre=None):
    d = obtener(codigo)
    guardados = ((configuracion or {}).get('reportes', {}).get(codigo, {}) or {}).get('parametros', {}) or {}
    valores = {}
    for p in d['parametros']:
        if p['clave'] in guardados and not p.get('no_persistir'):
            valores[p['clave']] = guardados[p['clave']]
        elif p.get('default_cierre') and cierre and cierre.get(p['default_cierre']):
            valores[p['clave']] = cierre[p['default_cierre']]
        else:
            valores[p['clave']] = p.get('default')
    return valores


def _error(p, mensaje):
    return ValueError(f'{p.get("titulo", p["clave"])}: {mensaje}')


def validar_parametros(codigo, valores):
    """Normaliza y valida; devuelve sólo los parámetros definidos."""
    d = obtener(codigo)
    valores = valores or {}
    salida = {}
    for p in d['parametros']:
        v = valores.get(p['clave'], p.get('default'))
        tipo = p['tipo']
        obligatorio = p.get('obligatorio', False)
        if v is None or v == '' or v == []:
            if obligatorio:
                raise _error(p, 'es obligatorio.')
            salida[p['clave']] = [] if tipo in ('lista', 'tabla') else (False if tipo == 'booleano' else None)
            continue
        if tipo == 'fecha':
            v = str(v).strip()
            if not _RE_FECHA.match(v):
                raise _error(p, 'la fecha tiene que ser AAAA-MM-DD.')
            try:
                date.fromisoformat(v)
            except ValueError:
                raise _error(p, 'no es una fecha válida.')
        elif tipo == 'texto' or tipo == 'ruta':
            v = str(v).strip()
            if len(v) > 1000:
                raise _error(p, 'es demasiado largo.')
        elif tipo == 'opcion':
            v = str(v)
            if v not in [o['valor'] for o in p['opciones']]:
                raise _error(p, 'no es una opción válida.')
        elif tipo == 'lista':
            if isinstance(v, str):
                v = [x.strip() for x in re.split(r'[\n;]', v) if x.strip()]
            if not isinstance(v, list):
                raise _error(p, 'tiene que ser una lista.')
            v = [str(x).strip() for x in v if str(x).strip()]
            if p.get('opciones'):
                permitidas = [o['valor'] for o in p['opciones']]
                malas = [x for x in v if x not in permitidas]
                if malas:
                    raise _error(p, 'incluye valores no válidos: ' + ', '.join(malas))
        elif tipo == 'booleano':
            v = v in (True, 'true', 'True', '1', 1, 'sí', 'si')
        elif tipo == 'tabla':
            if not isinstance(v, list) or not all(isinstance(x, dict) for x in v):
                raise _error(p, 'tiene que ser una tabla.')
            columnas = [c['clave'] for c in p['columnas']]
            v = [{c: (x.get(c) if isinstance(x.get(c), bool) else str(x.get(c, '') or '').strip()) for c in columnas} for x in v]
        elif tipo == 'decimal':
            v = str(v).strip().replace(',', '.')
            if not _RE_DECIMAL.match(v):
                raise _error(p, 'tiene que ser un número.')
        salida[p['clave']] = v
    return salida


def entradas_de(codigo):
    return obtener(codigo)['entradas']


def descripcion_publica(codigo, raiz=RAIZ, probar=True):
    d = obtener(codigo)
    disp = disponibilidad(codigo, raiz, probar)
    return {'codigo': d['codigo'], 'nombre': d['nombre'], 'descripcion': d['descripcion'], 'disponible': disp['disponible'], 'motivo': disp['motivo'],
            'entradas': [{k: v for k, v in e.items() if k != 'detectar'} for e in d['entradas']],
            'parametros': d['parametros'], 'salidas': d['salidas'], 'pausas': d.get('pausas', []), 'ayuda': d.get('ayuda', ''),
            'ambito': d.get('ambito', 'cierre'), 'icono': d.get('icono', 'reporte')}
