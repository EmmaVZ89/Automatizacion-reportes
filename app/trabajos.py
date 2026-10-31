"""Trabajos: cada reporte corre como subproceso. Este módulo lo lanza, lee su protocolo (líneas
JSON por stdout; lo que no es JSON es log), le manda órdenes por stdin (continuar, cancelar),
guarda el estado en trabajos.json y avisa por el bus de eventos."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from .almacen import escribir_json_atomico, leer_json

ESTADOS = ('corriendo', 'esperando', 'ok', 'error', 'cancelado', 'interrumpido')
ACTIVOS = ('corriendo', 'esperando')
MAX_LINEAS = 400
MAX_TERMINADOS = 40
MENSAJE_ERROR_LLANO = 'El reporte terminó con un error. Podés ver el detalle en el registro.'
MENSAJE_INTERRUMPIDO = 'Se cerró la herramienta mientras el reporte corría. Volvé a ejecutarlo.'


def es_activo(t):
    return t['estado'] in ACTIVOS


class Trabajos:
    def __init__(self, archivo, bus=None, ahora=time.time, demora_grabar=0.2):
        self.archivo = Path(archivo)
        self.bus = bus
        self.ahora = ahora
        self.demora_grabar = demora_grabar
        self._lock = threading.RLock()
        self._lock_registro = threading.Lock()
        self._procesos = {}
        self._cancelar_pedido = set()
        self._timer = None
        self._al_terminar = []
        self._lista = self._cargar()
        self._siguiente = max((t['id'] for t in self._lista), default=0) + 1
        for t in self._lista:
            if es_activo(t):
                t['estado'] = 'interrumpido'
                t['fin'] = self.ahora()
                t['error'] = MENSAJE_INTERRUMPIDO
                t['espera'] = None
        if self._lista:
            self._grabar()

    def _cargar(self):
        datos = leer_json(self.archivo, {}) or {}
        lista = datos.get('trabajos') if isinstance(datos, dict) else None
        return [t for t in (lista or []) if isinstance(t, dict) and isinstance(t.get('id'), int) and t.get('estado') in ESTADOS]

    # --- consulta ---
    def listar(self):
        with self._lock:
            return [dict(t) for t in self._lista]

    def obtener(self, id):
        with self._lock:
            t = self._buscar(id)
            return dict(t) if t else None

    def activos(self):
        with self._lock:
            return [dict(t) for t in self._lista if es_activo(t)]

    def activo_de(self, ejecucion_id):
        with self._lock:
            return next((dict(t) for t in self._lista if es_activo(t) and t['ejecucionId'] == ejecucion_id), None)

    def al_terminar(self, fn):
        self._al_terminar.append(fn)

    def _buscar(self, id):
        return next((t for t in self._lista if t['id'] == id), None)

    # --- lanzar ---
    def lanzar(self, ejecucion_id, comando, cwd, env=None, registro=None, titulo=''):
        with self._lock:
            if any(es_activo(t) and t['ejecucionId'] == ejecucion_id for t in self._lista):
                raise ValueError('Ya hay un reporte corriendo para esta ejecución.')
            t = {'id': self._siguiente, 'ejecucionId': ejecucion_id, 'titulo': titulo, 'estado': 'corriendo',
                 'paso': 'Arrancando', 'progreso': 0.0, 'lineas': [], 'espera': None, 'tablas': {},
                 'resumen': None, 'inicio': self.ahora(), 'fin': None, 'error': None, 'codigo': None}
            self._siguiente += 1
            self._lista.append(t)
            self._podar()
        entorno = dict(os.environ)
        entorno.update(env or {})
        entorno.setdefault('PYTHONIOENCODING', 'utf-8')
        entorno['REPORTES_PROTOCOLO'] = '1'
        archivo_registro = Path(registro) if registro else None
        if archivo_registro:
            archivo_registro.parent.mkdir(parents=True, exist_ok=True)
        try:
            proc = subprocess.Popen(list(comando), cwd=str(cwd), env=entorno, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except OSError as e:
            with self._lock:
                t['estado'] = 'error'
                t['error'] = 'No se pudo iniciar el reporte: ' + str(e)
                t['fin'] = self.ahora()
            self._cambio(t)
            self._avisar_fin(t)
            return dict(t)
        with self._lock:
            self._procesos[t['id']] = proc
        self._cambio(t)
        hilo_err = threading.Thread(target=self._leer_stderr, args=(t, proc, archivo_registro), daemon=True)
        hilo_out = threading.Thread(target=self._leer_stdout, args=(t, proc, archivo_registro, hilo_err), daemon=True)
        hilo_err.start()
        hilo_out.start()
        return dict(t)

    def _escribir_registro(self, archivo, texto):
        if not archivo:
            return
        with self._lock_registro:
            try:
                with archivo.open('a', encoding='utf-8') as f:
                    f.write(texto + '\n')
            except OSError:
                pass

    def _agregar_linea(self, t, texto):
        t['lineas'].append(texto)
        if len(t['lineas']) > MAX_LINEAS:
            del t['lineas'][:len(t['lineas']) - MAX_LINEAS]

    def _leer_stderr(self, t, proc, registro):
        ultimas = []
        for cruda in iter(proc.stderr.readline, b''):
            linea = cruda.decode('utf-8', 'replace').rstrip('\r\n')
            if not linea.strip():
                continue
            self._escribir_registro(registro, '[err] ' + linea)
            ultimas.append(linea)
            del ultimas[:-20]
        t['_stderr'] = ultimas

    def _leer_stdout(self, t, proc, registro, hilo_err):
        for cruda in iter(proc.stdout.readline, b''):
            linea = cruda.decode('utf-8', 'replace').rstrip('\r\n')
            if not linea.strip():
                continue
            evento = None
            if linea.startswith('{'):
                try:
                    evento = json.loads(linea)
                except ValueError:
                    evento = None
            with self._lock:
                self._procesar(t, evento if isinstance(evento, dict) and 't' in evento else {'t': 'log', 'm': linea}, registro)
            self._cambio(t)
        codigo = proc.wait()
        hilo_err.join(timeout=5)
        for flujo in (proc.stdout, proc.stderr, proc.stdin):
            try:
                flujo.close()
            except (OSError, ValueError):
                pass
        stderr = t.pop('_stderr', [])
        with self._lock:
            t['codigo'] = codigo
            t['fin'] = self.ahora()
            t['espera'] = None
            if t['id'] in self._cancelar_pedido:
                t['estado'] = 'cancelado'
                t['error'] = None
            elif codigo == 0 and not t.get('error'):
                t['estado'] = 'ok'
                t['progreso'] = 1.0
            else:
                t['estado'] = 'error'
                if not t.get('error'):
                    t['error'] = MENSAJE_ERROR_LLANO
                if stderr:
                    self._agregar_linea(t, '[detalle] ' + stderr[-1])
            self._procesos.pop(t['id'], None)
            self._cancelar_pedido.discard(t['id'])
        self._escribir_registro(registro, f'[fin] estado={t["estado"]} codigo={codigo}')
        self._cambio(t)
        self._avisar_fin(t)

    def _procesar(self, t, ev, registro):
        tipo = ev.get('t')
        if tipo == 'log':
            self._agregar_linea(t, str(ev.get('m', '')))
            self._escribir_registro(registro, str(ev.get('m', '')))
        elif tipo == 'paso':
            t['paso'] = str(ev.get('m', ''))
            self._agregar_linea(t, '== ' + t['paso'])
            self._escribir_registro(registro, '== ' + t['paso'])
        elif tipo == 'progreso':
            try:
                t['progreso'] = max(0.0, min(1.0, float(ev.get('v', 0))))
            except (TypeError, ValueError):
                pass
            if ev.get('m'):
                self._agregar_linea(t, str(ev['m']))
                self._escribir_registro(registro, str(ev['m']))
        elif tipo == 'esperar':
            t['estado'] = 'esperando'
            t['espera'] = {'id': str(ev.get('id', '')), 'mensaje': str(ev.get('m', '')), 'boton': str(ev.get('boton') or 'Continuar')}
            self._escribir_registro(registro, '[espera] ' + t['espera']['mensaje'])
        elif tipo == 'tabla':
            try:
                t['tablas'][str(ev.get('tabla'))] = int(ev.get('filas', 0))
            except (TypeError, ValueError):
                pass
        elif tipo == 'resumen':
            t['resumen'] = ev.get('datos') if isinstance(ev.get('datos'), dict) else {'valor': ev.get('datos')}
        elif tipo == 'error':
            t['error'] = str(ev.get('m', '')) or MENSAJE_ERROR_LLANO
            self._agregar_linea(t, 'ERROR: ' + t['error'])
            self._escribir_registro(registro, 'ERROR: ' + t['error'])
        else:
            self._agregar_linea(t, json.dumps(ev, ensure_ascii=False))

    # --- órdenes ---
    def continuar(self, id, espera_id=None):
        with self._lock:
            t = self._buscar(id)
            proc = self._procesos.get(id)
            if not t or not proc or t['estado'] != 'esperando' or not t.get('espera'):
                return False
            if espera_id is not None and t['espera']['id'] != espera_id:
                return False
            orden = json.dumps({'t': 'continuar', 'id': t['espera']['id']}) + '\n'
            try:
                proc.stdin.write(orden.encode('utf-8'))
                proc.stdin.flush()
            except (OSError, ValueError):
                return False
            t['estado'] = 'corriendo'
            t['espera'] = None
        self._cambio(t)
        return True

    def cancelar(self, id):
        with self._lock:
            t = self._buscar(id)
            proc = self._procesos.get(id)
            if not t or not proc or not es_activo(t):
                return False
            self._cancelar_pedido.add(id)
            t['paso'] = 'Cancelando'
            try:
                proc.stdin.write(b'{"t":"cancelar"}\n')
                proc.stdin.flush()
            except (OSError, ValueError):
                pass
        self._cambio(t)
        threading.Thread(target=self._matar_si_sigue, args=(proc,), daemon=True).start()
        return True

    def _matar_si_sigue(self, proc):
        try:
            proc.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass

    # --- persistencia y avisos ---
    def _publico(self, t):
        return {k: v for k, v in t.items() if not k.startswith('_')}

    def _cambio(self, t):
        with self._lock:
            if self._timer is None:
                self._timer = threading.Timer(self.demora_grabar, self._grabar)
                self._timer.daemon = True
                self._timer.start()
        if self.bus:
            self.bus.emitir('trabajo', self._publico(t))

    def _grabar(self):
        with self._lock:
            self._timer = None
            lista = [self._publico(t) for t in self._lista]
        try:
            escribir_json_atomico(self.archivo, {'trabajos': lista})
        except OSError:
            pass

    def guardar_ahora(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
        self._grabar()

    def _podar(self):
        terminados = [t for t in self._lista if not es_activo(t)]
        for t in terminados[:max(0, len(terminados) - MAX_TERMINADOS)]:
            self._lista.remove(t)

    def _avisar_fin(self, t):
        for fn in list(self._al_terminar):
            try:
                fn(self._publico(t))
            except Exception as e:  # el callback no puede tumbar el lector
                print('al_terminar falló:', e, file=sys.stderr)

    def cerrar(self):
        """Al apagar el server: mata lo que siga corriendo y graba."""
        with self._lock:
            procesos = list(self._procesos.values())
        for p in procesos:
            try:
                p.kill()
            except OSError:
                pass
        self.guardar_ahora()
