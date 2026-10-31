import sys
import unittest

from app import catalogo
from tests.fixtures import carpeta_temporal


class CatalogoTests(unittest.TestCase):
    def setUp(self):
        catalogo.cargar()

    def test_catalogo_carga_cinco_reportes_con_campos_obligatorios(self):
        self.assertEqual(sorted(catalogo.REPORTES), ['conciliacion_general', 'control_cheques', 'control_mora', 'controles_sga', 'descarga_facturas'])
        for d in catalogo.REPORTES.values():
            for campo in catalogo.CAMPOS_OBLIGATORIOS:
                self.assertIn(campo, d)
            for s in d['salidas']:
                self.assertTrue(s['clave'])
        pub = catalogo.descripcion_publica('control_mora', probar=False)
        self.assertNotIn('detectar', pub['entradas'][0])
        self.assertTrue(pub['disponible'])

    def test_ambito_icono_y_orden(self):
        sprite = (catalogo.RAIZ / 'app' / 'web' / 'index.html').read_text(encoding='utf-8')
        ambitos = {c: catalogo.descripcion_publica(c, probar=False)['ambito'] for c in catalogo.REPORTES}
        self.assertEqual(ambitos.pop('descarga_facturas'), 'herramienta')
        self.assertEqual(set(ambitos.values()), {'cierre'})
        self.assertEqual(list(catalogo.REPORTES)[0], 'conciliacion_general')
        for c in catalogo.REPORTES:
            icono = catalogo.descripcion_publica(c, probar=False)['icono']
            self.assertIn(f'id="i-{icono}"', sprite, c)
        for d in catalogo.REPORTES.values():
            principales = [s['tabla'] for s in d['salidas'] if s.get('principal')]
            self.assertLessEqual(len(principales), 1, d['codigo'])
            self.assertTrue(any(s.get('revisable', True) for s in d['salidas']) or principales, d['codigo'])

    def test_disponibilidad_sin_venv_es_false_con_motivo_llano(self):
        with carpeta_temporal() as d:
            r = catalogo.disponibilidad('descarga_facturas', raiz=d)
            self.assertFalse(r['disponible'])
            self.assertIn('Instalar descarga de facturas', r['motivo'])
            self.assertNotIn('venv', r['motivo'].lower())
            self.assertTrue(catalogo.disponibilidad('controles_sga', raiz=d)['disponible'])

    def test_interprete_usa_el_python_actual_o_el_venv(self):
        self.assertEqual(catalogo.interprete('control_mora')[0], sys.executable)
        self.assertTrue(catalogo.interprete('control_mora')[2].endswith('ejecutar.py'))
        self.assertIn('.venv', catalogo.interprete('descarga_facturas')[0])

    def test_parametros_default_toma_configuracion_y_cierre(self):
        conf = {'reportes': {'control_mora': {'parametros': {'cuentas': ['1'], 'fondo': 'Otro'}}}}
        v = catalogo.parametros_default('control_mora', conf)
        self.assertEqual(v['cuentas'], ['1'])
        self.assertEqual(v['fondo'], 'Otro')
        self.assertEqual(v['grupo'], 'Mora')
        c = catalogo.parametros_default('controles_sga', {'reportes': {'controles_sga': {'parametros': {'corte': '2000-01-01'}}}}, cierre={'corte': '2026-10-31'})
        self.assertEqual(c['corte'], '2026-10-31')  # no_persistir: la del cierre manda
        self.assertEqual(c['tolerancia'], '0.02')

    def test_validar_parametros(self):
        with self.assertRaises(ValueError):
            catalogo.validar_parametros('controles_sga', {'corte': '31/10/2026'})
        with self.assertRaises(ValueError):
            catalogo.validar_parametros('controles_sga', {'corte': '2026-02-30'})
        with self.assertRaises(ValueError):
            catalogo.validar_parametros('conciliacion_general', {'corte': '2026-10-31'})  # falta alcance
        with self.assertRaises(ValueError):
            catalogo.validar_parametros('conciliacion_general', {'alcance': 'todo'})
        v = catalogo.validar_parametros('controles_sga', {'corte': '2026-10-31', 'salidas_a_generar': 'Saldo_MORA;Comprobantes_Abiertos', 'tolerancia': '0,05',
                                                          'reglas': [{'concepto': ' X ', 'datos': 'APORTE', 'datos_confirmados': True}]})
        self.assertEqual(v['salidas_a_generar'], ['Saldo_MORA', 'Comprobantes_Abiertos'])
        self.assertEqual(v['tolerancia'], '0.05')
        self.assertEqual(v['reglas'], [{'concepto': 'X', 'datos': 'APORTE', 'datos_confirmados': True, 'agrupador': '', 'agrupador_confirmado': ''}])
        self.assertEqual(v['documentos_excluidos'], ['CH-20190722105522839'])
        with self.assertRaises(ValueError):
            catalogo.validar_parametros('controles_sga', {'corte': '2026-10-31', 'salidas_a_generar': ['Inventado']})
        m = catalogo.validar_parametros('control_mora', {'cuentas': []})
        self.assertEqual(m['cuentas'], [])
        self.assertEqual(m['unidad_negocio'], 'FRG')

    def test_registrar_para_pruebas(self):
        catalogo.registrar_para_pruebas('falso', {'codigo': 'falso', 'nombre': 'Falso', 'descripcion': 'x', 'entradas': [], 'parametros': [], 'salidas': [], 'requiere': 'stdlib'}, [sys.executable, 'x.py'])
        self.assertEqual(catalogo.interprete('falso'), [sys.executable, 'x.py'])
        self.assertTrue(catalogo.disponibilidad('falso')['disponible'])


if __name__ == '__main__':
    unittest.main()
