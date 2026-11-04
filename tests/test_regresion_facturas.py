"""herramientas/regresion_facturas.py: lectura de los PDF contra el legado y descarga simulada, con PDF sintéticos."""
import contextlib
import io
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'herramientas'))
from tests.fixtures import carpeta_temporal  # noqa: E402
from tests.test_descarga_facturas import HAY_PDFPLUMBER, _factura, _factura_b, _factura_dos_hojas  # noqa: E402
import regresion_facturas  # noqa: E402

SIN_ROTULO = {'hojas': 1, 'subtotal': False, 'total': False, 'en_otra_hoja': False}
SOLO_TOTAL = {'hojas': 1, 'subtotal': False, 'total': True, 'en_otra_hoja': False}
CON_SUBTOTAL = {'hojas': 1, 'subtotal': True, 'total': True, 'en_otra_hoja': False}
D = date(2026, 10, 15)


class Explicar(unittest.TestCase):
    def test_conceptos_iguales(self):
        self.assertEqual(regresion_facturas.explicar((D, ['X']), (D, ['X']), CON_SUBTOTAL), ('conceptos iguales', True))

    def test_fecha_distinta_no_se_explica(self):
        self.assertFalse(regresion_facturas.explicar((D, ['X']), (date(2026, 10, 16), ['X']), CON_SUBTOTAL)[1])

    def test_factura_b_el_legado_se_lleva_lo_que_sigue_al_item(self):
        texto, explicada = regresion_facturas.explicar((D, ['X ***DOS***']), (D, ['X']), SOLO_TOTAL)
        self.assertTrue(explicada)
        self.assertIn('TOTAL:', texto)

    def test_sin_rotulo_va_a_para_revisar(self):
        texto, explicada = regresion_facturas.explicar((D, ['X ***DOS***']), (D, []), SIN_ROTULO)
        self.assertTrue(explicada)
        self.assertIn('Para revisar', texto)

    def test_concepto_perdido_con_rotulo_no_se_explica(self):
        """Es lo que hizo la 2026.11.03 con las facturas de varias hojas: el legado lo leía y el nuevo no."""
        self.assertEqual(regresion_facturas.explicar((D, ['X']), (D, []), CON_SUBTOTAL), ('CONCEPTOS DISTINTOS', False))

    def test_concepto_recortado_con_subtotal_no_se_explica(self):
        self.assertFalse(regresion_facturas.explicar((D, ['X ***DOS***']), (D, ['X']), CON_SUBTOTAL)[1])


@unittest.skipUnless(HAY_PDFPLUMBER, 'pdfplumber no está instalado en este intérprete (se corre dentro del .venv de facturas o con py -3.12)')
class Forma(unittest.TestCase):
    def test_factura_a(self):
        f = regresion_facturas.forma(_factura('FC-A000000000001', '12/10/2026', ['Servicio mensual']))
        self.assertEqual(f, {'hojas': 1, 'subtotal': True, 'total': False, 'en_otra_hoja': False})

    def test_factura_b(self):
        self.assertEqual(regresion_facturas.forma(_factura_b(['TOTAL:'])), SOLO_TOTAL)

    def test_rotulos_en_la_hoja_siguiente(self):
        f = regresion_facturas.forma(_factura_dos_hojas(['SubTotal:', 'TOTAL:']))
        self.assertEqual(f, {'hojas': 2, 'subtotal': True, 'total': True, 'en_otra_hoja': True})


@unittest.skipUnless(HAY_PDFPLUMBER, 'pdfplumber no está instalado en este intérprete (se corre dentro del .venv de facturas o con py -3.12)')
class Main(unittest.TestCase):
    def _correr(self, d, pdfs, *extra):
        carpeta = d / 'pdfs'
        carpeta.mkdir()
        for nombre, datos in pdfs.items():
            (carpeta / (nombre + '.pdf')).write_bytes(datos)
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = regresion_facturas.main(['--pdfs', str(carpeta), '--salida', str(d / 'salida'), *extra])
        return codigo, salida.getvalue()

    def test_a_b_y_dos_hojas_sin_diferencias_no_explicadas(self):
        pdfs = {'FC-A000000000001': _factura('FC-A000000000001', '12/10/2026', ['Servicio mensual']),
                'FC-B000000000001': _factura_b(['TOTAL:']),
                'FC-A000000000009': _factura_dos_hojas(['SubTotal:', 'TOTAL:'])}
        with carpeta_temporal() as d:
            codigo, texto = self._correr(d, pdfs)
            destino = d / 'salida' / 'destino'
            self.assertEqual(codigo, 0, texto)
            self.assertIn('SIN DIFERENCIAS NO EXPLICADAS', texto)
            self.assertIn('rótulo en la hoja siguiente', texto)
            self.assertEqual(texto.count('Copiada'), 3, texto)
            self.assertEqual(sorted(p.name for p in destino.rglob('*.pdf')), sorted(n + '.pdf' for n in pdfs))
            self.assertNotIn('Servicio mensual', texto)  # los conceptos, sólo con --mostrar-conceptos

    def test_sin_rotulo_queda_en_para_revisar_y_se_explica(self):
        with carpeta_temporal() as d:
            codigo, texto = self._correr(d, {'FC-B000000000001': _factura_b([])})
            self.assertEqual(codigo, 0, texto)
            self.assertIn('REVISAR: concepto no identificado', texto)
            self.assertIn('Para revisar', texto)

    def test_mostrar_conceptos(self):
        with carpeta_temporal() as d:
            texto = self._correr(d, {'FC-A000000000001': _factura('FC-A000000000001', '12/10/2026', ['Servicio mensual'])},
                                 '--mostrar-conceptos')[1]
            self.assertIn('Servicio mensual', texto)

    def test_sale_con_1_si_el_motor_no_confirma_el_numero(self):
        """El nombre del archivo tiene que ser el número de la factura, como en la biblioteca."""
        with carpeta_temporal() as d:
            codigo, texto = self._correr(d, {'FC-A000000000007': _factura('FC-A000000000099', '12/10/2026', ['Servicio mensual'])})
            self.assertEqual(codigo, 1, texto)
            self.assertIn('ERROR', texto)


if __name__ == '__main__':
    unittest.main()
