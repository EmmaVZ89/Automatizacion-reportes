import unittest

from tests.cliente import Cliente, servidor_de_prueba
from tests.fixtures import carpeta_temporal


class ServidorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = carpeta_temporal()
        self.d = self._tmp.__enter__()
        self.s = servidor_de_prueba(self.d, puerto=7390)
        self.c = Cliente(self.s)

    def tearDown(self):
        self.s.cerrar()
        self._tmp.__exit__(None, None, None)

    def test_sin_token_api_403_y_pagina_403(self):
        status, _, cuerpo = self.c.get('/api/estado', sin_token=True)
        self.assertEqual(status, 403)
        self.assertIn('acceso directo', cuerpo['error'])
        status, _, cuerpo = self.c.get('/', sin_token=True)
        self.assertEqual(status, 403)
        self.assertIn('acceso directo', cuerpo.decode('utf-8'))
        status, _, _ = self.c.get('/api/estado', sin_token=True, cabeceras={'Cookie': 'reportes_token=otro'})
        self.assertEqual(status, 403)

    def test_query_t_setea_cookie_y_redirige(self):
        status, cab, _ = self.c.get(f'/?t={self.s.token}', sin_token=True)
        self.assertEqual(status, 303)
        self.assertEqual(cab['Location'], '/')
        self.assertIn('HttpOnly', cab['Set-Cookie'])
        self.assertIn('SameSite=Strict', cab['Set-Cookie'])

    def test_cabeceras_csp_nosniff_en_pagina_y_no_store_en_api(self):
        status, cab, cuerpo = self.c.get('/')
        self.assertEqual(status, 200)
        self.assertIn("default-src 'self'", cab['Content-Security-Policy'])
        self.assertEqual(cab['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(cab['Referrer-Policy'], 'no-referrer')
        self.assertIn(b'Reportes de cierre', cuerpo)
        status, cab, _ = self.c.get('/api/estado')
        self.assertEqual(status, 200)
        self.assertEqual(cab['Cache-Control'], 'no-store')
        status, cab, _ = self.c.get('/estilos.css')
        self.assertEqual(status, 200)
        self.assertIn('text/css', cab['Content-Type'])

    def test_post_con_origin_ajeno_403(self):
        status, _, cuerpo = self.c.post('/api/cierres', {'periodo': '2026-10', 'corte': '2026-10-31'}, origin='http://otro.local')
        self.assertEqual(status, 403)
        status, _, _ = self.c.post('/api/cierres', {'periodo': '2026-10', 'corte': '2026-10-31'}, origin=f'http://127.0.0.1:{self.s.puerto}')
        self.assertEqual(status, 201)

    def test_estado_lista_cinco_reportes(self):
        status, _, estado = self.c.get('/api/estado')
        self.assertEqual(status, 200)
        codigos = {r['codigo'] for r in estado['reportes']}
        self.assertTrue({'conciliacion_general', 'controles_sga', 'control_mora', 'control_cheques', 'descarga_facturas'} <= codigos)
        facturas = next(r for r in estado['reportes'] if r['codigo'] == 'descarga_facturas')
        self.assertIn('disponible', facturas)
        self.assertEqual(estado['trabajosActivos'], 0)
        self.assertNotIn('token', estado)
        self.assertIs(estado['reiniciar'], False)
        self.assertEqual(estado['origenes'], [])

    def test_crud_cierres_y_ejecuciones(self):
        status, _, c = self.c.post('/api/cierres', {'periodo': '2026-10', 'corte': '2026-10-31', 'nombre': 'Octubre'})
        self.assertEqual(status, 201)
        self.assertEqual(c['reportes'], {})
        status, _, cuerpo = self.c.post('/api/cierres', {'periodo': '2026-10', 'corte': '2026-10-31'})
        self.assertEqual(status, 400)
        self.assertIn('Ya existe', cuerpo['error'])
        status, _, lista = self.c.get('/api/cierres')
        self.assertEqual([x['periodo'] for x in lista], ['2026-10'])
        status, _, c2 = self.c.patch(f'/api/cierres/{c["id"]}', {'nombre': 'Octubre 2026', 'corte': '2026-10-30'})
        self.assertEqual((c2['nombre'], c2['corte']), ('Octubre 2026', '2026-10-30'))
        status, _, e = self.c.post('/api/ejecuciones', {'cierre': c['id'], 'reporte': 'control_mora'})
        self.assertEqual(status, 201)
        self.assertEqual((e['version'], e['estado']), (1, 'borrador'))
        status, _, cuerpo = self.c.post('/api/ejecuciones', {'cierre': c['id'], 'reporte': 'inventado'})
        self.assertEqual(status, 404)
        status, _, e2 = self.c.patch(f'/api/ejecuciones/{e["id"]}', {'parametros': {'cuentas': ['1']}})
        self.assertEqual(e2['parametros'], {'cuentas': ['1']})
        self.assertIn('trabajo', e2)
        status, _, detalle = self.c.get(f'/api/cierres/{c["id"]}')
        self.assertEqual(detalle['reportes']['control_mora']['versiones'], 1)
        status, _, lista = self.c.get(f'/api/ejecuciones?cierre={c["id"]}&reporte=control_mora')
        self.assertEqual(len(lista), 1)
        status, _, _ = self.c.delete(f'/api/ejecuciones/{e["id"]}')
        self.assertEqual(status, 200)
        status, _, _ = self.c.get(f'/api/ejecuciones/{e["id"]}')
        self.assertEqual(status, 404)
        status, _, _ = self.c.delete(f'/api/cierres/{c["id"]}')
        self.assertEqual(status, 200)
        self.assertEqual(self.c.get('/api/cierres')[2], [])

    def test_espacio_de_facturas_aparte_de_los_cierres(self):
        status, _, h1 = self.c.get('/api/herramientas/descarga_facturas')
        self.assertEqual(status, 200)
        self.assertEqual(h1['herramienta'], 'descarga_facturas')
        self.assertEqual(self.c.get('/api/herramientas/descarga_facturas')[2]['id'], h1['id'])
        self.assertEqual(self.c.get('/api/cierres')[2], [])
        status, _, cuerpo = self.c.get('/api/herramientas/control_mora')
        self.assertEqual(status, 404)
        self.assertIn('cierre mensual', cuerpo['error'])

    def test_post_que_no_usa_el_cuerpo_no_ensucia_la_conexion(self):
        import http.client
        _, _, c = self.c.post('/api/cierres', {'periodo': '2026-10', 'corte': '2026-10-31'})
        _, _, e = self.c.post('/api/ejecuciones', {'cierre': c['id'], 'reporte': 'conciliacion_general'})
        con = http.client.HTTPConnection('127.0.0.1', self.s.puerto, timeout=30)
        cab = {'Cookie': f'reportes_token={self.s.token}', 'Content-Type': 'application/json'}
        try:
            for ruta in (f'/api/ejecuciones/{e["id"]}/traer-revision-anterior', f'/api/ejecuciones/{e["id"]}/origen/preparar', '/api/trabajos/999/cancelar'):
                con.request('POST', ruta, body=b'{}', headers=cab)
                con.getresponse().read()
                con.request('GET', '/api/estado', headers=cab)
                r = con.getresponse()
                r.read()
                self.assertEqual(r.status, 200, ruta)
        finally:
            con.close()

    def test_reiniciar_arranca_otra_con_el_mismo_token_y_puerto(self):
        import threading
        from unittest import mock
        from app.servidor import comando_reinicio
        cerrado = threading.Event()
        with mock.patch('subprocess.Popen') as popen, mock.patch.object(self.s, 'cerrar', side_effect=cerrado.set):
            status, _, r = self.c.post('/api/reiniciar', {})
            self.assertTrue(cerrado.wait(5), 'no soltó el puerto')
        self.assertEqual((status, r), (200, {'ok': True}))
        comando = popen.call_args[0][0]
        self.assertEqual(comando, comando_reinicio(self.s.dir_datos, self.s.token, self.s.puerto))
        self.assertEqual(comando[-2:], ['--reinicio', self.s.token])

    def test_error_inesperado_no_filtra_traza(self):
        status, _, cuerpo = self.c.get('/api/pruebas/error')
        self.assertEqual(status, 500)
        self.assertNotIn('Traceback', cuerpo['error'])
        self.assertNotIn('RuntimeError', cuerpo['error'])
        self.assertIn('registro', cuerpo['error'])
        registro = (self.d / 'servidor.log').read_text(encoding='utf-8')
        self.assertIn('error provocado para la prueba', registro)

    def test_estatico_fuera_de_web_404_y_cuerpo_invalido_400(self):
        for ruta in ('/../app/servidor.py', '/app/servidor.py', '/.gitignore', '/index.html.bak', '/servidor.py'):
            status, _, _ = self.c.get(ruta)
            self.assertEqual(status, 404, ruta)
        status, _, cuerpo = self.c.post('/api/cierres', crudo=b'[1,2]', cabeceras={'Content-Type': 'application/json'})
        self.assertEqual(status, 400)
        status, _, cuerpo = self.c.post('/api/cierres', crudo=b'{no', cabeceras={'Content-Type': 'application/json'})
        self.assertEqual(status, 400)
        status, _, _ = self.c.get('/api/no-existe')
        self.assertEqual(status, 404)
        status, _, _ = self.c.pedir('PUT', '/api/estado')
        self.assertIn(status, (405, 501))


if __name__ == '__main__':
    unittest.main()
