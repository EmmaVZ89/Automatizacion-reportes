"""Regresión de la Descarga de facturas contra el legado, sobre PDF reales. Imprime cada diferencia con su
explicación y sale con 0 (SIN DIFERENCIAS NO EXPLICADAS) o 1.

    .venv\\Scripts\\python.exe herramientas/regresion_facturas.py --pdfs <carpeta> [--mostrar-conceptos] [--salida <carpeta>]

1. Lectura: para cada PDF de la carpeta compara la fecha y los conceptos que leen `read_pdf` del legado
   (`legado/descarga_facturas/facturas.py`, v5) y `app/reportes/descarga_facturas/sharepoint.read_pdf`, y explica
   la diferencia por los cambios acordados (docs/reglas/descarga_facturas.md).
2. Descarga simulada: corre el motor con el navegador simulado sobre esos PDF (CUIT inventado, sin Chrome ni
   SharePoint) y muestra el estado de cada factura y la carpeta del destino donde quedó.

Cada archivo se tiene que llamar como el número de la factura (`FC-A002100000000.pdf`, como en la biblioteca): el
motor confirma que el número esté dentro del PDF. Necesita pdfplumber (el .venv de facturas). Los conceptos se
muestran sólo con --mostrar-conceptos, porque el del legado puede traer el importe en letras. El destino simulado
queda en --salida (por defecto una carpeta temporal) para mirarlo."""
import argparse
import hashlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'vendor'))

LEGADO = RAIZ / 'legado' / 'descarga_facturas' / 'facturas.py'
CUIT = '20123456789'
ORIGEN = 'https://ejemplo.sharepoint.com'
RESERVADAS = ('Para revisar', 'Varios conceptos')


def forma(data):
    """Cómo cierra los ítems el PDF: {hojas, subtotal, total, en_otra_hoja}. `en_otra_hoja`: la primera hoja con
    ítems no tiene rótulo de cierre y una hoja siguiente sí."""
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        hojas = [{w['text'] for w in page.extract_words()} for page in pdf.pages]
    rotulos = [{t.lower() for t in h} & {'subtotal:', 'total:'} for h in hojas]
    con_items = next((i for i, h in enumerate(hojas) if 'Concepto' in h and h & {'Operación', 'Operacion'}), None)
    return {'hojas': len(hojas), 'subtotal': any('subtotal:' in r for r in rotulos),
            'total': any('total:' in r for r in rotulos),
            'en_otra_hoja': con_items is not None and not rotulos[con_items] and any(rotulos[con_items + 1:])}


def describir(f):
    texto = 'A (SubTotal:)' if f['subtotal'] else 'B (sólo TOTAL:)' if f['total'] else 'sin rótulo'
    texto += ', 1 hoja' if f['hojas'] == 1 else f", {f['hojas']} hojas"
    return texto + (', rótulo en la hoja siguiente' if f['en_otra_hoja'] else '')


def explicar(legado, nuevo, f):
    """(texto, explicada) para la lectura del legado y la nueva, cada una (fecha, conceptos), de un PDF de forma `f`."""
    if legado[0] != nuevo[0]:
        return 'FECHA DISTINTA', False
    if legado[1] == nuevo[1]:
        return 'conceptos iguales', True
    if not nuevo[1] and not f['subtotal'] and not f['total']:
        return 'sin SubTotal: ni TOTAL: el nuevo la manda a Para revisar (cambio 2026.11.03)', True
    if (f['total'] and not f['subtotal'] and len(legado[1]) == len(nuevo[1])
            and all(v.startswith(n) and v != n for v, n in zip(legado[1], nuevo[1]))):
        return 'el legado se lleva lo que sigue al ítem (el importe en letras); el nuevo corta en TOTAL: (cambio 2026.11.03)', True
    return 'CONCEPTOS DISTINTOS', False


def _legado():
    spec = importlib.util.spec_from_file_location('facturas_legado', LEGADO)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def comparar(pdfs):
    """Una fila por PDF: {archivo, sha8, forma, legado, nuevo, explicacion, explicada}."""
    from app.reportes.descarga_facturas import sharepoint
    legado = _legado()
    filas = []
    for ruta in pdfs:
        data = ruta.read_bytes()
        f = forma(data)
        viejo, nuevo = legado.read_pdf(data), sharepoint.read_pdf(data)
        texto, explicada = explicar(viejo, nuevo, f)
        filas.append({'archivo': ruta.name, 'sha8': hashlib.sha256(data).hexdigest()[:8], 'forma': f, 'legado': viejo,
                      'nuevo': nuevo, 'explicacion': texto, 'explicada': explicada})
    return filas


class _Silencio:
    """Protocolo mudo para el motor: la pausa de inicio de sesión sigue sola."""

    def log(self, m):
        pass

    def paso(self, m):
        pass

    def progreso(self, v, m=''):
        pass

    def esperar(self, id, mensaje, boton='Continuar'):
        pass


def simular(pdfs, trabajo):
    """Corre el motor con el navegador simulado: devuelve el destino y [(factura, estado, carpeta del destino)]."""
    import openpyxl
    from app.reportes.descarga_facturas import motor
    biblioteca, destino = trabajo / 'biblioteca', trabajo / 'destino'
    (biblioteca / CUIT).mkdir(parents=True)
    destino.mkdir()
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append(['CUIT', 'NumeroFactura'])
    for ruta in pdfs:
        (biblioteca / CUIT / ruta.name).write_bytes(ruta.read_bytes())
        hoja.append([CUIT, ruta.stem])
    libro.save(trabajo / 'listado.xlsx')
    parametros = {'origen': ORIGEN, 'sitio': '/sites/Sitio', 'biblioteca': '/sites/Sitio/Area/Comprobantes',
                  'destino': str(destino), 'desde': None, 'hasta': None, 'concepto': '',
                  'sesion_chrome': str(trabajo / 'sesion')}
    r = motor.ejecutar([trabajo / 'listado.xlsx'], trabajo / 'salidas', parametros, informar=_Silencio(),
                       fabrica_navegador=motor.navegador_simulado(biblioteca, ORIGEN + '/sites/Sitio'))
    filas = []
    for fila in r['descarga']:
        detalle = Path(fila[5]) if fila[5] else None
        carpeta = detalle.parent.name if detalle and detalle.parent.parent == destino else ''
        filas.append((fila[1], fila[4], carpeta))
    return destino, filas


def main(argv=None):
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description='Regresión de la Descarga de facturas contra el legado')
    p.add_argument('--pdfs', required=True, help='Carpeta con los PDF reales, cada uno con el número de la factura como nombre')
    p.add_argument('--mostrar-conceptos', action='store_true', help='Muestra los conceptos (pueden traer el importe en letras)')
    p.add_argument('--salida', help='Carpeta donde dejar la descarga simulada (default: temporal)')
    args = p.parse_args(argv)
    pdfs = sorted(Path(args.pdfs).glob('*.pdf'))
    if not pdfs:
        p.error('La carpeta no tiene PDF.')
    salida = Path(args.salida) if args.salida else Path(tempfile.mkdtemp(prefix='regresion_facturas_'))
    salida.mkdir(parents=True, exist_ok=True)
    problemas = 0
    print(f'Lectura de los PDF, legado contra nuevo ({len(pdfs)}):')
    for fila in comparar(pdfs):
        problemas += not fila['explicada']
        print(f"  {fila['archivo']}  sha256={fila['sha8']}…  {describir(fila['forma'])}  |  {fila['explicacion']}")
        if args.mostrar_conceptos:
            print(f"      legado: {fila['legado'][1]}\n      nuevo:  {fila['nuevo'][1]}")
    destino, filas = simular(pdfs, salida)
    print(f'Descarga simulada (destino: {destino}):')
    for factura, estado, carpeta in filas:
        problemas += estado == 'ERROR'
        if carpeta and carpeta not in RESERVADAS and not args.mostrar_conceptos:
            carpeta = '<carpeta del concepto>'
        print(f'  {factura}  {estado}  {carpeta}')
    print('SIN DIFERENCIAS NO EXPLICADAS' if not problemas else f'{problemas} DIFERENCIAS NO EXPLICADAS O ERRORES')
    return 1 if problemas else 0


if __name__ == '__main__':
    sys.exit(main())
