"""Control de Mora: el motor nuevo contra el dorado del legado (tests/dorados/control_mora, generado con
tests/dorados/control_mora/generar.py), tramos, errores y el volcado de ejecutar.py."""
import csv
import json
import os
import sqlite3
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from app.reportes._comun import protocolo
from app.reportes.control_mora import motor
from tests.fixtures import carpeta_temporal, xlsx_openpyxl

RAIZ = Path(__file__).resolve().parent.parent
DORADO = RAIZ / 'tests' / 'dorados' / 'control_mora'
EJECUTAR = RAIZ / 'app' / 'reportes' / 'control_mora' / 'ejecutar.py'
ARCHIVOS = ['Resultado_Control_Mora.csv', 'Respaldo_ERP.csv', 'Respaldo_SGA_Mora.csv', 'PROCESO_COMPLETO.txt']
# El legado elige los archivos por prefijo de nombre: los fixtures lo respetan para que el dorado sea comparable.
NOMBRE_ERP = 'Saldo de comprobación_prueba.xlsx'
NOMBRE_SGA = 'ReporteHistoricoDeCuentaCorriente_prueba.xlsx'
NOMBRES_SGA_TRAMOS = ['ReporteHistoricoDeCuentaCorriente_1.xlsx', 'ReporteHistoricoDeCuentaCorriente_2.xlsx']

ENCABEZADO_ERP = ['MainAccount', 'MainAccountName', 'BusinessUnit', 'Saldo inicial', 'Débito', 'Crédito', 'Saldo de cierre']
ENCABEZADO_SGA = ['FondoDeRiesgo', 'CodigoEmpresa', 'NumeroFactura', 'FechaFactura', 'TipoComprobante', 'GrupoConceptoFacturacion',
                  'Concepto', 'Importe', 'Observaciones', 'NumeroComprobanteImputacion']


def filas_erp(sin_cuenta=None):
    filas = [
        [113601, 'Mora cuenta 1', 'FRG', 1000.5, 200.0, 50.25, 1150.25],
        [113602.0, 'Mora cuenta 2', 'frg ', 0, 0, 0, 2500.1],
        ['113603', 'Mora cuenta 3', 'FRG', -300.75, None, None, -300.75],
        [113604, 'Mora cuenta 4', 'FRG', 0.1, 0, 0, 0.1],
        [113605, 'Mora cuenta 5', 'FRG', 0.2, 0, 0, 0.2],
        [113601, 'Mora cuenta 1 de otra unidad', 'OTR', 999.99, 0, 0, 999.99],
        [113606, 'Otra cuenta', 'FRG', 5.0, 0, 0, 5.0],
        [220001, 'Proveedores', 'FRG', -10, 0, 0, -10],
    ]
    return [f for f in filas if motor.codigo(f[0]) != sin_cuenta]


def filas_sga():
    return [
        ['Fondo de Riesgo General', 1001, 'FC-A 0001-00000001', datetime(2026, 1, 15), 'FC-A', 'MORA', 'Intereses por mora', 1200.5, None, None],
        ['Fondo de Riesgo General', 1001, 'RC 0001-00000010', datetime(2026, 2, 1, 10, 30), 'RC', 'Mora', 'Imputación', -1200.5, '=SUMA(A1)', 'FC-A 0001-00000001'],
        ['Fondo de Riesgo General', 1002, 'FC-A 0001-00000002', datetime(2026, 3, 3), 'FC-A', 'mora', 'Intereses', 0.1, 'Texto normal', None],
        ['Fondo de Riesgo General', 1002, 'FC-A 0001-00000003', datetime(2026, 3, 4), 'FC-A', 'MORA', 'Intereses', 0.2, '+ignorar', None],
        ['Fondo de Riesgo Específico', 1003, 'FC-A 0001-00000004', datetime(2026, 4, 4), 'FC-A', 'MORA', 'Intereses', 500.0, None, None],
        ['Fondo de Riesgo General', 1003, 'FC-A 0001-00000005', datetime(2026, 4, 5), 'FC-A', 'APORTES', 'Aporte', 300.0, None, None],
        ['Fondo de Riesgo General', 1004, 'FC-A 0001-00000006', datetime(2026, 5, 5), 'FC-A', 'MORA ', 'Intereses', 2149.1, '@mencion', None],
        ['Fondo de Riesgo General', 1004, 'ND 0001-00000001', datetime(2026, 6, 6), 'ND', 'Móra', 'Intereses', 1000.0, None, None],
        ['Fondo de Riesgo General', 1005, 'FC-A 0001-00000007', datetime(2026, 6, 7), 'FC-A', None, 'Sin grupo', 50.0, None, None],
        [None, 1005, 'FC-A 0001-00000008', datetime(2026, 6, 8), 'FC-A', 'MORA', 'Sin fondo', 20.0, None, None],
        ['fondo de riesgo general', 1006, 'FC-A 0001-00000009', datetime(2026, 7, 7), 'FC-A', 'Mora', 'Intereses', 200.55, None, None],
        ['Fondo de Riesgo General', 1006, 'RC 0001-00000011', None, 'RC', 'Mora', 'Imputación', 0, None, 'FC-A 0001-00000009'],
    ]


def _libro_sga(path, filas):
    return xlsx_openpyxl(path, [
        ('Parametros', [['Clave', 'Valor'], ['Corte', '2026-10-31']]),
        ('CtaCteCompleta', [ENCABEZADO_SGA] + filas),
    ])


def armar_entradas(carpeta, tramos_sga=False, sin_cuenta=None):
    """Escribe los fixtures en `carpeta` y devuelve (rutas ERP, rutas SGA)."""
    carpeta = Path(carpeta)
    erp = xlsx_openpyxl(carpeta / NOMBRE_ERP, [('Sheet1', [['Saldo de comprobación', None, None], ENCABEZADO_ERP] + filas_erp(sin_cuenta))])
    filas = filas_sga()
    if tramos_sga:
        mitad = len(filas) // 2
        sga = [_libro_sga(carpeta / NOMBRES_SGA_TRAMOS[0], filas[:mitad]), _libro_sga(carpeta / NOMBRES_SGA_TRAMOS[1], filas[mitad:])]
    else:
        sga = [_libro_sga(carpeta / NOMBRE_SGA, filas)]
    return [erp], sga


def leer_csv(ruta):
    with Path(ruta).open('r', newline='', encoding='utf-8-sig') as f:
        return list(csv.reader(f, delimiter=';'))


def correr_motor(carpeta, **kw):
    erp, sga = armar_entradas(carpeta, **kw)
    salida = carpeta / 'salida'
    with mock.patch.object(protocolo, 'ACTIVO', False), mock.patch('builtins.print'):
        resumen = motor.ejecutar(erp, sga, salida, {}, informar=protocolo)
    return salida, resumen


def preparar_trabajo(carpeta, **kw):
    """Carpeta de trabajo como la arma el server: parametros.json + entradas.json (archivos con nombre <sha8>-<nombre>)."""
    entrada = carpeta / 'entrada'
    entrada.mkdir()
    erp, sga = armar_entradas(entrada, **kw)
    trabajo = carpeta / 'trabajo'
    trabajo.mkdir()
    guardados = {}
    for clave, rutas in (('erp', erp), ('sga', sga)):
        guardados[clave] = []
        for i, r in enumerate(rutas):
            destino = trabajo / f'{i:08x}-{r.name}'
            destino.write_bytes(r.read_bytes())
            guardados[clave].append({'ruta': str(destino), 'nombre': r.name, 'sha256': '0' * 64})
    (trabajo / 'parametros.json').write_text(json.dumps({
        'cuentas': ['113601', '113602', '113603', '113604', '113605'], 'unidad_negocio': 'FRG', 'fondo': 'Fondo de Riesgo General', 'grupo': 'Mora',
    }), encoding='utf-8')
    (trabajo / 'entradas.json').write_text(json.dumps(guardados), encoding='utf-8')
    return trabajo


def correr_ejecutar(trabajo):
    env = {**os.environ, 'REPORTES_PROTOCOLO': '1'}
    p = subprocess.run([sys.executable, '-I', str(EJECUTAR), '--trabajo', str(trabajo)], capture_output=True, text=True, encoding='utf-8', env=env, cwd=str(trabajo))
    eventos = [json.loads(l) for l in p.stdout.splitlines() if l.startswith('{')]
    return p, eventos


class ControlMoraTests(unittest.TestCase):
    def test_igual_a_dorado(self):
        with carpeta_temporal() as d:
            salida, resumen = correr_motor(d)
            for nombre in ARCHIVOS:
                with self.subTest(archivo=nombre):
                    self.assertEqual((salida / nombre).read_bytes(), (DORADO / nombre).read_bytes())
            self.assertEqual(resumen['estado'], 'REVISAR DIFERENCIA')
            self.assertEqual(resumen['saldo_erp'], '3349.90')
            self.assertEqual(resumen['saldo_sga'], '3349.95')
            self.assertEqual(resumen['diferencia'], '-0.05')
            self.assertEqual((resumen['filas_erp'], resumen['filas_sga']), (5, 8))
            self.assertEqual(resumen['hojas_sga'], ['CtaCteCompleta'])

    def test_tramos_sga_suman(self):
        with carpeta_temporal() as d:
            salida, resumen = correr_motor(d, tramos_sga=True)
            dorado = dict(leer_csv(DORADO / 'Resultado_Control_Mora.csv')[1:])
            nuevo = dict(leer_csv(salida / 'Resultado_Control_Mora.csv')[1:])
            for concepto in ('Estado', 'Saldo ERP FRG', 'Saldo SGA Mora FRG', 'Diferencia ERP menos SGA', 'Filas ERP', 'Filas SGA', 'Hoja SGA'):
                self.assertEqual(nuevo[concepto], dorado[concepto], concepto)
            self.assertEqual(nuevo['Archivo SGA'], ', '.join(NOMBRES_SGA_TRAMOS))
            self.assertEqual((salida / 'PROCESO_COMPLETO.txt').read_bytes(), (DORADO / 'PROCESO_COMPLETO.txt').read_bytes())
            self.assertEqual((salida / 'Respaldo_ERP.csv').read_bytes(), (DORADO / 'Respaldo_ERP.csv').read_bytes())
            respaldo = leer_csv(salida / 'Respaldo_SGA_Mora.csv')
            esperado = leer_csv(DORADO / 'Respaldo_SGA_Mora.csv')
            self.assertEqual(respaldo[0], esperado[0])
            self.assertEqual(respaldo[0][:3], ['ArchivoOrigen', 'HojaOrigen', 'FilaOrigen'])
            # Mismas filas y en el mismo orden; cambia sólo el archivo de origen y la fila dentro de cada tramo.
            self.assertEqual([f[1:2] + f[3:] for f in respaldo[1:]], [f[1:2] + f[3:] for f in esperado[1:]])
            self.assertEqual([f[0] for f in respaldo[1:]], [NOMBRES_SGA_TRAMOS[0]] * 4 + [NOMBRES_SGA_TRAMOS[1]] * 4)
            self.assertEqual([f[2] for f in respaldo[1:]], ['2', '3', '4', '5', '2', '3', '6', '7'])
            self.assertEqual(resumen['archivos_sga'], NOMBRES_SGA_TRAMOS)

    def test_faltan_cuentas_corta(self):
        with carpeta_temporal() as d:
            erp, sga = armar_entradas(d, sin_cuenta='113605')
            with mock.patch.object(protocolo, 'ACTIVO', False), mock.patch('builtins.print'):
                with self.assertRaises(ValueError) as cm:
                    motor.ejecutar(erp, sga, d / 'salida', {}, informar=protocolo)
            self.assertIn('Faltan cuentas FRG', str(cm.exception))
            self.assertFalse((d / 'salida' / 'PROCESO_COMPLETO.txt').exists())
        with carpeta_temporal() as d:
            trabajo = preparar_trabajo(d, sin_cuenta='113605')
            p, eventos = correr_ejecutar(trabajo)
            self.assertEqual(p.returncode, 1, p.stderr)
            errores = [e for e in eventos if e['t'] == 'error']
            self.assertEqual(len(errores), 1)
            self.assertIn('Faltan cuentas FRG o hay cuentas duplicadas', errores[0]['m'])
            self.assertNotIn('Traceback', p.stderr)
            self.assertFalse((trabajo / 'salidas' / 'PROCESO_COMPLETO.txt').exists())

    def test_ejecutar_vuelca_tres_tablas(self):
        with carpeta_temporal() as d:
            trabajo = preparar_trabajo(d)
            p, eventos = correr_ejecutar(trabajo)
            self.assertEqual(p.returncode, 0, p.stderr)
            for nombre in ARCHIVOS:
                with self.subTest(archivo=nombre):
                    self.assertEqual((trabajo / 'salidas' / nombre).read_bytes(), (DORADO / nombre).read_bytes())
            tablas = [e for e in eventos if e['t'] == 'tabla']
            self.assertEqual([(e['tabla'], e['filas']) for e in tablas], [('resultado', 13), ('respaldo_erp', 5), ('respaldo_sga', 8)])
            resumenes = [e for e in eventos if e['t'] == 'resumen']
            self.assertEqual(len(resumenes), 1)
            datos = resumenes[0]['datos']
            self.assertEqual(datos['estado'], 'REVISAR DIFERENCIA')
            self.assertEqual(datos['archivos_erp'], [NOMBRE_ERP])
            self.assertEqual(datos['archivos_sga'], [NOMBRE_SGA])
            self.assertNotIn(str(trabajo), json.dumps(datos))
            con = sqlite3.connect(str(trabajo / 'resultados.sqlite'))
            try:
                self.assertEqual([r[0] for r in con.execute('SELECT tabla FROM _tablas ORDER BY orden')], ['resultado', 'respaldo_erp', 'respaldo_sga'])
                self.assertEqual(con.execute('SELECT COUNT(*) FROM t_respaldo_sga').fetchone()[0], 8)
                columnas = [r[0] for r in con.execute("SELECT nombre FROM _columnas WHERE tabla='respaldo_sga' ORDER BY posicion")]
                self.assertEqual(columnas, ['ArchivoOrigen', 'HojaOrigen', 'FilaOrigen'] + ENCABEZADO_SGA)
                clave, c0, c10 = con.execute('SELECT _clave, c0, c10 FROM t_respaldo_sga WHERE _fila = 0').fetchone()
                self.assertEqual(clave.split('\x1f'), [NOMBRE_SGA, 'CtaCteCompleta', '2'])
                self.assertEqual((c0, c10), (NOMBRE_SGA, '1200,5'))
                self.assertEqual(con.execute("SELECT tipo FROM _columnas WHERE tabla='respaldo_sga' AND nombre='Importe'").fetchone()[0], 'numero')
                self.assertEqual(con.execute("SELECT _clave, c1 FROM t_resultado WHERE c0 = 'Estado'").fetchone(), ('Estado', 'REVISAR DIFERENCIA'))
            finally:
                con.close()


if __name__ == '__main__':
    unittest.main()
