import time
import unittest

from app.dominio import Dominio
from tests.cliente import Cliente, servidor_de_prueba
from tests.fixtures import carpeta_temporal


def esperar_hasta(cond, timeout=20):
    fin = time.time() + timeout
    while time.time() < fin:
        if cond():
            return True
        time.sleep(0.05)
    return False


class EjecutarTests(unittest.TestCase):
    def setUp(self):
        self._tmp = carpeta_temporal()
        self.d = self._tmp.__enter__()
        self.s = servidor_de_prueba(self.d, puerto=7410, args_motor=('--esperar',))
        self.c = Cliente(self.s)
        _, _, self.cierre = self.c.post('/api/cierres', {'periodo': '2026-10', 'corte': '2026-10-31'})

    def tearDown(self):
        self.s.cerrar()
        self._tmp.__exit__(None, None, None)

    def _estado(self, eid):
        return self.c.get(f'/api/ejecuciones/{eid}')[2]

    def _correr_falso(self):
        _, _, e = self.c.post('/api/ejecuciones', {'cierre': self.cierre['id'], 'reporte': 'falso'})
        status, _, r = self.c.post(f'/api/ejecuciones/{e["id"]}/ejecutar', {'entradas': {}, 'parametros': {'nota': 'hola'}})
        self.assertEqual(status, 202, r)
        self.assertTrue(esperar_hasta(lambda: self._estado(e['id'])['estado'] == 'esperando'))
        tid = self._estado(e['id'])['trabajoId']
        status, _, _ = self.c.post(f'/api/trabajos/{tid}/continuar', {'espera': 'login'})
        self.assertEqual(status, 200)
        self.assertTrue(esperar_hasta(lambda: self._estado(e['id'])['estado'] == 'ok'))
        return self._estado(e['id'])

    def test_ejecutar_llega_a_esperando_continuar_y_ok_con_tablas(self):
        e = self._correr_falso()
        self.assertEqual(e['trabajo']['estado'], 'ok')
        self.assertEqual(e['resumen']['estado'], 'SIN DIFERENCIAS')
        self.assertEqual([s['tabla'] for s in e['salidas']], ['resultado'])
        self.assertEqual(e['salidas'][0]['filas'], 3)
        self.assertEqual(e['revision'], {'pendientes': 3, 'revisadas': 0, 'omitidas': 0})
        self.assertEqual(e['parametros']['nota'], 'hola')
        self.assertEqual(e['parametros']['sesion_chrome'], str(self.d / 'sesion_chrome'))
        status, _, tablas = self.c.get(f'/api/ejecuciones/{e["id"]}/tablas')
        self.assertEqual(tablas['tablas'][0]['titulo'], 'Resultado')
        status, _, archivos = self.c.get(f'/api/ejecuciones/{e["id"]}/archivos')
        self.assertEqual([a['ruta'] for a in archivos], ['Resultado.csv'])
        status, _, registro = self.c.get(f'/api/ejecuciones/{e["id"]}/registro')
        self.assertIn('Reconocí 3 archivos', registro['registro'])
        status, _, cuerpo = self.c.post(f'/api/ejecuciones/{e["id"]}/ejecutar', {})
        self.assertEqual(status, 409)

    def test_entradas_incompletas_400_llano(self):
        _, _, e = self.c.post('/api/ejecuciones', {'cierre': self.cierre['id'], 'reporte': 'control_mora'})
        status, _, cuerpo = self.c.post(f'/api/ejecuciones/{e["id"]}/ejecutar', {'entradas': {}, 'parametros': {}})
        self.assertEqual(status, 400)
        self.assertIn('Falta el archivo', cuerpo['error'])
        self.assertIn('Saldo de comprobación', cuerpo['error'])
        _, _, e2 = self.c.post('/api/ejecuciones', {'cierre': self.cierre['id'], 'reporte': 'controles_sga'})
        status, _, cuerpo = self.c.post(f'/api/ejecuciones/{e2["id"]}/ejecutar', {'entradas': {}, 'parametros': {'corte': 'ayer'}})
        self.assertEqual(status, 400)

    def test_sse_recibe_evento_trabajo_y_cancelar(self):
        _, _, e = self.c.post('/api/ejecuciones', {'cierre': self.cierre['id'], 'reporte': 'falso'})
        import threading
        recibidos = []
        hilo = threading.Thread(target=lambda: recibidos.extend(self.c.sse(1, filtro=lambda t, d: t == 'trabajo')), daemon=True)
        hilo.start()
        time.sleep(0.3)
        status, _, r = self.c.post(f'/api/ejecuciones/{e["id"]}/ejecutar', {})
        self.assertEqual(status, 202)
        hilo.join(20)
        self.assertEqual(recibidos[0][0], 'trabajo')
        self.assertEqual(recibidos[0][1]['ejecucionId'], e['id'])
        self.assertTrue(esperar_hasta(lambda: self._estado(e['id'])['estado'] == 'esperando'))
        tid = self._estado(e['id'])['trabajoId']
        status, _, _ = self.c.post(f'/api/trabajos/{tid}/cancelar', {})
        self.assertEqual(status, 200)
        self.assertTrue(esperar_hasta(lambda: self._estado(e['id'])['estado'] == 'cancelado'))
        status, _, _ = self.c.post(f'/api/trabajos/{tid}/cancelar', {})
        self.assertEqual(status, 409)

    def test_pestana_cerrada_y_reabierta_recupera_lineas(self):
        _, _, e = self.c.post('/api/ejecuciones', {'cierre': self.cierre['id'], 'reporte': 'falso'})
        self.c.post(f'/api/ejecuciones/{e["id"]}/ejecutar', {})
        self.assertTrue(esperar_hasta(lambda: self._estado(e['id'])['estado'] == 'esperando'))
        # "Otra pestaña": consulta fría del trabajo por id, sin haber escuchado eventos.
        tid = self._estado(e['id'])['trabajoId']
        status, _, t = self.c.get(f'/api/trabajos/{tid}')
        self.assertEqual(t['estado'], 'esperando')
        self.assertIn('Reconocí 3 archivos', t['lineas'])
        self.assertEqual(t['espera']['id'], 'login')
        self.c.post(f'/api/trabajos/{tid}/continuar', {'espera': 'login'})
        self.assertTrue(esperar_hasta(lambda: self._estado(e['id'])['estado'] == 'ok'))

    def test_segunda_version_traslada_revision(self):
        e1 = self._correr_falso()
        status, _, r = self.c.post(f'/api/ejecuciones/{e1["id"]}/triage', {'tabla': 'resultado', 'filas': [0, 1], 'estado': 'omitida', 'obs': 'ya vista'})
        self.assertEqual(status, 200)
        self.assertEqual(r['marcadas'], 2)
        self.assertEqual(r['revision'], {'pendientes': 1, 'revisadas': 0, 'omitidas': 2})
        e2 = self._correr_falso()
        self.assertEqual(e2['version'], 2)
        self.assertEqual(e2['traslado'], {'aplicadas': 2, 'sin_destino': 0, 'desde': 1})
        status, _, t = self.c.get(f'/api/ejecuciones/{e2["id"]}/tablas/resultado?estado=omitida')
        self.assertEqual(t['total'], 2)
        self.assertEqual(t['filas'][0]['_obs'], 'ya vista')
        self.assertEqual(t['filas'][0]['_origen'], 'version')
        status, _, _ = self.c.patch(f'/api/ejecuciones/{e2["id"]}', {'final': True})
        self.assertEqual(status, 200)
        status, _, cuerpo = self.c.delete(f'/api/ejecuciones/{e2["id"]}')
        self.assertEqual(status, 409)
        status, _, _ = self.c.delete(f'/api/ejecuciones/{e2["id"]}?forzar=1')
        self.assertEqual(status, 200)

    def test_arranque_marca_interrumpidas(self):
        self.s.cerrar()
        dom = Dominio(self.d)
        e = dom.crear_ejecucion(self.cierre['id'], 'falso')
        dom.actualizar_estado(e['id'], 'corriendo')
        self.s = servidor_de_prueba(self.d, puerto=7410)
        self.c = Cliente(self.s)
        estado = self._estado(e['id'])
        self.assertEqual(estado['estado'], 'error')
        self.assertIn('cerró la herramienta', estado['error'])


if __name__ == '__main__':
    unittest.main()
