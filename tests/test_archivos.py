import hashlib
import os
import tracemalloc
import unittest
from urllib.parse import quote

from tests.cliente import Cliente, servidor_de_prueba
from tests.fixtures import carpeta_temporal, xlsx_sintetico

SGA = ['CodigoEmpresa', 'CUIT', 'RazonSocial', 'NumeroFactura', 'Importe', 'GrupoConceptoFacturacion', 'FondoDeRiesgo', 'Subrecibo', 'NumeroComprobanteImputacion']


class ArchivosTests(unittest.TestCase):
    def setUp(self):
        self._tmp = carpeta_temporal()
        self.d = self._tmp.__enter__()
        self.s = servidor_de_prueba(self.d, puerto=7400)
        self.c = Cliente(self.s)
        _, _, self.cierre = self.c.post('/api/cierres', {'periodo': '2026-10', 'corte': '2026-10-31'})
        self.base = f'/api/cierres/{self.cierre["id"]}/archivos'

    def tearDown(self):
        self.s.cerrar()
        self._tmp.__exit__(None, None, None)

    def _subir(self, nombre, datos, **kw):
        return self.c.post(self.base, crudo=datos, cabeceras={'X-Nombre': quote(nombre), 'Content-Type': 'application/octet-stream'}, **kw)

    def test_subida_grande_por_streaming_no_carga_en_memoria(self):
        grande = self.d / 'grande.bin'
        bloque = os.urandom(1024 * 1024)
        with grande.open('wb') as f:
            for _ in range(70):
                f.write(bloque)
        sha = hashlib.sha256()
        with grande.open('rb') as f:
            for b in iter(lambda: f.read(1024 * 1024), b''):
                sha.update(b)
        tracemalloc.start()
        import http.client
        con = http.client.HTTPConnection('127.0.0.1', self.s.puerto, timeout=120)
        with grande.open('rb') as f:
            con.request('POST', self.base, body=f, headers={'Cookie': f'reportes_token={self.s.token}', 'X-Nombre': 'grande.xlsx',
                                                            'Content-Length': str(grande.stat().st_size), 'Content-Type': 'application/octet-stream'})
            r = con.getresponse()
            cuerpo = r.read()
        actual, pico = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertEqual(r.status, 201, cuerpo)
        self.assertLess(pico, 25 * 1024 * 1024, f'pico de memoria {pico / 1e6:.1f} MB')
        import json
        archivo = json.loads(cuerpo)
        self.assertEqual(archivo['sha256'], sha.hexdigest())
        self.assertEqual(archivo['bytes'], 70 * 1024 * 1024)
        self.assertIsNone(archivo['tipo'])
        self.assertTrue(archivo['error'])

    def test_mas_de_limite_413_sin_leer(self):
        self.c.patch('/api/configuracion', {'limiteMB': 10})
        peticion = (f'POST {self.base} HTTP/1.1\r\nHost: 127.0.0.1:{self.s.puerto}\r\nCookie: reportes_token={self.s.token}\r\n'
                    f'X-Nombre: grande.xlsx\r\nContent-Length: {20 * 1024 * 1024}\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
        respuesta = self.c.socket_crudo(peticion + b'x' * 1000)
        self.assertIn(b' 413 ', respuesta.split(b'\r\n', 1)[0])
        self.assertIn('supera los 10 MB'.encode('utf-8'), respuesta)
        self.assertEqual(self.c.get(self.base)[2], [])

    def test_extension_invalida_400_y_vacio_400(self):
        status, _, cuerpo = self._subir('datos.csv', b'a;b')
        self.assertEqual(status, 400)
        self.assertIn('.xlsx', cuerpo['error'])
        status, _, cuerpo = self._subir('datos.xlsx', b'')
        self.assertEqual(status, 400)

    def test_subida_reconoce_tipo_y_dedup(self):
        ruta = xlsx_sintetico(self.d / 'sga.xlsx', [('CtaCte', [SGA, ['1', '2', '3', 'F', '1', 'Mora', 'FRG', '', '']])])
        status, _, a = self._subir('Reporte (7).xlsx', ruta.read_bytes())
        self.assertEqual(status, 201)
        self.assertEqual((a['tipo'], a['hoja'], a['nombre']), ('historico_sga', 'CtaCte', 'Reporte (7).xlsx'))
        status, _, b = self._subir('otro.xlsx', ruta.read_bytes())
        self.assertEqual(b['id'], a['id'])
        self.assertEqual(len(self.c.get(self.base)[2]), 1)
        status, _, _ = self.c.delete(f'{self.base}/{a["id"]}')
        self.assertEqual(status, 200)
        self.assertEqual(self.c.get(self.base)[2], [])

    def test_desde_carpeta_copia_y_detecta_tipo(self):
        carpeta = self.d / 'bajadas'
        carpeta.mkdir()
        xlsx_sintetico(carpeta / 'Saldo de comprobación_1.xlsx', [('H', [['MainAccount', 'BusinessUnit', 'Saldo de cierre']])])
        xlsx_sintetico(carpeta / '~$temporal.xlsx', [('H', [['a', 'b', 'c']])])
        (carpeta / 'nota.txt').write_text('x')
        status, _, lista = self.c.post(f'{self.base}/carpeta', {'ruta': str(carpeta)})
        self.assertEqual(status, 200)
        self.assertEqual([x['nombre'] for x in lista['archivos']], ['Saldo de comprobación_1.xlsx'])
        status, _, cuerpo = self.c.post(f'{self.base}/carpeta', {'ruta': str(self.d / 'no-existe')})
        self.assertEqual(status, 400)
        status, _, agregados = self.c.post(f'{self.base}/desde-carpeta', {'ruta': str(carpeta), 'nombres': ['Saldo de comprobación_1.xlsx']})
        self.assertEqual(status, 201)
        self.assertEqual(agregados[0]['tipo'], 'saldo_comprobacion')
        self.assertTrue((carpeta / 'Saldo de comprobación_1.xlsx').exists())
        status, _, cuerpo = self.c.post(f'{self.base}/desde-carpeta', {'ruta': str(carpeta), 'nombres': ['../../x.xlsx']})
        self.assertEqual(status, 400)

    def test_nombre_con_ruta_se_sanea(self):
        ruta = xlsx_sintetico(self.d / 'a.xlsx', [('H', [['a', 'b', 'c']])])
        status, _, a = self._subir('C:\\Users\\alguien\\..\\..\\evil<>.xlsx', ruta.read_bytes())
        self.assertEqual(status, 201)
        self.assertEqual(a['nombre'], 'evil-.xlsx')
        self.assertTrue(str(self.d / 'cierres') in a['ruta'])


if __name__ == '__main__':
    unittest.main()
