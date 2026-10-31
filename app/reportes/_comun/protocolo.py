"""Lado motor del protocolo motor ↔ server: una línea JSON por evento en stdout, órdenes por stdin.

Si la variable REPORTES_PROTOCOLO no está (el script se corre a mano, por consola), `log` imprime
texto plano y `esperar` usa input(), así cada ejecutar.py sirve también fuera de la herramienta."""
import json
import os
import sys

ACTIVO = os.environ.get('REPORTES_PROTOCOLO') == '1'


class Cancelado(Exception):
    """El server pidió cancelar (o cerró la entrada) mientras el motor esperaba."""


def _emitir(objeto):
    sys.stdout.write(json.dumps(objeto, ensure_ascii=False, default=str) + '\n')
    sys.stdout.flush()


def log(mensaje):
    if ACTIVO:
        _emitir({'t': 'log', 'm': str(mensaje)})
    else:
        print(mensaje, flush=True)


def paso(titulo):
    if ACTIVO:
        _emitir({'t': 'paso', 'm': str(titulo)})
    else:
        print(f'== {titulo}', flush=True)


def progreso(valor, mensaje=''):
    if ACTIVO:
        _emitir({'t': 'progreso', 'v': max(0.0, min(1.0, float(valor))), 'm': str(mensaje)})
    elif mensaje:
        print(mensaje, flush=True)


def tabla(nombre, filas):
    if ACTIVO:
        _emitir({'t': 'tabla', 'tabla': nombre, 'filas': int(filas)})


def resumen(datos):
    if ACTIVO:
        _emitir({'t': 'resumen', 'datos': datos})


def error(mensaje):
    if ACTIVO:
        _emitir({'t': 'error', 'm': str(mensaje)})
    else:
        print(f'ERROR: {mensaje}', file=sys.stderr, flush=True)


def esperar(id, mensaje, boton='Continuar'):
    if not ACTIVO:
        input(f'{mensaje} [Enter para continuar] ')
        return
    _emitir({'t': 'esperar', 'id': id, 'm': str(mensaje), 'boton': boton})
    while True:
        linea = sys.stdin.readline()
        if not linea:
            raise Cancelado()
        try:
            orden = json.loads(linea)
        except ValueError:
            continue
        if orden.get('t') == 'cancelar':
            raise Cancelado()
        if orden.get('t') == 'continuar' and orden.get('id') == id:
            return


def preparar_salida():
    """Fuerza UTF-8 en stdout/stderr del subproceso (las consolas de Windows usan cp1252)."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


if ACTIVO:
    preparar_salida()
