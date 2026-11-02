import hashlib
import io
import unittest
from decimal import Decimal
from unittest import mock

import openpyxl

from app import exportar
from app.dominio import Dominio
from app.reportes._comun import protocolo
from app.reportes._comun.salidas import Volcador
from tests.cliente import Cliente, servidor_de_prueba
from tests.fixtures import carpeta_temporal

COLS_GENERAL = ['Tipo', 'Cliente', 'Comprobante', 'CUIT', 'Razon social', 'Saldo SGA', 'Saldo ERP', 'Diferencia SGA menos ERP', 'Resultado',
                'Filas SGA', 'Filas ERP', 'Origen SGA (primeras 5)', 'Origen ERP (primeras 5)', 'Estado revision', 'Observaciones', 'Fondo', 'Detalle identificacion']


def ejecucion_con_tablas(dom, cierre_id, reporte, tablas):
    e = dom.crear_ejecucion(cierre_id, reporte)
    with mock.patch.object(protocolo, 'ACTIVO', False), Volcador(dom.rutas(e['id'])['sqlite']) as v:
        for nombre, columnas, filas, clave, marcas in tablas:
            v.tabla(nombre, columnas, filas, clave=clave, marcas=marcas)
    dom.actualizar_estado(e['id'], 'ok', salidas=[{k: v for k, v in s.items() if k != 'tipos'} for s in dom.tablas(e['id']).listar()], resumen={'x': 1})
    return dom.obtener_ejecucion(e['id'])


def hoja(datos, indice=0):
    libro = openpyxl.load_workbook(io.BytesIO(datos))
    h = libro.worksheets[indice]
    filas = [list(r) for r in h.iter_rows(min_row=4, values_only=True)]
    return filas[0], [f for f in filas[1:] if any(v is not None for v in f)], h


class ExportarTests(unittest.TestCase):
    def test_exportar_tabla_agrega_dos_columnas_y_excluye_omitidas(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, reconocer=lambda r: {})
            c = dom.crear_cierre('2026-10', '2026-10-31')
            e = ejecucion_con_tablas(dom, c['id'], 'control_cheques', [('revisar', ['Motivo', 'ID SGA', 'Importe SGA'], [['Falta ID', '1', '10,50'], ['Diferencia', '2', '3,00'], ['Cancelado', '3', '1,00']], ['ID SGA', 'Motivo'], [(1, 'Importe SGA')])])
            t = dom.tablas(e['id'])
            t.marcar('revisar', [0], 'revisada', obs='ok')
            t.marcar('revisar', [2], 'omitida', obs='proveedor')
            datos, nombre = exportar.exportar_tabla(dom, e, 'revisar', incluir_omitidas=True)
            self.assertEqual(nombre, 'Cheques_para_revisar.csv')
            enc, filas, h = hoja(datos)
            self.assertEqual(enc, ['Motivo', 'ID SGA', 'Importe SGA', 'Estado revisión', 'Observaciones'])
            self.assertEqual([f[3] for f in filas], ['Revisada', None, 'Omitida'])
            self.assertEqual(filas[2][4], 'proveedor')
            self.assertEqual(h['C6'].fill.fgColor.rgb, 'FFF4B183')
            datos, _ = exportar.exportar_tabla(dom, e, 'revisar', incluir_omitidas=False)
            self.assertEqual(len(hoja(datos)[1]), 2)
            with self.assertRaises(ValueError):
                exportar.exportar_tabla(dom, e, 'inexistente')

    def test_exportar_libro_conciliacion_completa_estado_y_observaciones(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, reconocer=lambda r: {})
            c = dom.crear_cierre('2026-10', '2026-10-31')
            fila = lambda tipo, cli, comp, sga: [tipo, cli, comp, '20', 'Socio', sga, '1.00', '0.00', 'COINCIDE', '1', '1', 'a:1', 'b:1', '', '', 'Fondo', '']
            e = ejecucion_con_tablas(dom, c['id'], 'conciliacion_general', [
                ('resumen', ['Control', 'Saldo SGA', 'Saldo ERP', 'Diferencia', 'Resultado / cantidad', 'Detalle'], [['TOTAL', '1', '1', '0', 'x', 'y']], ['Control'], []),
                ('general', COLS_GENERAL, [fila('FACTURA', '1', 'F1', '1.00'), fila('OP-X', '2', 'SR-1', '2.00')], ['Tipo', 'Cliente', 'Comprobante'], [])])
            dom.tablas(e['id']).marcar('general', [1], 'omitida', obs='histórica')
            datos, nombre = exportar.exportar_libro(dom, e, 'Conciliacion_general.xlsx')
            self.assertEqual(nombre, 'Conciliacion_general.xlsx')
            libro = openpyxl.load_workbook(io.BytesIO(datos))
            self.assertEqual(libro.sheetnames, ['Resumen', 'Conciliación general'])
            enc, filas, h = hoja(datos, 1)
            self.assertEqual(enc, COLS_GENERAL)  # no se agregan columnas: se completan las existentes
            self.assertEqual(filas[1][13], 'Omitida')
            self.assertEqual(filas[1][14], 'histórica')
            self.assertEqual(filas[0][5], 1.0)  # importe numérico
            with self.assertRaises(ValueError):
                exportar.exportar_libro(dom, e, 'Otro.xlsx')

    def test_exportar_e_importar_cierre_round_trip(self):
        with carpeta_temporal() as d:
            dom = Dominio(d / 'a', reconocer=lambda r: {'tipo': 'x'})
            c = dom.crear_cierre('2026-10', '2026-10-31', 'Octubre')
            dom.agregar_archivo(c['id'], 'a.xlsx', bytes_iter=iter([b'123']))
            e1 = ejecucion_con_tablas(dom, c['id'], 'control_cheques', [('revisar', ['Motivo', 'ID SGA'], [['Falta ID', '1'], ['Diferencia', '2']], ['ID SGA', 'Motivo'], [])])
            dom.tablas(e1['id']).marcar('revisar', [1], 'omitida', obs='vista')
            dom.guardar_triage(e1['id'])
            dom.marcar_final(e1['id'])
            e2 = ejecucion_con_tablas(dom, c['id'], 'control_mora', [('resultado', ['Concepto', 'Valor'], [['Estado', 'SIN DIFERENCIAS']], ['Concepto'], [])])
            borrador = dom.crear_ejecucion(c['id'], 'controles_sga')
            datos = exportar.exportar_cierre(dom, c['id'])
            self.assertNotIn(b'"ruta"', datos[:0])  # sanity
            otro = Dominio(d / 'b', reconocer=lambda r: {})
            c2 = exportar.importar_cierre(otro, datos)
            self.assertEqual((c2['periodo'], c2['nombre'], c2['importado']), ('2026-10', 'Octubre', True))
            self.assertEqual(c2['archivos'][0]['nombre'], 'a.xlsx')
            self.assertEqual(c2['archivos'][0]['ruta'], '')
            ejecuciones = {e['reporte']: e for e in otro.listar_ejecuciones(c2['id'])}
            self.assertEqual(set(ejecuciones), {'control_cheques', 'control_mora'})
            self.assertTrue(ejecuciones['control_cheques']['final'])
            t = otro.tablas(ejecuciones['control_cheques']['id'])
            r = t.consultar('revisar')
            self.assertEqual(r['columnas'], ['Motivo', 'ID SGA'])
            self.assertEqual([f['_estado'] for f in r['filas']], ['pendiente', 'omitida'])
            self.assertEqual(r['filas'][1]['_obs'], 'vista')
            self.assertEqual(ejecuciones['control_cheques']['revision']['omitidas'], 1)
            with self.assertRaises(ValueError):
                exportar.importar_cierre(otro, b'no es zip')
            with self.assertRaises(ValueError):
                exportar.importar_cierre(otro, datos)  # período repetido

    def test_descarga_de_salida_original_intacta_y_cantidad_acotada(self):
        with carpeta_temporal() as d:
            s = servidor_de_prueba(d, puerto=7420)
            try:
                c = Cliente(s)
                _, _, cierre = c.post('/api/cierres', {'periodo': '2026-10', 'corte': '2026-10-31'})
                e = ejecucion_con_tablas(s.dominio, cierre['id'], 'control_cheques', [('revisar', ['Motivo', 'ID SGA'], [[str(i), str(i)] for i in range(700)], ['ID SGA', 'Motivo'], [])])
                salidas = s.dominio.rutas(e['id'])['salidas']
                salidas.mkdir()
                contenido = 'Motivo;ID\nx;1\n'.encode('utf-8-sig')
                (salidas / 'Cheques_para_revisar.csv').write_bytes(contenido)
                status, cab, cuerpo = c.get(f'/api/ejecuciones/{e["id"]}/archivos/Cheques_para_revisar.csv')
                self.assertEqual(status, 200)
                self.assertEqual(hashlib.sha256(cuerpo).hexdigest(), hashlib.sha256(contenido).hexdigest())
                self.assertIn('attachment', cab['Content-Disposition'])
                status, _, _ = c.get(f'/api/ejecuciones/{e["id"]}/archivos/../parametros.json')
                self.assertEqual(status, 404)
                status, _, r = c.get(f'/api/ejecuciones/{e["id"]}/tablas/revisar?cantidad=9999')
                self.assertEqual(len(r['filas']), 500)
                self.assertEqual(r['total'], 700)
                status, cab, datos = c.get(f'/api/ejecuciones/{e["id"]}/exportar?tabla=revisar')
                self.assertEqual(status, 200)
                self.assertIn('trabajado', cab['Content-Disposition'])
                self.assertEqual(len(hoja(datos)[1]), 700)
                status, cab, datos = c.get(f'/api/cierres/{cierre["id"]}/exportar')
                self.assertEqual(status, 200)
                self.assertEqual(datos[:2], b'PK')
            finally:
                s.cerrar()


class HojasDeContinuacionTests(unittest.TestCase):
    """Una tabla que no entra en una hoja de Excel sigue en otras, con el mismo encabezado (se prueba con el límite
    achicado), y un cierre exportado así se vuelve a importar entero."""

    def test_tabla_que_no_entra_en_una_hoja_sigue_en_otra(self):
        from app.reportes._comun import xlsx_escritura
        with carpeta_temporal() as d, mock.patch.object(xlsx_escritura, 'MAX_FILAS_EXCEL', 7):  # 3 filas de datos por hoja
            ruta = d / 'libro.xlsx'
            escritas = xlsx_escritura.escribir_libro(ruta, [
                {'nombre': 'Resumen', 'columnas': ['Control'], 'filas': [['Total']]},
                {'nombre': 'Revisar', 'columnas': ['ID', 'Importe'], 'tipos': ['texto', 'numero'], 'nota': 'Todas las filas.',
                 'filas': [[str(i), str(i * 10)] for i in range(8)], 'resaltadas': {(4, 1)}}])
            self.assertEqual(escritas, [1, 8])
            libro = openpyxl.load_workbook(ruta)
            self.assertEqual(libro.sheetnames, ['Resumen', 'Revisar', 'Revisar (2)', 'Revisar (3)'])
            partes = [libro[n] for n in libro.sheetnames[1:]]
            self.assertTrue(all([c.value for c in h[4]] == ['ID', 'Importe'] for h in partes))
            self.assertEqual([[r[0] for r in h.iter_rows(min_row=5, values_only=True)] for h in partes], [['0', '1', '2'], ['3', '4', '5'], ['6', '7']])
            self.assertEqual(partes[1]['A2'].value, 'Sigue de la hoja «Revisar»: en una hoja de Excel entran 3 filas. Todas las filas.')
            self.assertEqual(partes[1]['B6'].fill.fgColor.rgb, 'FFF4B183')  # la fila 4 de la tabla, resaltada, cae en la segunda hoja
            self.assertEqual(partes[0]['A4'].value, 'ID')

    def test_nombre_de_hoja_respeta_los_31_caracteres(self):
        from app.reportes._comun.xlsx_escritura import nombre_de_hoja
        self.assertEqual(nombre_de_hoja('Conciliación general', 2), 'Conciliación general (2)')
        self.assertEqual(nombre_de_hoja('x' * 40), 'x' * 31)
        self.assertEqual(nombre_de_hoja('x' * 40, 12), 'x' * 26 + ' (12)')

    def test_cierre_con_una_tabla_en_varias_hojas_se_importa_entero(self):
        from app.reportes._comun import xlsx_escritura
        with carpeta_temporal() as d, mock.patch.object(xlsx_escritura, 'MAX_FILAS_EXCEL', 6):  # 2 filas de datos por hoja
            dom = Dominio(d / 'a', reconocer=lambda r: {'tipo': 'x'})
            c = dom.crear_cierre('2026-10', '2026-10-31', 'Octubre')
            filas = [['Diferencia', str(i)] for i in range(5)]
            e = ejecucion_con_tablas(dom, c['id'], 'control_cheques', [('revisar', ['Motivo', 'ID SGA'], filas, ['ID SGA', 'Motivo'], [])])
            dom.tablas(e['id']).marcar('revisar', [3], 'omitida', obs='en la segunda hoja')
            dom.guardar_triage(e['id'])
            datos = exportar.exportar_cierre(dom, c['id'])
            otro = Dominio(d / 'b', reconocer=lambda r: {})
            c2 = exportar.importar_cierre(otro, datos)
            e2 = otro.listar_ejecuciones(c2['id'])[0]
            r = otro.tablas(e2['id']).consultar('revisar')
            self.assertEqual([f['valores'][1] for f in r['filas']], ['0', '1', '2', '3', '4'])
            self.assertEqual([(f['_estado'], f['_obs']) for f in r['filas']][3], ('omitida', 'en la segunda hoja'))


if __name__ == '__main__':
    unittest.main()
