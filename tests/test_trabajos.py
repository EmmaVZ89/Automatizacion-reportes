import json
import sys
import time
import unittest
from pathlib import Path

from app.eventos import Bus
from app.trabajos import Trabajos
from app.almacen import escribir_json_atomico
from tests.fixtures import carpeta_temporal

MOTOR = Path(__file__).resolve().parent / 'motor_falso.py'
RAIZ = MOTOR.parent.parent


def esperar_hasta(cond, timeout=15):
    fin = time.time() + timeout
    while time.time() < fin:
        if cond():
            return True
        time.sleep(0.05)
    return False


def lanzar(tr, d, *args, ejecucion='e1'):
    return tr.lanzar(ejecucion, [sys.executable, str(MOTOR), *args], cwd=RAIZ, registro=d / 'registro.log')


class TrabajosTests(unittest.TestCase):
    def test_motor_falso_llega_a_esperando_y_continua_hasta_ok(self):
        with carpeta_temporal() as d:
            bus = Bus()
            cola = bus.suscribir()
            tr = Trabajos(d / 'trabajos.json', bus)
            t = lanzar(tr, d, '--esperar')
            self.assertTrue(esperar_hasta(lambda: tr.obtener(t['id'])['estado'] == 'esperando'))
            esp = tr.obtener(t['id'])['espera']
            self.assertEqual(esp['id'], 'login')
            self.assertIn('Continuar', esp['boton'])
            self.assertFalse(tr.continuar(t['id'], 'otra'))
            self.assertTrue(tr.continuar(t['id'], 'login'))
            self.assertTrue(esperar_hasta(lambda: tr.obtener(t['id'])['estado'] == 'ok'))
            final = tr.obtener(t['id'])
            self.assertEqual(final['tablas'], {'resultado': 12})
            self.assertEqual(final['resumen']['estado'], 'SIN DIFERENCIAS')
            self.assertEqual(final['paso'], 'Leyendo archivos')
            self.assertEqual(final['progreso'], 1.0)
            self.assertIn('continuó', final['lineas'])
            tipos = {cola.get_nowait()[0] for _ in range(cola.qsize())}
            self.assertEqual(tipos, {'trabajo'})
            tr.guardar_ahora()
            guardado = json.loads((d / 'trabajos.json').read_text(encoding='utf-8'))
            self.assertEqual(guardado['trabajos'][0]['estado'], 'ok')

    def test_cancelar_mata_el_proceso_y_queda_cancelado(self):
        with carpeta_temporal() as d:
            tr = Trabajos(d / 'trabajos.json')
            t = lanzar(tr, d, '--lento')
            self.assertTrue(esperar_hasta(lambda: 'Reconocí 3 archivos' in tr.obtener(t['id'])['lineas']))
            self.assertTrue(tr.cancelar(t['id']))
            self.assertTrue(esperar_hasta(lambda: tr.obtener(t['id'])['estado'] == 'cancelado', 10))
            self.assertFalse(tr.cancelar(t['id']))

    def test_cancelar_durante_espera(self):
        with carpeta_temporal() as d:
            tr = Trabajos(d / 'trabajos.json')
            t = lanzar(tr, d, '--esperar')
            self.assertTrue(esperar_hasta(lambda: tr.obtener(t['id'])['estado'] == 'esperando'))
            tr.cancelar(t['id'])
            self.assertTrue(esperar_hasta(lambda: tr.obtener(t['id'])['estado'] == 'cancelado'))

    def test_salida_no_json_se_registra_como_log(self):
        with carpeta_temporal() as d:
            tr = Trabajos(d / 'trabajos.json')
            t = lanzar(tr, d, '--texto-plano')
            self.assertTrue(esperar_hasta(lambda: tr.obtener(t['id'])['estado'] == 'ok'))
            lineas = tr.obtener(t['id'])['lineas']
            self.assertIn('línea suelta sin json', lineas)
            self.assertIn('{no es json}', lineas)
            self.assertIn('línea suelta sin json', (d / 'registro.log').read_text(encoding='utf-8'))

    def test_codigo_distinto_de_cero_queda_error_con_mensaje_llano(self):
        with carpeta_temporal() as d:
            tr = Trabajos(d / 'trabajos.json')
            t = lanzar(tr, d, '--fallar')
            self.assertTrue(esperar_hasta(lambda: tr.obtener(t['id'])['estado'] == 'error'))
            final = tr.obtener(t['id'])
            self.assertNotIn('Traceback', final['error'])
            self.assertIn('registro', final['error'])
            self.assertIn('ValueError', (d / 'registro.log').read_text(encoding='utf-8'))
            self.assertTrue(any('falta la columna Importe' in l for l in final['lineas']))

    def test_error_propio_del_motor_se_muestra_tal_cual(self):
        with carpeta_temporal() as d:
            tr = Trabajos(d / 'trabajos.json')
            t = lanzar(tr, d, '--error-propio')
            self.assertTrue(esperar_hasta(lambda: tr.obtener(t['id'])['estado'] == 'error'))
            self.assertEqual(tr.obtener(t['id'])['error'], 'Hay dos archivos de SGA; dejá uno solo.')

    def test_un_trabajo_activo_por_ejecucion(self):
        with carpeta_temporal() as d:
            tr = Trabajos(d / 'trabajos.json')
            t = lanzar(tr, d, '--lento')
            with self.assertRaises(ValueError):
                lanzar(tr, d, '--lento')
            tr.cancelar(t['id'])
            self.assertTrue(esperar_hasta(lambda: tr.obtener(t['id'])['estado'] == 'cancelado'))

    def test_al_arrancar_los_activos_quedan_interrumpidos(self):
        with carpeta_temporal() as d:
            escribir_json_atomico(d / 'trabajos.json', {'trabajos': [
                {'id': 7, 'ejecucionId': 'e9', 'estado': 'corriendo', 'lineas': [], 'espera': None},
                {'id': 8, 'ejecucionId': 'e8', 'estado': 'esperando', 'lineas': [], 'espera': {'id': 'x'}},
                {'id': 9, 'ejecucionId': 'e7', 'estado': 'ok', 'lineas': []},
            ]})
            tr = Trabajos(d / 'trabajos.json')
            estados = {t['id']: t['estado'] for t in tr.listar()}
            self.assertEqual(estados, {7: 'interrumpido', 8: 'interrumpido', 9: 'ok'})
            self.assertIsNone(tr.obtener(8)['espera'])
            nuevo = tr.lanzar('e1', [sys.executable, str(MOTOR)], cwd=RAIZ)
            self.assertEqual(nuevo['id'], 10)
            self.assertTrue(esperar_hasta(lambda: tr.obtener(10)['estado'] == 'ok'))

    def test_lineas_se_acotan_a_400_y_registro_log_las_tiene_todas(self):
        with carpeta_temporal() as d:
            guion = d / 'muchas.py'
            guion.write_text('import sys\nfor i in range(1000): print("linea", i)\n', encoding='utf-8')
            tr = Trabajos(d / 'trabajos.json')
            t = tr.lanzar('e1', [sys.executable, str(guion)], cwd=d, registro=d / 'registro.log')
            self.assertTrue(esperar_hasta(lambda: tr.obtener(t['id'])['estado'] == 'ok'))
            lineas = tr.obtener(t['id'])['lineas']
            self.assertEqual(len(lineas), 400)
            self.assertEqual(lineas[-1], 'linea 999')
            self.assertEqual((d / 'registro.log').read_text(encoding='utf-8').count('linea '), 1000)

    def test_al_terminar_se_llama_con_el_trabajo_final(self):
        with carpeta_temporal() as d:
            tr = Trabajos(d / 'trabajos.json')
            vistos = []
            tr.al_terminar(vistos.append)
            t = lanzar(tr, d)
            self.assertTrue(esperar_hasta(lambda: vistos))
            self.assertEqual(vistos[0]['id'], t['id'])
            self.assertEqual(vistos[0]['estado'], 'ok')


if __name__ == '__main__':
    unittest.main()
