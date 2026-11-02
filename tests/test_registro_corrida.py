"""Registro de una corrida para mandar a soporte (app/registro_corrida.py)."""
import unittest
from datetime import datetime

from app import catalogo, registro_corrida

NL = chr(10)


class RegistroCorridaTests(unittest.TestCase):
    def test_corrida_con_error(self):
        e = {'reporte': 'conciliacion_general', 'version': 3, 'final': False, 'estado': 'error',
             'error': 'El detalle supera el máximo de filas de Excel.', 'inicio': '2026-11-02T09:31:05', 'fin': '2026-11-02T09:37:40',
             'parametros': {'alcance': 'completo', 'corte': '2026-10-31', 'fondo': 'Fondo de Riesgo General', 'sesion_chrome': 'C:/datos/sesion'},
             'entradas': {'sga': ['a1'], 'erp': ['a2', 'a9'], 'otra': []}}
        cierre = {'periodo': '2026-10', 'corte': '2026-10-31', 'archivos': [
            {'id': 'a1', 'nombre': 'historico.xlsx', 'bytes': 64 * 1024 * 1024, 'hoja': 'CtaCteCompleta', 'filas': 451026},
            {'id': 'a2', 'nombre': 'erp_1.xlsx', 'bytes': 300 * 1024, 'hoja': 'Sheet1', 'filas': 192840, 'fondo': 'Fondo de Riesgo General'}]}
        registro = NL.join(['09:31:05 == Leyendo SGA Historico historico.xlsx', '09:37:40 ERROR: El detalle supera el máximo de filas de Excel.'])
        texto = registro_corrida.armar(e, cierre, catalogo.obtener('conciliacion_general'), registro, '2026.11.02',
                                       'Fondo de Riesgo General', ahora=datetime(2026, 11, 2, 10, 0))
        lineas = texto.split(NL)
        self.assertEqual(lineas[:2], ['Reportes de cierre 2026.11.02 · Registro de la corrida', 'Bajado el 02/11/2026 10:00'])
        for esperada in ['Reporte:   Conciliación general · Fondo de Riesgo General',
                         'Cierre:    octubre 2026 (corte 31/10/2026)',
                         'Versión:   3',
                         'Horario:   02/11/2026 09:31:05 a 09:37:40 (6 min 35 s)',
                         'Estado:    Terminó con un error',
                         'Qué pasó:  El detalle supera el máximo de filas de Excel.',
                         '  Alcance del reporte ERP: Reporte completo',
                         '  Fecha de corte: 31/10/2026',
                         '  Fondo de riesgo: Fondo de Riesgo General',
                         '  Histórico de cuenta corriente (SGA)',
                         '    historico.xlsx · 64,0 MB · hoja CtaCteCompleta · 451.026 filas',
                         '    erp_1.xlsx · 300 KB · hoja Sheet1 · 192.840 filas · Fondo de Riesgo General',
                         '    (un archivo que ya no está en el cierre)',
                         '  09:37:40 ERROR: El detalle supera el máximo de filas de Excel.']:
            self.assertIn(esperada, lineas)
        self.assertNotIn('sesion', texto)
        self.assertNotIn('Resultados', lineas)

    def test_corrida_que_no_llego_a_arrancar(self):
        e = {'reporte': 'control_mora', 'version': 1, 'estado': 'borrador', 'parametros': {}, 'entradas': {}}
        texto = registro_corrida.armar(e, {}, catalogo.obtener('control_mora'), '', '2026.11.02')
        self.assertIn('Estado:    Todavía no corrió', texto)
        self.assertIn('  (vacío: el reporte no llegó a arrancar)', texto)
        self.assertNotIn('Opciones', texto)

    def test_corrida_terminada_lleva_resultados_y_revision(self):
        e = {'reporte': 'control_cheques', 'version': 2, 'final': True, 'estado': 'ok', 'inicio': '2026-11-02T09:00:00', 'fin': '2026-11-02T09:00:12',
             'parametros': {}, 'entradas': {}, 'salidas': [{'tabla': 'revisar', 'titulo': 'Cheques a revisar', 'filas': 1234}],
             'revision': {'pendientes': 3, 'revisadas': 1200, 'omitidas': 31}}
        texto = registro_corrida.armar(e, {'periodo': '2026-10'}, catalogo.obtener('control_cheques'), '09:00:12 [fin] estado=ok codigo=0', '2026.11.02')
        self.assertIn('Versión:   2 (resultado final)', texto)
        self.assertIn('Horario:   02/11/2026 09:00:00 a 09:00:12 (12 s)', texto)
        self.assertIn('  Cheques a revisar: 1.234 filas', texto)
        self.assertIn('  Revisión: 3 pendientes, 1.200 revisadas, 31 omitidas', texto)


if __name__ == '__main__':
    unittest.main()
