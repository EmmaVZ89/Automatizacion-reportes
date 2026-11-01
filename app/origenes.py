"""Excel de origen de una fila de resultado: las filas de los Excel de entrada que formaron esa fila, con las
columnas y formatos del archivo original (primero SGA, dos filas libres, después ERP; cada lado sólo si tiene
filas).

Para no releer libros de cientos de miles de filas en cada pedido, cada hoja de entrada se copia una vez a una
base de consulta (`_comun/cache_filas.py`, en un subproceso) junto al archivo en la biblioteca del cierre:
`archivos/<sha8>/filas-<hoja>.sqlite`. La copia se arma sola al terminar la corrida, o la primera vez que se pide.

Un reporte ofrece esto si su salida tiene `'origen': True` y el reporte tiene un módulo `origen.py` con este
contrato (ver conciliacion_general/origen.py y controles_sga/origen.py). `ctx` = {'salidas': carpeta de salidas de la
ejecución, 'entradas': {clave: [{ruta, nombre}]}, 'hojas': {ruta del archivo: hoja de datos reconocida}}:
  fuentes(ctx) -> [(lado, archivo, hoja)]            (FileNotFoundError si la versión no tiene el detalle)
  filas_de(ctx, fila) -> [(lado, archivo, hoja, [números de fila], {número: columnas a pintar de anaranjado})]
  es_encabezado(lado, textos) -> bool
  nombre(fila) -> texto para el nombre del archivo (opcional)
`fila` es {columna: valor} de la fila del resultado, con '_marcas' (las columnas observadas en pantalla)."""
import hashlib
import importlib
import io
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import catalogo
from .reportes._comun.cache_filas import CacheFilas

RAIZ = Path(__file__).resolve().parent.parent
CONSTRUCTOR = RAIZ / 'app' / 'reportes' / '_comun' / 'cache_filas.py'
FILAS_LIBRES = 2


class SinOrigen(ValueError):
    pass


def ruta_cache(xlsx, hoja):
    return Path(xlsx).parent / f'filas-{hashlib.sha1(hoja.encode("utf-8")).hexdigest()[:10]}.sqlite'


class Origenes:
    def __init__(self, dominio, registro=None, bus=None):
        self.dominio = dominio
        self.registro = registro
        self.bus = bus  # avisa el avance a la pantalla (visor de tareas)
        self._lock = threading.RLock()  # reentrante: tomarlo dos veces en el mismo hilo no traba
        self._en_curso = {}  # ejecucion_id -> {'progreso': float, 'error': str | None}
        self._por_copia = {}  # ruta de la copia -> candado (dos versiones pueden usar el mismo archivo)

    # ---------- qué hace falta ----------
    def _modulo(self, e, tabla=None):
        try:
            d = catalogo.obtener(e['reporte'])
        except KeyError:
            return None
        if not any(s.get('origen') and (tabla is None or s['tabla'] == tabla) for s in d['salidas']):
            return None
        try:
            return importlib.import_module(f'app.reportes.{e["reporte"]}.origen')
        except ImportError:
            return None

    def _contexto(self, e):
        rutas = self.dominio.rutas(e['id'])
        if not rutas['entradas'].exists():
            raise SinOrigen('Esta versión no tiene el detalle de origen: volvé a correrla para poder bajarlo.')
        entradas = json.loads(rutas['entradas'].read_text(encoding='utf-8-sig'))
        cierre = self.dominio.obtener_cierre(e['cierreId']) or {}
        hojas = {str(Path(a['ruta'])): a.get('hoja') for a in cierre.get('archivos', []) if a.get('ruta')}
        return {'salidas': rutas['salidas'], 'entradas': entradas, 'hojas': hojas}

    def _necesarios(self, e, modulo):
        """[{xlsx, hoja, cache, lado}] de las hojas de entrada que usó la ejecución."""
        ctx = self._contexto(e)
        por_nombre = {Path(x['ruta']).name: Path(x['ruta']) for lista in ctx['entradas'].values() for x in (lista or [])}
        try:
            fuentes = modulo.fuentes(ctx)
        except FileNotFoundError:
            raise SinOrigen('Esta versión no tiene el detalle de origen: volvé a correrla para poder bajarlo.')
        salida = []
        for lado, archivo, hoja in fuentes:
            xlsx = por_nombre.get(archivo)
            if xlsx is None or not xlsx.exists():
                raise SinOrigen(f'Ya no está el archivo de entrada {archivo} (se borró con la limpieza): no se puede armar el Excel de origen.')
            salida.append({'lado': lado, 'archivo': archivo, 'xlsx': xlsx, 'hoja': hoja, 'cache': ruta_cache(xlsx, hoja)})
        return salida

    def estado(self, e):
        modulo = self._modulo(e)
        if modulo is None:
            return {'disponible': False}
        with self._lock:
            curso = dict(self._en_curso.get(e['id']) or {})
        try:
            necesarios = self._necesarios(e, modulo)
        except SinOrigen as err:
            return {'disponible': True, 'listo': False, 'preparando': False, 'error': str(err)}
        listo = all(CacheFilas(n['cache']).lista() for n in necesarios)
        if listo:
            return {'disponible': True, 'listo': True, 'preparando': False, 'progreso': 1.0}
        return {'disponible': True, 'listo': False, 'preparando': bool(curso) and not curso.get('error'),
                'progreso': curso.get('progreso', 0.0), 'error': curso.get('error')}

    def _avisar(self, ejecucion_id, **datos):
        if self.bus is not None:
            self.bus.emitir('origen', {'ejecucionId': ejecucion_id, **datos})

    def en_curso(self):
        """[{ejecucionId, progreso}] de las copias que se están armando (para el visor de tareas)."""
        with self._lock:
            return [{'ejecucionId': k, 'progreso': v.get('progreso', 0.0)} for k, v in self._en_curso.items() if not v.get('error')]

    # ---------- preparación ----------
    def preparar(self, e):
        """Arma en segundo plano las copias que falten. Devuelve el estado."""
        modulo = self._modulo(e)
        if modulo is None:
            return {'disponible': False}
        try:
            faltan = [n for n in self._necesarios(e, modulo) if not CacheFilas(n['cache']).lista()]
        except SinOrigen as err:
            return {'disponible': True, 'listo': False, 'preparando': False, 'error': str(err)}
        if not faltan:
            return self.estado(e)
        # El estado se pide después de soltar el candado: estado() lo toma, y pedirlo adentro trababa la herramienta
        # entera cuando la pantalla pedía la copia mientras se armaba (la que arranca sola al terminar la corrida).
        with self._lock:
            actual = self._en_curso.get(e['id'])
            ya_en_curso = bool(actual) and not actual.get('error')
            if not ya_en_curso:
                self._en_curso[e['id']] = {'progreso': 0.0, 'error': None}
        if ya_en_curso:
            return self.estado(e)
        self._avisar(e['id'], progreso=0.0)
        threading.Thread(target=self._construir, args=(e['id'], faltan), daemon=True).start()
        return self.estado(e)

    def _construir(self, ejecucion_id, faltan):
        total = sum(max(1, n['xlsx'].stat().st_size) for n in faltan)
        hecho = 0
        inicio = time.time()
        if self.registro:
            self.registro.info('Excel de origen de %s: se copian %s hoja(s), %.0f MB', ejecucion_id, len(faltan), total / 1e6)
        try:
            for n in faltan:
                peso = max(1, n['xlsx'].stat().st_size)
                with self._lock:
                    candado = self._por_copia.setdefault(str(n['cache']), threading.Lock())
                with candado:
                    if not CacheFilas(n['cache']).lista():
                        self._correr(ejecucion_id, n, hecho / total, peso / total)
                hecho += peso
            with self._lock:
                self._en_curso.pop(ejecucion_id, None)
            if self.registro:
                self.registro.info('Excel de origen de %s: listo en %.0f s', ejecucion_id, time.time() - inicio)
            self._avisar(ejecucion_id, progreso=1.0, listo=True)
        except Exception as err:  # el detalle va al registro; la pantalla muestra un texto llano
            if self.registro:
                self.registro.error('Copia de consulta para %s: %s', ejecucion_id, err)
            mensaje = 'No se pudo preparar el Excel de origen: ' + str(err)
            with self._lock:
                self._en_curso[ejecucion_id] = {'progreso': 0.0, 'error': mensaje}
            self._avisar(ejecucion_id, error=mensaje)

    def _correr(self, ejecucion_id, n, base, peso):
        comando = [sys.executable, '-I', str(CONSTRUCTOR), '--xlsx', str(n['xlsx']), '--hoja', n['hoja'], '--destino', str(n['cache'])]
        error = None
        with subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as proc:
            for linea in proc.stdout:
                try:
                    dato = json.loads(linea)
                except ValueError:
                    continue
                if 'progreso' in dato:
                    avance = round(base + peso * float(dato['progreso']), 3)
                    with self._lock:
                        actual = self._en_curso.get(ejecucion_id)
                        anterior = actual.get('progreso', 0.0) if actual else None
                        if actual is not None:
                            actual['progreso'] = avance
                    if anterior is not None and avance - anterior >= 0.01:
                        self._avisar(ejecucion_id, progreso=avance)
                if 'error' in dato:
                    error = dato['error']
            detalle = (proc.stderr.read() or '').strip()[-300:]
        if proc.returncode != 0:
            raise RuntimeError(error or detalle or f'código {proc.returncode}')

    # ---------- el Excel ----------
    def libro(self, e, tabla, numero_fila):
        """(bytes del .xlsx, nombre sugerido) con las filas de origen de una fila de resultado."""
        modulo = self._modulo(e, tabla)
        if modulo is None:
            raise SinOrigen('Esta tabla no tiene Excel de origen.')
        necesarios = {(n['lado'], n['archivo'], n['hoja']): n for n in self._necesarios(e, modulo)}
        if not all(CacheFilas(n['cache']).lista() for n in necesarios.values()):
            raise SinOrigen('Todavía se está preparando el Excel de origen.')
        fila = self.dominio.tablas(e['id']).fila(tabla, numero_fila)
        grupos = modulo.filas_de(self._contexto(e), fila)
        if not grupos:
            raise SinOrigen('Esta fila no tiene filas de origen.')
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
        anaranjado = PatternFill('solid', fgColor='FFF4B183')  # el mismo de los Excel de los reportes
        wb = openpyxl.Workbook()
        hoja = wb.active
        hoja.title = 'Origen'
        actual = 1
        anchos = {}
        negrita = Font(bold=True)
        for grupo in grupos:
            lado, archivo, nombre_hoja, numeros = grupo[:4]
            resaltar = grupo[4] if len(grupo) > 4 else {}
            cache = CacheFilas(necesarios[(lado, archivo, nombre_hoja)]['cache'])
            encabezado = next((celdas for _, celdas in cache.primeras(20) if modulo.es_encabezado(lado, [str(v) for _, v, _ in celdas])), None)
            columna_de = {str(v): col for col, v, _ in (encabezado or [])}
            filas = cache.leer(numeros)
            if actual > 1:
                actual += FILAS_LIBRES
            bloque = ([(None, encabezado)] if encabezado else []) + [(x, filas[x]) for x in numeros if x in filas]
            for numero, celdas in bloque:
                for col, valor, formato in celdas:
                    c = hoja.cell(row=actual, column=col + 1, value=valor)
                    if isinstance(valor, str) and valor.startswith('='):
                        c.data_type = 's'  # un texto que empieza con = queda como texto, nunca como fórmula
                    if formato and formato != 'General':
                        c.number_format = formato
                    if numero is None:
                        c.font = negrita
                # celdas a completar o corregir: anaranjadas, aunque estén vacías
                for nombre in (resaltar.get(numero) or ()) if numero is not None else ():
                    if nombre in columna_de:
                        hoja.cell(row=actual, column=columna_de[nombre] + 1).fill = anaranjado
                actual += 1
            for col, ancho in cache.anchos().items():
                anchos[col] = max(anchos.get(col, 0), ancho)
        for col, ancho in anchos.items():
            hoja.column_dimensions[get_column_letter(col + 1)].width = ancho
        buffer = io.BytesIO()
        wb.save(buffer)
        sugerido = modulo.nombre(fila) if hasattr(modulo, 'nombre') else fila.get('Comprobante')
        nombre = re.sub(r'[^\w.\- ]+', '_', str(sugerido or f'fila {numero_fila}'))[:80]
        return buffer.getvalue(), f'Origen {nombre}.xlsx'
