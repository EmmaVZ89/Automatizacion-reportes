import unittest

from tests.fixtures import xlsx_sintetico, xlsx_openpyxl, carpeta_temporal


class Fixtures(unittest.TestCase):
    def test_xlsx_sintetico_se_lee_con_openpyxl(self):
        import openpyxl
        with carpeta_temporal() as d:
            ruta = xlsx_sintetico(d / 'a.xlsx', [('Resumen', [['Saldo', 'Importe']]), ('Datos', [['A', 'B'], ['1', 'x'], ['', 'y']])])
            libro = openpyxl.load_workbook(ruta, read_only=True)
            self.assertEqual(libro.sheetnames, ['Resumen', 'Datos'])
            filas = [list(r) for r in libro['Datos'].iter_rows(values_only=True)]
            self.assertEqual(filas, [['A', 'B'], ['1', 'x'], [None, 'y']])

    def test_xlsx_openpyxl_conserva_tipos(self):
        import openpyxl
        from datetime import datetime
        with carpeta_temporal() as d:
            ruta = xlsx_openpyxl(d / 'b.xlsx', [('Hoja', [['n', 'f'], [1.5, datetime(2026, 10, 31)]])])
            libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
            fila = next(libro['Hoja'].iter_rows(min_row=2, values_only=True))
            self.assertEqual(fila, (1.5, datetime(2026, 10, 31)))


if __name__ == '__main__':
    unittest.main()
