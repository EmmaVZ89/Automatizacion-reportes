import unittest

from app.reportes._comun import detectores
from app.reportes._comun.entradas import encabezados_xlsx, detectar, ordenar_tramos, aviso_recorte, resumen_archivo, ArchivoNoLegible
from app.reportes._comun.xlsx_escritura import escribir_libro
from tests.fixtures import xlsx_sintetico, xlsx_openpyxl, carpeta_temporal

SGA = ['CodigoEmpresa', 'CUIT', 'RazonSocial', 'NumeroFactura', 'Importe', 'GrupoConceptoFacturacion', 'FondoDeRiesgo', 'Subrecibo', 'NumeroComprobanteImputacion']
ERP = ['Saldo2', 'Cuenta de cliente', 'Factura', 'Número de recibo', 'Número de Recibo global', 'Asiento', 'Tipo de transacción']


class EntradasTests(unittest.TestCase):
    def test_encabezados_detecta_primera_fila_con_datos_y_filas_aprox(self):
        with carpeta_temporal() as d:
            # Con openpyxl: cadenas compartidas y <dimension>.
            ruta = xlsx_openpyxl(d / 'a.xlsx', [('Resumen', [['Título'], [None], ['Saldo', 'Importe', 'Otro']]), ('Datos', [SGA] + [['1', '2', '3', 'F', 1.5, 'Mora', 'FRG', '', ''] for _ in range(5)])])
            hojas = encabezados_xlsx(ruta)
            self.assertEqual([(h[0], h[1]) for h in hojas], [('Resumen', 3), ('Datos', 1)])
            self.assertEqual(hojas[1][2], SGA)
            self.assertEqual(hojas[1][3], 5)
            # Sintético: inlineStr, sin dimension.
            ruta2 = xlsx_sintetico(d / 'b.xlsx', [('X', [ERP, ['1', '2', '3', '', '', '', 'Cliente']])], con_referencias=False)
            hojas2 = encabezados_xlsx(ruta2)
            self.assertEqual(hojas2[0][2], ERP)
            self.assertIsNone(hojas2[0][3])

    def test_detectar_reconoce_tipos_y_rechaza_dos(self):
        with carpeta_temporal() as d:
            sga = xlsx_sintetico(d / 'sga.xlsx', [('Resumen', [['Saldo', 'Importe', 'x']]), ('CtaCte', [SGA])])
            erp = xlsx_sintetico(d / 'erp.xlsx', [('Sheet1', [ERP])])
            mixto = xlsx_sintetico(d / 'mixto.xlsx', [('A', [SGA]), ('B', [ERP])])
            self.assertEqual(detectar(sga, detectores.TODOS), 'historico_sga')
            self.assertEqual(detectar(erp, detectores.TODOS), 'erp_transacciones')
            self.assertEqual(detectores.reconocer(sga), 'historico_sga')
            with self.assertRaises(ValueError):
                detectar(mixto, detectores.TODOS)
            saldo = xlsx_sintetico(d / 's.xlsx', [('H', [['mainaccount', 'BUSINESSUNIT', 'Saldo de Cierre', 'x']])])
            self.assertEqual(detectores.reconocer(saldo), 'saldo_comprobacion')
            cheques = xlsx_sintetico(d / 'c.xlsx', [('H', [['IdCheque', 'Estado', 'Importe']])])
            self.assertEqual(detectores.reconocer(cheques), 'cheques_sga')
            teso = xlsx_sintetico(d / 't.xlsx', [('H', [['Id de Transacción', 'Estado', 'Pagado a']])])
            self.assertEqual(detectores.reconocer(teso), 'tesoreria_erp')
            listado = xlsx_sintetico(d / 'l.xlsx', [('H', [['Cliente', 'CUIT del cliente', 'Nro. de Factura']])])
            self.assertEqual(detectores.reconocer(listado), 'listado_facturas')
            nada = xlsx_sintetico(d / 'n.xlsx', [('H', [['a', 'b', 'c']])])
            self.assertIsNone(detectores.reconocer(nada))
            resumen = resumen_archivo(sga, detectores.TODOS)
            self.assertEqual((resumen['tipo'], resumen['hoja']), ('historico_sga', 'CtaCte'))

    def test_archivo_que_no_es_excel_da_error_llano(self):
        with carpeta_temporal() as d:
            (d / 'x.xlsx').write_bytes(b'no soy un zip')
            with self.assertRaises(ArchivoNoLegible):
                encabezados_xlsx(d / 'x.xlsx')

    def test_ordenar_tramos_natural(self):
        nombres = ['Reporte_10.xlsx', 'Reporte_2.xlsx', 'reporte_1.xlsx', 'Reporte (7).xlsx']
        self.assertEqual([p.name for p in ordenar_tramos(nombres)], ['Reporte (7).xlsx', 'reporte_1.xlsx', 'Reporte_2.xlsx', 'Reporte_10.xlsx'])

    def test_aviso_recorte(self):
        self.assertIsNone(aviso_recorte(None))
        self.assertIsNone(aviso_recorte(120))
        self.assertIsNone(aviso_recorte(452999))
        self.assertIn('450.000', aviso_recorte(450000))
        self.assertIn('454.123', aviso_recorte(454123))
        self.assertIsNone(aviso_recorte(455001))

    def test_escribir_libro_se_abre_con_openpyxl_y_conserva_tipos(self):
        import openpyxl
        with carpeta_temporal() as d:
            ruta = d / 'salida.xlsx'
            n = escribir_libro(ruta, [{'nombre': 'Datos', 'columnas': ['Texto', 'Importe', 'Id'], 'tipos': ['texto', 'numero', 'texto'],
                                       'filas': [['=SUMA(1)', '100.50', '0012'], ['b', -3, '0013']], 'nota': 'una nota', 'resaltadas': {(0, 1)}}])
            self.assertEqual(n, [2])
            libro = openpyxl.load_workbook(ruta)
            h = libro['Datos']
            self.assertEqual(h['A4'].value, 'Texto')
            self.assertEqual(h['A5'].value, '=SUMA(1)')
            self.assertEqual(h['A5'].data_type, 's')
            self.assertEqual(h['B5'].value, 100.5)
            self.assertEqual(h['C5'].value, '0012')
            self.assertEqual(h['B6'].value, -3)
            self.assertEqual(h['A2'].value, 'una nota')
            self.assertEqual(h['B5'].fill.fgColor.rgb, 'FFF4B183')
            self.assertNotEqual(h['B6'].fill.fgColor.rgb, 'FFF4B183')


if __name__ == '__main__':
    unittest.main()
