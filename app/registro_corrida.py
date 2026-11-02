"""Registro de una corrida para mandar a quien da soporte: un .txt con qué se corrió (reporte, cierre, versión,
opciones y archivos), cómo terminó y el registro completo del reporte, con la hora de cada línea. Lo baja el botón
"Descargar el registro" de Ejecución y de Historial (`GET /api/ejecuciones/<id>/registro/descargar`)."""
import json
from datetime import datetime

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre')
ESTADOS = {'borrador': 'Todavía no corrió', 'listo': 'Lista para correr', 'corriendo': 'Corriendo',
           'esperando': 'Espera una acción', 'ok': 'Terminó bien', 'error': 'Terminó con un error', 'cancelado': 'Se canceló'}
MAX_REGISTRO = 5_000_000  # caracteres; de un registro más largo va el final, que es donde está el error


def _miles(n):
    return f'{n:,}'.replace(',', '.')


def _periodo(p):
    """'2026-10' -> 'octubre 2026'."""
    try:
        anio, mes = str(p).split('-')
        return f'{MESES[int(mes) - 1]} {anio}'
    except (ValueError, IndexError):
        return str(p)


def _fecha(texto):
    """'2026-10-31' -> '31/10/2026'; '2026-11-02T09:31:05' -> '02/11/2026 09:31:05'."""
    try:
        if 'T' in str(texto):
            return datetime.fromisoformat(texto).strftime('%d/%m/%Y %H:%M:%S')
        return datetime.strptime(str(texto), '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        return str(texto)


def _duracion(inicio, fin):
    try:
        segundos = int((datetime.fromisoformat(fin) - datetime.fromisoformat(inicio)).total_seconds())
    except (TypeError, ValueError):
        return ''
    h, resto = divmod(max(0, segundos), 3600)
    m, s = divmod(resto, 60)
    if h:
        return f'{h} h {m} min'
    return f'{m} min {s} s' if m else f'{s} s'


def _tamano(n):
    if n >= 1024 * 1024:
        return f'{n / 1024 / 1024:.1f} MB'.replace('.', ',')
    return f'{max(1, round(n / 1024))} KB'


def valor_parametro(p, v):
    """El valor de una opción como se ve en la pantalla."""
    if v is None or v == '':
        return '(sin completar)'
    for o in p.get('opciones') or []:
        if o.get('valor') == v:
            return o.get('titulo') or str(v)
    if p.get('tipo') == 'fecha':
        return _fecha(v)
    if isinstance(v, bool):
        return 'Sí' if v else 'No'
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def armar(e, cierre, definicion, registro, version, variante='', ahora=None):
    """El texto del registro. `e` es la ejecución, `cierre` su cierre (con sus archivos), `definicion` la del
    reporte en el catálogo, `registro` el texto del registro.log y `variante` el título del fondo, si tiene."""
    ahora = ahora or datetime.now()
    lineas = [f'Reportes de cierre {version} · Registro de la corrida', f'Bajado el {ahora.strftime("%d/%m/%Y %H:%M")}', '']
    lineas.append('Reporte:   ' + (definicion.get('nombre') or e['reporte']) + (f' · {variante}' if variante else ''))
    if cierre.get('periodo'):
        lineas.append('Cierre:    ' + _periodo(cierre['periodo']) + (f' (corte {_fecha(cierre["corte"])})' if cierre.get('corte') else ''))
    lineas.append(f'Versión:   {e.get("version")}' + (' (resultado final)' if e.get('final') else ''))
    if e.get('inicio'):
        horario = _fecha(e['inicio'])
        if e.get('fin'):
            duracion = _duracion(e['inicio'], e['fin'])
            horario += f' a {_fecha(e["fin"])[-8:]}' + (f' ({duracion})' if duracion else '')
        lineas.append('Horario:   ' + horario)
    lineas.append('Estado:    ' + ESTADOS.get(e.get('estado'), str(e.get('estado'))))
    if e.get('error'):
        lineas.append('Qué pasó:  ' + str(e['error']))

    parametros = e.get('parametros') or {}
    opciones = [p for p in definicion.get('parametros') or [] if p['clave'] in parametros and p['clave'] != 'sesion_chrome']
    if opciones:
        lineas += ['', 'Opciones'] + [f'  {p.get("titulo") or p["clave"]}: {valor_parametro(p, parametros[p["clave"]])}' for p in opciones]

    entradas = {k: v for k, v in (e.get('entradas') or {}).items() if v}
    if entradas:
        archivos = {a['id']: a for a in cierre.get('archivos') or []}
        titulos = {x['clave']: x.get('titulo') or x['clave'] for x in definicion.get('entradas') or []}
        lineas += ['', 'Archivos']
        for clave, ids in entradas.items():
            lineas.append('  ' + titulos.get(clave, clave))
            for i in ids:
                a = archivos.get(i)
                if not a:
                    lineas.append('    (un archivo que ya no está en el cierre)')
                    continue
                partes = [a.get('nombre') or '']
                if a.get('bytes'):
                    partes.append(_tamano(a['bytes']))
                if a.get('hoja'):
                    partes.append('hoja ' + str(a['hoja']))
                if isinstance(a.get('filas'), int):
                    partes.append(_miles(a['filas']) + ' filas')
                if a.get('fondo'):
                    partes.append(str(a['fondo']))
                lineas.append('    ' + ' · '.join(partes))

    if e.get('estado') == 'ok' and e.get('salidas'):
        lineas += ['', 'Resultados'] + [f'  {s.get("titulo") or s.get("tabla")}: {_miles(s.get("filas") or 0)} filas' for s in e['salidas']]
        r = e.get('revision') or {}
        if any(r.values()):
            lineas.append(f'  Revisión: {_miles(r.get("pendientes", 0))} pendientes, {_miles(r.get("revisadas", 0))} revisadas, '
                          f'{_miles(r.get("omitidas", 0))} omitidas')

    lineas += ['', 'Registro del reporte']
    texto = registro or ''
    if len(texto) > MAX_REGISTRO:
        texto = '(el principio se recortó: va el final del registro)\n' + texto[-MAX_REGISTRO:]
    cuerpo = texto.splitlines()
    lineas += ['  ' + x for x in cuerpo] if cuerpo else ['  (vacío: el reporte no llegó a arrancar)']
    return '\n'.join(lineas) + '\n'
