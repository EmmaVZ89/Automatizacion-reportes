"""Control de cheques: el motor nuevo contra el dorado del legado, tramos, importes y ejecutar.py.

Para regenerar el dorado (tests/dorados/control_cheques/) a partir del legado:
  py -3 -c "from tests.test_control_cheques import generar_fixtures; generar_fixtures(r'<carpeta>')"
  py -3.12 legado/control_cheques/control_cheques.py --sga <carpeta>/cheques_sga.xlsx --erp <carpeta>/tesoreria_erp.xlsx --salida <carpeta>/salida
y copiar Cheques_para_revisar.csv y Resumen.txt de la subcarpeta con sello de tiempo."""
import csv
import json
import os
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

from app.reportes.control_cheques import motor
from tests.fixtures import carpeta_temporal, xlsx_openpyxl

DORADOS = Path(__file__).resolve().parent / 'dorados' / 'control_cheques'
EJECUTAR = Path(__file__).resolve().parent.parent / 'app' / 'reportes' / 'control_cheques' / 'ejecutar.py'

ENCABEZADO_SGA = ['IdCheque', 'IdCheque2', 'RazonSocial', 'Cuit', 'NumeroCheque', 'Importe', 'Estado']
FILAS_SGA = [
    [10000000001, 1, 'Empresa Uno', 30000000001, 101, 1500.0, 'Acreditado'],          # coincide (En Cartera)
    ['10000000002', 2, 'Empresa Dos', 30000000002, 102, 2500.5, 'Depositado'],        # coincide (DEPOSITADO)
    [10000000003, 3, 'Empresa Tres', 30000000003, 103, 1234.5, 'Acreditado'],         # diferencia de estado
    [10000000004, 4, 'Empresa Cuatro', 30000000004, 104, 800.0, 'Acreditado'],        # duplicado en ERP
    [10000000005, 5, 'Empresa Cinco', 30000000005, 105, 900.0, 'Acreditado'],         # cancelado en ERP
    [10000000006, 6, 'Empresa Seis', 30000000006, 106, 950.0, 'Rechazado'],           # excluido: Debitado
    [10000000007, 7, 'Empresa Siete', 30000000007, 107, 1000.0, 'Acreditado'],        # excluido: Pagado a
    [10000000008, 8, 'Empresa Ocho', 30000000008, 108, 1100.0, 'Acreditado'],         # válido: canjeado
    [563000000009, 9, 'Empresa Nueve', 30000000009, 109, 1200.0, 'Acreditado'],       # histórico 563
    [None, 10, 'Empresa Diez', 30000000010, 110, 1300.0, 'Acreditado'],               # falta ID
    [None, None, None, None, None, None, None],                                       # fila vacía: se saltea
    [10000000011, 11, 'Empresa Once', 30000000011, 111, 1400.0, 'Acreditado'],        # sin cruce
    [10000000012, 12, 'Empresa Doce', 30000000012, 112, '1.600,00', 'Rechazado'],     # ERP sin regla; importe texto
    [10000000013, 13, 'Empresa Trece', 30000000013, 113, 1700.0, 'ACREDITADO'],       # coincide (mayúsculas)
    [10000000014, 14, 'Empresa Catorce', 30000000014, 114, 1800.0, 'Depositado'],     # diferencia (ERP Rechazado)
]
ENCABEZADO_ERP = ['Id de Transacción', 'Fecha', 'Estado', 'Pagado a', 'Importe']
FILAS_ERP = [
    ['gtz-000001', '2026-01-02', 'En Cartera', None, 1500.0],
    ['gtz-000002', '2026-01-03', 'DEPOSITADO', None, 2500.5],
    ['gtz-000004', '2026-01-04', 'En cartera', None, 800.0],
    ['gtz-000003', '2026-01-05', 'Depositado', None, 1234.5],
    ['gtz-000005', '2026-01-06', 'Cancelado', None, 900.0],
    [None, '2026-01-06', 'En cartera', None, 5.0],                 # sin ID: no se cruza
    ['gtz-000006', '2026-01-07', 'Debitado', None, 950.0],
    ['gtz-000007', '2026-01-08', 'En cartera', 'Proveedor Genérico', 1000.0],
    ['gtz-000008', '2026-01-09', 'canjeado', None, 1100.0],
    ['gtz-000004', '2026-01-10', 'Depositado', None, 800.0],        # duplicado
    ['gtz-000012', '2026-01-11', 'Anulado', None, 1600.0],
    ['gtz-000013', '2026-01-12', 'En Cartera', None, 1700.0],
    ['gtz-000014', '2026-01-13', 'Rechazado', None, 1800.0],
    ['gtz-000099', '2026-01-14', 'En cartera', None, 1.0],          # sólo en ERP
]


def generar_fixtures(carpeta, filas_erp=None, nombre_erp='tesoreria_erp.xlsx', filas_sga=None, nombre_sga='cheques_sga.xlsx'):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    sga = xlsx_openpyxl(carpeta / nombre_sga, [('Cheques', [ENCABEZADO_SGA] + (filas_sga if filas_sga is not None else FILAS_SGA)), ('Notas', [['Comentario'], ['sin datos']])])
    erp = xlsx_openpyxl(carpeta / nombre_erp, [('Valores', [ENCABEZADO_ERP] + (filas_erp if filas_erp is not None else FILAS_ERP))])
    return sga, erp


COLUMNAS_NUEVAS = ('Fecha', 'Fecha de depósito')


def sin_fechas(filas):
    """Las filas sin las dos columnas que pidió quien usa el reporte (el legado no las tiene)."""
    quedan = [i for i, c in enumerate(filas[0]) if c not in COLUMNAS_NUEVAS]
    return [[f[i] for i in quedan] for f in filas]


def _leer_csv(ruta):
    with Path(ruta).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.reader(f, delimiter=';'))


def _lineas_resumen(ruta):
    return [l for l in Path(ruta).read_text(encoding='utf-8').splitlines() if not l.startswith(('SGA:', 'ERP:'))]


class Silencio:
    """Un `informar` que no imprime nada."""

    def __getattr__(self, nombre):
        return lambda *a, **k: None


class ControlChequesTests(unittest.TestCase):
    def test_igual_a_dorado(self):
        with carpeta_temporal() as tmp:
            sga, erp = generar_fixtures(tmp)
            motor.controlar([sga], [erp], tmp / 'salida', {}, informar=Silencio())
            self.assertEqual(sin_fechas(_leer_csv(tmp / 'salida' / 'Cheques_para_revisar.csv')), _leer_csv(DORADOS / 'Cheques_para_revisar.csv'))
            self.assertEqual(_lineas_resumen(tmp / 'salida' / 'Resumen.txt'), _lineas_resumen(DORADOS / 'Resumen.txt'))

    def test_tramos_erp_se_indexan_juntos(self):
        with carpeta_temporal() as tmp:
            sga, _ = generar_fixtures(tmp)
            _, erp1 = generar_fixtures(tmp, filas_erp=FILAS_ERP[:6], nombre_erp='erp_1.xlsx')
            _, erp2 = generar_fixtures(tmp, filas_erp=FILAS_ERP[6:], nombre_erp='erp_2.xlsx')
            resumen = motor.controlar([sga], [erp1, erp2], tmp / 'salida', {}, informar=Silencio())
            dorado = _leer_csv(DORADOS / 'Cheques_para_revisar.csv')
            nuevo = sin_fechas(_leer_csv(tmp / 'salida' / 'Cheques_para_revisar.csv'))
            self.assertEqual(nuevo[0], dorado[0][:11] + ['Archivos ERP'])
            # Sin las columnas de fila/archivo ERP (la fila cambia al partir el archivo) el resultado es el mismo.
            self.assertEqual([f[:10] for f in nuevo], [f[:10] for f in dorado])
            duplicado = next(f for f in nuevo if f[0].startswith('ID duplicado'))
            self.assertEqual(duplicado[10], '4 / 5')
            self.assertEqual(duplicado[11], 'erp_1.xlsx / erp_2.xlsx')
            self.assertEqual(resumen['Filas ERP'], len(FILAS_ERP))
            self.assertEqual(_lineas_resumen(tmp / 'salida' / 'Resumen.txt'), _lineas_resumen(DORADOS / 'Resumen.txt'))
            encabezado = (tmp / 'salida' / 'Resumen.txt').read_text(encoding='utf-8').splitlines()[2]
            self.assertEqual(encabezado, 'ERP: erp_1.xlsx / erp_2.xlsx')

    def test_tramos_sga_agregan_columna_archivo(self):
        with carpeta_temporal() as tmp:
            _, erp = generar_fixtures(tmp)
            sga1, _ = generar_fixtures(tmp, filas_sga=FILAS_SGA[:4], nombre_sga='sga_1.xlsx')
            sga2, _ = generar_fixtures(tmp, filas_sga=FILAS_SGA[4:], nombre_sga='sga_2.xlsx')
            motor.controlar([sga1, sga2], [erp], tmp / 'salida', {}, informar=Silencio())
            dorado = _leer_csv(DORADOS / 'Cheques_para_revisar.csv')
            nuevo = sin_fechas(_leer_csv(tmp / 'salida' / 'Cheques_para_revisar.csv'))
            self.assertEqual(nuevo[0], dorado[0][:10] + ['Archivo SGA', 'Filas ERP'])
            self.assertEqual([f[:9] + f[11:] for f in nuevo], [f[:9] + f[10:] for f in dorado])
            self.assertEqual([f[10] for f in nuevo[1:]], ['sga_1.xlsx', 'sga_1.xlsx'] + ['sga_2.xlsx'] * (len(nuevo) - 3))

    def test_fechas_y_pedido_a_sistemas(self):
        from datetime import datetime
        with carpeta_temporal() as tmp:
            sga, _ = generar_fixtures(tmp)
            # ERP con la columna nueva: fecha de depósito en algunas filas (como fecha de Excel o como texto)
            filas = [f + [datetime(2026, 1, 10) if i % 2 == 0 else ''] for i, f in enumerate(FILAS_ERP)]
            erp = xlsx_openpyxl(tmp / 'erp_con_deposito.xlsx', [('Valores', [ENCABEZADO_ERP + ['Fecha de Depósito']] + filas)])
            motor.controlar([sga], [erp], tmp / 'salida', {}, informar=Silencio())
            revisar = _leer_csv(tmp / 'salida' / 'Cheques_para_revisar.csv')
            enc = revisar[0]
            self.assertEqual(enc[enc.index('Estado ERP') + 1:enc.index('Estado ERP') + 3], ['Fecha', 'Fecha de depósito'])
            por_id = {f[enc.index('ID SGA')]: f for f in revisar[1:]}
            diferencias = [f for f in revisar[1:] if f[0] == 'Diferencia de estado']
            self.assertTrue(diferencias)
            for f in diferencias:
                erp_fila = next(x for i, x in enumerate(FILAS_ERP) if x[0] == f[enc.index('ID ERP')])
                i_erp = FILAS_ERP.index(erp_fila)
                self.assertEqual(f[enc.index('Fecha')], erp_fila[1])
                self.assertEqual(f[enc.index('Fecha de depósito')], '10/01/2026' if i_erp % 2 == 0 else '')
            pedido = _leer_csv(tmp / 'salida' / 'Pedido_a_sistemas.csv')
            self.assertEqual(pedido[0], ['ID SGA', 'Fecha de depósito'])
            self.assertEqual(pedido[1:], [[f[enc.index('ID SGA')], f[enc.index('Fecha de depósito')]] for f in diferencias])
            self.assertTrue(por_id)

    def test_sin_columna_de_deposito_sale_vacia_y_lo_avisa(self):
        class Anota(Silencio):
            def __init__(self):
                self.lineas = []

            def log(self, m):
                self.lineas.append(m)
        with carpeta_temporal() as tmp:
            sga, erp = generar_fixtures(tmp)
            anota = Anota()
            motor.controlar([sga], [erp], tmp / 'salida', {}, informar=anota)
            revisar = _leer_csv(tmp / 'salida' / 'Cheques_para_revisar.csv')
            i = revisar[0].index('Fecha de depósito')
            self.assertEqual({f[i] for f in revisar[1:]}, {''})
            self.assertTrue(any('Fecha de depósito' in l for l in anota.lineas))

    def test_importe_numerico_con_coma(self):
        with carpeta_temporal() as tmp:
            sga, erp = generar_fixtures(tmp)
            motor.controlar([sga], [erp], tmp / 'salida', {}, informar=Silencio())
            filas = {f[2]: f for f in _leer_csv(tmp / 'salida' / 'Cheques_para_revisar.csv')[1:]}
            self.assertEqual(filas['10000000003'][6], '1234,50')
            self.assertEqual(filas['10000000004'][6], '800,00')
            self.assertEqual(filas['10000000012'][6], '1.600,00')

    def test_parametros_reemplazan_constantes(self):
        with carpeta_temporal() as tmp:
            sga, erp = generar_fixtures(tmp)
            parametros = {'prefijos_historicos': ['563', '10000000011'], 'estados_validos': ['canjeado', 'anulado'],
                          'equivalencias': [{'erp': 'rechazado', 'sga': 'depositado'}, {'erp': 'depositado', 'sga': 'depositado'}, {'erp': 'en cartera', 'sga': 'acreditado'}]}
            resumen = motor.controlar([sga], [erp], tmp / 'salida', parametros, informar=Silencio())
            self.assertEqual(resumen['Validos: ID historico 563'], 2)
            self.assertEqual(resumen['Validos: Canjeado historico'], 2)
            self.assertNotIn('ID no encontrado en ERP', resumen)
            self.assertNotIn('Estado ERP sin regla definida', resumen)
            self.assertEqual(resumen['Diferencia de estado'], 1)
            self.assertEqual(resumen['Estados coincidentes'], 4)

    def test_archivo_sin_columnas_corta_con_valueerror(self):
        with carpeta_temporal() as tmp:
            sga, _ = generar_fixtures(tmp)
            with self.assertRaises(ValueError):
                motor.controlar([sga], [sga], tmp / 'salida', {}, informar=Silencio())

    def test_ejecutar_vuelca_dos_tablas_y_resumen(self):
        with carpeta_temporal() as tmp:
            sga, erp = generar_fixtures(tmp / 'archivos')
            trabajo = tmp / 'trabajo'
            trabajo.mkdir()
            (trabajo / 'parametros.json').write_text(json.dumps({'prefijos_historicos': ['563']}), encoding='utf-8')
            (trabajo / 'entradas.json').write_text(json.dumps({
                'sga': [{'ruta': str(sga), 'nombre': 'cheques_sga.xlsx', 'sha256': '0' * 64}],
                'erp': [{'ruta': str(erp), 'nombre': 'tesoreria_erp.xlsx', 'sha256': '1' * 64}],
            }), encoding='utf-8')
            entorno = dict(os.environ, REPORTES_PROTOCOLO='1', PYTHONIOENCODING='utf-8')
            proceso = subprocess.run([sys.executable, '-I', str(EJECUTAR), '--trabajo', str(trabajo)], capture_output=True, text=True, encoding='utf-8', env=entorno, cwd=str(tmp))
            self.assertEqual(proceso.returncode, 0, proceso.stderr)
            eventos = [json.loads(l) for l in proceso.stdout.splitlines() if l.strip()]
            tipos = [e['t'] for e in eventos]
            self.assertIn('paso', tipos)
            self.assertEqual([e for e in eventos if e['t'] == 'tabla'], [{'t': 'tabla', 'tabla': 'revisar', 'filas': 7}, {'t': 'tabla', 'tabla': 'resumen', 'filas': 14},
                                                                         {'t': 'tabla', 'tabla': 'pedido_sistemas', 'filas': 2}])
            resumen = [e for e in eventos if e['t'] == 'resumen'][-1]['datos']
            self.assertEqual(resumen['total_para_revisar'], 7)
            self.assertEqual(resumen['sga'], ['cheques_sga.xlsx'])
            self.assertEqual(sin_fechas(_leer_csv(trabajo / 'salidas' / 'Cheques_para_revisar.csv')), _leer_csv(DORADOS / 'Cheques_para_revisar.csv'))
            con = sqlite3.connect(str(trabajo / 'resultados.sqlite'))
            try:
                tablas = dict(con.execute('SELECT tabla, filas FROM _tablas').fetchall())
                self.assertEqual(tablas, {'revisar': 7, 'resumen': 14, 'pedido_sistemas': 2})
                columnas = [r[0] for r in con.execute("SELECT nombre FROM _columnas WHERE tabla='revisar' ORDER BY posicion")]
                self.assertEqual(columnas, motor.CAMPOS)
                claves = [r[0] for r in con.execute('SELECT _clave FROM t_revisar ORDER BY _fila')]
                self.assertEqual(claves[0], '10000000003\x1fDiferencia de estado')
                self.assertEqual(con.execute("SELECT c1 FROM t_resumen WHERE c0='Total para revisar'").fetchone(), ('7',))
                self.assertEqual(con.execute("SELECT _clave FROM t_resumen WHERE c0='Filas SGA'").fetchone(), ('Filas SGA',))
            finally:
                con.close()

    def test_ejecutar_informa_error_esperable(self):
        with carpeta_temporal() as tmp:
            sga, _ = generar_fixtures(tmp / 'archivos')
            trabajo = tmp / 'trabajo'
            trabajo.mkdir()
            (trabajo / 'parametros.json').write_text('{}', encoding='utf-8')
            (trabajo / 'entradas.json').write_text(json.dumps({
                'sga': [{'ruta': str(sga), 'nombre': 'cheques_sga.xlsx', 'sha256': '0' * 64}],
                'erp': [{'ruta': str(sga), 'nombre': 'otro.xlsx', 'sha256': '1' * 64}],
            }), encoding='utf-8')
            entorno = dict(os.environ, REPORTES_PROTOCOLO='1', PYTHONIOENCODING='utf-8')
            proceso = subprocess.run([sys.executable, '-I', str(EJECUTAR), '--trabajo', str(trabajo)], capture_output=True, text=True, encoding='utf-8', env=entorno)
            self.assertEqual(proceso.returncode, 1)
            eventos = [json.loads(l) for l in proceso.stdout.splitlines() if l.strip()]
            self.assertEqual(eventos[-1]['t'], 'error')
            self.assertIn('se esperaba una única hoja', eventos[-1]['m'])


if __name__ == '__main__':
    unittest.main()
