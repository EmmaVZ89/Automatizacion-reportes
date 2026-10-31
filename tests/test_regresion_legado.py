import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'herramientas'))
from regresion_legado import comparar_carpetas, clasificar  # noqa: E402
from tests.fixtures import carpeta_temporal, xlsx_openpyxl, xlsx_sintetico


class RegresionTests(unittest.TestCase):
    def test_comparar_carpetas_detecta_celda_distinta_y_normaliza_sellos(self):
        with carpeta_temporal() as d:
            a, b = d / 'a', d / 'b' / 'sub'
            a.mkdir()
            b.mkdir(parents=True)
            xlsx_openpyxl(a / 'Libro.xlsx', [('Hoja', [['x', 'y'], [1, 'a'], [2, 'b']])])
            xlsx_openpyxl(b / 'Libro.xlsx', [('Hoja', [['x', 'y'], [1, 'a'], [2, 'c']])])
            (a / 'salida.csv').write_text('a;b\n1;20261031_120000\n', encoding='utf-8-sig')
            (b / 'salida.csv').write_text('a;b\n1;20261101_090909_123456\n', encoding='utf-8-sig')
            (a / 'r.json').write_text(json.dumps({'total': 1, 'archivo': 'x.xlsx', 'fuentes': [{'archivo': 'a', 'n': 1}]}), encoding='utf-8')
            (b / 'r.json').write_text(json.dumps({'total': 1, 'archivo': 'y.xlsx', 'fuentes': [{'archivo': 'b', 'n': 1}]}), encoding='utf-8')
            (a / 'Resumen.txt').write_text('SGA: C:\\ruta\\a.xlsx\nTotal: 3\n', encoding='utf-8')
            (b / 'Resumen.txt').write_text('SGA: otra\nTotal: 3\n', encoding='utf-8')
            dif = comparar_carpetas(a, d / 'b', 'control_cheques')
            self.assertEqual(len(dif), 2, dif)
            self.assertTrue(any('Libro.xlsx' in x and 'fila 3 columna 2' in x for x in dif))
            self.assertTrue(any('r.json' in x for x in dif))
            dif_sga = comparar_carpetas(a, d / 'b', 'controles_sga')
            self.assertEqual(len(dif_sga), 2, dif_sga)  # Libro.xlsx y Resumen.txt (las líneas SGA: sólo se ignoran en cheques)
            (b / 'Libro.xlsx').unlink()
            xlsx_openpyxl(b / 'Libro.xlsx', [('Hoja', [['x', 'y'], [1, 'a'], [2, 'b']])])
            restantes = comparar_carpetas(a, d / 'b', 'controles_sga')
            self.assertEqual(len(restantes), 1, restantes)  # sólo queda Resumen.txt

    def test_clasificar_reconoce_tipos(self):
        with carpeta_temporal() as d:
            xlsx_sintetico(d / 'c.xlsx', [('H', [['IdCheque', 'Estado', 'Importe']])])
            xlsx_sintetico(d / 't.xlsx', [('H', [['Id de Transacción', 'Estado', 'Pagado a']])])
            (d / 'nota.txt').write_text('x')
            tipos = clasificar(d)
            self.assertEqual({k: [p.name for p in v] for k, v in tipos.items()}, {'cheques_sga': ['c.xlsx'], 'tesoreria_erp': ['t.xlsx']})


if __name__ == '__main__':
    unittest.main()
