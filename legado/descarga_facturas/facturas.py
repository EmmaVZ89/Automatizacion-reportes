import csv
import hashlib
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import pdfplumber

BASE = Path(__file__).resolve().parent
ORIGIN = 'https://ORGANIZACION.sharepoint.com'  # redactado para el repositorio público
SITE = ORIGIN + '/sites/DynamicsERP'
ROOT = '/sites/DynamicsERP/GTZ/Comprobantes'
VIEW = ORIGIN + ROOT + '/Forms/AllItems.aspx'
DEST = Path(r'C:\RUTA\DESTINO\20 FACTURAS')  # redactado para el repositorio público


def read_pdf(data):
    dates, concepts = set(), set()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            dates.update(re.findall(r'Fecha de Emisi[oó]n:\s*(\d{2}/\d{2}/\d{4})', text, re.I))
            words = page.extract_words()
            heads = [w for w in words if w['text'] == 'Concepto']
            ops = [w for w in words if w['text'] in ('Operación', 'Operacion')]
            if not heads or not ops:
                continue
            top = heads[0]['bottom'] + 2
            right = ops[0]['x0'] - 5
            stops = [w['top'] for w in words if w['top'] > top and w['text'].lower() == 'subtotal:']
            bottom = min(stops) if stops else page.height - 120
            starts = sorted({round(w['top'], 1) for w in words
                             if top < w['top'] < bottom and right < w['x0'] < right + 100
                             and re.fullmatch(r'\d+/\d+', w['text'])})
            if not starts:
                continue
            for a, b in zip(starts, starts[1:] + [bottom]):
                selected = [w for w in words if w['x0'] < right and a - 3 <= w['top'] < b - 3]
                selected.sort(key=lambda w: (round(w['top'] / 3), w['x0']))
                concept = re.sub(r'\s+', ' ', ' '.join(w['text'] for w in selected)).strip(' .')
                if concept:
                    concepts.add(concept)
    if len(dates) != 1:
        raise ValueError('No se pudo identificar una única fecha de emisión')
    return datetime.strptime(dates.pop(), '%d/%m/%Y').date(), sorted(concepts)


def safe_name(text):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f#%]', '-', text).strip(' .')
    if len(text) > 90:
        text = text[:80] + '-' + hashlib.sha256(text.encode()).hexdigest()[:8]
    return text or 'Para revisar'


def endpoint(folder, collection):
    escaped = quote(folder.replace("'", "''"), safe='/')
    return SITE + "/_api/web/GetFolderByServerRelativeUrl('" + escaped + "')/" + collection


def check_url(url):
    if urlparse(url).netloc != urlparse(ORIGIN).netloc:
        raise ValueError('SharePoint devolvió una dirección fuera del sitio esperado')
    return url


def get_response(context, url, timeout_ms=30000, attempts=3):
    check_url(url)
    import time
    for attempt in range(attempts):
        try:
            response = context.request.get(url, headers={'Accept': 'application/json;odata=nometadata'}, timeout=timeout_ms)
        except Exception as exc:
            if 'Timeout' in type(exc).__name__:
                raise RuntimeError('SharePoint no respondió dentro de 30 segundos. No se completó la consulta; no se confirmó una descarga completa.') from exc
            raise
        check_url(response.url)
        if response.status in (429, 503) and attempt < attempts - 1:
            try:
                delay = max(1, min(int(response.headers.get('retry-after', '10')), 30))
            except ValueError:
                delay = 10
            print(f'SharePoint está ocupado (HTTP {response.status}). Reintento en {delay} segundos...', flush=True)
            time.sleep(delay)
            continue
        if not response.ok:
            detail = re.sub(r'\s+', ' ', response.text())[:900]
            raise RuntimeError(f'SharePoint respondió HTTP {response.status}. Detalle: {detail}')
        return response


def list_items(context, url):
    while url:
        response = get_response(context, url)
        try:
            value = response.json()
        except Exception:
            raise RuntimeError('No se pudo leer la biblioteca. Revisá que hayas iniciado sesión.')
        payload = value.get('d', value)
        yield from payload.get('results', payload.get('value', []))
        url = payload.get('__next') or payload.get('odata.nextLink') or payload.get('@odata.nextLink')
        if url:
            url = urljoin(SITE + '/', url)


def inventory(context, folder):
    # Enumerate indexed ID ranges instead of requesting a large folder view.
    escaped = quote(ROOT.replace("'", "''"), safe='/')
    base = SITE + "/_api/web/GetList('" + escaped + "')/items"
    print('PASO 1: consultando el último registro de la biblioteca (máximo 30 segundos)...', flush=True)
    try:
        response = get_response(context, base + '?$select=Id&$orderby=Id%20desc&$top=1', attempts=1)
        value = response.json()
        payload = value.get('d', value)
        latest = payload.get('results', payload.get('value', []))
    except Exception as exc:
        raise RuntimeError('Falló PASO 1, consulta del último registro. ' + str(exc)) from exc
    if not latest:
        return
    maximum = int(latest[0]['Id'])
    print(f'PASO 1 completado. Último ID: {maximum}. Comienza la consulta por bloques.', flush=True)
    for lower in range(0, maximum, 2000):
        upper = min(lower + 2000, maximum)
        print(f'Consultando bloque de registros {lower + 1} a {upper} (máximo {maximum})...', flush=True)
        url = (base + '?$select=Id,FileLeafRef,FileRef,FSObjType,Modified'
               + f'&$filter=Id%20gt%20{lower}%20and%20Id%20le%20{upper}'
               + '&$orderby=Id%20asc&$top=500')
        for item in list_items(context, url):
            path = item.get('FileRef', '')
            if int(item.get('FSObjType', 1)) == 0 and path.startswith(folder.rstrip('/') + '/'):
                yield {'Name': item['FileLeafRef'], 'ServerRelativeUrl': path,
                       'TimeLastModified': item['Modified']}


def selected_files(context, numbers, folder):
    for number in sorted(numbers):
        name = number.upper() + '.pdf'
        path = folder + '/' + name
        escaped = quote(path.replace("'", "''"), safe='/')
        url = SITE + "/_api/web/GetFileByServerRelativeUrl('" + escaped + "')?$select=Name,ServerRelativeUrl,TimeLastModified"
        value = get_response(context, url).json()
        yield value.get('d', value)


def ask_date(label):
    while True:
        try:
            return datetime.strptime(input(label + ' (dd/mm/aaaa): ').strip(), '%d/%m/%Y').date()
        except ValueError:
            print('Escribí una fecha válida, por ejemplo 22/10/2026.')


def wait_for_library(page):
    from playwright.sync_api import Error
    import time
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if page.is_closed():
            raise RuntimeError('Se cerró Chrome. Volvé a ejecutar y dejá abierta la biblioteca.')
        try:
            page.wait_for_load_state('domcontentloaded', timeout=5000)
            if urlparse(page.url).netloc == urlparse(ORIGIN).netloc and '/Comprobantes' in urlparse(page.url).path:
                web_url = page.evaluate("() => window._spPageContextInfo && window._spPageContextInfo.webAbsoluteUrl || null")
                return web_url
        except Error:
            pass
        page.wait_for_timeout(1000)
    raise RuntimeError('Chrome no llegó a la biblioteca Comprobantes. Volvé a ejecutar, completá el inicio de sesión y presioná Enter solo cuando veas los archivos.')


def main():
    global SITE
    from playwright.sync_api import sync_playwright
    print('DESCARGA Y CLASIFICACIÓN DE FACTURAS - VERSION 5\n')
    print('Programa: ' + str(Path(__file__).resolve()), flush=True)
    start = ask_date('Fecha de emisión desde')
    end = ask_date('Fecha de emisión hasta')
    if start > end:
        raise ValueError('La fecha desde debe ser anterior o igual a la fecha hasta.')
    concept_filter = input('Concepto a buscar (vacío = todos): ').strip().casefold()
    numbers = {x.strip().casefold().removesuffix('.pdf') for x in input('Números completos de factura separados por coma (vacío = todas): ').split(',') if x.strip()}
    cuit = input('CUIT de la carpeta de origen (opcional; vacío = buscar en todas): ').strip()
    if cuit and not re.fullmatch(r'\d{11}', cuit):
        raise ValueError('El CUIT debe tener 11 números, sin guiones ni espacios.')
    folder = ROOT + '/' + cuit if cuit else ROOT
    if not DEST.is_dir():
        raise RuntimeError('No existe la carpeta de destino configurada. Revisá DEST en facturas.py.')
    print('\nPara conocer la emisión y el concepto hay que leer los PDF.')
    print('La primera ejecución puede tardar: examina toda la biblioteca. Las siguientes reutilizan la caché local.')
    cache = BASE / 'cache_pdf'
    cache.mkdir(exist_ok=True)
    logdir = BASE / 'resultados'
    logdir.mkdir(exist_ok=True)
    report = logdir / ('resultado_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.csv')
    count = errors = examined = 0
    with report.open('w', newline='', encoding='utf-8-sig') as f, sync_playwright() as p:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Archivo', 'Emision', 'Conceptos', 'Estado', 'Destino o detalle'])
        context = p.chromium.launch_persistent_context(str(BASE / 'sesion_chrome'), channel='chrome', headless=False, accept_downloads=True)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(VIEW, wait_until='domcontentloaded', timeout=120000)
            input('\nIniciá sesión en Chrome. Esperá a ver los PDF de Comprobantes. Después volvé acá y presioná SOLO ENTER (no escribas el número de factura). ')
            print('Esperando a que Chrome termine de cargar la biblioteca...')
            web_url = wait_for_library(page)
            if web_url:
                SITE = check_url(web_url).rstrip('/')
            print('Buscando las facturas indicadas...' if numbers else 'Leyendo el listado de archivos...')
            seen = set()
            items = selected_files(context, numbers, folder) if numbers and cuit else inventory(context, folder)
            for item in items:
                name = item['Name']
                source = item['ServerRelativeUrl']
                if source in seen or not name.lower().endswith('.pdf'):
                    continue
                seen.add(source)
                if numbers and name.casefold().removesuffix('.pdf') not in numbers:
                    continue
                try:
                    examined += 1
                    if examined == 1 or examined % 50 == 0:
                        print(f'PDF examinados: {examined}. Copiados: {count}. Actual: {name}', flush=True)
                    key = hashlib.sha256((source + item['TimeLastModified']).encode()).hexdigest()
                    cached = cache / (key + '.pdf')
                    if not cached.exists():
                        response = get_response(context, ORIGIN + quote(source, safe='/'))
                        data = response.body()
                        if b'%PDF-' not in data[:1024]:
                            raise ValueError('La respuesta no es un PDF; podría requerir iniciar sesión nuevamente')
                        cached.write_bytes(data)
                    data = cached.read_bytes()
                    emitted, concepts = read_pdf(data)
                    if not start <= emitted <= end:
                        continue
                    if concept_filter and concepts and not any(concept_filter in c.casefold() for c in concepts):
                        continue
                    category = concepts[0] if len(concepts) == 1 else ('Varios conceptos' if concepts else 'Para revisar')
                    target = DEST / emitted.strftime('%Y-%m') / safe_name(category) / safe_name(name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        if target.read_bytes() == data:
                            status = 'Ya existía'
                        else:
                            status = 'REVISAR: mismo nombre con contenido diferente; no se reemplazó'
                            errors += 1
                    else:
                        with target.open('xb') as out:
                            out.write(data)
                        status = 'Copiada' if concepts else 'REVISAR: concepto no identificado'
                        count += 1
                    writer.writerow([name, emitted.strftime('%d/%m/%Y'), ' | '.join(concepts), status, str(target)])
                    f.flush()
                    print(name + ': ' + status)
                except Exception as exc:
                    errors += 1
                    writer.writerow([name, '', '', 'ERROR / PARA REVISAR', str(exc)])
                    f.flush()
                    print(name + ': ERROR (ver resultado)')
            print(f'\nFinalizado. Copiadas: {count}. Errores/conflictos: {errors}.')
            if numbers:
                found_names = {Path(path).name.casefold().removesuffix('.pdf') for path in seen}
                missing = numbers - found_names
                for missing_name in sorted(missing):
                    writer.writerow([missing_name, '', '', 'NO ENCONTRADA', 'No se encontró en las carpetas consultadas'])
                    print('NO ENCONTRADA: ' + missing_name)
            print('Resultado: ' + str(report))
            print('La subida a SharePoint depende de que OneDrive esté sincronizando la carpeta destino.')
        finally:
            context.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nProceso interrumpido. Podés volver a ejecutarlo.')
        sys.exit(1)
    except Exception as exc:
        print('\nNo se completó el proceso: ' + str(exc))
        sys.exit(1)
