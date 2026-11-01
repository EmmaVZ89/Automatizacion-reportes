"""Acceso directo "Reportes de cierre": ícono, PowerShell que lo escribe y cuándo se crea o se corrige. PowerShell se
reemplaza por un doble: las pruebas nunca tocan el Escritorio real."""
import json
import struct
import unittest
from pathlib import Path
from unittest import mock

from app import acceso_directo as acceso
from app import arranque
from tests.cliente import Cliente, servidor_de_prueba
from tests.fixtures import carpeta_temporal


class PowerShellFalso:
    """Crea los .lnk como archivos vacíos; el Escritorio es una carpeta de la prueba."""
    def __init__(self, escritorio):
        self.escritorio = Path(escritorio)
        self.scripts = []

    def __call__(self, script):
        self.scripts.append(script)
        inicio = script.index('@(') + 2
        lista = script[inicio:script.index(')) {', inicio) + 1]
        rutas = []
        for parte in lista.split("', "):
            if 'GetFolderPath' in parte:
                rutas.append(str(self.escritorio / acceso.NOMBRE))
            elif parte.strip():
                rutas.append(parte.strip(" '()").replace("''", "'"))
        for r in rutas:
            Path(r).write_bytes(b'')
        return '\n'.join(rutas) + '\n'


class IconoTests(unittest.TestCase):
    def test_ico_con_un_png_por_tamano(self):
        datos = acceso.icono_ico()
        reservado, tipo, cantidad = struct.unpack('<HHH', datos[:6])
        self.assertEqual((reservado, tipo, cantidad), (0, 1, len(acceso.TAMANOS)))
        for i, lado in enumerate(acceso.TAMANOS):
            ancho, alto, _, _, planos, bits, largo, desde = struct.unpack('<BBBBHHII', datos[6 + 16 * i:22 + 16 * i])
            self.assertEqual((ancho, alto, planos, bits), (lado % 256, lado % 256, 1, 32))
            self.assertEqual(datos[desde:desde + 8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(struct.unpack('>II', datos[desde + 16:desde + 24]), (lado, lado))

    def test_dibujo_del_logo(self):
        lado = 32
        px = acceso.pixeles(lado)
        en = lambda x, y: tuple(px[(y * lado + x) * 4:(y * lado + x) * 4 + 4])
        self.assertEqual(en(0, 31)[3], 0)  # esquina: transparente
        self.assertEqual(en(4, 27), (*acceso.HOJA, 255))  # cuerpo de la hoja
        self.assertEqual(en(14, 23), (*acceso.BLANCO, 255))  # vértice de la tilde


class AccesoDirectoTests(unittest.TestCase):
    def test_script_abre_iniciar_vbs_con_wscript_y_escapa_comillas(self):
        script = acceso.script_powershell(r"D:\Herramientas\Lo de Ana's", r'C:\datos\icono.ico', [r"D:\Herramientas\Lo de Ana's\Reportes de cierre.lnk", acceso.ESCRITORIO])
        self.assertIn("wscript.exe'", script)
        self.assertIn(r"""'"D:\Herramientas\Lo de Ana''s\app\iniciar.vbs"'""", script)
        self.assertIn("[Environment]::GetFolderPath('Desktop')", script)
        self.assertIn(r"'C:\datos\icono.ico,0'", script)

    def test_primera_vez_carpeta_y_escritorio_despues_nada(self):
        with carpeta_temporal() as d:
            raiz, datos, escritorio = d / 'herramienta', d / 'datos', d / 'escritorio'
            for c in (raiz, datos, escritorio):
                c.mkdir()
            ps = PowerShellFalso(escritorio)
            creados = acceso.asegurar(raiz, datos, ejecutar=ps)
            self.assertEqual(creados, [str(raiz / acceso.NOMBRE), str(escritorio / acceso.NOMBRE)])
            self.assertTrue((datos / acceso.ARCHIVO_ICONO).exists())
            self.assertEqual(json.loads((datos / acceso.ARCHIVO_ESTADO).read_text(encoding='utf-8')),
                             {'raiz': str(raiz), 'escritorio': str(escritorio / acceso.NOMBRE)})
            self.assertEqual(acceso.asegurar(raiz, datos, ejecutar=ps), [])
            self.assertEqual(len(ps.scripts), 1)
            # Si se borra el del Escritorio no vuelve solo; el de la carpeta sí.
            (escritorio / acceso.NOMBRE).unlink()
            (raiz / acceso.NOMBRE).unlink()
            self.assertEqual(acceso.asegurar(raiz, datos, ejecutar=ps), [str(raiz / acceso.NOMBRE)])
            self.assertFalse((escritorio / acceso.NOMBRE).exists())
            # Desde Configuración se vuelve a crear.
            self.assertEqual(acceso.crear_en_escritorio(raiz, datos, ejecutar=ps), [str(raiz / acceso.NOMBRE), str(escritorio / acceso.NOMBRE)])

    def test_si_la_herramienta_se_movio_se_corrigen_los_dos(self):
        with carpeta_temporal() as d:
            vieja, nueva, datos, escritorio = d / 'vieja', d / 'nueva', d / 'datos', d / 'escritorio'
            for c in (vieja, nueva, datos, escritorio):
                c.mkdir()
            ps = PowerShellFalso(escritorio)
            acceso.asegurar(vieja, datos, ejecutar=ps)
            creados = acceso.asegurar(nueva, datos, ejecutar=ps)
            self.assertEqual(creados, [str(nueva / acceso.NOMBRE), str(escritorio / acceso.NOMBRE)])
            self.assertIn(str(nueva / 'app' / 'iniciar.vbs'), ps.scripts[-1])
            self.assertEqual(json.loads((datos / acceso.ARCHIVO_ESTADO).read_text(encoding='utf-8'))['raiz'], str(nueva))

    def test_un_error_de_powershell_no_impide_abrir_y_queda_en_el_registro(self):
        registro = mock.Mock()
        with carpeta_temporal() as d, mock.patch.object(acceso, '_powershell', side_effect=OSError('sin COM')), mock.patch.object(acceso.os, 'name', 'nt'):
            acceso.asegurar_en_hilo(d, d, registro).join(10)
            self.assertFalse((d / acceso.ARCHIVO_ESTADO).exists())  # se reintenta la próxima vez
        registro.warning.assert_called_once()

    def test_el_arranque_lo_pide_solo_si_se_lo_pasan(self):
        with carpeta_temporal() as d:
            pedidos = []
            s = arranque.main(['--datos', str(d), '--puerto', '7432', '--sin-navegador'], abrir=lambda u: None, bloquear=False, inactividad_segundos=0,
                              acceso=lambda raiz, datos, registro: pedidos.append((raiz, datos)))
            try:
                self.assertEqual(pedidos, [(arranque.RAIZ, d)])
            finally:
                s.cerrar()

    def test_boton_de_configuracion(self):
        with carpeta_temporal() as d:
            s = servidor_de_prueba(d, puerto=7392)
            try:
                c = Cliente(s)
                with mock.patch.object(acceso, 'crear_en_escritorio', return_value=['a.lnk', 'b.lnk']) as crear:
                    status, _, r = c.post('/api/acceso-directo', {})
                self.assertEqual((status, r), (200, {'rutas': ['a.lnk', 'b.lnk']}))
                crear.assert_called_once_with(s.raiz, s.dir_datos)
                with mock.patch.object(acceso, 'crear_en_escritorio', side_effect=OSError('sin COM')):
                    status, _, r = c.post('/api/acceso-directo', {})
                self.assertEqual(status, 500)
                self.assertIn('No se pudo crear el acceso directo', r['error'])
            finally:
                s.cerrar()


if __name__ == '__main__':
    unittest.main()
