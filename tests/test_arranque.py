import json
import sys
import time
import unittest
import unittest.mock

from app import arranque
from app.servidor import crear_servidor
from tests.cliente import Cliente, servidor_de_prueba, MOTOR_FALSO
from tests.fixtures import carpeta_temporal


def esperar_hasta(cond, timeout=15):
    fin = time.time() + timeout
    while time.time() < fin:
        if cond():
            return True
        time.sleep(0.05)
    return False


class ArranqueTests(unittest.TestCase):
    def test_segundo_arranque_reusa_instancia_y_no_abre_otro_puerto(self):
        with carpeta_temporal() as d:
            capturas = []
            s = arranque.main(['--datos', str(d), '--puerto', '7430'], abrir=capturas.append, bloquear=False, inactividad_segundos=0)
            try:
                self.assertEqual(s.puerto, 7430)
                info = json.loads((d / '.servidor.json').read_text(encoding='utf-8'))
                self.assertEqual((info['puerto'], info['token']), (7430, s.token))
                otro = arranque.main(['--datos', str(d), '--puerto', '7430'], abrir=capturas.append, bloquear=False)
                self.assertIsNone(otro)
                self.assertEqual(len(capturas), 2)
                self.assertEqual(capturas[0], capturas[1])
                self.assertIn(f'127.0.0.1:7430/?t={s.token}', capturas[1])
            finally:
                s.cerrar()
            self.assertFalse((d / '.servidor.json').exists())

    def test_servidor_json_viejo_se_ignora_si_no_responde(self):
        with carpeta_temporal() as d:
            (d / '.servidor.json').write_text(json.dumps({'pid': 1, 'puerto': 7431, 'token': 'viejo'}), encoding='utf-8')
            self.assertIsNone(arranque.instancia_viva(d))
            s = arranque.main(['--datos', str(d), '--puerto', '7431', '--sin-navegador'], abrir=lambda u: None, bloquear=False, inactividad_segundos=0)
            try:
                self.assertEqual(s.puerto, 7431)
                self.assertNotEqual(json.loads((d / '.servidor.json').read_text(encoding='utf-8'))['token'], 'viejo')
            finally:
                s.cerrar()

    def test_dir_datos_por_defecto_fuera_del_programa(self):
        import os
        with unittest.mock.patch.dict(os.environ, {'REPORTES_DATOS': ''}, clear=False):
            os.environ.pop('REPORTES_DATOS', None)
            ruta = arranque.dir_datos()
            self.assertTrue(str(ruta).endswith('ReportesDeCierre\\datos') or str(ruta).endswith('ReportesDeCierre/datos'))
            self.assertNotIn('Automatizacion-reportes', str(ruta))
        with unittest.mock.patch.dict(os.environ, {'REPORTES_DATOS': 'C:/x/datos'}):
            self.assertEqual(str(arranque.dir_datos()).replace('\\', '/'), 'C:/x/datos')

    def test_cerrar_con_trabajo_activo_409_y_apaga_sin_trabajos(self):
        with carpeta_temporal() as d:
            s = servidor_de_prueba(d, puerto=7432, args_motor=('--lento',))
            c = Cliente(s)
            try:
                _, _, cierre = c.post('/api/cierres', {'periodo': '2026-10', 'corte': '2026-10-31'})
                _, _, e = c.post('/api/ejecuciones', {'cierre': cierre['id'], 'reporte': 'falso'})
                status, _, _ = c.post(f'/api/ejecuciones/{e["id"]}/ejecutar', {})
                self.assertEqual(status, 202)
                status, _, cuerpo = c.post('/api/cerrar', {})
                self.assertEqual(status, 409)
                self.assertIn('corriendo', cuerpo['error'])
                tid = c.get(f'/api/ejecuciones/{e["id"]}')[2]['trabajoId']
                c.post(f'/api/trabajos/{tid}/cancelar', {})
                self.assertTrue(esperar_hasta(lambda: c.get(f'/api/ejecuciones/{e["id"]}')[2]['estado'] == 'cancelado'))
                status, _, cuerpo = c.post('/api/cerrar', {})
                self.assertEqual(status, 200)
                self.assertTrue(esperar_hasta(lambda: s.cerrando))

                def caido():
                    try:
                        c.get('/api/estado')
                        return False
                    except OSError:
                        return True
                self.assertTrue(esperar_hasta(caido))
            finally:
                s.cerrar()

    def test_patch_configuracion_guarda_parametros_por_reporte(self):
        with carpeta_temporal() as d:
            s = servidor_de_prueba(d, puerto=7433)
            c = Cliente(s)
            try:
                status, _, conf = c.get('/api/configuracion')
                self.assertEqual(conf['tema'], 'claro')
                self.assertEqual(conf['carpetaDatos'], str(d))
                status, _, conf = c.patch('/api/configuracion', {'tema': 'oscuro', 'reportes': {'control_mora': {'parametros': {'cuentas': ['1', '2']}}}})
                self.assertEqual(conf['tema'], 'oscuro')
                status, _, p = c.get('/api/parametros/control_mora')
                self.assertEqual(p['valores']['cuentas'], ['1', '2'])
                self.assertEqual(p['valores']['fondo'], 'Fondo de Riesgo General')
                _, _, cierre = c.post('/api/cierres', {'periodo': '2026-10', 'corte': '2026-10-31'})
                status, _, p = c.get(f'/api/parametros/controles_sga?cierre={cierre["id"]}')
                self.assertEqual(p['valores']['corte'], '2026-10-31')
                # guardarDefaults al ejecutar persiste lo persistible
                _, _, e = c.post('/api/ejecuciones', {'cierre': cierre['id'], 'reporte': 'falso'})
                status, _, _ = c.post(f'/api/ejecuciones/{e["id"]}/ejecutar', {'parametros': {'nota': 'guardada'}, 'guardarDefaults': True})
                self.assertEqual(status, 202)
                self.assertEqual(c.get('/api/parametros/falso')[2]['valores']['nota'], 'guardada')
                self.assertTrue(esperar_hasta(lambda: c.get(f'/api/ejecuciones/{e["id"]}')[2]['estado'] == 'ok'))
            finally:
                s.cerrar()

    def test_inactividad_apaga(self):
        with carpeta_temporal() as d:
            s = crear_servidor(d, puerto_inicial=7434, intentos=5, probar_venv=False, inactividad_segundos=1)
            s.ultima_peticion = time.time() - 5
            s._vigilar_inactividad()
            s.servir_en_hilo()
            try:
                self.assertTrue(esperar_hasta(lambda: s.cerrando, 10))
            finally:
                s.cerrar()

    def test_con_una_pestana_abierta_no_se_apaga_y_el_motivo_queda_en_el_registro(self):
        with carpeta_temporal() as d:
            s = crear_servidor(d, puerto_inicial=7435, intentos=5, probar_venv=False, inactividad_segundos=1)
            pestana = s.bus.suscribir()  # lo que hace /api/eventos mientras la pantalla está abierta
            s.ultima_peticion = time.time() - 5
            s._vigilar_inactividad()
            s.servir_en_hilo()
            try:
                time.sleep(3.5)
                self.assertFalse(s.cerrando)
                s.bus.desuscribir(pestana)
                self.assertTrue(esperar_hasta(lambda: s.cerrando, 10))
            finally:
                s.cerrar()
            registro = (d / 'servidor.log').read_text(encoding='utf-8')
            self.assertIn('Se cierra la herramienta por inactividad (1 s sin pestañas abiertas)', registro)
            self.assertEqual(registro.count('Se cierra la herramienta'), 1)

    def test_registro_de_apertura_y_de_sesion_anterior_sin_cerrar(self):
        with carpeta_temporal() as d:
            (d / '.servidor.json').write_text(json.dumps({'pid': 1, 'puerto': 7436, 'token': 'viejo', 'inicio': '2026-11-01T09:00:00'}), encoding='utf-8')
            s = arranque.main(['--datos', str(d), '--puerto', '7436', '--sin-navegador'], abrir=lambda u: None, bloquear=False, inactividad_segundos=0)
            try:
                c = Cliente(s)
                status, _, r = c.post('/api/cerrar', {})
                self.assertEqual(status, 200)
                self.assertTrue(esperar_hasta(lambda: s.cerrando, 10))
            finally:
                s.cerrar()
            registro = (d / 'servidor.log').read_text(encoding='utf-8')
            self.assertIn('Se abre la herramienta: versión', registro)
            self.assertIn('La sesión anterior (pid 1, abierta el 2026-11-01T09:00:00) terminó sin cerrarse', registro)
            self.assertIn('Se cierra la herramienta desde la pantalla', registro)
            self.assertFalse((d / '.servidor.json').exists())  # cerrada bien: la próxima no avisa nada

    def test_errores_sin_atrapar_van_al_registro(self):
        import threading
        from unittest import mock
        registro = mock.Mock()
        anteriores = (sys.excepthook, threading.excepthook, sys.stderr)
        with carpeta_temporal() as d:
            try:
                arranque.registrar_fallas(d, registro)
                try:
                    raise ValueError('falla de prueba')
                except ValueError:
                    sys.excepthook(*sys.exc_info())
                hilo = threading.Thread(target=lambda: 1 / 0, name='hilo-de-prueba')
                hilo.start()
                hilo.join()
                self.assertTrue((d / arranque.ARCHIVO_FALLAS).exists())
            finally:
                import faulthandler
                faulthandler.disable()
                sys.excepthook, threading.excepthook, sys.stderr = anteriores
        textos = [str(c.args) for c in registro.critical.call_args_list]
        self.assertTrue(any('falla de prueba' in x for x in textos))
        self.assertTrue(any('hilo-de-prueba' in x and 'ZeroDivisionError' in x for x in textos))

    def test_descargar_el_registro(self):
        with carpeta_temporal() as d:
            s = servidor_de_prueba(d, puerto=7437)
            try:
                s.registro.info('línea de prueba del registro')
                (d / 'fallas.log').write_text('Fatal Python error: prueba' + chr(10), encoding='utf-8')
                status, cabeceras, cuerpo = Cliente(s).get('/api/registro')
                self.assertEqual(status, 200)
                texto = cuerpo.decode('utf-8')
                self.assertIn('===== servidor.log =====', texto)
                self.assertIn('línea de prueba del registro', texto)
                self.assertIn('Fatal Python error: prueba', texto)
                self.assertIn('attachment', cabeceras.get('Content-Disposition', ''))
            finally:
                s.cerrar()


if __name__ == '__main__':
    unittest.main()
