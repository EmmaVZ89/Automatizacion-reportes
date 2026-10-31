"""Token de sesión, cookie, verificación de origen, cabeceras y saneado de nombres y rutas."""
import re
import secrets
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

NOMBRE_COOKIE = 'reportes_token'
EXT_ENTRADA = {'.xlsx', '.xlsm'}
CABECERAS_BASE = {
    'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'",
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
    'X-Frame-Options': 'DENY',
}


def nuevo_token():
    return secrets.token_urlsafe(32)


def cookie_de_token(token):
    return f'{NOMBRE_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict'


def _query(valor):
    if isinstance(valor, dict):
        return valor
    return {k: v[0] for k, v in parse_qs(valor or '', keep_blank_values=False).items()}


def token_de_peticion(headers, query):
    q = _query(query)
    if q.get('t'):
        return q['t']
    crudo = headers.get('Cookie') if hasattr(headers, 'get') else None
    if crudo:
        jar = SimpleCookie()
        try:
            jar.load(crudo)
        except Exception:
            return None
        if NOMBRE_COOKIE in jar:
            return jar[NOMBRE_COOKIE].value
    return None


def peticion_autorizada(headers, query, token, modifica, host):
    """(ok, motivo). Toda petición exige el token; las que modifican, además, un origen propio."""
    recibido = token_de_peticion(headers, query)
    if not recibido or not secrets.compare_digest(recibido, token):
        return False, 'Abrí la herramienta desde su acceso directo.'
    if modifica:
        origen = headers.get('Origin')
        if origen and origen.rstrip('/') != f'http://{host}':
            return False, 'La petición no viene de la herramienta.'
        sitio = headers.get('Sec-Fetch-Site')
        if sitio and sitio not in ('same-origin', 'none'):
            return False, 'La petición no viene de la herramienta.'
    return True, ''


_RE_NOMBRE = re.compile(r'[^\w .()\-]+', re.UNICODE)


def nombre_seguro(nombre):
    base = str(nombre or '').replace('\\', '/').split('/')[-1].strip()
    base = _RE_NOMBRE.sub('-', base).strip(' .')
    if not base:
        base = 'archivo'
    punto = base.rfind('.')
    if punto > 0:
        base = base[:punto] + base[punto:].lower()
    if len(base) > 120:
        ext = base[punto:] if punto > 0 else ''
        base = base[:120 - len(ext)] + ext
    return base


def ruta_confinada(base, relativa):
    base = Path(base).resolve()
    texto = str(relativa or '')
    if not texto or '\x00' in texto or re.match(r'^[A-Za-z]:', texto) or texto.startswith(('/', '\\')):
        raise ValueError('Ruta no permitida')
    destino = (base / texto).resolve()
    if destino != base and base not in destino.parents:
        raise ValueError('Ruta no permitida')
    return destino


def host_de(headers, por_defecto):
    valor = headers.get('Host') if hasattr(headers, 'get') else None
    return valor or por_defecto


def ruta_y_query(objetivo):
    partes = urlsplit(objetivo)
    return partes.path, _query(partes.query)
