"""Conciliación general: el motor nuevo contra los dorados del legado, tramos, errores y ejecutar.py."""
import csv
import json
import os
import sqlite3
import subprocess
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

from app.reportes.conciliacion_general import motor
from tests.fixtures import xlsx_sintetico, carpeta_temporal

RAIZ = Path(__file__).resolve().parent.parent
DORADOS = Path(__file__).resolve().parent / 'dorados' / 'conciliacion_general'
EJECUTAR = RAIZ / 'app' / 'reportes' / 'conciliacion_general' / 'ejecutar.py'
FONDO = 'Fondo de Riesgo General'
S = ['FondoDeRiesgo', 'CodigoEmpresa', 'NumeroFactura', 'Importe', 'GrupoConceptoFacturacion', 'Subrecibo', 'NumeroComprobanteImputacion', 'CUIT', 'RazonSocial']
E = ['Saldo2', 'Cuenta de cliente', 'Factura', 'Número de recibo', 'Número de Recibo global', 'Asiento', 'Tipo de transacción']
# Mismos casos que las pruebas del legado (datos inventados).
SGA_FILAS = [S,
             [FONDO, '1', 'F1', '100', 'Otros', '', '', '201', 'Socio'],
             [FONDO, '1', 'F1', '-20', 'Otros', '', '', '201', 'Socio'],
             [FONDO, '1', 'F2', '50', 'Otros', '', '', '201', 'Socio'],
             [FONDO, '1', 'F0', '20', 'Otros', '', '', '201', 'Socio'],
             [FONDO, '1', 'F0', '-20', 'Otros', '', '', '201', 'Socio'],
             [FONDO, '1', '', '-2', 'Movimientos Pendientes', '', 'NC-1', '201', 'Socio'],
             [FONDO, '1', '', '-10', 'Movimientos Pendientes', 'SR-1', '', '201', 'Socio'],
             [FONDO, '1', 'FC-X1', '1', 'Otros', '', '', '201', 'Socio'],
             ['Otro fondo', '9', 'F9', '999', 'Otros', '', '', '209', 'Ajeno']]
ERP_FILAS = [['80', '1', 'F1', '', '', '', 'Cliente'],
             ['30', '2', 'F3', '', '', '', 'Cliente'],
             ['-2', '1', 'NC-1', '', '', '', 'Cliente'],
             ['-10', '1', '', 'SR-1', 'OP-X1', '', 'Pago'],
             ['7', '1', '', '', '', 'REH1', 'Pago'],
             ['1', '1', 'FC-X1', '', '', '', 'Diario general']]
# Casos de los cambios de la v1.5 (datos inventados): pendiente de un FI-P con cruce recíproco, recibos RC-X y RC-R,
# orden de pago OP-X, recibo sólo en SGA, ausentes en ERP con saldo cero y distinto de cero, y ausentes en SGA.
SGA_REGLAS_15 = [S,
                 [FONDO, '10', 'FI-P0001', '-300', 'Aportes', '', 'FI-P0002', '27000000010', 'Socia diez'],
                 [FONDO, '10', 'FI-P0002', '-300', 'Aportes', '', '', '27000000010', 'Socia diez'],
                 [FONDO, '10', 'FI-P0002', '300', 'Aportes', '', 'FI-P0001', '27000000010', 'Socia diez'],
                 [FONDO, '10', '', '300', 'Movimientos Pendientes', '', 'FI-P0001', '27000000010', 'Socia diez'],
                 [FONDO, '11', '', '-50', 'Movimientos Pendientes', 'SR-0011', 'RC-X0001', '20000000011', 'Socio once'],
                 [FONDO, '12', '', '-40', 'Movimientos Pendientes', 'SR-0012', 'RC-R0001', '20000000012', 'Socio doce'],
                 [FONDO, '13', '', '25', 'Movimientos Pendientes', 'SR-0013', 'OP-X0001', '20000000013', 'Socio trece'],
                 [FONDO, '14', '', '-15', 'Movimientos Pendientes', 'SR-0014', 'RC-X0002', '20000000014', 'Socio catorce'],
                 [FONDO, '15', 'FC-A0001', '100', 'Otros', '', '', '20000000015', 'Socio quince'],
                 [FONDO, '15', 'FC-A0001', '-100', 'Otros', 'SR-0099', 'RC-X0099', '20000000015', 'Socio quince'],
                 [FONDO, '16', 'FC-A0002', '70', 'Otros', '', '', '20000000016', 'Socio dieciseis'],
                 [FONDO, '20', '', '-9', 'Movimientos Pendientes', 'SR-0020', '', '20000000020', 'Socio veinte']]
ERP_REGLAS_15 = [['-50', '11', '', 'SR-0011', 'RC-X0001', '', 'Pago'],
                 ['-40', '12', '', 'SR-0012', 'RC-R0001', '', 'Pago'],
                 ['25', '13', '', 'SR-0013', 'OP-X0001', '', 'Pago'],
                 ['0', '17', 'FC-A0003', '', '', '', 'Cliente'],
                 ['5', '18', '', 'SR-0018', 'RC-X0003', '', 'Pago'],
                 ['1', '19', 'FC-A0004', '', '', '', 'Diario general']]


class Silencio:
    """`informar` mudo para los tests."""
    def log(self, m): pass
    def paso(self, m): pass
    def progreso(self, v, m=''): pass


def hojas_xlsx_a_csv(xlsx, destino):
    """Cada hoja del libro como xlsx_<hoja>.csv (celdas como texto, sin vacíos al final de la fila)."""
    for nombre, filas in leer_hojas(xlsx):
        with (Path(destino) / f'xlsx_{nombre}.csv').open('w', encoding='utf-8', newline='') as f:
            csv.writer(f, delimiter=';').writerows(filas)


def leer_hojas(xlsx):
    import openpyxl
    libro = openpyxl.load_workbook(xlsx, read_only=True)
    for hoja in libro.worksheets:
        filas = []
        for fila in hoja.iter_rows(values_only=True):
            celdas = ['' if v is None else str(v) for v in fila]
            while celdas and celdas[-1] == '':
                celdas.pop()
            filas.append(celdas)
        yield hoja.title.replace(' ', '_'), filas
    libro.close()


def leer_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f, delimiter=';'))


FECHAS = ('Fecha SGA', 'Fecha ERP')  # columnas informativas nuevas (01/11/2026): los dorados son de antes


def sin_fechas(filas):
    """Filas (con encabezado) sin las columnas de fecha, para comparar con los dorados."""
    quitar = {i for i, c in enumerate(filas[0]) if c in FECHAS}
    return [[v for i, v in enumerate(r) if i not in quitar] for r in filas]


def filas_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.reader(f, delimiter=';'))


def xlsx_con_error(path, hojas):
    """Libro con una celda de error de Excel (t="e") donde el valor es la cadena '#ERROR'."""
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with ZipFile(path, 'w') as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="' + ns + '" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + ''.join(f'<sheet name="{n}" sheetId="{i}" r:id="r{i}"/>' for i, (n, _) in enumerate(hojas, 1)) + '</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(f'<Relationship Id="r{i}" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(hojas) + 1)) + '</Relationships>')
        for i, (_, filas) in enumerate(hojas, 1):
            partes = []
            for n, fila in enumerate(filas, 1):
                celdas = ''.join('<c t="e"><v>#N/A</v></c>' if v == '#ERROR' else '<c t="inlineStr"><is><t>' + escape(str(v)) + '</t></is></c>' for v in fila)
                partes.append(f'<row r="{n}">{celdas}</row>')
            z.writestr(f'xl/worksheets/sheet{i}.xml', '<worksheet xmlns="' + ns + '"><sheetData>' + ''.join(partes) + '</sheetData></worksheet>')
    return path


def correr(entradas, salida, alcance='abiertos', corte='2026-10-31', fondo=FONDO):
    return motor.run(entradas, salida, alcance, corte, fondo, informar=Silencio())


def normalizar_resumen(datos):
    datos = json.loads(json.dumps(datos))
    for fuente in datos['fuentes']:
        fuente.pop('fecha_descarga', None)
    return datos


class DoradosTests(unittest.TestCase):
    def comparar_con_dorado(self, caso, entradas):
        dorado = DORADOS / caso
        with carpeta_temporal() as d:
            resumen = correr(entradas, d)
            self.assertTrue((d / 'Respaldo_tecnico' / 'Conciliacion_general.csv').read_bytes().startswith(b'\xef\xbb\xbf'))
            self.assertEqual(sin_fechas(filas_csv(d / 'Respaldo_tecnico' / 'Conciliacion_general.csv')), filas_csv(dorado / 'Conciliacion_general.csv'))
            esperado = json.loads((dorado / 'Resumen.json').read_text(encoding='utf-8'))
            self.assertEqual(normalizar_resumen(resumen), normalizar_resumen(esperado))
            self.assertEqual(normalizar_resumen(json.loads((d / 'Respaldo_tecnico' / 'Resumen.json').read_text(encoding='utf-8'))), normalizar_resumen(esperado))
            hojas = dict(leer_hojas(d / 'Conciliacion_general.xlsx'))
            self.assertEqual(list(hojas), ['Resumen', 'Conciliación_general'])
            for nombre, filas in hojas.items():
                with (dorado / f'xlsx_{nombre}.csv').open(encoding='utf-8', newline='') as f:
                    esperado = list(csv.reader(f, delimiter=';'))
                if FECHAS[0] in filas[0]:
                    # sin fechas en las entradas, las columnas nuevas quedan vacías: se recortan los vacíos del final
                    filas = [r[:max([i + 1 for i, v in enumerate(r) if v] or [0])] for r in sin_fechas(filas)]
                self.assertEqual(filas, esperado, nombre)
            self.assertEqual(sorted(p.name for p in d.iterdir()), ['Conciliacion_general.xlsx', 'Respaldo_tecnico'])
            self.assertTrue((d / 'Respaldo_tecnico' / 'COMPLETADO.txt').exists())
            self.assertTrue((d / 'Respaldo_tecnico' / 'trazabilidad.sqlite').exists())

    def test_igual_a_dorado_unificado(self):
        e = DORADOS / 'unificado' / 'entradas'
        self.comparar_con_dorado('unificado', {'sga': [e / 'cualquier_sga.xlsx'], 'erp': [e / 'erp_12345.xlsx']})

    def test_igual_a_dorado_separado(self):
        e = DORADOS / 'separado' / 'entradas'
        self.comparar_con_dorado('separado', {'sga': [e / 'cualquier_sga.xlsx'], 'erp': [e / f'descarga_{i}.xlsx' for i in range(3)]})

    def test_detectar_tipo(self):
        e = DORADOS / 'unificado' / 'entradas'
        self.assertEqual(motor.detectar_tipo(e / 'cualquier_sga.xlsx'), 'SGA')
        self.assertEqual(motor.detectar_tipo(e / 'erp_12345.xlsx'), 'ERP')
        with carpeta_temporal() as d:
            self.assertIsNone(motor.detectar_tipo(xlsx_sintetico(d / 'x.xlsx', [('H', [['a', 'b']])])))


class TramosTests(unittest.TestCase):
    def test_dos_tramos_sga_equivalen_a_uno_y_agregan_archivo(self):
        with carpeta_temporal() as d:
            erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + ERP_FILAS)])
            uno = xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA_FILAS)])
            t1 = xlsx_sintetico(d / 'sga_1.xlsx', [('Datos', SGA_FILAS[:5])])
            t2 = xlsx_sintetico(d / 'sga_2.xlsx', [('Datos', [S] + SGA_FILAS[5:])])
            r1 = correr({'sga': [uno], 'erp': [erp]}, d / 'uno')
            r2 = correr({'sga': [t1, t2], 'erp': [erp]}, d / 'dos')
            datos1 = leer_csv(d / 'uno' / 'Respaldo_tecnico' / 'Conciliacion_general.csv')
            datos2 = leer_csv(d / 'dos' / 'Respaldo_tecnico' / 'Conciliacion_general.csv')
            cuerpo1 = [r for r in datos1 if r['Tipo'] != 'CONTROL']
            cuerpo2 = [r for r in datos2 if r['Tipo'] != 'CONTROL']
            sin_origen = lambda filas: [{k: v for k, v in r.items() if not k.startswith('Origen')} for r in filas]
            self.assertEqual(sin_origen(cuerpo1), sin_origen(cuerpo2))
            self.assertEqual(r1['cobertura_salida'], r2['cobertura_salida'])
            self.assertEqual([f['archivo'] for f in r2['fuentes']], ['sga_1.xlsx', 'sga_2.xlsx', 'erp.xlsx'])
            self.assertEqual([f['filas_incluidas'] for f in r2['fuentes'] if f['sistema'] == 'SGA'], [4, 4])
            # El origen de cada fila dice en qué archivo está: F1 en el primer tramo, FC-X1 en el segundo.
            f1 = next(r for r in cuerpo2 if r['Comprobante'] == 'F1')
            self.assertEqual(f1['Origen SGA (primeras 5)'], 'sga_1.xlsx [Datos]:2 | sga_1.xlsx [Datos]:3')
            fcx1 = next(r for r in cuerpo2 if r['Comprobante'] == 'FC-X1')
            self.assertEqual(fcx1['Origen SGA (primeras 5)'], 'sga_2.xlsx [Datos]:5')
            fuentes = [r['Observaciones'] for r in datos2 if r['Comprobante'] == 'FUENTE SGA']
            self.assertEqual(len(fuentes), 2)
            self.assertTrue(fuentes[0].startswith('sga_1.xlsx / hoja Datos / filas incluidas 4 / SHA256 '))
            self.assertFalse([r for r in datos2 if r['Comprobante'] == 'ALERTA' and 'Tramos' in r['Observaciones']])

    def test_dos_tramos_erp_del_mismo_tipo_se_aceptan_con_alerta(self):
        with carpeta_temporal() as d:
            sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA_FILAS)])
            uno = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + ERP_FILAS)])
            a = xlsx_sintetico(d / 'erp_a.xlsx', [('Datos', [E] + ERP_FILAS[:2])])
            b = xlsx_sintetico(d / 'erp_b.xlsx', [('Datos', [E] + ERP_FILAS[2:])])
            r1 = correr({'sga': [sga], 'erp': [uno]}, d / 'uno')
            r2 = correr({'sga': [sga], 'erp': [a, b]}, d / 'dos')
            self.assertEqual(r1['conteos'], r2['conteos'])
            self.assertEqual(r1['cobertura_salida'], r2['cobertura_salida'])
            alertas = [x for x in r2['alertas'] if 'Tramos' in x[5]]
            self.assertEqual(alertas, [['ERP', '', '', '', 'Cliente', 'Tramos del mismo tipo de transacción: erp_a.xlsx, erp_b.xlsx. Verificar que sean partes de una misma descarga', '']])
            datos = leer_csv(d / 'dos' / 'Respaldo_tecnico' / 'Conciliacion_general.csv')
            fila = next(r for r in datos if r['Comprobante'] == 'ALERTA' and 'Tramos' in r['Observaciones'])
            self.assertEqual(fila['Observaciones'], 'ERP | Cliente | Tramos del mismo tipo de transacción: erp_a.xlsx, erp_b.xlsx. Verificar que sean partes de una misma descarga')
            self.assertEqual(fila['Resultado'], 'REVISAR')
            self.assertFalse([x for x in r1['alertas'] if 'Tramos' in x[5]])

    def test_archivo_duplicado_por_contenido_corta(self):
        with carpeta_temporal() as d:
            sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA_FILAS)])
            erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + ERP_FILAS)])
            copia = d / 'erp_copia.xlsx'
            copia.write_bytes(erp.read_bytes())
            with self.assertRaisesRegex(ValueError, 'duplicado por contenido'):
                correr({'sga': [sga], 'erp': [erp, copia]}, d / 'salida')
            self.assertFalse((d / 'salida' / 'Respaldo_tecnico' / 'COMPLETADO.txt').exists())


class ErroresTests(unittest.TestCase):
    def test_celda_error_en_columna_requerida_corta(self):
        with carpeta_temporal() as d:
            filas = [S, [FONDO, '1', 'F1', '100', 'Otros', '', '', '201', 'Socio'], [FONDO, '1', 'F2', '#ERROR', 'Otros', '', '', '201', 'Socio']]
            sga = xlsx_con_error(d / 'sga.xlsx', [('Datos', filas)])
            erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + ERP_FILAS)])
            with self.assertRaisesRegex(ValueError, r'sga\.xlsx \[Datos\], fila 3: error Excel en una columna requerida'):
                correr({'sga': [sga], 'erp': [erp]}, d / 'salida')
            self.assertFalse((d / 'salida' / 'Conciliacion_general.xlsx').exists())
            self.assertFalse((d / 'salida' / 'Respaldo_tecnico' / 'COMPLETADO.txt').exists())

    def test_importe_vacio_corta(self):
        with carpeta_temporal() as d:
            sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', [S, [FONDO, '1', 'F1', '', 'Otros', '', '', '201', 'Socio']])])
            erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + ERP_FILAS)])
            with self.assertRaisesRegex(ValueError, 'importe vacío o inválido'):
                correr({'sga': [sga], 'erp': [erp]}, d / 'salida')

    def test_entrada_con_archivo_del_otro_sistema_corta(self):
        with carpeta_temporal() as d:
            sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA_FILAS)])
            erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + ERP_FILAS)])
            with self.assertRaisesRegex(ValueError, 'es un archivo de ERP y se lo indicó como SGA'):
                correr({'sga': [erp], 'erp': [sga]}, d / 'salida')
            with self.assertRaisesRegex(ValueError, 'al menos un archivo de SGA'):
                correr({'sga': [], 'erp': [erp]}, d / 'salida')
            with self.assertRaisesRegex(ValueError, 'Indique el alcance'):
                correr({'sga': [sga], 'erp': [erp]}, d / 'salida', alcance='todo')
            with self.assertRaisesRegex(ValueError, 'Fecha de corte inválida'):
                correr({'sga': [sga], 'erp': [erp]}, d / 'salida', corte='31/10/2026')
            (d / 'roto.xlsx').write_bytes(b'no soy un libro')
            with self.assertRaisesRegex(ValueError, 'no es un libro de Excel'):
                correr({'sga': [d / 'roto.xlsx'], 'erp': [erp]}, d / 'salida')

    def test_fondo_filtra_solo_sga(self):
        with carpeta_temporal() as d:
            sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA_FILAS)])
            erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + ERP_FILAS)])
            r = correr({'sga': [sga], 'erp': [erp]}, d / 'salida', fondo='Otro fondo')
            self.assertEqual(r['fondo'], 'Otro fondo')
            self.assertEqual(r['cobertura_salida']['SGA']['filas_fuente'], 1)
            self.assertEqual(r['cobertura_salida']['ERP']['filas_fuente'], len(ERP_FILAS))
            datos = leer_csv(d / 'salida' / 'Respaldo_tecnico' / 'Conciliacion_general.csv')
            self.assertEqual({r['Fondo'] for r in datos}, {'Otro fondo'})
            self.assertEqual(next(r for r in datos if r['Comprobante'] == 'F9')['Saldo SGA'], '999.00')


class LogicaTests(unittest.TestCase):
    """Casos del legado (pruebas_general.py) sobre el motor nuevo."""

    def test_opx_usa_socio_y_subrecibo_no_numero_global(self):
        with carpeta_temporal() as d:
            sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', [S, [FONDO, '1', '', '-30', 'Movimientos Pendientes', 'SR-1', '', '201', 'Uno'], [FONDO, '2', '', '-40', 'Movimientos Pendientes', 'SR-1', '', '202', 'Dos']])])
            erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E, ['-10', '1', '', 'SR-1', 'OP-X111', '', 'Pago'], ['-20', '1', '', 'SR-1', 'OP-X222', '', 'Pago'], ['-40', '2', '', 'SR-1', 'OP-X111', '', 'Pago'], ['-7', '3', '', '', 'OP-X333', '', 'Pago']])])
            correr({'sga': [sga], 'erp': [erp]}, d / 'salida')
            cuerpo = [r for r in leer_csv(d / 'salida' / 'Respaldo_tecnico' / 'Conciliacion_general.csv') if r['Tipo'] != 'CONTROL']
            self.assertEqual(len(cuerpo), 3)
            self.assertTrue(all(r['Tipo'] == 'OP-X' for r in cuerpo))
            pares = [r for r in cuerpo if r['Comprobante'] == 'SR-1']
            self.assertEqual({r['Cliente'] for r in pares}, {'1', '2'})
            self.assertTrue(all(r['Resultado'] == 'COINCIDE' for r in pares))
            sin_sr = next(r for r in cuerpo if r['Comprobante'] == 'OP-X333')
            self.assertEqual(sin_sr['Saldo SGA'], '')
            self.assertEqual(sin_sr['Resultado'], 'SOLO EN ERP — REVISAR EN SGA')

    def test_no_oculta_redondeo_por_comprobante(self):
        with carpeta_temporal() as d:
            sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', [S, [FONDO, '1', 'A', '0.005', 'Otros', '', '', '201', 'Socio'], [FONDO, '1', 'B', '0.005', 'Otros', '', '', '201', 'Socio']])])
            erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + ERP_FILAS)])
            correr({'sga': [sga], 'erp': [erp]}, d / 'salida', alcance='completo')
            datos = leer_csv(d / 'salida' / 'Respaldo_tecnico' / 'Conciliacion_general.csv')
            self.assertEqual(next(r for r in datos if r['Comprobante'] == 'DIFERENCIA DE REDONDEO')['Saldo SGA'], '-0.01')
            self.assertEqual(sum(Decimal(r['Saldo SGA']) for r in datos if r['Tipo'] != 'CONTROL' and r['Saldo SGA']), Decimal('0.02'))


class FechasTests(unittest.TestCase):
    """Fecha SGA y Fecha ERP (pedido del 01/11/2026): en SGA, FechaFactura salvo que el comprobante sea de imputación
    (FechaComprobanteImputacion); en ERP, Fecha. Sólo informan: los saldos y resultados no cambian."""

    def test_fecha_del_comprobante_en_cada_sistema(self):
        import openpyxl
        s = S + ['FechaFactura', 'FechaComprobanteImputacion']
        e = E + ['Fecha']
        sga = [s,
               [FONDO, '1', 'F1', '100', 'Otros', '', '', '201', 'Socio', '45931', ''],          # factura: FechaFactura
               [FONDO, '1', 'F1', '-40', 'Otros', '', 'RC-X9', '201', 'Socio', '45931', '45945'],  # su cobro: sigue la factura
               [FONDO, '2', '', '-10', 'Movimientos Pendientes', 'SR-1', 'RC-X1', '202', 'Otro', '', '45941'],  # imputación
               [FONDO, '3', 'F3', '30', 'Otros', '', '', '203', 'Tres', '', '']]                  # sin fecha
        erp = [e,
               ['60', '1', 'F1', '', '', '', 'Cliente', '45936'],
               ['-10', '2', '', 'SR-1', 'RC-X1', '', 'Pago', '15/10/2025'],
               ['5', '4', 'F4', '', '', '', 'Cliente', '2025-10-20']]
        with carpeta_temporal() as d:
            entradas = {'sga': [xlsx_sintetico(d / 'sga.xlsx', [('Datos', sga)])], 'erp': [xlsx_sintetico(d / 'erp.xlsx', [('Datos', erp)])]}
            correr(entradas, d / 'salida')
            filas = {(r['Tipo'], r['Comprobante']): r for r in leer_csv(d / 'salida' / 'Respaldo_tecnico' / 'Conciliacion_general.csv') if r['Tipo'] != 'CONTROL'}
            fechas = {k: (r['Fecha SGA'], r['Fecha ERP']) for k, r in filas.items()}
            self.assertEqual(fechas[('FACTURA', 'F1')], ('2025-10-01', '2025-10-06'))
            self.assertEqual(fechas[('RC-X', 'SR-1')], ('2025-10-11', '2025-10-15'))
            self.assertEqual(fechas[('FACTURA', 'F3')], ('', ''))       # sólo en SGA y sin fecha
            self.assertEqual(fechas[('FACTURA', 'F4')], ('', '2025-10-20'))  # sólo en ERP
            self.assertEqual(filas[('FACTURA', 'F1')]['Saldo SGA'], '60.00')
            # en el Excel van como fechas reales, a la izquierda de Comprobante
            hoja = openpyxl.load_workbook(d / 'salida' / 'Conciliacion_general.xlsx').worksheets[1]  # Conciliación general
            encabezado = [c.value for c in hoja[1]]
            self.assertEqual(encabezado[2:5], ['Fecha SGA', 'Fecha ERP', 'Comprobante'])
            fila_f1 = next(r for r in hoja.iter_rows(min_row=2) if r[4].value == 'F1')
            self.assertEqual(fila_f1[2].value.date().isoformat(), '2025-10-01')
            self.assertTrue(fila_f1[2].is_date)
            # en la grilla, las dos fechas en anaranjado cuando el comprobante está en los dos sistemas con fechas distintas
            from app.reportes.conciliacion_general import ejecutar
            from app.tablas import Tablas
            ejecutar.volcar(d / 'salida', d / 'r.sqlite')
            pagina = Tablas(d / 'r.sqlite').consultar('general', cantidad=100)
            marcas = {f['valores'][pagina['columnas'].index('Comprobante')]: f['_marcas'] for f in pagina['filas']}
            self.assertEqual(marcas['F1'], ['Fecha SGA', 'Fecha ERP'])
            self.assertEqual(marcas['F4'], [])  # sólo en ERP: nada que comparar


class EjecutarTests(unittest.TestCase):
    def test_ejecutar_vuelca_dos_tablas_y_resumen(self):
        e = DORADOS / 'separado' / 'entradas'
        with carpeta_temporal() as d:
            # Nombres como los guarda el server (<sha8>-<nombre>) y en desorden: se ordenan por el nombre original.
            copias = {}
            for origen, guardado in [('cualquier_sga.xlsx', 'aaaaaaaa-cualquier_sga.xlsx'), ('descarga_0.xlsx', 'cccccccc-descarga_0.xlsx'), ('descarga_1.xlsx', 'bbbbbbbb-descarga_1.xlsx'), ('descarga_2.xlsx', 'dddddddd-descarga_2.xlsx')]:
                (d / guardado).write_bytes((e / origen).read_bytes())
                copias[origen] = d / guardado
            (d / 'parametros.json').write_text(json.dumps({'alcance': 'abiertos', 'corte': '2026-10-31', 'fondo': FONDO}), encoding='utf-8')
            (d / 'entradas.json').write_text(json.dumps({
                'sga': [{'ruta': str(copias['cualquier_sga.xlsx']), 'nombre': 'cualquier_sga.xlsx', 'sha256': ''}],
                'erp': [{'ruta': str(copias[n]), 'nombre': n, 'sha256': ''} for n in ('descarga_2.xlsx', 'descarga_0.xlsx', 'descarga_1.xlsx')],
            }), encoding='utf-8')
            ambiente = dict(os.environ, REPORTES_PROTOCOLO='1')
            proceso = subprocess.run([sys.executable, '-I', str(EJECUTAR), '--trabajo', str(d)], capture_output=True, text=True, encoding='utf-8', env=ambiente, cwd=str(d.parent))
            self.assertEqual(proceso.returncode, 0, proceso.stderr)
            eventos = [json.loads(l) for l in proceso.stdout.splitlines() if l.strip()]
            tablas = {ev['tabla']: ev['filas'] for ev in eventos if ev['t'] == 'tabla'}
            resumen = next(ev['datos'] for ev in eventos if ev['t'] == 'resumen')
            self.assertEqual(resumen['registros_datos'], 8)
            self.assertEqual([f['archivo'] for f in resumen['fuentes']], ['aaaaaaaa-cualquier_sga.xlsx', 'cccccccc-descarga_0.xlsx', 'bbbbbbbb-descarga_1.xlsx', 'dddddddd-descarga_2.xlsx'])
            self.assertTrue((d / 'salidas' / 'Conciliacion_general.xlsx').exists())
            self.assertTrue((d / 'salidas' / 'Respaldo_tecnico' / 'Resumen.json').exists())
            con = sqlite3.connect(d / 'resultados.sqlite')
            try:
                nombres = [r[0] for r in con.execute('SELECT tabla FROM _tablas ORDER BY orden')]
                self.assertEqual(nombres, ['resumen', 'general'])
                self.assertEqual(con.execute('SELECT COUNT(*) FROM t_general').fetchone()[0], tablas['general'])
                self.assertEqual(tablas['general'], 8)
                columnas = [r[0] for r in con.execute("SELECT nombre FROM _columnas WHERE tabla='general' ORDER BY posicion")]
                self.assertEqual(len(columnas), 19)
                self.assertEqual(columnas[:5], ['Tipo', 'Cliente', 'Fecha SGA', 'Fecha ERP', 'Comprobante'])
                self.assertEqual(con.execute("SELECT COUNT(*) FROM t_general WHERE c0='CONTROL'").fetchone()[0], 0)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM t_general WHERE c0='OP-X'").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT _clave FROM t_general WHERE c4='F1'").fetchone()[0], 'FACTURA\x1f1\x1fF1')
                self.assertEqual([r[0] for r in con.execute("SELECT nombre FROM _columnas WHERE tabla='resumen' ORDER BY posicion")], ['Control', 'Saldo SGA', 'Saldo ERP', 'Diferencia', 'Resultado / cantidad', 'Detalle'])
                self.assertEqual(con.execute("SELECT c1, c2 FROM t_resumen WHERE c0='TOTAL GENERAL POR COMPROBANTE'").fetchone(), ('119.00', '106.00'))
                self.assertEqual(con.execute('SELECT COUNT(*) FROM t_resumen').fetchone()[0], tablas['resumen'])
            finally:
                con.close()

    def test_ejecutar_informa_error_esperable(self):
        with carpeta_temporal() as d:
            sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', [S, [FONDO, '1', 'F1', 'abc', 'Otros', '', '', '201', 'Socio']])])
            erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + ERP_FILAS)])
            (d / 'parametros.json').write_text(json.dumps({'alcance': 'abiertos', 'corte': None, 'fondo': FONDO}), encoding='utf-8')
            (d / 'entradas.json').write_text(json.dumps({'sga': [{'ruta': str(sga), 'nombre': 'sga.xlsx', 'sha256': ''}], 'erp': [{'ruta': str(erp), 'nombre': 'erp.xlsx', 'sha256': ''}]}), encoding='utf-8')
            proceso = subprocess.run([sys.executable, '-I', str(EJECUTAR), '--trabajo', str(d)], capture_output=True, text=True, encoding='utf-8', env=dict(os.environ, REPORTES_PROTOCOLO='1'))
            self.assertEqual(proceso.returncode, 1)
            errores = [json.loads(l) for l in proceso.stdout.splitlines() if l.strip() and json.loads(l)['t'] == 'error']
            self.assertEqual(len(errores), 1)
            self.assertIn('importe vacío o inválido', errores[0]['m'])
            self.assertFalse((d / 'resultados.sqlite').exists())


class ReglasV15Tests(unittest.TestCase):
    """Los tres cambios de negocio de la v1.5 (pedido de la responsable funcional del 31/10/2026)."""

    def correr_reglas(self, d, alcance='abiertos'):
        sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA_REGLAS_15)])
        erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + ERP_REGLAS_15)])
        resumen = correr({'sga': [sga], 'erp': [erp]}, d / 'salida', alcance=alcance)
        filas = [r for r in leer_csv(d / 'salida' / 'Respaldo_tecnico' / 'Conciliacion_general.csv') if r['Tipo'] != 'CONTROL']
        return {(r['Tipo'], r['Cliente'], r['Comprobante']): r for r in filas}, resumen

    def test_abiertos_ausente_en_erp_se_compara_contra_cero(self):
        with carpeta_temporal() as d:
            f, resumen = self.correr_reglas(d)
            cero = f[('FACTURA', '15', 'FC-A0001')]
            self.assertEqual((cero['Saldo SGA'], cero['Saldo ERP'], cero['Diferencia SGA menos ERP'], cero['Resultado']), ('0.00', '0.00', '0.00', 'COINCIDE'))
            self.assertIn(motor.NOTA_ABIERTOS, cero['Observaciones'])
            con_saldo = f[('FACTURA', '16', 'FC-A0002')]
            self.assertEqual((con_saldo['Saldo SGA'], con_saldo['Saldo ERP'], con_saldo['Diferencia SGA menos ERP'], con_saldo['Resultado']), ('70.00', '0.00', '70.00', 'DIFERENCIA'))
            # Lo que está sólo en ERP no cambia.
            self.assertEqual(f[('FACTURA', '17', 'FC-A0003')]['Resultado'], 'NO EVALUADO - ERP SOLO ABIERTOS')
            solo_erp = f[('FACTURA', '19', 'FC-A0004')]
            self.assertEqual((solo_erp['Saldo SGA'], solo_erp['Resultado']), ('', 'SOLO EN ERP — REVISAR EN SGA'))
            self.assertNotIn('SOLO EN SGA — REVISAR EN ERP', resumen['conteos'])
            self.assertEqual(resumen['version'], '1.5')

    def test_completo_conserva_los_estados_de_ausentes(self):
        with carpeta_temporal() as d:
            f, _ = self.correr_reglas(d, alcance='completo')
            self.assertEqual(f[('FACTURA', '16', 'FC-A0002')]['Resultado'], 'PENDIENTE NUEVA DESCARGA ERP')
            self.assertEqual(f[('FACTURA', '16', 'FC-A0002')]['Saldo ERP'], '')
            self.assertEqual(f[('FACTURA', '15', 'FC-A0001')]['Resultado'], 'SOLO SGA SALDO CERO - REVISAR')
            self.assertNotIn(motor.NOTA_ABIERTOS, f[('FACTURA', '15', 'FC-A0001')]['Observaciones'])

    def test_pendiente_de_factura_va_en_fila_aparte(self):
        with carpeta_temporal() as d:
            f, resumen = self.correr_reglas(d)
            factura = f[('FACTURA', '10', 'FI-P0001')]
            self.assertEqual((factura['Saldo SGA'], factura['Filas SGA'], factura['Resultado'], factura['Diferencia SGA menos ERP']), ('-300.00', '1', 'DIFERENCIA', '-300.00'))
            self.assertNotIn('movimiento pendiente', factura['Observaciones'].lower())
            pendiente = f[('PENDIENTE', '10', 'FI-P0001')]
            self.assertEqual((pendiente['Saldo SGA'], pendiente['Filas SGA'], pendiente['Filas ERP']), ('300.00', '1', '0'))
            self.assertTrue(pendiente['Observaciones'].startswith(motor.NOTA_PENDIENTE))
            self.assertEqual(f[('FACTURA', '10', 'FI-P0002')]['Resultado'], 'COINCIDE')
            # Cobertura: todas las filas y los importes siguen en la salida, una sola vez.
            self.assertEqual(resumen['cobertura_salida']['SGA']['filas_fuente'], sum(int(r['Filas SGA']) for r in f.values()))
            self.assertEqual(Decimal(resumen['cobertura_salida']['SGA']['total_fuente_exacto']), sum(Decimal(r['Saldo SGA']) for r in f.values() if r['Saldo SGA']))

    def test_tipo_por_comprobante_principal_y_cruce_por_subrecibo(self):
        with carpeta_temporal() as d:
            f, _ = self.correr_reglas(d)
            self.assertEqual(f[('RC-X', '11', 'SR-0011')]['Resultado'], 'COINCIDE')
            self.assertEqual(f[('RC-R', '12', 'SR-0012')]['Resultado'], 'COINCIDE')
            self.assertEqual(f[('OP-X', '13', 'SR-0013')]['Resultado'], 'COINCIDE')
            solo_sga = f[('RC-X', '14', 'SR-0014')]
            self.assertEqual(solo_sga['Resultado'], 'DIFERENCIA')
            self.assertIn('RC-X0002', solo_sga['Detalle identificacion'])
            self.assertEqual(f[('RC-X', '18', 'SR-0018')]['Resultado'], 'SOLO EN ERP — REVISAR EN SGA')
            self.assertFalse([k for k in f if k[0] == 'OP-X' and k[1] != '13'])
            sin_principal = f[('SUBRECIBO', '20', 'SR-0020')]
            self.assertIn(motor.NOTA_SIN_PRINCIPAL, sin_principal['Observaciones'])

    def test_tipo_visible(self):
        self.assertEqual(motor.tipo_visible('SR', {'RC-X0001'}), 'RC-X')
        self.assertEqual(motor.tipo_visible('SR', {'RC-R0001'}), 'RC-R')
        self.assertEqual(motor.tipo_visible('OPX', {'OP-X0001'}), 'OP-X')
        self.assertEqual(motor.tipo_visible('SR', {'RC-X1', 'OP-X2'}), 'OP-X / RC-X')
        self.assertEqual(motor.tipo_visible('SR', set()), 'SUBRECIBO')
        self.assertEqual(motor.tipo_visible('MP', set()), 'PENDIENTE')
        self.assertEqual(motor.tipo_visible('FACTURA', {'RC-X1'}), 'FACTURA')

    def test_diferencias_con_el_legado_explicadas(self):
        sys.path.insert(0, str(RAIZ / 'herramientas'))
        import cambios_conciliacion as cc
        for caso in ('unificado', 'separado', 'reglas_1_5'):
            legado, nuevo = DORADOS / caso / 'legado_1_4', DORADOS / caso
            no_explicadas, explicadas = cc.explicar(legado / 'Conciliacion_general.csv', nuevo / 'Conciliacion_general.csv', 'abiertos')
            self.assertEqual(no_explicadas, [], caso)
            datos, _ = cc.leer_csv(nuevo / 'Conciliacion_general.csv')
            pendientes = sum(1 for r in datos if r['Tipo'] == 'PENDIENTE')
            self.assertEqual(cc.explicar_resumen(legado / 'Resumen.json', nuevo / 'Resumen.json', pendientes, datos), [], caso)
            if caso == 'reglas_1_5':
                self.assertEqual(explicadas['pendiente_separado'], 1)
                self.assertGreaterEqual(explicadas['tipo_RC-X'], 3)
                self.assertGreaterEqual(explicadas['abiertos_diferencia'], 3)
                self.assertGreaterEqual(explicadas['abiertos_coincide'], 2)


class HojasDeContinuacionTests(unittest.TestCase):
    """Un detalle con más comprobantes de los que entran en una hoja de Excel sigue en otras (ERP completo cortado
    por fechas: más de 1.048.575 comprobantes, 02/11/2026). Se prueba con el límite achicado."""

    def test_detalle_que_no_entra_en_una_hoja_sigue_en_otra(self):
        from unittest import mock
        from app.reportes.conciliacion_general import excel
        sys.path.insert(0, str(RAIZ / 'herramientas'))
        import cambios_conciliacion
        with carpeta_temporal() as d:
            sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA_FILAS)])
            erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + ERP_FILAS)])
            with mock.patch.object(excel, 'MAX_FILAS', 4):  # encabezado + 3 comprobantes por hoja
                resumen = correr({'sga': [sga], 'erp': [erp]}, d / 'salida', alcance='completo')
            total = resumen['registros_datos']
            self.assertEqual(total, 8)
            xlsx = d / 'salida' / 'Conciliacion_general.xlsx'
            hojas = dict(leer_hojas(xlsx))
            nombres = [n for n in hojas if n.startswith('Conciliación')]
            self.assertEqual(nombres, ['Conciliación_general', 'Conciliación_general_(2)', 'Conciliación_general_(3)'])
            # El Resumen (una fila por control y alerta) también sigue en otras hojas, antes del detalle.
            resumen_hojas = list(hojas)[:list(hojas).index(nombres[0])]
            self.assertEqual(resumen_hojas[:2], ['Resumen', 'Resumen_(2)'])
            self.assertTrue(all(hojas[n][0] == ['Control', 'Saldo SGA', 'Saldo ERP', 'Diferencia', 'Resultado / cantidad', 'Detalle'] for n in resumen_hojas))
            controles = [f for f in filas_csv(d / 'salida' / 'Respaldo_tecnico' / 'Conciliacion_general.csv') if f[0] == 'CONTROL']
            self.assertEqual(sum(len(hojas[n]) - 1 for n in resumen_hojas), len(controles))
            cabecera = filas_csv(d / 'salida' / 'Respaldo_tecnico' / 'Conciliacion_general.csv')[0]
            detalle = [hojas[n] for n in nombres]
            self.assertTrue(all(h[0] == cabecera for h in detalle))
            self.assertEqual([len(h) - 1 for h in detalle], [3, 3, 2])
            self.assertEqual(cambios_conciliacion.xlsx_consistente(xlsx, d / 'salida' / 'Respaldo_tecnico' / 'Conciliacion_general.csv'), [])

    def test_con_el_limite_real_sigue_en_dos_hojas(self):
        with carpeta_temporal() as d:
            sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA_FILAS)])
            erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + ERP_FILAS)])
            correr({'sga': [sga], 'erp': [erp]}, d / 'salida')
            self.assertEqual([n for n, _ in leer_hojas(d / 'salida' / 'Conciliacion_general.xlsx')], ['Resumen', 'Conciliación_general'])


class DetalleDeLecturaTests(unittest.TestCase):
    """El registro de la corrida dice qué se tomó de cada archivo (filas y fechas) y cuántos comprobantes salieron,
    termine bien o con error."""

    def _correr(self, d, erp_filas, fondo=FONDO):
        sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA_FILAS)])
        erp = xlsx_sintetico(d / 'erp.xlsx', [('Datos', [E] + erp_filas)])
        (d / 'parametros.json').write_text(json.dumps({'alcance': 'completo', 'corte': '2026-10-31', 'fondo': fondo}), encoding='utf-8')
        (d / 'entradas.json').write_text(json.dumps({'sga': [{'ruta': str(sga), 'nombre': 'sga.xlsx'}], 'erp': [{'ruta': str(erp), 'nombre': 'erp.xlsx'}]}), encoding='utf-8')
        proceso = subprocess.run([sys.executable, '-I', str(EJECUTAR), '--trabajo', str(d)], capture_output=True, text=True, encoding='utf-8', env=dict(os.environ, REPORTES_PROTOCOLO='1'))
        eventos = [json.loads(x) for x in proceso.stdout.splitlines() if x.strip()]
        return proceso, eventos, [ev['m'] for ev in eventos if ev['t'] == 'log']

    def test_al_terminar_bien(self):
        with carpeta_temporal() as d:
            proceso, _, lineas = self._correr(d, ERP_FILAS)
            self.assertEqual(proceso.returncode, 0, proceso.stderr)
            inicio = lineas.index('Detalle de la lectura:')
            self.assertEqual(lineas[inicio + 1], '  SGA sga.xlsx [Datos]: 9 filas, 8 tomadas, sin fechas')
            self.assertEqual(lineas[inicio + 2], '  ERP erp.xlsx [Datos]: 6 filas tomadas, sin fechas (Cliente 3, Pago 2, Diario general 1)')
            self.assertIn('  Comprobantes de la conciliación: 8', lineas)
            self.assertTrue(any(x.startswith('  Resultado COINCIDE: ') for x in lineas))

    def test_con_error_despues_de_leer(self):
        with carpeta_temporal() as d:
            de_santa_fe = [['80', '1', 'F1', '', '', 'SaFe-1', 'Cliente'], ['30', '2', 'F3', '', '', 'SaFe-2', 'Cliente']]
            proceso, eventos, lineas = self._correr(d, de_santa_fe)
            self.assertEqual(proceso.returncode, 1)
            self.assertIn('FERF Prov. Santa Fe', next(ev['m'] for ev in eventos if ev['t'] == 'error'))
            self.assertIn('  SGA sga.xlsx [Datos]: 8 filas tomadas, sin fechas', lineas)
            self.assertIn('  ERP erp.xlsx [Datos]: 2 filas tomadas, sin fechas', lineas)
            # el detalle va antes del error
            tipos = [ev['t'] for ev in eventos]
            self.assertLess(max(i for i, ev in enumerate(eventos) if ev['t'] == 'log' and 'filas tomadas' in ev['m']), tipos.index('error'))


if __name__ == '__main__':
    unittest.main()
