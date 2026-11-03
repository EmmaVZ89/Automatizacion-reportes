"""Descarga de facturas: lectura del listado igual al legado, clasificación de los PDF con un
navegador simulado (sin Chrome ni SharePoint) y contrato de ejecutar.py."""
import csv
import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path

from app.reportes.descarga_facturas import motor, sharepoint
from tests.fixtures import carpeta_temporal, xlsx_openpyxl

RAIZ = Path(__file__).resolve().parent.parent
EJECUTAR = RAIZ / 'app' / 'reportes' / 'descarga_facturas' / 'ejecutar.py'
ORIGEN = 'https://ejemplo.sharepoint.com'
PARAMETROS = {'origen': ORIGEN, 'sitio': '/sites/Sitio', 'biblioteca': '/sites/Sitio/Area/Comprobantes'}
HAY_PDFPLUMBER = importlib.util.find_spec('pdfplumber') is not None


def _legado():
    ruta = RAIZ / 'tests' / 'dorados' / 'descarga_facturas' / 'listado_legado.py'
    spec = importlib.util.spec_from_file_location('listado_legado', ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class Informar:
    """Doble del protocolo: registra lo que el motor avisa."""

    def __init__(self):
        self.eventos = []

    def log(self, m):
        self.eventos.append(('log', str(m)))

    def paso(self, m):
        self.eventos.append(('paso', str(m)))

    def progreso(self, v, m=''):
        self.eventos.append(('progreso', float(v), str(m)))

    def esperar(self, id, mensaje, boton='Continuar'):
        self.eventos.append(('esperar', id, mensaje, boton))


# --- PDF mínimo escrito a mano (Helvetica, sin compresión) que pdfplumber lee con extract_words ---

def _pdf_minimo(lineas):
    return _pdf_hojas([lineas])


def _pdf_hojas(hojas):
    """PDF con una hoja por cada lista de renglones (x, y, texto)."""
    def esc(t):
        return t.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    objetos = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [' + b' '.join(f'{4 + 2 * i} 0 R'.encode() for i in range(len(hojas))) + b'] /Count '
        + str(len(hojas)).encode() + b' >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
    ]
    for i, lineas in enumerate(hojas):
        contenido = 'BT /F1 10 Tf\n' + '\n'.join(f'1 0 0 1 {x} {y} Tm ({esc(t)}) Tj' for x, y, t in lineas) + '\nET\n'
        cont = contenido.encode('latin-1')
        objetos += [
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>'.encode(),
            b'<< /Length ' + str(len(cont)).encode() + b' >>\nstream\n' + cont + b'endstream',
        ]
    out = io.BytesIO()
    out.write(b'%PDF-1.4\n')
    offsets = []
    for i, o in enumerate(objetos, 1):
        offsets.append(out.tell())
        out.write(f'{i} 0 obj\n'.encode() + o + b'\nendobj\n')
    xref = out.tell()
    out.write(f'xref\n0 {len(objetos) + 1}\n'.encode() + b'0000000000 65535 f \n')
    for off in offsets:
        out.write(f'{off:010d} 00000 n \n'.encode())
    out.write(f'trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return out.getvalue()


def _factura(numero, fecha, conceptos):
    """conceptos=None: sin bloque Concepto/Operación (el PDF no deja identificar concepto)."""
    lineas = [(50, 740, f'Fecha de Emisi\xf3n: {fecha}'), (50, 700, numero)]
    if conceptos is not None:
        lineas += [(50, 650, 'Concepto'), (400, 650, 'Operaci\xf3n')]
        y = 620
        for i, c in enumerate(conceptos, 1):
            lineas += [(50, y, c), (400, y, f'{i}/{len(conceptos)}')]
            y -= 20
        lineas.append((300, 550, 'Subtotal:'))
    return _pdf_minimo(lineas)


def _biblioteca_simulada(carpeta):
    """<carpeta>/<CUIT>/<numero>.pdf con los casos que el motor tiene que clasificar."""
    pdfs = {
        ('20123456789', 'FC-A002100588517'): _factura('FC-A002100588517', '12/10/2026', ['Servicio mensual']),
        ('20123456789', 'NC-B000000000001'): _factura('NC-B000000000001', '15/10/2026', ['Servicio mensual', 'Otro servicio de prueba']),
        ('27111111111', 'ND-C000000000002'): _factura('ND-C000000000002', '05/09/2026', ['Servicio mensual']),
        ('27111111111', 'FC-A000000000003'): _factura('FC-A000000000003', '20/10/2026', None),
        ('27111111111', 'FC-A000000000004'): _factura('FC-A000000000004', '18/10/2026', ['Servicio mensual']),
        ('27111111111', 'FC-A000000000005'): _factura('FC-A000000000005', '19/10/2026', ['Servicio mensual']),
        ('30999999997', 'FC-A000000000007'): _factura('FC-A000000000099', '21/10/2026', ['Servicio mensual']),
        ('30999999997', 'FC-A000000000008'): _factura('FC-A000000000008', '22/10/2026', ['Otro servicio']),
    }
    for (cuit, numero), datos in pdfs.items():
        ruta = Path(carpeta) / cuit / (numero + '.pdf')
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(datos)
    return pdfs


LISTADO_SIMULACION = [
    ['CUIT', 'NumeroFactura'],
    ['20123456789', 'FC-A002100588517'],
    ['20123456789', 'NC-B000000000001'],
    ['27111111111', 'ND-C000000000002'],
    ['27111111111', 'FC-A000000000003'],
    ['27111111111', 'FC-A000000000004'],
    ['27111111111', 'FC-A000000000005'],
    ['30999999997', 'FC-A000000000006'],
    ['30999999997', 'FC-A000000000007'],
    ['30999999997', 'FC-A000000000008'],
]


def _listado_simple(ruta):
    return xlsx_openpyxl(ruta, [('Hoja1', LISTADO_SIMULACION)])


def _leer_csv(ruta):
    with Path(ruta).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.reader(f, delimiter=';'))


class CargarListados(unittest.TestCase):
    def _fixture(self, d):
        hojas = [
            ('Datos', [
                ['Listado de facturas del mes'],
                [],
                ['Cliente', 'CUIT del cliente', 'Nro. de Factura', 'Importe'],
                ['Uno', '20-12345678-9', 'fc-a002100588517.pdf', 10],
                ['Uno', 20123456789, 'FC-A002100588517', 10],
                ['Dos', 27111111111.0, ' NC-B000000000001 ', 20.5],
                [],
                ['Cliente', 'CUIT del cliente', 'Nro. de Factura', 'Importe'],
                ['Tres', '123', 'FC-A000000000003', 1],
                ['Cuatro', '30-99999999-7', 'XX-1', 1],
                ['Cinco', 20.5, 'FC-A000000000005', 1],
                ['Seis', None, 'FC-A000000000006', 1],
                ['Siete', '30-99999999-7', None, 1],
                ['Ocho', '30999999997', 'ND-C0000000000021', 1],
            ]),
            ('Otra', [['Columna', 'Sin', 'Relacion'], [1, 2, 3]]),
            ('Comprobantes', [['Comprobante', 'NIF'], ['FC-A000000000009', '20123456789'], ['FC-A002100588517', '20123456789']]),
        ]
        a = xlsx_openpyxl(d / 'listado_a.xlsx', hojas)
        b = xlsx_openpyxl(d / 'listado_b.xlsx', [('Resumen', [['Fecha', 'Total'], ['2026-10-01', 5]])])
        return [a, b]

    def test_cargar_listados_igual_que_legado(self):
        legado = _legado()
        with carpeta_temporal() as d:
            paths = self._fixture(d)
            esperado = legado.load_inputs(paths)
            obtenido = motor.cargar_listados(paths)
            self.assertEqual(obtenido, esperado)
            tasks, issues, duplicates = obtenido
            self.assertEqual([t[1] for t in tasks], ['FC-A002100588517', 'NC-B000000000001', 'ND-C0000000000021', 'FC-A000000000009'])
            self.assertEqual(tasks[0][2], 'listado_a.xlsx / Datos / fila 4')
            self.assertEqual(duplicates, 2)
            self.assertEqual([i[2] for i in issues], [9, 10, 11, 12, 13, ''])
            self.assertEqual(issues[-1][0], 'listado_b.xlsx')

    def test_columnas_ambiguas_cortan_como_el_legado(self):
        legado = _legado()
        with carpeta_temporal() as d:
            p = xlsx_openpyxl(d / 'ambiguo.xlsx', [('Hoja1', [['CUIT', 'NIF', 'Factura'], ['20123456789', '20123456789', 'FC-A002100588517']])])
            with self.assertRaises(ValueError) as e1:
                legado.load_inputs([p])
            with self.assertRaises(ValueError) as e2:
                motor.cargar_listados([p])
            self.assertEqual(str(e1.exception), str(e2.exception))

    def test_nombre_original_en_fila_origen(self):
        with carpeta_temporal() as d:
            p = _listado_simple(d / '1a2b3c4d-Listado octubre.xlsx')
            tasks, issues, _ = motor.cargar_listados([p], {p: 'Listado octubre.xlsx'})
            self.assertEqual(tasks[0][2], 'Listado octubre.xlsx / Hoja1 / fila 2')


class Validaciones(unittest.TestCase):
    def test_check_url_rechaza_otro_dominio(self):
        self.assertEqual(sharepoint.check_url(ORIGEN + '/sites/x/a.pdf', ORIGEN), ORIGEN + '/sites/x/a.pdf')
        with self.assertRaises(ValueError) as e:
            sharepoint.check_url('https://otro-dominio.example/sites/x/a.pdf', ORIGEN)
        self.assertIn('fuera del sitio esperado', str(e.exception))
        with self.assertRaises(ValueError):
            sharepoint.get_response(None, 'https://otro-dominio.example/a', ORIGEN)

    def test_destino_inexistente_corta_con_mensaje_llano(self):
        with carpeta_temporal() as d:
            p = _listado_simple(d / 'listado.xlsx')
            parametros = dict(PARAMETROS, destino=str(d / 'no_existe'), sesion_chrome=str(d / 'sesion'))
            informar = Informar()
            with self.assertRaises(ValueError) as e:
                motor.ejecutar([p], d / 'salidas', parametros, informar=informar, fabrica_navegador=motor.navegador_simulado(d))
            self.assertEqual(str(e.exception), 'La carpeta destino no existe. Creala o copiá su ruta correcta.')
            self.assertNotIn(('esperar', 'login', motor.MENSAJE_LOGIN, 'Continuar'), informar.eventos)
            # entrada_a_revisar.csv se escribe igual (vacío) y descarga.csv todavía no.
            self.assertEqual(_leer_csv(d / 'salidas' / 'entrada_a_revisar.csv'), [motor.COLUMNAS_REVISAR])
            self.assertFalse((d / 'salidas' / 'descarga.csv').exists())

    def test_ejecutar_py_destino_inexistente_sale_con_error_del_protocolo(self):
        with carpeta_temporal() as d:
            trabajo = d / 'trabajo'
            trabajo.mkdir()
            p = _listado_simple(d / 'aa11bb22-listado.xlsx')
            (trabajo / 'parametros.json').write_text(json.dumps(dict(PARAMETROS, destino=str(d / 'no_existe'))), encoding='utf-8')
            (trabajo / 'entradas.json').write_text(json.dumps({'listado': [{'ruta': str(p), 'nombre': 'listado.xlsx', 'sha256': 'x'}]}), encoding='utf-8')
            r = self._correr(trabajo, d, simular=d / 'pdfs')
            self.assertEqual(r.returncode, 1, r.stderr)
            eventos = [json.loads(l) for l in r.stdout.splitlines() if l.startswith('{')]
            errores = [e for e in eventos if e['t'] == 'error']
            self.assertEqual(len(errores), 1)
            self.assertEqual(errores[0]['m'], 'La carpeta destino no existe. Creala o copiá su ruta correcta.')

    def test_desde_posterior_a_hasta_corta(self):
        with carpeta_temporal() as d:
            p = _listado_simple(d / 'listado.xlsx')
            parametros = dict(PARAMETROS, destino=str(d), desde='2026-10-31', hasta='2026-10-01')
            with self.assertRaises(ValueError) as e:
                motor.ejecutar([p], d / 'salidas', parametros, informar=Informar(), fabrica_navegador=motor.navegador_simulado(d))
            self.assertEqual(str(e.exception), 'Desde no puede ser posterior a hasta.')

    def test_sin_facturas_validas_corta(self):
        with carpeta_temporal() as d:
            p = xlsx_openpyxl(d / 'listado.xlsx', [('Hoja1', [['CUIT', 'NumeroFactura'], ['123', 'nada']])])
            with self.assertRaises(ValueError) as e:
                motor.ejecutar([p], d / 'salidas', dict(PARAMETROS, destino=str(d)), informar=Informar(), fabrica_navegador=motor.navegador_simulado(d))
            self.assertEqual(str(e.exception), 'No hay facturas válidas para descargar.')
            self.assertEqual(_leer_csv(d / 'salidas' / 'entrada_a_revisar.csv'), [motor.COLUMNAS_REVISAR, ['listado.xlsx', 'Hoja1', '2', 'CUIT ausente o inválido; se requieren 11 dígitos']])

    @staticmethod
    def _correr(trabajo, cwd, simular, entrada='{"t":"continuar","id":"login"}\n'):
        entorno = dict(os.environ, REPORTES_PROTOCOLO='1', PYTHONIOENCODING='utf-8')
        return subprocess.run([sys.executable, '-I', str(EJECUTAR), '--trabajo', str(trabajo), '--simular', str(simular)],
                              cwd=str(cwd), env=entorno, input=entrada, capture_output=True, text=True, encoding='utf-8', timeout=120)


IMPORTE_EN_LETRAS = '***CIENTO CUATRO MIL CON DIEZ CENTAVOS***'


def _factura_b(totales):
    """Factura B: debajo del ítem van la percepción, los rótulos de `totales` (a la derecha) y el importe en letras."""
    lineas = [(50, 740, 'Fecha de Emisión: 15/10/2026'), (50, 700, 'FC-B000000000001'),
              (50, 650, 'Concepto'), (400, 650, 'Operación'), (50, 620, 'Servicio mensual'), (400, 620, '1/1'),
              (450, 590, 'Percepción IIBB')]
    lineas += [(450, 570 - 20 * i, t) for i, t in enumerate(totales)]
    return _pdf_minimo(lineas + [(450, 510, 'Notas:'), (50, 490, IMPORTE_EN_LETRAS)])


def _factura_dos_hojas(rotulos_hoja_2):
    """Tantos ítems que los rótulos de `rotulos_hoja_2` y el importe en letras pasan a la hoja 2, que no repite el
    encabezado Concepto/Operación. Cada ítem repite el concepto en dos renglones."""
    cabecera = [(50, 740, 'Fecha de Emisión: 06/06/2024'), (50, 700, 'FC-A000000000009')]
    hoja_1 = cabecera + [(50, 650, 'Concepto'), (400, 650, 'Operación')]
    for i in range(1, 4):
        hoja_1 += [(50, 650 - 30 * i, 'Comision aval'), (400, 650 - 30 * i, f'1/{i}'), (50, 639 - 30 * i, '- propio.')]
    hoja_2 = cabecera + [(450, 600 - 20 * i, t) for i, t in enumerate(rotulos_hoja_2)] + [(50, 540, IMPORTE_EN_LETRAS)]
    return _pdf_hojas([hoja_1, hoja_2])


@unittest.skipUnless(HAY_PDFPLUMBER, 'pdfplumber no está instalado en este intérprete (se corre dentro del .venv de facturas o con py -3.12)')
class LecturaDelConcepto(unittest.TestCase):
    def test_factura_sin_subtotal_corta_el_concepto_en_total(self):
        self.assertEqual(sharepoint.read_pdf(_factura_b(['TOTAL:'])), (date(2026, 10, 15), ['Servicio mensual']))

    def test_corta_en_el_primer_rotulo_de_subtotal_o_total(self):
        self.assertEqual(sharepoint.read_pdf(_factura_b(['SubTotal:', 'TOTAL:']))[1], ['Servicio mensual'])

    def test_sin_subtotal_ni_total_no_hay_concepto(self):
        """Sin rótulo no se sabe dónde termina el último ítem: la factura va a «Para revisar» en vez de llevarse el
        importe en letras al concepto."""
        self.assertEqual(sharepoint.read_pdf(_factura_b([])), (date(2026, 10, 15), []))

    def test_factura_de_dos_hojas_con_los_rotulos_en_la_segunda(self):
        """Con muchos ítems, el SubTotal y el TOTAL pasan a la hoja 2: el último ítem de la hoja 1 termina al pie."""
        self.assertEqual(sharepoint.read_pdf(_factura_dos_hojas(['SubTotal:', 'TOTAL:'])),
                         (date(2024, 6, 6), ['Comision aval - propio']))

    def test_factura_b_de_dos_hojas_con_total_en_la_segunda(self):
        self.assertEqual(sharepoint.read_pdf(_factura_dos_hojas(['TOTAL:']))[1], ['Comision aval - propio'])

    def test_dos_hojas_sin_rotulo_en_ninguna_no_hay_concepto(self):
        self.assertEqual(sharepoint.read_pdf(_factura_dos_hojas([])), (date(2024, 6, 6), []))


@unittest.skipUnless(HAY_PDFPLUMBER, 'pdfplumber no está instalado en este intérprete (se corre dentro del .venv de facturas o con py -3.12)')
class EjecucionSimulada(unittest.TestCase):
    def _preparar(self, d):
        pdfs = _biblioteca_simulada(d / 'pdfs')
        destino = d / 'destino'
        # Conflicto: mismo nombre con otro contenido. Ya existía: mismo contenido.
        (destino / 'Servicio mensual').mkdir(parents=True)
        (destino / 'Servicio mensual' / 'FC-A000000000004.pdf').write_bytes(b'%PDF-otro contenido')
        (destino / 'Servicio mensual' / 'FC-A000000000005.pdf').write_bytes(pdfs[('27111111111', 'FC-A000000000005')])
        return destino

    def test_ejecutar_simulado_clasifica_por_concepto_y_conflicto(self):
        with carpeta_temporal() as d:
            destino = self._preparar(d)
            p = _listado_simple(d / 'listado.xlsx')
            parametros = dict(PARAMETROS, destino=str(destino), desde='2026-10-01', hasta=None, concepto='mensual', sesion_chrome=str(d / 'sesion'))
            informar = Informar()
            resultado = motor.ejecutar([p], d / 'salidas', parametros, informar=informar,
                                       fabrica_navegador=motor.navegador_simulado(d / 'pdfs', ORIGEN + '/sites/Sitio'))
            self.assertIn(('esperar', 'login', motor.MENSAJE_LOGIN, 'Continuar'), informar.eventos)
            progresos = [e for e in informar.eventos if e[0] == 'progreso']
            self.assertEqual(len(progresos), 9)
            self.assertEqual(progresos[0][2], '1/9 FC-A002100588517')
            self.assertEqual(progresos[-1][1], 1.0)

            filas = _leer_csv(d / 'salidas' / 'descarga.csv')
            self.assertEqual(filas[0], motor.COLUMNAS_DESCARGA)
            self.assertEqual([[str(v) for v in f] for f in resultado['descarga']], filas[1:])
            por_numero = {f[1]: f for f in filas[1:]}
            self.assertEqual([f[1] for f in filas[1:]], [r[1] for r in LISTADO_SIMULACION[1:]])

            f = por_numero['FC-A002100588517']
            self.assertEqual(f[2:5], ['12/10/2026', 'Servicio mensual', 'Copiada'])
            self.assertEqual(Path(f[5]), destino / 'Servicio mensual' / 'FC-A002100588517.pdf')
            self.assertEqual(f[6], 'listado.xlsx / Hoja1 / fila 2')
            self.assertTrue(Path(f[5]).exists())

            f = por_numero['NC-B000000000001']
            self.assertEqual(f[3:5], ['Otro servicio de prueba | Servicio mensual', 'Copiada'])
            self.assertEqual(Path(f[5]).parent.name, 'Varios conceptos')

            self.assertEqual(por_numero['ND-C000000000002'][2:6], ['05/09/2026', 'Servicio mensual', 'Fuera del período', ''])

            f = por_numero['FC-A000000000003']
            self.assertEqual(f[3:5], ['', 'REVISAR: concepto no identificado'])
            self.assertEqual(Path(f[5]).parent.name, 'Para revisar')

            f = por_numero['FC-A000000000004']
            self.assertEqual(f[4], 'CONFLICTO: no se reemplazó')
            self.assertEqual(Path(f[5]).read_bytes(), b'%PDF-otro contenido')
            self.assertEqual(por_numero['FC-A000000000005'][4], 'Ya existía')

            f = por_numero['FC-A000000000006']
            self.assertEqual(f[4], 'ERROR')
            self.assertTrue(f[5].startswith('SharePoint respondió HTTP 404'), f[5])
            self.assertEqual(por_numero['FC-A000000000007'][4:6], ['ERROR', 'No se pudo confirmar el número de factura dentro del PDF'])
            self.assertEqual(por_numero['FC-A000000000008'][3:6], ['Otro servicio', 'Otro concepto', ''])

            self.assertEqual(resultado['resumen'], {
                'facturas_unicas': 9, 'repeticiones_omitidas': 0, 'filas_a_revisar': 0,
                'estados': {'Copiada': 2, 'Fuera del período': 1, 'REVISAR: concepto no identificado': 1,
                            'CONFLICTO: no se reemplazó': 1, 'Ya existía': 1, 'ERROR': 2, 'Otro concepto': 1}})
            self.assertEqual(_leer_csv(d / 'salidas' / 'entrada_a_revisar.csv'), [motor.COLUMNAS_REVISAR])
            # Sólo carpetas de concepto, sin la del mes de emisión: los meses se juntan en la carpeta del concepto.
            self.assertEqual(sorted(c.name for c in destino.iterdir()), ['Para revisar', 'Servicio mensual', 'Varios conceptos'])

    def test_ejecutar_py_contrato_completo_con_simulacion(self):
        with carpeta_temporal() as d:
            destino = self._preparar(d)
            trabajo = d / 'trabajo'
            trabajo.mkdir()
            # Dos tramos guardados con prefijo, en orden inverso al nombre original.
            p2 = xlsx_openpyxl(d / 'ffff0000-Listado 2.xlsx', [('Hoja1', [['CUIT', 'NumeroFactura']] + LISTADO_SIMULACION[6:])])
            p1 = xlsx_openpyxl(d / 'aaaa0000-Listado 1.xlsx', [('Hoja1', LISTADO_SIMULACION[:6] + [['27111111111', 'FC-A000000000005']])])
            (trabajo / 'parametros.json').write_text(json.dumps(dict(PARAMETROS, destino=str(destino), desde=None, hasta=None, concepto='')), encoding='utf-8')
            (trabajo / 'entradas.json').write_text(json.dumps({'listado': [
                {'ruta': str(p2), 'nombre': 'Listado 2.xlsx', 'sha256': 'b'},
                {'ruta': str(p1), 'nombre': 'Listado 1.xlsx', 'sha256': 'a'}]}), encoding='utf-8')
            r = Validaciones._correr(trabajo, d, simular=d / 'pdfs')
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            eventos = [json.loads(l) for l in r.stdout.splitlines() if l.startswith('{')]
            tipos = [e['t'] for e in eventos]
            self.assertIn('esperar', tipos)
            self.assertLess(tipos.index('esperar'), tipos.index('resumen'))
            espera = next(e for e in eventos if e['t'] == 'esperar')
            self.assertEqual((espera['id'], espera['boton']), ('login', 'Continuar'))
            resumen = next(e for e in eventos if e['t'] == 'resumen')['datos']
            self.assertEqual(resumen['facturas_unicas'], 9)
            self.assertEqual(resumen['repeticiones_omitidas'], 1)
            self.assertEqual(resumen['estados'], {'Copiada': 4, 'REVISAR: concepto no identificado': 1, 'CONFLICTO: no se reemplazó': 1, 'Ya existía': 1, 'ERROR': 2})
            self.assertEqual({e['tabla']: e['filas'] for e in eventos if e['t'] == 'tabla'}, {'descarga': 9, 'entrada_a_revisar': 0})

            filas = _leer_csv(trabajo / 'salidas' / 'descarga.csv')
            self.assertEqual([f[6] for f in filas[1:3]], ['Listado 1.xlsx / Hoja1 / fila 2', 'Listado 1.xlsx / Hoja1 / fila 3'])
            self.assertEqual(filas[-1][6], 'Listado 2.xlsx / Hoja1 / fila 5')
            self.assertTrue((trabajo / 'salidas' / 'entrada_a_revisar.csv').exists())
            self.assertFalse((trabajo / 'sesion_chrome').exists())

            con = sqlite3.connect(str(trabajo / 'resultados.sqlite'))
            try:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM t_descarga').fetchone()[0], 9)
                self.assertEqual(con.execute('SELECT COUNT(*) FROM t_entrada_a_revisar').fetchone()[0], 0)
                clave = con.execute('SELECT _clave FROM t_descarga WHERE _fila = 0').fetchone()[0]
                self.assertEqual(clave.split('\x1f'), ['20123456789', 'FC-A002100588517'])
                columnas = [r[0] for r in con.execute("SELECT nombre FROM _columnas WHERE tabla = 'descarga' ORDER BY posicion")]
                self.assertEqual(columnas, motor.COLUMNAS_DESCARGA)
            finally:
                con.close()

    def test_ejecutar_py_cancelar_en_el_login_sale_sin_descargar(self):
        with carpeta_temporal() as d:
            destino = self._preparar(d)
            trabajo = d / 'trabajo'
            trabajo.mkdir()
            p = _listado_simple(d / 'listado.xlsx')
            (trabajo / 'parametros.json').write_text(json.dumps(dict(PARAMETROS, destino=str(destino))), encoding='utf-8')
            (trabajo / 'entradas.json').write_text(json.dumps({'listado': [{'ruta': str(p), 'nombre': 'listado.xlsx', 'sha256': 'a'}]}), encoding='utf-8')
            r = Validaciones._correr(trabajo, d, simular=d / 'pdfs', entrada='{"t":"cancelar"}\n')
            self.assertEqual(r.returncode, 2, r.stderr + r.stdout)
            self.assertEqual(_leer_csv(trabajo / 'salidas' / 'descarga.csv'), [motor.COLUMNAS_DESCARGA])
            self.assertFalse((destino / 'Servicio mensual' / 'FC-A002100588517.pdf').exists())


if __name__ == '__main__':
    unittest.main()
