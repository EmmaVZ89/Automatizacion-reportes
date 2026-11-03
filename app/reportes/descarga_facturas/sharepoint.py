"""Funciones de apoyo tomadas de `legado/descarga_facturas/facturas.py` (v5): lectura del PDF, nombre
seguro de carpeta, control de dominio, pedido con reintentos y espera de la biblioteca en Chrome.

Sin constantes fijas: el origen (`https://organizacion.sharepoint.com`) llega por parámetro y
`check_url` sólo acepta direcciones de ese dominio. El recorrido completo de la biblioteca de la v5
(`inventory`, `selected_files`, `main`) no se porta: el flujo que se usa es el de `listado.py` (v6)."""
import hashlib
import io
import re
import time
from datetime import datetime
from urllib.parse import quote, urlparse  # noqa: F401  (quote lo usa el motor)

from .._comun import protocolo


def read_pdf(data):
    import pdfplumber
    dates, concepts = set(), set()
    sin_corte = False
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        hojas = [(page, page.extract_words()) for page in pdf.pages]
        # Hojas que tienen el rótulo de cierre: con muchos ítems, el SubTotal/TOTAL pasa a la hoja siguiente.
        cierres = [any(w['text'].lower() in ('subtotal:', 'total:') for w in words) for _, words in hojas]
        for n, (page, words) in enumerate(hojas):
            text = page.extract_text() or ''
            dates.update(re.findall(r'Fecha de Emisi[oó]n:\s*(\d{2}/\d{2}/\d{4})', text, re.I))
            heads = [w for w in words if w['text'] == 'Concepto']
            ops = [w for w in words if w['text'] in ('Operación', 'Operacion')]
            if not heads or not ops:
                continue
            top = heads[0]['bottom'] + 2
            right = ops[0]['x0'] - 5
            # La factura A cierra los ítems con «SubTotal:»; la B no lo tiene y los cierra con «TOTAL:».
            stops = [w['top'] for w in words if w['top'] > top and w['text'].lower() in ('subtotal:', 'total:')]
            bottom = min(stops) if stops else page.height - 120
            starts = sorted({round(w['top'], 1) for w in words
                             if top < w['top'] < bottom and right < w['x0'] < right + 100
                             and re.fullmatch(r'\d+/\d+', w['text'])})
            if not starts:
                continue
            if not stops and not any(cierres[n + 1:]):
                # Sin rótulo en ninguna hoja no se sabe dónde termina el último ítem (se llevaría el importe en
                # letras): a «Para revisar». Si cierra en una hoja posterior, esta hoja termina al pie, como el legado.
                sin_corte = True
                continue
            for a, b in zip(starts, starts[1:] + [bottom]):
                selected = [w for w in words if w['x0'] < right and a - 3 <= w['top'] < b - 3]
                selected.sort(key=lambda w: (round(w['top'] / 3), w['x0']))
                concept = re.sub(r'\s+', ' ', ' '.join(w['text'] for w in selected)).strip(' .')
                if concept:
                    concepts.add(concept)
    if len(dates) != 1:
        raise ValueError('No se pudo identificar una única fecha de emisión')
    return datetime.strptime(dates.pop(), '%d/%m/%Y').date(), [] if sin_corte else sorted(concepts)


def texto_pdf(data):
    """Texto completo del PDF (para confirmar que SharePoint devolvió el comprobante pedido)."""
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return '\n'.join(page.extract_text() or '' for page in pdf.pages)


def safe_name(text):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f#%]', '-', text).strip(' .')
    if len(text) > 90:
        text = text[:80] + '-' + hashlib.sha256(text.encode()).hexdigest()[:8]
    return text or 'Para revisar'


def check_url(url, origen):
    if urlparse(url).netloc != urlparse(origen).netloc:
        raise ValueError('SharePoint devolvió una dirección fuera del sitio esperado')
    return url


def get_response(context, url, origen, timeout_ms=30000, attempts=3, informar=protocolo):
    check_url(url, origen)
    for attempt in range(attempts):
        try:
            response = context.request.get(url, headers={'Accept': 'application/json;odata=nometadata'}, timeout=timeout_ms)
        except Exception as exc:
            if 'Timeout' in type(exc).__name__:
                raise RuntimeError('SharePoint no respondió dentro de 30 segundos. No se completó la consulta; no se confirmó una descarga completa.') from exc
            raise
        check_url(response.url, origen)
        if response.status in (429, 503) and attempt < attempts - 1:
            try:
                delay = max(1, min(int(response.headers.get('retry-after', '10')), 30))
            except ValueError:
                delay = 10
            informar.log(f'SharePoint está ocupado (HTTP {response.status}). Reintento en {delay} segundos...')
            time.sleep(delay)
            continue
        if not response.ok:
            detail = re.sub(r'\s+', ' ', response.text())[:900]
            raise RuntimeError(f'SharePoint respondió HTTP {response.status}. Detalle: {detail}')
        return response


def wait_for_library(page, origen):
    try:
        from playwright.sync_api import Error
    except ImportError:  # dobles de prueba, sin Playwright instalado
        Error = Exception
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if page.is_closed():
            raise RuntimeError('Se cerró Chrome. Volvé a ejecutar y dejá abierta la biblioteca.')
        try:
            page.wait_for_load_state('domcontentloaded', timeout=5000)
            if urlparse(page.url).netloc == urlparse(origen).netloc and '/Comprobantes' in urlparse(page.url).path:
                web_url = page.evaluate("() => window._spPageContextInfo && window._spPageContextInfo.webAbsoluteUrl || null")
                return web_url
        except Error:
            pass
        page.wait_for_timeout(1000)
    raise RuntimeError('Chrome no llegó a la biblioteca Comprobantes. Volvé a ejecutar, completá el inicio de sesión y apretá Continuar solo cuando veas los archivos.')
