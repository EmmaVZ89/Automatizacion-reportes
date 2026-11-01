"""Dominio: cierres (período + fecha de corte + biblioteca de archivos), ejecuciones de reportes con
versiones dentro del cierre, revisión (triage) y configuración. Todo en JSON bajo datos/."""
import hashlib
import re
import shutil
import threading
import time
from datetime import date, datetime
from pathlib import Path

from .almacen import Almacen, escribir_json_atomico, leer_json
from .seguridad import nombre_seguro
from .tablas import Tablas

ESTADOS_EJECUCION = ('borrador', 'listo', 'corriendo', 'esperando', 'ok', 'error', 'cancelado')
_RE_PERIODO = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')
_RE_FECHA = re.compile(r'^\d{4}-\d{2}-\d{2}$')
CONFIGURACION_DEFAULT = {'tema': 'claro', 'limiteMB': 200, 'reportes': {}, 'vistas': {}, 'bienvenida': False, 'version': 1}
# Versión de la regla con que se cuentan las filas pendientes de una ejecución. Si cambia la regla (por ejemplo,
# las filas que coinciden dejan de contar), las ejecuciones guardadas con otra versión se recuentan al arrancar.
REVISION_V = 2
_RE_CODIGO = re.compile(r'^[a-z0-9_]{1,60}$')


def _iso(t):
    return datetime.fromtimestamp(t).strftime('%Y-%m-%dT%H:%M:%S')


class Dominio:
    def __init__(self, dir_datos, ahora=time.time, reconocer=None):
        self.dir = Path(dir_datos)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ahora = ahora
        self._lock = threading.RLock()
        self._cierres = Almacen(self.dir / 'cierres.json', ahora=ahora)
        self._ejecuciones = Almacen(self.dir / 'ejecuciones.json', ahora=ahora)
        self._reconocer = reconocer if reconocer is not None else self._reconocer_default
        self._secuencia = 0

    # ---------- utilidades ----------
    def _id(self, prefijo):
        self._secuencia += 1
        return f'{prefijo}_{datetime.fromtimestamp(self.ahora()).strftime("%Y%m%d%H%M%S")}_{self._secuencia:03d}'

    @staticmethod
    def _reconocer_default(ruta):
        from .reportes._comun import detectores
        from .reportes._comun.entradas import resumen_archivo, valores_columna
        r = resumen_archivo(ruta, detectores.TODOS)
        if r.get('tipo') == 'erp_transacciones' and r.get('hoja'):
            # de qué fondo es (para no mezclar el ERP del Fondo General con el de FERF Prov. Santa Fe)
            r['fondo'] = detectores.fondo_por_asientos(valores_columna(ruta, r['hoja'], 'Asiento'))
        return r

    def dir_cierre(self, cierre_id):
        return self.dir / 'cierres' / cierre_id

    def rutas(self, ejecucion_id):
        carpeta = self.dir / 'ejecuciones' / ejecucion_id
        return {'carpeta': carpeta, 'parametros': carpeta / 'parametros.json', 'entradas': carpeta / 'entradas.json',
                'resumen': carpeta / 'resumen.json', 'triage': carpeta / 'triage.json', 'registro': carpeta / 'registro.log',
                'salidas': carpeta / 'salidas', 'sqlite': carpeta / 'resultados.sqlite'}

    # ---------- cierres ----------
    def listar_cierres(self):
        with self._lock:
            return sorted((dict(c) for c in self._cierres.entradas if not c.get('herramienta')), key=lambda c: c['periodo'], reverse=True)

    def espacio_herramienta(self, codigo):
        """Los reportes que no son del cierre mensual (Descarga de facturas) guardan sus archivos y corridas en un
        espacio propio, con la misma forma que un cierre pero fuera de la lista de cierres. Se crea la primera vez."""
        with self._lock:
            existente = next((c for c in self._cierres.entradas if c.get('herramienta') == codigo), None)
            if existente:
                return dict(existente)
            c = {'id': self._id('h'), 'periodo': None, 'corte': None, 'nombre': codigo, 'herramienta': codigo,
                 'creado': _iso(self.ahora()), 'cerrado': None, 'notas': '', 'archivos': [], 'importado': False}
            self._cierres.entradas.append(c)
            self._cierres.guardar()
            (self.dir_cierre(c['id']) / 'archivos').mkdir(parents=True, exist_ok=True)
            return dict(c)

    def obtener_cierre(self, cierre_id):
        with self._lock:
            c = self._buscar_cierre(cierre_id)
            return dict(c) if c else None

    def _buscar_cierre(self, cierre_id):
        return next((c for c in self._cierres.entradas if c['id'] == cierre_id), None)

    def crear_cierre(self, periodo, corte, nombre=''):
        periodo = str(periodo or '').strip()
        corte = str(corte or '').strip()
        if not _RE_PERIODO.match(periodo):
            raise ValueError('El período tiene que ser AAAA-MM (por ejemplo 2026-10).')
        if not _RE_FECHA.match(corte):
            raise ValueError('La fecha de corte tiene que ser AAAA-MM-DD.')
        try:
            date.fromisoformat(corte)
        except ValueError:
            raise ValueError('La fecha de corte no es válida.')
        with self._lock:
            if any(c['periodo'] == periodo for c in self._cierres.entradas):
                raise ValueError(f'Ya existe un cierre para {periodo}.')
            c = {'id': self._id('c'), 'periodo': periodo, 'corte': corte, 'nombre': str(nombre or '').strip()[:120] or f'Cierre {periodo}',
                 'creado': _iso(self.ahora()), 'cerrado': None, 'notas': '', 'archivos': [], 'importado': False}
            self._cierres.entradas.append(c)
            self._cierres.guardar()
            (self.dir_cierre(c['id']) / 'archivos').mkdir(parents=True, exist_ok=True)
            return dict(c)

    def editar_cierre(self, cierre_id, **campos):
        with self._lock:
            c = self._buscar_cierre(cierre_id)
            if not c:
                raise KeyError('No existe ese cierre.')
            for k, v in campos.items():
                if k == 'corte':
                    if not _RE_FECHA.match(str(v)):
                        raise ValueError('La fecha de corte tiene que ser AAAA-MM-DD.')
                    c['corte'] = str(v)
                elif k == 'nombre':
                    c['nombre'] = str(v or '').strip()[:120] or c['nombre']
                elif k == 'notas':
                    c['notas'] = str(v or '')[:5000]
                elif k == 'cerrado':
                    c['cerrado'] = _iso(self.ahora()) if v else None
            self._cierres.guardar()
            return dict(c)

    def borrar_cierre(self, cierre_id, forzar=False):
        with self._lock:
            c = self._buscar_cierre(cierre_id)
            if not c:
                raise KeyError('No existe ese cierre.')
            ejecuciones = [e for e in self._ejecuciones.entradas if e['cierreId'] == cierre_id]
            if any(e.get('final') for e in ejecuciones) and not forzar:
                raise ValueError('Este cierre tiene resultados finales. Para borrarlo igual, confirmá que querés perderlos.')
            for e in ejecuciones:
                self._borrar_carpeta(self.rutas(e['id'])['carpeta'])
                self._ejecuciones.entradas.remove(e)
            self._ejecuciones.guardar()
            self._cierres.entradas.remove(c)
            self._cierres.guardar()
            self._borrar_carpeta(self.dir_cierre(cierre_id))

    @staticmethod
    def _borrar_archivo_fisico(ruta):
        if not ruta:
            return
        p = Path(ruta)
        p.unlink(missing_ok=True)
        for copia in p.parent.glob('filas-*.sqlite*'):  # copias de consulta del Excel de origen
            copia.unlink(missing_ok=True)
        try:
            p.parent.rmdir()
        except OSError:
            pass

    @staticmethod
    def _borrar_carpeta(ruta):
        if ruta.exists():
            shutil.rmtree(ruta, ignore_errors=True)

    # ---------- archivos del cierre ----------
    def archivos_de(self, cierre_id):
        c = self.obtener_cierre(cierre_id)
        if not c:
            raise KeyError('No existe ese cierre.')
        return list(c['archivos'])

    def agregar_archivo(self, cierre_id, nombre, origen=None, bytes_iter=None, reconocer=True):
        """Copia el archivo a archivos/<sha8>/<nombre original> (los motores usan el nombre tal cual en sus salidas). Mismo contenido ⇒ devuelve el existente."""
        with self._lock:
            c = self._buscar_cierre(cierre_id)
            if not c:
                raise KeyError('No existe ese cierre.')
        nombre = nombre_seguro(nombre)
        carpeta = self.dir_cierre(cierre_id) / 'archivos'
        carpeta.mkdir(parents=True, exist_ok=True)
        parcial = carpeta / (f'.parcial-{self._id("a")}')
        h = hashlib.sha256()
        total = 0
        try:
            with parcial.open('wb') as destino:
                if origen is not None:
                    with Path(origen).open('rb') as f:
                        for bloque in iter(lambda: f.read(1024 * 1024), b''):
                            h.update(bloque)
                            total += len(bloque)
                            destino.write(bloque)
                else:
                    for bloque in bytes_iter:
                        h.update(bloque)
                        total += len(bloque)
                        destino.write(bloque)
            sha = h.hexdigest()
            with self._lock:
                c = self._buscar_cierre(cierre_id)
                existente = next((a for a in c['archivos'] if a['sha256'] == sha), None)
                if existente:
                    parcial.unlink(missing_ok=True)
                    return dict(existente)
                final = carpeta / sha[:8] / nombre
                final.parent.mkdir(parents=True, exist_ok=True)
                parcial.replace(final)
                archivo = {'id': self._id('a'), 'nombre': nombre, 'bytes': total, 'sha256': sha, 'ruta': str(final),
                           'subido': _iso(self.ahora()), 'tipo': None, 'hoja': None, 'filas': None, 'aviso': None, 'error': None}
            if reconocer:
                try:
                    r = self._reconocer(final)
                    archivo.update({'tipo': r.get('tipo'), 'hoja': r.get('hoja'), 'filas': r.get('filas'), 'aviso': r.get('aviso'), 'fondo': r.get('fondo')})
                except Exception as e:  # el archivo queda, con el motivo
                    archivo['error'] = str(e)
            with self._lock:
                c = self._buscar_cierre(cierre_id)
                c['archivos'].append(archivo)
                self._cierres.guardar()
            return dict(archivo)
        finally:
            parcial.unlink(missing_ok=True)

    def obtener_archivo(self, cierre_id, archivo_id):
        for a in self.archivos_de(cierre_id):
            if a['id'] == archivo_id:
                return a
        raise KeyError('No existe ese archivo en el cierre.')

    def _referencias(self, archivo_id):
        return [e for e in self._ejecuciones.entradas if any(archivo_id in ids for ids in (e.get('entradas') or {}).values())]

    def quitar_archivo(self, cierre_id, archivo_id):
        with self._lock:
            c = self._buscar_cierre(cierre_id)
            if not c:
                raise KeyError('No existe ese cierre.')
            a = next((x for x in c['archivos'] if x['id'] == archivo_id), None)
            if not a:
                raise KeyError('No existe ese archivo en el cierre.')
            refs = self._referencias(archivo_id)
            if refs:
                raise ValueError('Ese archivo lo usa una ejecución de este cierre; no se puede quitar.')
            c['archivos'].remove(a)
            self._cierres.guardar()
            self._borrar_archivo_fisico(a['ruta'])

    def limpiar_archivos_no_referenciados(self, cierre_id=None):
        """Borra de la biblioteca lo que ninguna ejecución final usa. Devuelve bytes liberados."""
        liberados = 0
        with self._lock:
            for c in self._cierres.entradas:
                if cierre_id and c['id'] != cierre_id:
                    continue
                finales = [e for e in self._ejecuciones.entradas if e['cierreId'] == c['id'] and e.get('final')]
                usados = {aid for e in finales for ids in (e.get('entradas') or {}).values() for aid in ids}
                activos = [e for e in self._ejecuciones.entradas if e['cierreId'] == c['id'] and e['estado'] in ('corriendo', 'esperando', 'borrador', 'listo')]
                usados |= {aid for e in activos for ids in (e.get('entradas') or {}).values() for aid in ids}
                for a in list(c['archivos']):
                    if a['id'] in usados:
                        continue
                    liberados += a.get('bytes', 0)
                    self._borrar_archivo_fisico(a['ruta'])
                    c['archivos'].remove(a)
            self._cierres.guardar()
        return liberados

    # ---------- ejecuciones ----------
    def _buscar_ejecucion(self, ejecucion_id):
        return next((e for e in self._ejecuciones.entradas if e['id'] == ejecucion_id), None)

    def listar_ejecuciones(self, cierre_id=None, reporte=None):
        with self._lock:
            lista = [dict(e) for e in self._ejecuciones.entradas
                     if (cierre_id is None or e['cierreId'] == cierre_id) and (reporte is None or e['reporte'] == reporte)]
        return sorted(lista, key=lambda e: e['creado'], reverse=True)

    def obtener_ejecucion(self, ejecucion_id):
        with self._lock:
            e = self._buscar_ejecucion(ejecucion_id)
            return dict(e) if e else None

    # ---------- variantes ----------
    # Un reporte puede tener variantes (la Conciliación general, una por fondo de riesgo): cada una lleva sus propias
    # versiones, su resultado final y su traslado de marcas. La variante es el valor de un parámetro del reporte.
    @staticmethod
    def variantes(reporte):
        from . import catalogo
        try:
            return catalogo.obtener(reporte).get('variantes')
        except KeyError:
            return None

    def variante_de(self, e):
        """La variante de una ejecución (None si el reporte no tiene). Las de antes de las variantes la toman de sus
        parámetros, o es la primera."""
        v = self.variantes(e['reporte'])
        if not v:
            return None
        return e.get('variante') or (e.get('parametros') or {}).get(v['parametro']) or v['opciones'][0]['valor']

    def _misma_serie(self, a, b):
        return a['cierreId'] == b['cierreId'] and a['reporte'] == b['reporte'] and self.variante_de(a) == self.variante_de(b)

    def _siguiente_version(self, e):
        return max((x['version'] for x in self._ejecuciones.entradas if x is not e and self._misma_serie(x, e)), default=0) + 1

    def crear_ejecucion(self, cierre_id, reporte, variante=None):
        with self._lock:
            if not self._buscar_cierre(cierre_id):
                raise KeyError('No existe ese cierre.')
            v = self.variantes(reporte)
            parametros = {}
            if v:
                validas = [o['valor'] for o in v['opciones']]
                variante = variante if variante in validas else validas[0]
                parametros = {v['parametro']: variante}
            else:
                variante = None
            e = {'id': self._id('e'), 'cierreId': cierre_id, 'reporte': reporte, 'variante': variante, 'version': 0, 'estado': 'borrador',
                 'creado': _iso(self.ahora()), 'inicio': None, 'fin': None, 'parametros': parametros, 'entradas': {},
                 'resumen': None, 'salidas': [], 'revision': {'pendientes': 0, 'revisadas': 0, 'omitidas': 0},
                 'trabajoId': None, 'final': False, 'error': None, 'traslado': None}
            e['version'] = self._siguiente_version(e)
            self._ejecuciones.entradas.append(e)
            self._ejecuciones.guardar()
            self.rutas(e['id'])['carpeta'].mkdir(parents=True, exist_ok=True)
            return dict(e)

    def asignar_entradas(self, ejecucion_id, entradas):
        with self._lock:
            e = self._buscar_ejecucion(ejecucion_id)
            if not e:
                raise KeyError('No existe esa ejecución.')
            c = self._buscar_cierre(e['cierreId'])
            ids_validos = {a['id'] for a in c['archivos']}
            limpio = {}
            for clave, ids in (entradas or {}).items():
                ids = [str(i) for i in (ids or [])]
                malos = [i for i in ids if i not in ids_validos]
                if malos:
                    raise ValueError('Uno de los archivos elegidos ya no está en el cierre.')
                limpio[str(clave)] = ids
            e['entradas'] = limpio
            self._ejecuciones.guardar()
            return dict(e)

    def asignar_parametros(self, ejecucion_id, parametros):
        with self._lock:
            e = self._buscar_ejecucion(ejecucion_id)
            if not e:
                raise KeyError('No existe esa ejecución.')
            e['parametros'] = dict(parametros or {})
            v = self.variantes(e['reporte'])
            nueva = e['parametros'].get(v['parametro']) if v else None
            if nueva and nueva != self.variante_de(e):
                # cambiar el fondo en Opciones pasa la versión a la serie de ese fondo (sólo si todavía no corrió)
                if e['estado'] not in ('borrador', 'listo'):
                    raise ValueError('Esta versión ya corrió: para otro fondo, empezá una versión de ese fondo.')
                e['variante'] = nueva
                e['version'] = self._siguiente_version(e)
            elif v and not e.get('variante'):
                e['variante'] = self.variante_de(e)
            self._ejecuciones.guardar()
            escribir_json_atomico(self.rutas(ejecucion_id)['parametros'], e['parametros'])
            return dict(e)

    def actualizar_estado(self, ejecucion_id, estado, **campos):
        if estado not in ESTADOS_EJECUCION:
            raise ValueError('Estado no válido.')
        with self._lock:
            e = self._buscar_ejecucion(ejecucion_id)
            if not e:
                raise KeyError('No existe esa ejecución.')
            e['estado'] = estado
            for k, v in campos.items():
                e[k] = v
            if estado == 'corriendo' and not e.get('inicio'):
                e['inicio'] = _iso(self.ahora())
            if estado in ('ok', 'error', 'cancelado'):
                e['fin'] = _iso(self.ahora())
            self._ejecuciones.guardar()
            return dict(e)

    def marcar_final(self, ejecucion_id, valor=True):
        with self._lock:
            e = self._buscar_ejecucion(ejecucion_id)
            if not e:
                raise KeyError('No existe esa ejecución.')
            if valor and e['estado'] != 'ok':
                raise ValueError('Sólo una ejecución terminada puede ser el resultado final.')
            if valor:
                for otra in self._ejecuciones.entradas:
                    if self._misma_serie(otra, e):
                        otra['final'] = False
            e['final'] = bool(valor)
            self._ejecuciones.guardar()
            return dict(e)

    def borrar_ejecucion(self, ejecucion_id, forzar=False):
        with self._lock:
            e = self._buscar_ejecucion(ejecucion_id)
            if not e:
                raise KeyError('No existe esa ejecución.')
            if e.get('final') and not forzar:
                raise ValueError('Es el resultado final del cierre. Para borrarlo igual, confirmá que querés perderlo.')
            if e['estado'] in ('corriendo', 'esperando'):
                raise ValueError('Está corriendo: cancelala antes de borrarla.')
            self._ejecuciones.entradas.remove(e)
            self._ejecuciones.guardar()
            self._borrar_carpeta(self.rutas(ejecucion_id)['carpeta'])

    def version_anterior(self, ejecucion_id):
        with self._lock:
            e = self._buscar_ejecucion(ejecucion_id)
            if not e:
                raise KeyError('No existe esa ejecución.')
            previas = [x for x in self._ejecuciones.entradas if self._misma_serie(x, e) and x['version'] < e['version'] and x['estado'] == 'ok']
            return dict(max(previas, key=lambda x: x['version'])) if previas else None

    # ---------- revisión ----------
    def _salidas_de(self, ejecucion_id, anteriores=False):
        """Definición de las salidas del reporte de la ejecución ({tabla: salida}). Con `anteriores`, también las tablas
        que dejaban versiones anteriores del reporte (`salidas_anteriores`), marcadas con 'anterior'."""
        e = self.obtener_ejecucion(ejecucion_id)
        if not e:
            return {}
        from . import catalogo
        try:
            d = catalogo.obtener(e['reporte'])
        except KeyError:
            return {}
        salidas = {s['tabla']: s for s in d['salidas']}
        if anteriores:
            for s in d.get('salidas_anteriores', []):
                salidas.setdefault(s['tabla'], {**s, 'anterior': True})
        return salidas

    def _hermanas(self, ejecucion_id):
        """{tabla: [las otras tablas del mismo libro]}: una fila puede pasar de solapa entre versiones o entre meses
        (Mes en curso → Histórico), o su tabla puede haber cambiado de nombre; su marca se busca también ahí."""
        salidas = self._salidas_de(ejecucion_id, anteriores=True)
        return {t: [o for o, so in salidas.items() if o != t and so.get('archivo') and so.get('archivo') == s.get('archivo') and not so.get('anterior')]
                for t, s in salidas.items()}

    def tablas(self, ejecucion_id):
        reglas = {k: s['revisar'] for k, s in self._salidas_de(ejecucion_id).items() if s.get('revisar')}
        return Tablas(self.rutas(ejecucion_id)['sqlite'], ahora=self.ahora, reglas=reglas)

    def tablas_informativas(self, ejecucion_id):
        """Tablas de la ejecución que son sólo informativas (no suman a la revisión), según la definición del reporte."""
        return {k for k, s in self._salidas_de(ejecucion_id).items() if s.get('revisable') is False}

    def refrescar_revisiones(self):
        """Recuenta las pendientes de las ejecuciones guardadas con una regla de revisión anterior."""
        with self._lock:
            viejas = [e['id'] for e in self._ejecuciones.entradas if e['estado'] == 'ok' and e.get('revisionV') != REVISION_V]
        for ejecucion_id in viejas:
            if self.tablas(ejecucion_id).existe():
                self.guardar_triage(ejecucion_id)
        return len(viejas)

    def guardar_triage(self, ejecucion_id):
        t = self.tablas(ejecucion_id)
        triage = t.triage()
        escribir_json_atomico(self.rutas(ejecucion_id)['triage'], triage)
        resumen = t.resumen_revision(self.tablas_informativas(ejecucion_id))
        with self._lock:
            e = self._buscar_ejecucion(ejecucion_id)
            if e:
                e['revision'] = resumen
                e['revisionV'] = REVISION_V
                self._ejecuciones.guardar()
        return resumen

    def resumen_revision(self, ejecucion_id):
        return self.tablas(ejecucion_id).resumen_revision(self.tablas_informativas(ejecucion_id))

    def trasladar_revision(self, ejecucion_id):
        anterior = self.version_anterior(ejecucion_id)
        if not anterior:
            return {'aplicadas': 0, 'sin_destino': 0, 'desde': None}
        triage = leer_json(self.rutas(anterior['id'])['triage'], {}) or {}
        r = self.tablas(ejecucion_id).aplicar_triage(triage, origen='version', hermanas=self._hermanas(ejecucion_id))
        r['desde'] = anterior['version']
        self.guardar_triage(ejecucion_id)
        with self._lock:
            e = self._buscar_ejecucion(ejecucion_id)
            if e:
                e['traslado'] = r
                self._ejecuciones.guardar()
        return r

    def traer_revision_cierre_anterior(self, ejecucion_id):
        with self._lock:
            e = self._buscar_ejecucion(ejecucion_id)
            if not e:
                raise KeyError('No existe esa ejecución.')
            c = self._buscar_cierre(e['cierreId'])
            if c.get('herramienta'):
                return {'aplicadas': 0, 'sin_destino': 0, 'desde': None}
            anteriores = [x for x in self._cierres.entradas if not x.get('herramienta') and x['periodo'] < c['periodo']]
            if not anteriores:
                return {'aplicadas': 0, 'sin_destino': 0, 'desde': None}
            previo = max(anteriores, key=lambda x: x['periodo'])
            candidatas = [x for x in self._ejecuciones.entradas if x['cierreId'] == previo['id'] and x['reporte'] == e['reporte'] and x['estado'] == 'ok'
                          and self.variante_de(x) == self.variante_de(e)]
            if not candidatas:
                return {'aplicadas': 0, 'sin_destino': 0, 'desde': previo['periodo']}
            finales = [x for x in candidatas if x.get('final')]
            origen = (finales or sorted(candidatas, key=lambda x: x['version']))[-1]
        triage = leer_json(self.rutas(origen['id'])['triage'], {}) or {}
        r = self.tablas(ejecucion_id).aplicar_triage(triage, origen='cierre', solo_estados=('omitida',), hermanas=self._hermanas(ejecucion_id))
        r['desde'] = previo['periodo']
        self.guardar_triage(ejecucion_id)
        return r

    # ---------- configuración ----------
    def leer_configuracion(self):
        conf = leer_json(self.dir / 'configuracion.json', None)
        base = {k: (dict(v) if isinstance(v, dict) else v) for k, v in CONFIGURACION_DEFAULT.items()}
        if isinstance(conf, dict):
            for k, v in conf.items():
                base[k] = v
        return base

    def guardar_configuracion(self, cambios):
        with self._lock:
            conf = self.leer_configuracion()
            for k, v in (cambios or {}).items():
                if k == 'tema':
                    if v in ('claro', 'oscuro'):
                        conf['tema'] = v
                elif k == 'limiteMB':
                    try:
                        conf['limiteMB'] = max(10, min(2000, int(v)))
                    except (TypeError, ValueError):
                        pass
                elif k == 'bienvenida':
                    conf['bienvenida'] = bool(v)
                elif k == 'vistas' and isinstance(v, dict):
                    vistas = conf.setdefault('vistas', {})
                    for codigo, por_tabla in v.items():
                        if not _RE_CODIGO.match(str(codigo)) or not isinstance(por_tabla, dict):
                            continue
                        actual = vistas.setdefault(codigo, {})
                        for tabla, vista in por_tabla.items():
                            if not _RE_CODIGO.match(str(tabla)):
                                continue
                            if vista is None:
                                actual.pop(tabla, None)
                            elif isinstance(vista, dict):
                                lista = lambda x: [str(c)[:200] for c in (x if isinstance(x, list) else []) if isinstance(c, str)][:400]
                                actual[tabla] = {'orden': lista(vista.get('orden')), 'ocultas': lista(vista.get('ocultas'))}
                        if not actual:
                            vistas.pop(codigo, None)
                elif k == 'reportes' and isinstance(v, dict):
                    conf.setdefault('reportes', {})
                    for codigo, datos in v.items():
                        if isinstance(datos, dict):
                            actual = conf['reportes'].setdefault(codigo, {})
                            for clave in ('parametros', 'reglas'):
                                if clave in datos and isinstance(datos[clave], dict):
                                    actual[clave] = datos[clave]
            escribir_json_atomico(self.dir / 'configuracion.json', conf)
            return conf
