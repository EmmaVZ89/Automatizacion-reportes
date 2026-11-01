"""Server HTTP local: sirve la página (app/web), la API JSON y los eventos en vivo (SSE).
Escucha sólo en 127.0.0.1 y exige el token de la sesión en todo lo que no sea estático."""
import itertools
import json
import logging
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from . import catalogo
from .dominio import Dominio
from .eventos import Bus
from .rutas_api import Api, RespuestaHttp
from .seguridad import CABECERAS_BASE, cookie_de_token, nuevo_token, peticion_autorizada, ruta_y_query, host_de
from .trabajos import Trabajos
from .version import VERSION

RAIZ = Path(__file__).resolve().parent.parent
DIR_WEB = Path(__file__).resolve().parent / 'web'
PUERTO_INICIAL = 7310
INTENTOS_PUERTO = 11
TIPOS = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
         '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.woff2': 'font/woff2'}
PAGINA_403 = '''<!doctype html><html lang="es"><meta charset="utf-8"><title>Reportes de cierre</title>
<body style="font-family:Segoe UI,Arial,sans-serif;max-width:40em;margin:4em auto;line-height:1.5">
<h1>Abrí la herramienta desde su acceso directo</h1>
<p>Esta dirección sólo funciona cuando se abre desde el acceso directo <b>Reportes de cierre</b> de tu PC.
Cerrá esta pestaña y hacé doble clic en el acceso directo.</p></body></html>'''


class _BusConSincronizacion:
    """Reenvía los eventos de Trabajos al bus y mantiene el estado de la ejecución al día."""

    def __init__(self, bus, servidor):
        self.bus = bus
        self.servidor = servidor

    def emitir(self, tipo, datos):
        if tipo == 'trabajo':
            self.servidor.sincronizar_ejecucion(datos)
        self.bus.emitir(tipo, datos)


class Servidor:
    def __init__(self, dir_datos, raiz=RAIZ, puerto_inicial=PUERTO_INICIAL, intentos=INTENTOS_PUERTO, token=None,
                 probar_venv=True, inactividad_segundos=3 * 3600, al_cerrar=None):
        self.dir_datos = Path(dir_datos)
        self.raiz = Path(raiz)
        self.token = token or nuevo_token()
        self.instancia = nuevo_token()[:16]  # cambia en cada arranque (la pantalla sabe así que ya reinició)
        self.probar_venv = probar_venv
        self.inactividad_segundos = inactividad_segundos
        self.motivo_cierre = None  # queda en el registro al cerrar
        self._cierre_registrado = False
        self.al_cerrar = al_cerrar
        self.ultima_peticion = time.time()
        self.cerrando = False
        self.dir_datos.mkdir(parents=True, exist_ok=True)
        self.registro = self._registro()
        catalogo.cargar()
        self.dominio = Dominio(self.dir_datos)
        self.bus = Bus()
        self.trabajos = Trabajos(self.dir_datos / 'trabajos.json', _BusConSincronizacion(self.bus, self))
        self.trabajos.al_terminar(self.terminar_ejecucion)
        from .origenes import Origenes
        self.origenes = Origenes(self.dominio, self.registro, self.bus)
        self.firma_codigo = firma_codigo(self.raiz)
        self._marcar_interrumpidas()
        threading.Thread(target=self._refrescar_revisiones, daemon=True).start()
        self.api = Api(self)
        self.httpd = None
        self.puerto = None
        self._hilo = None
        self._abrir_puerto(puerto_inicial, intentos)

    _numero = itertools.count(1)

    def _registro(self):
        # Un nombre que no se repite: con id(self), un servidor nuevo podía heredar el registro de uno ya liberado y
        # escribir en la carpeta de otro.
        log = logging.getLogger(f'reportes.servidor.{next(Servidor._numero)}')
        log.setLevel(logging.INFO)
        log.propagate = False
        if not log.handlers:
            try:
                from logging.handlers import RotatingFileHandler
                h = RotatingFileHandler(self.dir_datos / 'servidor.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
                h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
                log.addHandler(h)
            except OSError:
                log.addHandler(logging.StreamHandler(sys.stderr))
        return log

    def _abrir_puerto(self, inicial, intentos):
        servidor = self
        ultimo_error = None

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            server_version = 'ReportesDeCierre'
            sys_version = ''

            def log_message(self, fmt, *args):
                servidor.registro.info('%s ' + fmt, self.client_address[0], *args)

            def do_GET(self):
                servidor.atender(self, 'GET')

            def do_POST(self):
                servidor.atender(self, 'POST')

            def do_PATCH(self):
                servidor.atender(self, 'PATCH')

            def do_DELETE(self):
                servidor.atender(self, 'DELETE')

        for puerto in range(inicial, inicial + intentos):
            try:
                self.httpd = _ServidorHttp(('127.0.0.1', puerto), Handler)
                self.httpd.daemon_threads = True
                self.puerto = puerto
                return
            except OSError as e:
                ultimo_error = e
        raise OSError(f'No hay un puerto libre entre {inicial} y {inicial + intentos - 1}: {ultimo_error}')

    # ---------- ciclo de vida ----------
    @property
    def url(self):
        return f'http://127.0.0.1:{self.puerto}/'

    @property
    def url_con_token(self):
        return f'{self.url}?t={self.token}'

    def servir_en_hilo(self):
        self._hilo = threading.Thread(target=self.httpd.serve_forever, kwargs={'poll_interval': 0.25}, daemon=True)
        self._hilo.start()
        return self

    def servir(self):
        self._vigilar_inactividad()
        try:
            self.httpd.serve_forever(poll_interval=0.25)
        finally:
            self.cerrar()

    def _vigilar_inactividad(self):
        if not self.inactividad_segundos:
            return

        def vigilar():
            while not self.cerrando:
                time.sleep(min(30, max(1, self.inactividad_segundos / 10)))
                if self.cerrando:
                    return
                # Una pestaña abierta (escucha los eventos) o una copia del Excel de origen en preparación son uso:
                # sólo se apaga cuando nadie la tiene abierta.
                if self.bus.suscriptores or self.origenes.en_curso():
                    self.ultima_peticion = time.time()
                if time.time() - self.ultima_peticion > self.inactividad_segundos and not self.trabajos.activos():
                    s = self.inactividad_segundos
                    self.apagar(motivo=f'por inactividad ({f"{s // 3600} h" if s >= 3600 else f"{s} s"} sin pestañas abiertas)')
                    return
        threading.Thread(target=vigilar, daemon=True).start()

    def reiniciar(self, demora=0.5):
        """Arranca otra instancia con el mismo token y el mismo puerto (así la pantalla abierta sigue sin volver a
        entrar) y se apaga. La nueva espera a que esta suelte el puerto."""
        import subprocess
        flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        subprocess.Popen(comando_reinicio(self.dir_datos, self.token, self.puerto), cwd=str(self.raiz), creationflags=flags,
                         close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.registro.info('Reinicio pedido desde la pantalla')
        self.motivo_cierre = 'para reiniciarse'
        self.cerrando = True

        def cerrar():
            time.sleep(demora)
            self.cerrar()  # suelta el puerto enseguida para que lo tome la instancia nueva
        threading.Thread(target=cerrar, daemon=True).start()

    def apagar(self, demora=0.3, motivo='desde la pantalla ("Cerrar la herramienta")'):
        if self.cerrando:
            return
        self.motivo_cierre = motivo
        self.cerrando = True

        def parar():
            time.sleep(demora)
            self.httpd.shutdown()
        threading.Thread(target=parar, daemon=True).start()

    def cerrar(self):
        self.cerrando = True
        if not self._cierre_registrado:
            self._cierre_registrado = True
            self.registro.info('Se cierra la herramienta %s', self.motivo_cierre or '(fin del proceso)')
        try:
            self.httpd.shutdown()
        except Exception:
            pass
        try:
            self.httpd.server_close()
        except Exception:
            pass
        self.trabajos.cerrar()
        for h in list(self.registro.handlers):  # suelta servidor.log (en Windows, si no, queda tomado)
            self.registro.removeHandler(h)
            h.close()
        if self.al_cerrar:
            try:
                self.al_cerrar()
            except Exception:
                pass

    # ---------- ejecuciones ↔ trabajos ----------
    def _marcar_interrumpidas(self):
        for e in self.dominio.listar_ejecuciones():
            if e['estado'] in ('corriendo', 'esperando'):
                self.dominio.actualizar_estado(e['id'], 'error', error='Se cerró la herramienta mientras el reporte corría. Volvé a ejecutarlo.')

    def sincronizar_ejecucion(self, trabajo):
        e = self.dominio.obtener_ejecucion(trabajo.get('ejecucionId'))
        if not e or e['estado'] not in ('corriendo', 'esperando', 'listo'):
            return
        nuevo = 'esperando' if trabajo['estado'] == 'esperando' else 'corriendo' if trabajo['estado'] == 'corriendo' else None
        if nuevo and nuevo != e['estado']:
            self.dominio.actualizar_estado(e['id'], nuevo)
            self.bus.emitir('ejecucion', self.dominio.obtener_ejecucion(e['id']))

    def _refrescar_revisiones(self):
        try:
            self.dominio.refrescar_revisiones()
        except Exception:
            self.registro.error('Al recontar las revisiones:\n%s', traceback.format_exc())

    def terminar_ejecucion(self, trabajo):
        e = self.dominio.obtener_ejecucion(trabajo.get('ejecucionId'))
        if not e:
            return
        rutas = self.dominio.rutas(e['id'])
        if trabajo['estado'] == 'ok':
            try:
                tablas = self.dominio.tablas(e['id'])
                salidas = tablas.listar() if tablas.existe() else []
                resumen = trabajo.get('resumen') or {}
                from .almacen import escribir_json_atomico
                escribir_json_atomico(rutas['resumen'], resumen)
                traslado = self.dominio.trasladar_revision(e['id']) if tablas.existe() else None
                if tablas.existe():
                    self.dominio.guardar_triage(e['id'])
                self.dominio.actualizar_estado(e['id'], 'ok', resumen=resumen, salidas=[{k: v for k, v in s.items() if k != 'tipos'} for s in salidas], error=None, traslado=traslado)
                self.registro.info('Ejecución %s terminada; traslado %s', e['id'], traslado)
                try:
                    self.origenes.preparar(self.dominio.obtener_ejecucion(e['id']))
                except Exception:
                    self.registro.error('Al preparar el Excel de origen de %s:\n%s', e['id'], traceback.format_exc())
            except Exception:
                self.registro.error('Al cerrar la ejecución %s:\n%s', e['id'], traceback.format_exc())
                self.dominio.actualizar_estado(e['id'], 'error', error='El reporte terminó pero no se pudieron preparar los resultados; ver el registro.')
        elif trabajo['estado'] == 'cancelado':
            self.dominio.actualizar_estado(e['id'], 'cancelado', error=None)
        else:
            self.dominio.actualizar_estado(e['id'], 'error', error=trabajo.get('error') or 'El reporte terminó con un error.')
        self.bus.emitir('ejecucion', self.dominio.obtener_ejecucion(e['id']))

    # ---------- atención de peticiones ----------
    def atender(self, h, metodo):
        self.ultima_peticion = time.time()
        if self.cerrando:
            h.close_connection = True  # al apagarse no se sostienen conexiones: la pantalla busca la instancia nueva
        ruta, query = ruta_y_query(h.path)
        host = host_de(h.headers, f'127.0.0.1:{self.puerto}')
        try:
            if ruta.startswith('/api/'):
                ok, motivo = peticion_autorizada(h.headers, query, self.token, metodo != 'GET', host)
                if not ok:
                    raise RespuestaHttp(403, {'error': motivo})
                self.api.despachar(h, metodo, ruta, query)
            elif metodo == 'GET':
                self._estatico(h, ruta, query, host)
            else:
                raise RespuestaHttp(405, {'error': 'Método no permitido'})
        except RespuestaHttp as r:
            self.responder_json(h, r.status, r.cuerpo)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            self.registro.error('%s %s\n%s', metodo, ruta, traceback.format_exc())
            try:
                self.responder_json(h, 500, {'error': 'Ocurrió un error inesperado. Quedó anotado en el registro de la herramienta.'})
            except Exception:
                pass

    def _estatico(self, h, ruta, query, host):
        if ruta == '/':
            ok, _ = peticion_autorizada(h.headers, query, self.token, False, host)
            if not ok:
                self.responder_html(h, 403, PAGINA_403)
                return
            if query.get('t'):
                h.send_response(303)
                h.send_header('Set-Cookie', cookie_de_token(self.token))
                h.send_header('Location', '/')
                self._cabeceras(h)
                h.send_header('Content-Length', '0')
                h.end_headers()
                return
            self._archivo(h, DIR_WEB / 'index.html')
            return
        nombre = unquote(ruta.lstrip('/'))
        if '/' in nombre or nombre.startswith('.') or Path(nombre).suffix.lower() not in TIPOS:
            raise RespuestaHttp(404, {'error': 'No existe'})
        destino = DIR_WEB / nombre
        if not destino.is_file():
            raise RespuestaHttp(404, {'error': 'No existe'})
        self._archivo(h, destino)

    def _cabeceras(self, h, api=False):
        for k, v in CABECERAS_BASE.items():
            h.send_header(k, v)
        h.send_header('Cache-Control', 'no-store' if api else 'no-cache')

    def _archivo(self, h, ruta):
        datos = ruta.read_bytes()
        h.send_response(200)
        h.send_header('Content-Type', TIPOS.get(ruta.suffix.lower(), 'application/octet-stream'))
        h.send_header('Content-Length', str(len(datos)))
        self._cabeceras(h)
        h.end_headers()
        h.wfile.write(datos)

    def responder_json(self, h, status, objeto):
        datos = json.dumps(objeto, ensure_ascii=False, default=str).encode('utf-8')
        h.send_response(status)
        h.send_header('Content-Type', 'application/json; charset=utf-8')
        h.send_header('Content-Length', str(len(datos)))
        self._cabeceras(h, api=True)
        h.end_headers()
        if h.command != 'HEAD':
            h.wfile.write(datos)

    def responder_html(self, h, status, html):
        datos = html.encode('utf-8')
        h.send_response(status)
        h.send_header('Content-Type', 'text/html; charset=utf-8')
        h.send_header('Content-Length', str(len(datos)))
        self._cabeceras(h)
        h.end_headers()
        h.wfile.write(datos)

    def responder_bytes(self, h, datos, tipo, nombre):
        h.send_response(200)
        h.send_header('Content-Type', tipo)
        h.send_header('Content-Length', str(len(datos)))
        h.send_header('Content-Disposition', 'attachment; filename*=UTF-8\'\'' + _nombre_cabecera(nombre))
        self._cabeceras(h, api=True)
        h.end_headers()
        h.wfile.write(datos)

    def responder_archivo(self, h, ruta, nombre=None, tipo='application/octet-stream'):
        tamano = ruta.stat().st_size
        h.send_response(200)
        h.send_header('Content-Type', tipo)
        h.send_header('Content-Length', str(tamano))
        h.send_header('Content-Disposition', 'attachment; filename*=UTF-8\'\'' + _nombre_cabecera(nombre or ruta.name))
        self._cabeceras(h, api=True)
        h.end_headers()
        with ruta.open('rb') as f:
            for bloque in iter(lambda: f.read(1024 * 256), b''):
                h.wfile.write(bloque)

    def estado(self):
        return {'version': VERSION, 'puerto': self.puerto, 'datos': str(self.dir_datos), 'python': sys.version.split()[0],
                'reportes': [catalogo.descripcion_publica(c, self.raiz, self.probar_venv) for c in catalogo.REPORTES],
                'trabajosActivos': len(self.trabajos.activos()), 'origenes': self.origenes.en_curso(), 'instancia': self.instancia,
                # El código de la herramienta cambió en disco después de abrirla (se actualizó): hay que reiniciarla.
                'reiniciar': firma_codigo(self.raiz) != self.firma_codigo}


class _ServidorHttp(ThreadingHTTPServer):
    # En Windows, SO_REUSEADDR deja que otro proceso abra el mismo puerto mientras éste lo usa: el puerto es exclusivo.
    allow_reuse_address = sys.platform != 'win32'
    daemon_threads = True


def comando_reinicio(dir_datos, token, puerto):
    """Comando de la instancia que reemplaza a esta al reiniciar (mismo intérprete, datos, token y puerto)."""
    return [sys.executable, '-m', 'app.arranque', '--sin-navegador', '--datos', str(dir_datos), '--puerto', str(puerto), '--reinicio', token]


def firma_codigo(raiz):
    """Huella del código de la herramienta (nombre, tamaño y fecha de cada .py de app/)."""
    import hashlib
    h = hashlib.sha1()
    for p in sorted(Path(raiz, 'app').rglob('*.py')):
        try:
            st = p.stat()
        except OSError:
            continue
        h.update(f'{p.relative_to(raiz).as_posix()}|{st.st_size}|{st.st_mtime_ns}\n'.encode('utf-8'))
    return h.hexdigest()


def _nombre_cabecera(nombre):
    from urllib.parse import quote
    return quote(str(nombre), safe='')


def crear_servidor(dir_datos, raiz=RAIZ, puerto_inicial=PUERTO_INICIAL, intentos=INTENTOS_PUERTO, token=None, probar_venv=True,
                   inactividad_segundos=3 * 3600, al_cerrar=None):
    return Servidor(dir_datos, raiz, puerto_inicial, intentos, token, probar_venv, inactividad_segundos, al_cerrar)
