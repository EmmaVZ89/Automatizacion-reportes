import unittest

from app.seguridad import (cookie_de_token, peticion_autorizada, token_de_peticion, nombre_seguro,
                           ruta_confinada, nuevo_token, CABECERAS_BASE)
from tests.fixtures import carpeta_temporal


class Cabeceras(dict):
    def get(self, k, d=None):
        for clave, valor in self.items():
            if clave.lower() == k.lower():
                return valor
        return d


class SeguridadTests(unittest.TestCase):
    def test_cookie_httponly_samesite_strict(self):
        c = cookie_de_token('abc')
        self.assertIn('reportes_token=abc', c)
        self.assertIn('HttpOnly', c)
        self.assertIn('SameSite=Strict', c)
        self.assertIn('Path=/', c)

    def test_token_desde_query_o_cookie(self):
        self.assertEqual(token_de_peticion(Cabeceras(), 't=xyz'), 'xyz')
        self.assertEqual(token_de_peticion(Cabeceras({'Cookie': 'otra=1; reportes_token=qrs'}), ''), 'qrs')
        self.assertIsNone(token_de_peticion(Cabeceras(), ''))

    def test_peticion_que_modifica_con_origin_ajeno_se_rechaza(self):
        tok = nuevo_token()
        h = Cabeceras({'Cookie': f'reportes_token={tok}', 'Origin': 'http://malicioso.local'})
        ok, motivo = peticion_autorizada(h, '', tok, modifica=True, host='127.0.0.1:7310')
        self.assertFalse(ok)
        self.assertTrue(motivo)
        h = Cabeceras({'Cookie': f'reportes_token={tok}', 'Origin': 'http://127.0.0.1:7310'})
        self.assertTrue(peticion_autorizada(h, '', tok, modifica=True, host='127.0.0.1:7310')[0])
        h = Cabeceras({'Cookie': f'reportes_token={tok}', 'Sec-Fetch-Site': 'cross-site'})
        self.assertFalse(peticion_autorizada(h, '', tok, modifica=True, host='127.0.0.1:7310')[0])

    def test_peticion_get_sin_origin_se_acepta_y_sin_token_no(self):
        tok = nuevo_token()
        self.assertTrue(peticion_autorizada(Cabeceras({'Cookie': f'reportes_token={tok}'}), '', tok, False, '127.0.0.1:7310')[0])
        self.assertFalse(peticion_autorizada(Cabeceras(), '', tok, False, '127.0.0.1:7310')[0])
        self.assertFalse(peticion_autorizada(Cabeceras(), 't=otro', tok, False, '127.0.0.1:7310')[0])

    def test_nombre_seguro_quita_carpetas_y_caracteres(self):
        self.assertEqual(nombre_seguro('C:\\Users\\x\\Reporte (7).XLSX'), 'Reporte (7).xlsx')
        self.assertEqual(nombre_seguro('../../etc/passwd'), 'passwd')
        self.assertEqual(nombre_seguro('a<b>:c?.xlsx'), 'a-b-c-.xlsx')
        self.assertEqual(nombre_seguro(''), 'archivo')
        self.assertLessEqual(len(nombre_seguro('x' * 300 + '.xlsx')), 120)
        self.assertTrue(nombre_seguro('x' * 300 + '.xlsx').endswith('.xlsx'))
        self.assertEqual(nombre_seguro('Saldo de comprobación_639.xlsx'), 'Saldo de comprobación_639.xlsx')

    def test_ruta_confinada_rechaza_punto_punto_y_unidad(self):
        with carpeta_temporal() as d:
            self.assertEqual(ruta_confinada(d, 'salidas/a.csv'), (d / 'salidas' / 'a.csv').resolve())
            for mala in ('../x', 'C:/Windows', '/etc', 'a/../../b', ''):
                with self.assertRaises(ValueError):
                    ruta_confinada(d, mala)

    def test_cabeceras_base(self):
        self.assertIn("default-src 'self'", CABECERAS_BASE['Content-Security-Policy'])
        self.assertEqual(CABECERAS_BASE['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(CABECERAS_BASE['Referrer-Policy'], 'no-referrer')


if __name__ == '__main__':
    unittest.main()
