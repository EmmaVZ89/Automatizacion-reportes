"""Arranque de la herramienta: carpeta de datos, instancia única, navegador y apagado.

    python -m app.arranque [--sin-navegador] [--puerto N] [--datos CARPETA] [--consola]

Si ya hay una instancia viva (datos/.servidor.json responde), sólo abre el navegador en ella.
Con --reinicio TOKEN (lo usa "Reiniciar la herramienta"): espera a que la instancia anterior se apague y arranca con
ese token y en ese puerto, para que la pantalla abierta siga funcionando."""
import argparse
import json
import os
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ / 'vendor') not in sys.path:
    sys.path.insert(0, str(RAIZ / 'vendor'))
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app.servidor import crear_servidor, PUERTO_INICIAL, INTENTOS_PUERTO  # noqa: E402
from app.almacen import escribir_json_atomico, leer_json  # noqa: E402

ARCHIVO_INSTANCIA = '.servidor.json'


def dir_datos(explicita=None):
    if explicita:
        return Path(explicita)
    if os.environ.get('REPORTES_DATOS'):
        return Path(os.environ['REPORTES_DATOS'])
    base = os.environ.get('LOCALAPPDATA') or str(Path.home())
    return Path(base) / 'ReportesDeCierre' / 'datos'


def instancia_viva(carpeta, timeout=2.0):
    info = leer_json(Path(carpeta) / ARCHIVO_INSTANCIA, None)
    if not isinstance(info, dict) or not info.get('puerto') or not info.get('token'):
        return None
    url = f'http://127.0.0.1:{info["puerto"]}/api/estado?t={info["token"]}'
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            if r.status == 200:
                datos = json.loads(r.read().decode('utf-8'))
                return {**info, 'estado': datos}
    except Exception:
        return None
    return None


def abrir_navegador(url):
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main(argv=None, abrir=abrir_navegador, bloquear=True, inactividad_segundos=3 * 3600):
    p = argparse.ArgumentParser(description='Reportes de cierre')
    p.add_argument('--sin-navegador', action='store_true')
    p.add_argument('--puerto', type=int, default=PUERTO_INICIAL)
    p.add_argument('--datos')
    p.add_argument('--consola', action='store_true')
    p.add_argument('--reinicio', help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    carpeta = dir_datos(args.datos)
    carpeta.mkdir(parents=True, exist_ok=True)
    if args.reinicio:
        for _ in range(100):  # hasta 20 s a que se apague la anterior
            if not instancia_viva(carpeta, timeout=0.5):
                break
            time.sleep(0.2)
    viva = instancia_viva(carpeta)
    if viva:
        url = f'http://127.0.0.1:{viva["puerto"]}/?t={viva["token"]}'
        if args.consola:
            print(f'La herramienta ya está abierta en {url}')
        if not args.sin_navegador:
            abrir(url)
        return 0 if bloquear else None
    archivo = carpeta / ARCHIVO_INSTANCIA

    def al_cerrar():
        try:
            if leer_json(archivo, {}).get('pid') == os.getpid():
                archivo.unlink()
        except OSError:
            pass
    servidor = None
    if args.reinicio:
        for _ in range(25):  # el mismo puerto, apenas lo suelte la instancia anterior
            try:
                servidor = crear_servidor(carpeta, puerto_inicial=args.puerto, intentos=1, token=args.reinicio, inactividad_segundos=inactividad_segundos, al_cerrar=al_cerrar)
                break
            except OSError:
                time.sleep(0.4)
    if servidor is None:
        servidor = crear_servidor(carpeta, puerto_inicial=args.puerto, intentos=INTENTOS_PUERTO, token=args.reinicio, inactividad_segundos=inactividad_segundos, al_cerrar=al_cerrar)
    escribir_json_atomico(archivo, {'pid': os.getpid(), 'puerto': servidor.puerto, 'token': servidor.token, 'inicio': time.strftime('%Y-%m-%dT%H:%M:%S')})
    if args.consola:
        print(f'Reportes de cierre en {servidor.url_con_token}')
        print(f'Datos en {carpeta}')
    if not args.sin_navegador:
        abrir(servidor.url_con_token)
    if not bloquear:
        servidor.servir_en_hilo()
        return servidor
    servidor.servir()
    return 0


if __name__ == '__main__':
    sys.exit(main())
