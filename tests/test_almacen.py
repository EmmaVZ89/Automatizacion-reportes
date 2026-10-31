import json
import unittest

from app.almacen import Almacen, AlmacenCorrupto, escribir_json_atomico, leer_json
from tests.fixtures import carpeta_temporal


class Reloj:
    def __init__(self, t=1_700_000_000):
        self.t = t

    def __call__(self):
        return self.t


class AlmacenTests(unittest.TestCase):
    def test_guardar_escribe_tmp_y_renombra(self):
        with carpeta_temporal() as d:
            a = Almacen(d / 'cierres.json')
            a.entradas.append({'id': 'c1'})
            a.guardar()
            self.assertFalse((d / 'cierres.json.tmp').exists())
            self.assertEqual(json.loads((d / 'cierres.json').read_text(encoding='utf-8'))['entradas'], [{'id': 'c1'}])

    def test_json_invalido_pasa_a_solo_lectura_y_guardar_lanza(self):
        with carpeta_temporal() as d:
            (d / 'x.json').write_text('{no es json', encoding='utf-8')
            a = Almacen(d / 'x.json')
            self.assertTrue(a.solo_lectura)
            self.assertEqual(a.entradas, [])
            with self.assertRaises(AlmacenCorrupto):
                a.guardar()
            self.assertEqual((d / 'x.json').read_text(encoding='utf-8'), '{no es json')

    def test_backup_fechado_en_subcarpeta_backup_y_poda_a_max(self):
        with carpeta_temporal() as d:
            reloj = Reloj()
            a = Almacen(d / 'e.json', ahora=reloj, max_backups=2, minutos_entre_backups=1)
            a.guardar()  # primer archivo: sin backup
            for i in range(4):
                reloj.t += 120
                a.entradas.append(i)
                a.guardar()
            backups = sorted(p.name for p in (d / 'backup').iterdir())
            self.assertEqual(len(backups), 2)
            self.assertTrue(all(b.startswith('e-') and b.endswith('.json') for b in backups))

    def test_dos_guardados_en_menos_de_n_minutos_un_solo_backup(self):
        with carpeta_temporal() as d:
            reloj = Reloj()
            a = Almacen(d / 'e.json', ahora=reloj, minutos_entre_backups=10)
            a.guardar()
            reloj.t += 60
            a.guardar()
            reloj.t += 60
            a.guardar()
            self.assertEqual(len(list((d / 'backup').iterdir())), 1)

    def test_leer_json_default_si_no_existe_o_invalido(self):
        with carpeta_temporal() as d:
            self.assertEqual(leer_json(d / 'no.json', {'a': 1}), {'a': 1})
            escribir_json_atomico(d / 'si.json', {'b': 2})
            self.assertEqual(leer_json(d / 'si.json'), {'b': 2})


if __name__ == '__main__':
    unittest.main()
