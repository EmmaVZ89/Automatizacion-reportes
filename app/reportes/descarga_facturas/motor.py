"""Descarga directa de facturas desde listados Excel, sin enumerar la biblioteca.

Es `legado/descarga_facturas/listado.py` (v6) con los cambios mínimos: sin `input()`, sin rutas
propias, parámetros explícitos y avisos por `informar`. La lógica de lectura del listado
(`cargar_listados` = `load_inputs`), los estados y el formato de las salidas no cambian."""
import csv
import re
import unicodedata
from contextlib import closing, contextmanager
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import openpyxl

from .._comun import protocolo
from . import sharepoint as core

ALIASES = {
    'cuit': {'cuit', 'cuitcliente', 'cuitdelcliente', 'identificacionfiscal', 'nif'},
    'numero': {'numerofactura', 'nrofactura', 'nrodefactura', 'numerodefactura', 'factura', 'comprobante', 'numerocomprobante', 'numerodecomprobante'},
}
COLUMNAS_DESCARGA = ['CUIT', 'Factura', 'FechaEmisionPDF', 'ConceptosPDF', 'Estado', 'Detalle', 'FilaOrigen']
COLUMNAS_REVISAR = ['Archivo', 'Hoja', 'Fila', 'Motivo']
MENSAJE_LOGIN = 'Iniciá sesión en Chrome. Cuando veas la biblioteca Comprobantes, volvé acá y apretá Continuar.'


def normalize(value):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().lower())


def columns(row):
    result = {}
    for key, aliases in ALIASES.items():
        matches = [i for i, value in enumerate(row) if normalize(value) in aliases]
        if len(matches) > 1:
            raise ValueError('Hay varias columnas posibles para ' + key + '; dejá un solo encabezado inequívoco.')
        if matches:
            result[key] = matches[0]
    return result if len(result) == 2 else None


def parse_pair(cuit, number):
    if isinstance(cuit, (int, float)):
        if cuit != int(cuit):
            raise ValueError('CUIT numérico con decimales')
        cuit = str(int(cuit))
    cuit = re.sub(r'[\s-]', '', str(cuit or ''))
    if not re.fullmatch(r'\d{11}', cuit):
        raise ValueError('CUIT ausente o inválido; se requieren 11 dígitos')
    number = re.sub(r'\s+', '', str(number or '')).upper()
    if number.endswith('.PDF'):
        number = number[:-4]
    if not re.fullmatch(r'(?:FC|NC|ND)-[A-Z]\d{12,13}', number):
        raise ValueError('Número de comprobante ausente o no reconocido; ejemplo FC-A002100588517')
    return cuit, number


def cargar_listados(paths, nombres=None):
    """= load_inputs del legado. `nombres` ({ruta: nombre a mostrar}) permite informar el nombre original
    del archivo cuando el server lo guardó con otro nombre; sin él se usa el nombre de la ruta."""
    nombres = nombres or {}
    tasks, issues, seen = [], [], set()
    duplicates = 0
    for path in paths:
        path = Path(path)
        nombre = nombres.get(path, path.name)
        matched = False
        with closing(openpyxl.load_workbook(path, read_only=True, data_only=True)) as book:
            for sheet in book:
                mapping = None
                for rowno, row in enumerate(sheet.iter_rows(values_only=True), 1):
                    if mapping is None:
                        if rowno > 100:
                            break
                        mapping = columns(row)
                        if mapping:
                            matched = True
                        continue
                    if not any(v is not None and str(v).strip() for v in row):
                        continue
                    # A repeated header inside the report is not an invoice.
                    if normalize(row[mapping['cuit']]) in ALIASES['cuit'] and normalize(row[mapping['numero']]) in ALIASES['numero']:
                        continue
                    try:
                        pair = parse_pair(row[mapping['cuit']], row[mapping['numero']])
                        if pair in seen:
                            duplicates += 1
                            continue
                        seen.add(pair)
                        tasks.append((*pair, f'{nombre} / {sheet.title} / fila {rowno}'))
                    except Exception as exc:
                        issues.append([nombre, sheet.title, rowno, str(exc)])
        if not matched:
            issues.append([nombre, '', '', 'No se encontró una hoja con columnas CUIT y NumeroFactura en las primeras 100 filas'])
    return tasks, issues, duplicates


def _fecha(valor):
    if valor in (None, ''):
        return None
    if isinstance(valor, date):
        return valor
    return datetime.strptime(str(valor), '%Y-%m-%d').date()


def _escribir_csv(ruta, columnas, filas):
    with Path(ruta).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(columnas)
        writer.writerows(filas)


@contextmanager
def _navegador(sesion, fabrica_navegador):
    if fabrica_navegador is not None:
        context = fabrica_navegador()
        try:
            yield context
        finally:
            context.close()
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(sesion), channel='chrome', headless=False)
        try:
            yield context
        finally:
            context.close()


def ejecutar(listados, salida, parametros, informar=protocolo, fabrica_navegador=None, nombres=None):
    """Descarga las facturas de los listados. Escribe descarga.csv y entrada_a_revisar.csv en `salida`
    y devuelve {'descarga': filas, 'entrada_a_revisar': filas, 'resumen': {...}}."""
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    origen = str(parametros['origen']).strip().rstrip('/')
    sitio = origen + '/' + str(parametros.get('sitio') or '').strip('/')
    biblioteca = '/' + str(parametros['biblioteca']).strip().strip('/')
    vista = origen + biblioteca + '/Forms/AllItems.aspx'
    sesion = Path(parametros.get('sesion_chrome') or (salida.parent / 'sesion_chrome'))

    informar.paso('Leyendo el listado')
    tasks, issues, duplicates = cargar_listados([Path(p) for p in listados], nombres)
    _escribir_csv(salida / 'entrada_a_revisar.csv', COLUMNAS_REVISAR, issues)
    informar.log(f'Facturas únicas: {len(tasks)}. Repeticiones omitidas: {duplicates}. Filas/archivos para revisar: {len(issues)}.')
    if not tasks:
        raise ValueError('No hay facturas válidas para descargar.')
    start = _fecha(parametros.get('desde'))
    end = _fecha(parametros.get('hasta'))
    if start and end and start > end:
        raise ValueError('Desde no puede ser posterior a hasta.')
    concept_filter = str(parametros.get('concepto') or '').strip()
    dest = Path(str(parametros['destino']).strip().strip('"'))
    if not dest.is_dir():
        raise ValueError('La carpeta destino no existe. Creala o copiá su ruta correcta.')

    report = salida / 'descarga.csv'
    counts = {}
    filas = []
    informar.paso('Abriendo Chrome')
    with report.open('w', newline='', encoding='utf-8-sig') as f, _navegador(sesion, fabrica_navegador) as context:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(COLUMNAS_DESCARGA)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(vista, wait_until='domcontentloaded', timeout=120000)
        informar.esperar('login', MENSAJE_LOGIN, 'Continuar')
        web = core.wait_for_library(page, origen)
        if web:
            sitio = core.check_url(web, origen).rstrip('/')
        informar.paso('Descargando facturas')
        total = len(tasks)
        for index, (cuit, number, source_row) in enumerate(tasks, 1):
            emitted, concepts = None, []
            informar.progreso(index / total, f'{index}/{total} {number}')
            try:
                source = biblioteca + '/' + cuit + '/' + number + '.pdf'
                response = core.get_response(context, origen + quote(source, safe='/'), origen, informar=informar)
                data = response.body()
                if b'%PDF-' not in data[:1024]:
                    raise ValueError('La respuesta no es un PDF; revisar sesión o ubicación')
                emitted, concepts = core.read_pdf(data)
                # Check that SharePoint returned the requested document.
                text = core.texto_pdf(data)
                if number not in re.sub(r'\s+', '', text).upper():
                    raise ValueError('No se pudo confirmar el número de factura dentro del PDF')
                if (start and emitted < start) or (end and emitted > end):
                    status, detail = 'Fuera del período', ''
                elif concept_filter and concepts and not any(normalize(concept_filter) in normalize(c) for c in concepts):
                    status, detail = 'Otro concepto', ''
                else:
                    category = concepts[0] if len(concepts) == 1 else ('Varios conceptos' if concepts else 'Para revisar')
                    target = dest / emitted.strftime('%Y-%m') / core.safe_name(category) / (number + '.pdf')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        status = 'Ya existía' if target.read_bytes() == data else 'CONFLICTO: no se reemplazó'
                    else:
                        with target.open('xb') as out:
                            out.write(data)
                        status = 'Copiada' if concepts else 'REVISAR: concepto no identificado'
                    detail = str(target)
            except Exception as exc:
                status, detail = 'ERROR', str(exc)
            counts[status] = counts.get(status, 0) + 1
            fila = [cuit, number, emitted.strftime('%d/%m/%Y') if emitted else '', ' | '.join(concepts), status, detail, source_row]
            filas.append(fila)
            writer.writerow(fila)
            f.flush()
            informar.log('  ' + status)
    informar.log('Finalizó la lectura del listado.')
    for status, count in counts.items():
        informar.log(f'{status}: {count}')
    informar.log('Revisá los errores, conflictos y filas de entrada inválidas antes de dar la descarga por completa.')
    informar.log('OneDrive debe estar sincronizando la carpeta destino para subir las copias a SharePoint.')
    resumen = {'facturas_unicas': len(tasks), 'repeticiones_omitidas': duplicates, 'filas_a_revisar': len(issues),
               'estados': dict(counts)}
    return {'descarga': filas, 'entrada_a_revisar': issues, 'resumen': resumen, 'sitio': sitio}


# --- Doble de navegador para pruebas (sin Playwright ni SharePoint) ---

class _RespuestaSimulada:
    def __init__(self, url, datos):
        self.url = url
        self.status = 200 if datos is not None else 404
        self.ok = datos is not None
        self.headers = {}
        self._datos = datos if datos is not None else b'No existe el archivo'

    def body(self):
        return self._datos

    def text(self):
        return self._datos.decode('utf-8', 'replace')

    def json(self):
        raise ValueError('No es JSON')


class _PedidosSimulados:
    def __init__(self, carpeta):
        self.carpeta = Path(carpeta)

    def get(self, url, headers=None, timeout=None):
        partes = [unquote(p) for p in urlparse(url).path.split('/') if p]
        ruta = self.carpeta.joinpath(*partes[-2:]) if len(partes) >= 2 else None
        datos = ruta.read_bytes() if ruta and ruta.is_file() else None
        return _RespuestaSimulada(url, datos)


class _PaginaSimulada:
    def __init__(self, sitio):
        self.url = 'about:blank'
        self._sitio = sitio

    def goto(self, url, **kwargs):
        self.url = url

    def is_closed(self):
        return False

    def wait_for_load_state(self, *args, **kwargs):
        pass

    def wait_for_timeout(self, ms):
        pass

    def evaluate(self, script):
        return self._sitio


class _NavegadorSimulado:
    def __init__(self, carpeta, sitio):
        self.pages = [_PaginaSimulada(sitio)]
        self.request = _PedidosSimulados(carpeta)
        self.cerrado = False

    def new_page(self):
        pagina = _PaginaSimulada(self.pages[0]._sitio if self.pages else '')
        self.pages.append(pagina)
        return pagina

    def close(self):
        self.cerrado = True


def navegador_simulado(carpeta, sitio=''):
    """Fábrica para `ejecutar(..., fabrica_navegador=...)`: sirve `<carpeta>/<CUIT>/<numero>.pdf`."""
    return lambda: _NavegadorSimulado(carpeta, sitio)
