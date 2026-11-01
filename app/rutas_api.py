"""Rutas de la API JSON. Cada handler recibe (h, coincidencia, query) y responde por el servidor."""
import json
import queue
import re
import time
from pathlib import Path
from urllib.parse import unquote

from . import acceso_directo, catalogo, exportar
from .almacen import escribir_json_atomico, leer_json
from .reportes._comun.entradas import ordenar_tramos
from .seguridad import EXT_ENTRADA, nombre_seguro, ruta_confinada

MAX_BODY = 20 * 1024 * 1024
BLOQUE = 1024 * 1024
ESTADOS_REVISION = {'pendiente', 'revisada', 'omitida'}


class RespuestaHttp(Exception):
    def __init__(self, status, cuerpo):
        super().__init__(cuerpo.get('error') if isinstance(cuerpo, dict) else str(cuerpo))
        self.status = status
        self.cuerpo = cuerpo


def _error(status, mensaje):
    return RespuestaHttp(status, {'error': mensaje})


class Api:
    def __init__(self, servidor):
        self.s = servidor
        self.modo_pruebas = False
        R = []

        def ruta(metodo, patron, fn):
            R.append((metodo, re.compile('^' + patron + '$'), fn))

        ruta('GET', '/api/estado', self.estado)
        ruta('GET', '/api/eventos', self.eventos)
        ruta('GET', '/api/configuracion', self.configuracion)
        ruta('PATCH', '/api/configuracion', self.guardar_configuracion)
        ruta('POST', '/api/cerrar', self.cerrar)
        ruta('POST', '/api/reiniciar', self.reiniciar)
        ruta('POST', '/api/acceso-directo', self.acceso_directo)
        ruta('GET', '/api/registro', self.registro_herramienta)
        ruta('POST', '/api/limpieza', self.limpieza)
        ruta('GET', '/api/parametros/([a-z_]+)', self.parametros)
        ruta('GET', '/api/cierres', self.cierres)
        ruta('GET', '/api/herramientas/([a-z_]+)', self.herramienta)
        ruta('POST', '/api/cierres', self.crear_cierre)
        ruta('POST', '/api/cierres/importar', self.importar_cierre)
        ruta('GET', '/api/cierres/([^/]+)', self.cierre)
        ruta('PATCH', '/api/cierres/([^/]+)', self.editar_cierre)
        ruta('DELETE', '/api/cierres/([^/]+)', self.borrar_cierre)
        ruta('GET', '/api/cierres/([^/]+)/exportar', self.exportar_cierre)
        ruta('GET', '/api/cierres/([^/]+)/archivos', self.archivos)
        ruta('POST', '/api/cierres/([^/]+)/archivos', self.subir_archivo)
        ruta('POST', '/api/cierres/([^/]+)/archivos/carpeta', self.listar_carpeta)
        ruta('POST', '/api/cierres/([^/]+)/archivos/desde-carpeta', self.desde_carpeta)
        ruta('DELETE', '/api/cierres/([^/]+)/archivos/([^/]+)', self.quitar_archivo)
        ruta('GET', '/api/ejecuciones', self.ejecuciones)
        ruta('POST', '/api/ejecuciones', self.crear_ejecucion)
        ruta('GET', '/api/ejecuciones/([^/]+)', self.ejecucion)
        ruta('PATCH', '/api/ejecuciones/([^/]+)', self.editar_ejecucion)
        ruta('DELETE', '/api/ejecuciones/([^/]+)', self.borrar_ejecucion)
        ruta('POST', '/api/ejecuciones/([^/]+)/ejecutar', self.ejecutar)
        ruta('GET', '/api/ejecuciones/([^/]+)/tablas', self.tablas)
        ruta('GET', '/api/ejecuciones/([^/]+)/tablas/([a-z0-9_]+)', self.tabla)
        ruta('GET', '/api/ejecuciones/([^/]+)/tablas/([a-z0-9_]+)/distintos', self.distintos)
        ruta('GET', '/api/ejecuciones/([^/]+)/exportar-vista', self.exportar_vista)
        ruta('GET', '/api/ejecuciones/([^/]+)/origen/estado', self.origen_estado)
        ruta('POST', '/api/ejecuciones/([^/]+)/origen/preparar', self.origen_preparar)
        ruta('GET', '/api/ejecuciones/([^/]+)/origen', self.origen)
        ruta('POST', '/api/ejecuciones/([^/]+)/triage', self.triage)
        ruta('POST', '/api/ejecuciones/([^/]+)/traer-revision-anterior', self.traer_revision_anterior)
        ruta('GET', '/api/ejecuciones/([^/]+)/exportar', self.exportar_ejecucion)
        ruta('GET', '/api/ejecuciones/([^/]+)/archivos', self.archivos_salida)
        ruta('GET', '/api/ejecuciones/([^/]+)/archivos/(.+)', self.archivo_salida)
        ruta('GET', '/api/ejecuciones/([^/]+)/registro', self.registro)
        ruta('GET', '/api/trabajos', self.trabajos)
        ruta('GET', '/api/trabajos/(\\d+)', self.trabajo)
        ruta('POST', '/api/trabajos/(\\d+)/continuar', self.continuar)
        ruta('POST', '/api/trabajos/(\\d+)/cancelar', self.cancelar)
        ruta('GET', '/api/pruebas/error', self.error_de_prueba)
        self.rutas = R

    # ---------- infraestructura ----------
    def despachar(self, h, metodo, ruta, query):
        for m, rx, fn in self.rutas:
            if m != metodo:
                continue
            mt = rx.match(ruta)
            if mt:
                return fn(h, mt, query)
        raise _error(404, 'No existe esa dirección.')

    def _json(self, h, objeto, status=200):
        self.s.responder_json(h, status, objeto)

    def _body(self, h):
        try:
            largo = int(h.headers.get('Content-Length') or 0)
        except ValueError:
            raise _error(400, 'Petición inválida.')
        if largo > MAX_BODY:
            raise _error(413, 'La petición es demasiado grande.')
        crudo = h.rfile.read(largo) if largo else b''
        if not crudo.strip():
            return {}
        try:
            valor = json.loads(crudo.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise _error(400, 'El contenido no es válido.')
        if not isinstance(valor, dict):
            raise _error(400, 'El contenido no es válido.')
        return valor

    def _cierre(self, cierre_id):
        c = self.s.dominio.obtener_cierre(cierre_id)
        if not c:
            raise _error(404, 'No existe ese cierre.')
        return c

    def _ejecucion(self, ejecucion_id):
        e = self.s.dominio.obtener_ejecucion(ejecucion_id)
        if not e:
            raise _error(404, 'No existe esa ejecución.')
        return e

    def _definicion(self, codigo):
        try:
            return catalogo.obtener(codigo)
        except KeyError:
            raise _error(404, 'No existe ese reporte.')

    # ---------- generales ----------
    def estado(self, h, mt, q):
        self._json(h, self.s.estado())

    def error_de_prueba(self, h, mt, q):
        if not self.modo_pruebas:
            raise _error(404, 'No existe esa dirección.')
        raise RuntimeError('error provocado para la prueba')

    def eventos(self, h, mt, q):
        h.send_response(200)
        h.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        h.send_header('Cache-Control', 'no-store')
        h.send_header('Connection', 'close')
        h.send_header('X-Content-Type-Options', 'nosniff')
        h.end_headers()
        h.close_connection = True
        cola = self.s.bus.suscribir()
        try:
            h.wfile.write(b': conectado\n\n')
            h.wfile.flush()
            while not self.s.cerrando:
                try:
                    tipo, datos = cola.get(timeout=15)
                except queue.Empty:
                    h.wfile.write(b': ping\n\n')
                    h.wfile.flush()
                    continue
                cuerpo = json.dumps(datos, ensure_ascii=False, default=str)
                h.wfile.write(f'event: {tipo}\ndata: {cuerpo}\n\n'.encode('utf-8'))
                h.wfile.flush()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            self.s.bus.desuscribir(cola)

    def configuracion(self, h, mt, q):
        conf = self.s.dominio.leer_configuracion()
        conf['carpetaDatos'] = str(self.s.dir_datos)
        self._json(h, conf)

    def guardar_configuracion(self, h, mt, q):
        cambios = self._body(h)
        conf = self.s.dominio.guardar_configuracion(cambios)
        conf['carpetaDatos'] = str(self.s.dir_datos)
        self._json(h, conf)

    def cerrar(self, h, mt, q):
        self._body(h)  # se lee aunque no se use: si queda en la conexión, ensucia la petición siguiente
        if self.s.trabajos.activos():
            raise _error(409, 'Hay un reporte corriendo. Esperá a que termine o cancelalo antes de cerrar.')
        self._json(h, {'ok': True})
        self.s.apagar(0.5)

    def registro_herramienta(self, h, mt, q):
        """El registro de la herramienta en un solo .txt, para mandarlo a soporte: los anteriores (rotados), el actual y
        fallas.log (caídas del intérprete)."""
        d = self.s.dir_datos
        partes = []
        for nombre in ['servidor.log.3', 'servidor.log.2', 'servidor.log.1', 'servidor.log', 'fallas.log']:
            ruta = d / nombre
            if ruta.is_file():
                partes.append(f'===== {nombre} =====\n' + ruta.read_text(encoding='utf-8', errors='replace'))
        if not partes:
            raise _error(404, 'Todavía no hay registro.')
        datos = '\n'.join(partes).encode('utf-8')
        self.s.responder_bytes(h, datos, 'text/plain; charset=utf-8', f'Registro de Reportes de cierre {time.strftime("%Y-%m-%d %H%M")}.txt')

    def acceso_directo(self, h, mt, q):
        self._body(h)
        try:
            rutas = acceso_directo.crear_en_escritorio(self.s.raiz, self.s.dir_datos)
        except (OSError, ValueError) as e:
            self.s.registro.warning('No se pudo crear el acceso directo: %s', e)
            raise _error(500, 'No se pudo crear el acceso directo. El detalle quedó en el registro de la herramienta.')
        self._json(h, {'rutas': rutas})

    def reiniciar(self, h, mt, q):
        self._body(h)
        if self.s.trabajos.activos():
            raise _error(409, 'Hay un reporte corriendo. Esperá a que termine o cancelalo antes de reiniciar.')
        self._json(h, {'ok': True})
        self.s.reiniciar()

    def limpieza(self, h, mt, q):
        cuerpo = self._body(h)
        liberados = self.s.dominio.limpiar_archivos_no_referenciados(cuerpo.get('cierre'))
        self._json(h, {'liberadosMB': round(liberados / (1024 * 1024), 1)})

    def parametros(self, h, mt, q):
        codigo = mt.group(1)
        d = self._definicion(codigo)
        cierre = self.s.dominio.obtener_cierre(q.get('cierre', '')) if q.get('cierre') else None
        self._json(h, {'parametros': d['parametros'], 'valores': catalogo.parametros_default(codigo, self.s.dominio.leer_configuracion(), cierre)})

    # ---------- cierres ----------
    def _resumen_cierre(self, c):
        ejecuciones = self.s.dominio.listar_ejecuciones(c['id'])
        por_reporte = {}

        def sumar(r, e):
            r['versiones'] += 1
            if r['ultima'] is None or e['creado'] > r['ultima']['creado']:
                r['ultima'] = e
            if e.get('final'):
                r['final'] = e
        for e in ejecuciones:
            r = por_reporte.setdefault(e['reporte'], {'versiones': 0, 'ultima': None, 'final': None})
            sumar(r, e)
            variante = self.s.dominio.variante_de(e)
            if variante:
                e['variante'] = variante
                sumar(r.setdefault('variantes', {}).setdefault(variante, {'versiones': 0, 'ultima': None, 'final': None}), e)
        return {**c, 'reportes': por_reporte, 'ejecuciones': ejecuciones}

    def _corto(self, e):
        """El nombre corto de la variante de una ejecución ('FERF Santa Fe'), o ''."""
        v = catalogo.obtener(e['reporte']).get('variantes') if e['reporte'] in catalogo.REPORTES else None
        variante = self.s.dominio.variante_de(e) if v else None
        return next((o.get('corto') or o['titulo'] for o in v['opciones'] if o['valor'] == variante), '') if v else ''

    def herramienta(self, h, mt, q):
        d = self._definicion(mt.group(1))
        if d.get('ambito') != 'herramienta':
            raise _error(404, 'Ese reporte es parte del cierre mensual.')
        c = self.s.dominio.espacio_herramienta(d['codigo'])
        self._json(h, self._resumen_cierre(c))

    def cierres(self, h, mt, q):
        self._json(h, [self._resumen_cierre(c) for c in self.s.dominio.listar_cierres()])

    def crear_cierre(self, h, mt, q):
        b = self._body(h)
        try:
            c = self.s.dominio.crear_cierre(b.get('periodo'), b.get('corte'), b.get('nombre', ''))
        except ValueError as e:
            raise _error(400, str(e))
        self.s.bus.emitir('cierre', c)
        self._json(h, self._resumen_cierre(c), 201)

    def cierre(self, h, mt, q):
        self._json(h, self._resumen_cierre(self._cierre(mt.group(1))))

    def editar_cierre(self, h, mt, q):
        self._cierre(mt.group(1))
        b = self._body(h)
        try:
            c = self.s.dominio.editar_cierre(mt.group(1), **{k: v for k, v in b.items() if k in ('corte', 'nombre', 'notas', 'cerrado')})
        except ValueError as e:
            raise _error(400, str(e))
        self.s.bus.emitir('cierre', c)
        self._json(h, self._resumen_cierre(c))

    def borrar_cierre(self, h, mt, q):
        c = self._cierre(mt.group(1))
        if any(e['estado'] in ('corriendo', 'esperando') for e in self.s.dominio.listar_ejecuciones(c['id'])):
            raise _error(409, 'Hay un reporte corriendo en este cierre. Cancelalo antes de borrarlo.')
        try:
            self.s.dominio.borrar_cierre(c['id'], forzar=q.get('forzar') == '1')
        except ValueError as e:
            raise _error(409, str(e))
        self.s.bus.emitir('cierre', {'id': c['id'], 'borrado': True})
        self._json(h, {'ok': True})

    def exportar_cierre(self, h, mt, q):
        c = self._cierre(mt.group(1))
        datos = exportar.exportar_cierre(self.s.dominio, c['id'])
        self.s.responder_bytes(h, datos, 'application/zip', f'Cierre {c["periodo"]}.zip')

    def importar_cierre(self, h, mt, q):
        try:
            largo = int(h.headers.get('Content-Length') or 0)
        except ValueError:
            raise _error(400, 'Petición inválida.')
        if largo <= 0 or largo > 500 * 1024 * 1024:
            raise _error(413, 'El archivo es demasiado grande.')
        datos = h.rfile.read(largo)
        try:
            c = exportar.importar_cierre(self.s.dominio, datos)
        except ValueError as e:
            raise _error(400, str(e))
        self.s.bus.emitir('cierre', c)
        self._json(h, self._resumen_cierre(c), 201)

    # ---------- archivos del cierre ----------
    def archivos(self, h, mt, q):
        c = self._cierre(mt.group(1))
        self._json(h, c['archivos'])

    def _validar_extension(self, nombre):
        if Path(nombre).suffix.lower() not in EXT_ENTRADA:
            raise _error(400, 'Sólo se aceptan libros de Excel (.xlsx o .xlsm).')

    def subir_archivo(self, h, mt, q):
        c = self._cierre(mt.group(1))
        nombre = nombre_seguro(unquote(h.headers.get('X-Nombre') or 'archivo.xlsx'))
        self._validar_extension(nombre)
        try:
            largo = int(h.headers.get('Content-Length') or 0)
        except ValueError:
            raise _error(400, 'Petición inválida.')
        limite = int(self.s.dominio.leer_configuracion().get('limiteMB', 200)) * 1024 * 1024
        if largo <= 0:
            raise _error(400, 'El archivo está vacío.')
        if largo > limite:
            h.close_connection = True
            raise _error(413, f'El archivo supera los {limite // (1024 * 1024)} MB permitidos. Podés subir el límite en Configuración.')

        def bloques():
            restante = largo
            while restante > 0:
                b = h.rfile.read(min(BLOQUE, restante))
                if not b:
                    raise _error(400, 'La subida se cortó antes de terminar.')
                restante -= len(b)
                yield b
        archivo = self.s.dominio.agregar_archivo(c['id'], nombre, bytes_iter=bloques())
        self.s.bus.emitir('cierre', self.s.dominio.obtener_cierre(c['id']))
        self._json(h, archivo, 201)

    def _carpeta_local(self, ruta):
        texto = str(ruta or '').strip().strip('"')
        if not texto:
            raise _error(400, 'Indicá la carpeta.')
        carpeta = Path(texto)
        if not carpeta.is_dir():
            raise _error(400, 'No se encontró esa carpeta en esta PC.')
        return carpeta

    def listar_carpeta(self, h, mt, q):
        self._cierre(mt.group(1))
        carpeta = self._carpeta_local(self._body(h).get('ruta'))
        archivos = [{'nombre': p.name, 'bytes': p.stat().st_size} for p in sorted(carpeta.iterdir())
                    if p.is_file() and p.suffix.lower() in EXT_ENTRADA and not p.name.startswith('~$')]
        self._json(h, {'ruta': str(carpeta), 'archivos': archivos})

    def desde_carpeta(self, h, mt, q):
        c = self._cierre(mt.group(1))
        b = self._body(h)
        carpeta = self._carpeta_local(b.get('ruta'))
        nombres = b.get('nombres') or []
        if not isinstance(nombres, list) or not nombres:
            raise _error(400, 'Elegí al menos un archivo.')
        limite = int(self.s.dominio.leer_configuracion().get('limiteMB', 200)) * 1024 * 1024
        agregados = []
        for n in nombres:
            nombre = nombre_seguro(n)
            origen = carpeta / nombre
            if not origen.is_file() or origen.suffix.lower() not in EXT_ENTRADA:
                raise _error(400, f'No se encontró {nombre} en la carpeta.')
            if origen.stat().st_size > limite:
                raise _error(413, f'{nombre} supera los {limite // (1024 * 1024)} MB permitidos.')
            agregados.append(self.s.dominio.agregar_archivo(c['id'], nombre, origen=origen))
        self.s.bus.emitir('cierre', self.s.dominio.obtener_cierre(c['id']))
        self._json(h, agregados, 201)

    def quitar_archivo(self, h, mt, q):
        c = self._cierre(mt.group(1))
        try:
            self.s.dominio.quitar_archivo(c['id'], mt.group(2))
        except KeyError as e:
            raise _error(404, str(e))
        except ValueError as e:
            raise _error(409, str(e))
        self.s.bus.emitir('cierre', self.s.dominio.obtener_cierre(c['id']))
        self._json(h, {'ok': True})

    # ---------- ejecuciones ----------
    def ejecuciones(self, h, mt, q):
        self._json(h, self.s.dominio.listar_ejecuciones(q.get('cierre') or None, q.get('reporte') or None))

    def crear_ejecucion(self, h, mt, q):
        b = self._body(h)
        c = self._cierre(str(b.get('cierre', '')))
        d = self._definicion(str(b.get('reporte', '')))
        e = self.s.dominio.crear_ejecucion(c['id'], d['codigo'], b.get('variante'))
        self.s.bus.emitir('ejecucion', e)
        self._json(h, e, 201)

    def _con_trabajo(self, e):
        t = self.s.trabajos.obtener(e['trabajoId']) if e.get('trabajoId') else None
        if t:
            t = dict(t)
            t.pop('lineas', None)
        return {**e, 'trabajo': t}

    def ejecucion(self, h, mt, q):
        self._json(h, self._con_trabajo(self._ejecucion(mt.group(1))))

    def editar_ejecucion(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        b = self._body(h)
        try:
            if 'entradas' in b:
                e = self.s.dominio.asignar_entradas(e['id'], b['entradas'] if isinstance(b['entradas'], dict) else {})
            if 'parametros' in b:
                e = self.s.dominio.asignar_parametros(e['id'], b['parametros'] if isinstance(b['parametros'], dict) else {})
            if 'final' in b:
                e = self.s.dominio.marcar_final(e['id'], bool(b['final']))
        except ValueError as err:
            raise _error(400, str(err))
        self.s.bus.emitir('ejecucion', e)
        self._json(h, self._con_trabajo(e))

    def borrar_ejecucion(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        try:
            self.s.dominio.borrar_ejecucion(e['id'], forzar=q.get('forzar') == '1')
        except ValueError as err:
            raise _error(409, str(err))
        self.s.bus.emitir('ejecucion', {'id': e['id'], 'cierreId': e['cierreId'], 'borrado': True})
        self._json(h, {'ok': True})

    def _validar_entradas(self, d, c, entradas):
        archivos = {a['id']: a for a in c['archivos']}
        limpio = {}
        for ent in d['entradas']:
            ids = entradas.get(ent['clave']) or []
            if not isinstance(ids, list):
                raise _error(400, f'{ent["titulo"]}: lista de archivos inválida.')
            ids = [str(i) for i in ids]
            if len(ids) < ent.get('minimo', 1):
                raise _error(400, f'Falta el archivo: {ent["titulo"]}.')
            if len(ids) > ent.get('maximo', 1):
                raise _error(400, f'{ent["titulo"]}: hay más archivos de los que admite ({ent.get("maximo", 1)}).')
            if len(set(ids)) != len(ids):
                raise _error(400, f'{ent["titulo"]}: hay un archivo repetido.')
            for i in ids:
                a = archivos.get(i)
                if not a:
                    raise _error(400, f'{ent["titulo"]}: uno de los archivos ya no está en el cierre.')
                if a.get('error'):
                    raise _error(400, f'{a["nombre"]}: no se pudo leer ({a["error"]}).')
                if a.get('tipo') != ent['tipo']:
                    raise _error(400, f'{a["nombre"]} no parece ser "{ent["titulo"]}". Reconocí: {a.get("tipo") or "nada"}.')
            limpio[ent['clave']] = ids
        return limpio

    def ejecutar(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        if e['estado'] in ('corriendo', 'esperando'):
            raise _error(409, 'Esta ejecución ya está corriendo.')
        if e['estado'] in ('ok', 'error', 'cancelado'):
            raise _error(409, 'Esta ejecución ya terminó. Para volver a correr, creá una versión nueva.')
        c = self._cierre(e['cierreId'])
        d = self._definicion(e['reporte'])
        disp = catalogo.disponibilidad(d['codigo'], self.s.raiz, self.s.probar_venv)
        if not disp['disponible']:
            raise _error(409, disp['motivo'])
        b = self._body(h)
        entradas = self._validar_entradas(d, c, b.get('entradas') if isinstance(b.get('entradas'), dict) else e.get('entradas') or {})
        try:
            parametros = catalogo.validar_parametros(d['codigo'], b.get('parametros') if isinstance(b.get('parametros'), dict) else e.get('parametros') or {})
        except ValueError as err:
            raise _error(400, str(err))
        if b.get('guardarDefaults'):
            persistibles = {p['clave']: parametros[p['clave']] for p in d['parametros'] if not p.get('no_persistir')}
            self.s.dominio.guardar_configuracion({'reportes': {d['codigo']: {'parametros': persistibles}}})
        variantes = d.get('variantes')
        if variantes:
            fondo = parametros.get(variantes['parametro'])
            for ids in entradas.values():
                for i in ids:
                    a = next((x for x in c['archivos'] if x['id'] == i), {})
                    if a.get('fondo') == 'mezcla':
                        raise _error(400, f'{a["nombre"]} mezcla movimientos de los dos fondos. Usá el ERP de un solo fondo.')
                    if a.get('fondo') and a['fondo'] != fondo:
                        raise _error(400, f'{a["nombre"]} es el ERP de {a["fondo"]} y esta versión es de {fondo}. Elegí el ERP de {fondo}.')
        try:
            e = self.s.dominio.asignar_parametros(e['id'], parametros)
        except ValueError as err:
            raise _error(400, str(err))
        self.s.dominio.asignar_entradas(e['id'], entradas)
        rutas = self.s.dominio.rutas(e['id'])
        archivos = {a['id']: a for a in c['archivos']}
        entradas_json = {}
        for clave, ids in entradas.items():
            lista = [{'ruta': archivos[i]['ruta'], 'nombre': archivos[i]['nombre'], 'sha256': archivos[i]['sha256']} for i in ids]
            orden = {p.name: k for k, p in enumerate(ordenar_tramos([x['nombre'] for x in lista]))}
            entradas_json[clave] = sorted(lista, key=lambda x: orden.get(x['nombre'], 0))
        if 'login' in d.get('pausas', []):
            parametros['sesion_chrome'] = str(self.s.dir_datos / 'sesion_chrome')
        self.s.dominio.asignar_parametros(e['id'], parametros)
        escribir_json_atomico(rutas['entradas'], entradas_json)
        rutas['salidas'].mkdir(parents=True, exist_ok=True)
        try:
            t = self.s.trabajos.lanzar(e['id'], catalogo.interprete(d['codigo'], self.s.raiz) + ['--trabajo', str(rutas['carpeta'])],
                                       cwd=self.s.raiz, env={'PYTHONPATH': f'{self.s.raiz};{self.s.raiz / "vendor"}'},
                                       registro=rutas['registro'], titulo=f'{d["nombre"]} · ' + (f'{self._corto(e)} · ' if self._corto(e) else '') + (f'{_mes_corto(c["periodo"])} · ' if c.get('periodo') else '') + f'v{e["version"]}')
        except ValueError as err:
            raise _error(409, str(err))
        e = self.s.dominio.actualizar_estado(e['id'], 'corriendo', trabajoId=t['id'], error=None)
        self.s.bus.emitir('ejecucion', e)
        self._json(h, {**self._con_trabajo(e), 'trabajo': t}, 202)

    # ---------- resultados ----------
    def _titulos(self, e):
        return self.s.dominio._salidas_de(e['id'], anteriores=True)

    def tablas(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        tablas = self.s.dominio.tablas(e['id'])
        definiciones = self._titulos(e)
        lista = []
        for t in tablas.listar():
            d = definiciones.get(t['tabla'], {})
            lista.append({**t, 'titulo': d.get('titulo', t['titulo']), 'archivo': d.get('archivo'), 'hoja': d.get('hoja'), 'seccion': d.get('seccion'),
                          # tabla de una versión anterior del reporte: la pantalla avisa que conviene correr una nueva
                          'anterior': bool(definiciones) and (bool(d.get('anterior')) or not d),
                          'revisable': d.get('revisable', True), 'principal': bool(d.get('principal')),
                          'vista': d.get('vista'), 'origen': bool(d.get('origen')), 'revisar': d.get('revisar')})
        self._json(h, {'tablas': lista, 'resumen': e.get('resumen'), 'traslado': e.get('traslado'), 'revision': e.get('revision')})

    @staticmethod
    def _lista_json(q, clave):
        if not q.get(clave):
            return None
        try:
            valor = json.loads(q[clave])
        except ValueError:
            raise _error(400, 'El filtro no es válido.')
        return valor

    def _consulta_de(self, q):
        """Filtros, búsqueda y orden de una consulta de tabla, tal como los manda la grilla o Exportar."""
        filtros = self._lista_json(q, 'filtros')
        if filtros is not None and (not isinstance(filtros, dict) or not all(
                isinstance(v, list) or (isinstance(v, dict) and isinstance(v.get('excluir', []), list)) for v in filtros.values())):
            raise _error(400, 'El filtro no es válido.')
        condiciones = self._lista_json(q, 'condiciones')
        if condiciones is not None and (not isinstance(condiciones, dict) or not all(isinstance(v, dict) for v in condiciones.values())):
            raise _error(400, 'El filtro no es válido.')
        return {'orden': q.get('orden') or None, 'descendente': q.get('desc') == '1', 'filtro': q.get('filtro', ''),
                'estado': q.get('estado') or None, 'columna_filtro': q.get('columna') or None, 'filtros': filtros,
                'estados': [x for x in (q.get('estados') or '').split(',') if x] or None,
                'con_obs': q.get('conObs') == '1', 'requiere': q.get('requiere') == '1', 'condiciones': condiciones}

    def tabla(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        try:
            r = self.s.dominio.tablas(e['id']).consultar(
                mt.group(2), desde=int(q.get('desde', 0) or 0), cantidad=int(q.get('cantidad', 100) or 100), **self._consulta_de(q))
        except FileNotFoundError as err:
            raise _error(404, str(err))
        except ValueError as err:
            raise _error(400, str(err))
        self._json(h, r)

    def distintos(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        try:
            # valoresDe: la columna de la lista (filtro de encabezado); el resto de la consulta son los otros filtros.
            if q.get('valoresDe'):
                columna, consulta = q['valoresDe'], self._consulta_de(q)
            else:
                columna, consulta = q.get('columna') or '', self._consulta_de({k: v for k, v in q.items() if k != 'columna'})
            r = self.s.dominio.tablas(e['id']).distintos(mt.group(2), columna, buscar=q.get('buscar', ''),
                                                         por_valor=q.get('ordenValores') == 'valor', **consulta)
        except FileNotFoundError as err:
            raise _error(404, str(err))
        except ValueError as err:
            raise _error(400, str(err))
        self._json(h, r)

    def exportar_vista(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        tabla = q.get('tabla') or ''
        if not re.match(r'^[a-z0-9_]+$', tabla):
            raise _error(400, 'Indicá qué tabla exportar.')
        columnas = self._lista_json(q, 'columnas')
        if columnas is not None and (not isinstance(columnas, list) or not all(isinstance(c, str) for c in columnas)):
            raise _error(400, 'Las columnas no son válidas.')
        try:
            datos, nombre = exportar.exportar_vista(self.s.dominio, e, tabla, self._consulta_de(q), columnas, q.get('resumen') == '1')
        except (ValueError, FileNotFoundError) as err:
            raise _error(400, str(err))
        c = self.s.dominio.obtener_cierre(e['cierreId']) or {}
        sufijo = f' - {c.get("periodo") or ""} {self._corto(e)} v{e["version"]}'.replace('  ', ' ')
        self.s.responder_bytes(h, datos, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', f'{Path(nombre).stem}{sufijo} (vista).xlsx')

    def origen_estado(self, h, mt, q):
        self._json(h, self.s.origenes.estado(self._ejecucion(mt.group(1))))

    def origen_preparar(self, h, mt, q):
        self._body(h)  # se lee aunque no se use: si queda en la conexión, ensucia la petición siguiente
        self._json(h, self.s.origenes.preparar(self._ejecucion(mt.group(1))))

    def origen(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        tabla = q.get('tabla') or ''
        try:
            fila = int(q.get('fila', ''))
        except ValueError:
            raise _error(400, 'Indicá la fila.')
        if not re.match(r'^[a-z0-9_]+$', tabla):
            raise _error(400, 'Indicá la tabla.')
        from .origenes import SinOrigen
        try:
            datos, nombre = self.s.origenes.libro(e, tabla, fila)
        except SinOrigen as err:
            raise _error(409, str(err))
        except (ValueError, FileNotFoundError) as err:
            raise _error(400, str(err))
        self.s.responder_bytes(h, datos, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', nombre)

    def triage(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        b = self._body(h)
        tabla = str(b.get('tabla', ''))
        filas = b.get('filas')
        if not re.match(r'^[a-z0-9_]+$', tabla) or not isinstance(filas, list) or not filas:
            raise _error(400, 'Indicá la tabla y las filas.')
        estado = b.get('estado')
        if estado is not None and estado not in ESTADOS_REVISION:
            raise _error(400, 'Estado de revisión no válido.')
        obs = b.get('obs')
        if obs is not None:
            obs = str(obs)[:2000]
        try:
            n = self.s.dominio.tablas(e['id']).marcar(tabla, [int(f) for f in filas][:5000], estado, obs)
        except (ValueError, TypeError) as err:
            raise _error(400, str(err))
        except FileNotFoundError as err:
            raise _error(404, str(err))
        resumen = self.s.dominio.guardar_triage(e['id'])
        self.s.bus.emitir('ejecucion', self.s.dominio.obtener_ejecucion(e['id']))
        self._json(h, {'marcadas': n, 'revision': resumen, 'estados': {t['tabla']: t['estados'] for t in self.s.dominio.tablas(e['id']).listar()}})

    def traer_revision_anterior(self, h, mt, q):
        self._body(h)  # se lee aunque no se use: si queda en la conexión, ensucia la petición siguiente
        e = self._ejecucion(mt.group(1))
        r = self.s.dominio.traer_revision_cierre_anterior(e['id'])
        self.s.bus.emitir('ejecucion', self.s.dominio.obtener_ejecucion(e['id']))
        self._json(h, r)

    def exportar_ejecucion(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        incluir = q.get('incluirOmitidas', '1') != '0'
        c = self.s.dominio.obtener_cierre(e['cierreId']) or {}
        try:
            if q.get('tabla'):
                datos, nombre = exportar.exportar_tabla(self.s.dominio, e, q['tabla'], incluir)
            elif q.get('libro'):
                datos, nombre = exportar.exportar_libro(self.s.dominio, e, q['libro'], incluir)
            else:
                raise _error(400, 'Indicá qué exportar.')
        except (ValueError, FileNotFoundError) as err:
            raise _error(400, str(err))
        sufijo = f' - {c.get("periodo", "")} {self._corto(e)} v{e["version"]}'.replace('  ', ' ').rstrip()
        base = Path(nombre)
        self.s.responder_bytes(h, datos, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', f'{base.stem}{sufijo} (trabajado).xlsx')

    def archivos_salida(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        base = self.s.dominio.rutas(e['id'])['salidas']
        lista = []
        if base.exists():
            for p in sorted(base.rglob('*')):
                if p.is_file() and p.suffix.lower() not in ('.sqlite', '.tmp'):
                    lista.append({'ruta': p.relative_to(base).as_posix(), 'bytes': p.stat().st_size})
        self._json(h, lista)

    def archivo_salida(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        base = self.s.dominio.rutas(e['id'])['salidas']
        try:
            ruta = ruta_confinada(base, unquote(mt.group(2)))
        except ValueError:
            raise _error(404, 'No existe ese archivo.')
        if not ruta.is_file() or ruta.suffix.lower() in ('.sqlite',):
            raise _error(404, 'No existe ese archivo.')
        corto = self._corto(e)
        self.s.responder_archivo(h, ruta, f'{ruta.stem} - {corto}{ruta.suffix}' if corto else ruta.name)

    def registro(self, h, mt, q):
        e = self._ejecucion(mt.group(1))
        ruta = self.s.dominio.rutas(e['id'])['registro']
        texto = ruta.read_text(encoding='utf-8', errors='replace') if ruta.exists() else ''
        self._json(h, {'registro': texto[-200000:]})

    # ---------- trabajos ----------
    def trabajos(self, h, mt, q):
        lista = []
        for t in self.s.trabajos.listar():
            t = dict(t)
            t['lineas'] = t['lineas'][-5:]
            lista.append(t)
        self._json(h, lista)

    def trabajo(self, h, mt, q):
        t = self.s.trabajos.obtener(int(mt.group(1)))
        if not t:
            raise _error(404, 'No existe ese trabajo.')
        self._json(h, t)

    def continuar(self, h, mt, q):
        b = self._body(h)
        if not self.s.trabajos.continuar(int(mt.group(1)), b.get('espera')):
            raise _error(409, 'El reporte no está esperando una acción.')
        self._json(h, {'ok': True})

    def cancelar(self, h, mt, q):
        self._body(h)  # se lee aunque no se use: si queda en la conexión, ensucia la petición siguiente
        if not self.s.trabajos.cancelar(int(mt.group(1))):
            raise _error(409, 'El reporte no está corriendo.')
        self._json(h, {'ok': True})


MESES_CORTOS = ('ene.', 'feb.', 'mar.', 'abr.', 'may.', 'jun.', 'jul.', 'ago.', 'sep.', 'oct.', 'nov.', 'dic.')


def _mes_corto(periodo):
    """'2026-10' -> 'oct. 2026' (para títulos cortos)."""
    try:
        anio, mes = str(periodo).split('-')
        return f'{MESES_CORTOS[int(mes) - 1]} {anio}'
    except (ValueError, IndexError):
        return str(periodo)
