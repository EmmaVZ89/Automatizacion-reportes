import io
import json
import sys
import unittest
from unittest import mock

from app.reportes._comun import protocolo


class ProtocoloTests(unittest.TestCase):
    def _capturar(self, activo, fn):
        salida = io.StringIO()
        with mock.patch.object(protocolo, 'ACTIVO', activo), mock.patch.object(sys, 'stdout', salida):
            fn()
        return salida.getvalue()

    def test_eventos_son_lineas_json(self):
        texto = self._capturar(True, lambda: (protocolo.log('hola'), protocolo.paso('p'), protocolo.progreso(2, 'x'),
                                              protocolo.tabla('t', 3), protocolo.resumen({'a': 1}), protocolo.error('e')))
        lineas = [json.loads(l) for l in texto.splitlines()]
        self.assertEqual([l['t'] for l in lineas], ['log', 'paso', 'progreso', 'tabla', 'resumen', 'error'])
        self.assertEqual(lineas[2]['v'], 1.0)
        self.assertEqual(lineas[3], {'t': 'tabla', 'tabla': 't', 'filas': 3})

    def test_sin_server_log_es_texto_plano_y_esperar_usa_input(self):
        texto = self._capturar(False, lambda: protocolo.log('hola'))
        self.assertEqual(texto, 'hola\n')
        with mock.patch.object(protocolo, 'ACTIVO', False), mock.patch('builtins.input', return_value='') as inp:
            protocolo.esperar('login', 'Iniciá sesión')
            inp.assert_called_once()

    def test_esperar_lee_stdin_hasta_continuar_con_el_mismo_id(self):
        entrada = io.StringIO('basura\n{"t":"continuar","id":"otro"}\n{"t":"continuar","id":"login"}\n')
        salida = io.StringIO()
        with mock.patch.object(protocolo, 'ACTIVO', True), mock.patch.object(sys, 'stdin', entrada), mock.patch.object(sys, 'stdout', salida):
            protocolo.esperar('login', 'msg', 'Seguir')
        ev = json.loads(salida.getvalue().splitlines()[0])
        self.assertEqual(ev, {'t': 'esperar', 'id': 'login', 'm': 'msg', 'boton': 'Seguir'})

    def test_esperar_cancelar_o_fin_de_entrada_lanza(self):
        with mock.patch.object(protocolo, 'ACTIVO', True), mock.patch.object(sys, 'stdout', io.StringIO()):
            with mock.patch.object(sys, 'stdin', io.StringIO('{"t":"cancelar"}\n')):
                with self.assertRaises(protocolo.Cancelado):
                    protocolo.esperar('x', 'm')
            with mock.patch.object(sys, 'stdin', io.StringIO('')):
                with self.assertRaises(protocolo.Cancelado):
                    protocolo.esperar('x', 'm')


if __name__ == '__main__':
    unittest.main()
