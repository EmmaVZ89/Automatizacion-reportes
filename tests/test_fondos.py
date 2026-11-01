"""Conciliación por fondo de riesgo (pedido del 01/11/2026): Fondo de Riesgo General y FERF Prov. Santa Fe.

El fondo es un desplegable en Opciones y una variante del reporte: cada fondo tiene sus versiones, su resultado final y
su traslado de marcas. El ERP no trae el fondo: se reconoce por sus asientos ("SaFe…" Santa Fe, "Ventas-…" General).
Los ERP de Santa Fe traen movimientos de tipo Liquidación, que se cruzan por su factura como los de tipo Cliente."""
import csv
import json
import unittest
from pathlib import Path
from urllib.parse import quote

from app import catalogo
from app.dominio import Dominio
from app.reportes._comun import detectores
from app.reportes._comun.entradas import valores_columna
from tests.cliente import Cliente, servidor_de_prueba
from tests.fixtures import carpeta_temporal, xlsx_sintetico
from tests.test_conciliacion_general import E, S, correr

GENERAL = detectores.FONDO_GENERAL
SANTA_FE = detectores.FONDO_SANTA_FE
SGA = [S,
       [GENERAL, '1', 'FC-A1', '100', 'Otros', '', '', '201', 'Uno'],
       [SANTA_FE, '7', 'FC-Y7', '50', 'Aportes', '', '', '207', 'Siete'],
       [SANTA_FE, '8', 'FC-Y8', '30', 'Aportes', '', '', '208', 'Ocho']]
ERP_GENERAL = [E, ['100', '1', 'FC-A1', '', '', 'Ventas-001', 'Cliente']]
ERP_SANTA_FE = [E,
                ['20', '7', 'FC-Y7', '', '', 'SaFe-001', 'Cliente'],
                ['30', '7', 'FC-Y7', '', '', 'SaFe-002', 'Liquidación'],  # se suma a su factura
                ['30', '8', 'FC-Y8', '', '', 'SaFe-003', 'Cliente']]


def resultados(salida):
    with (Path(salida) / 'Respaldo_tecnico' / 'Conciliacion_general.csv').open(encoding='utf-8-sig', newline='') as f:
        return {r['Comprobante']: r for r in csv.DictReader(f, delimiter=';') if r['Tipo'] != 'CONTROL'}


class MotorPorFondoTests(unittest.TestCase):
    def test_santa_fe_toma_sus_filas_de_sga_y_suma_las_liquidaciones(self):
        with carpeta_temporal() as d:
            entradas = {'sga': [xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA)])], 'erp': [xlsx_sintetico(d / 'erp.xlsx', [('Datos', ERP_SANTA_FE)])]}
            resumen = correr(entradas, d / 'salida', alcance='completo', fondo=SANTA_FE)
            filas = resultados(d / 'salida')
            self.assertEqual(set(filas), {'FC-Y7', 'FC-Y8'})  # la factura del Fondo General no entra
            self.assertEqual((filas['FC-Y7']['Saldo SGA'], filas['FC-Y7']['Saldo ERP'], filas['FC-Y7']['Resultado']), ('50.00', '50.00', 'COINCIDE'))
            self.assertEqual(filas['FC-Y7']['Fondo'], SANTA_FE)
            self.assertEqual(resumen['fondo'], SANTA_FE)

    def test_el_general_sigue_igual(self):
        with carpeta_temporal() as d:
            entradas = {'sga': [xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA)])], 'erp': [xlsx_sintetico(d / 'erp.xlsx', [('Datos', ERP_GENERAL)])]}
            correr(entradas, d / 'salida', alcance='completo', fondo=GENERAL)
            self.assertEqual(set(resultados(d / 'salida')), {'FC-A1'})

    def test_el_erp_de_otro_fondo_o_mezclado_corta_con_un_mensaje_claro(self):
        with carpeta_temporal() as d:
            sga = xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA)])
            casos = [(GENERAL, ERP_SANTA_FE, 'son de FERF Prov. Santa Fe y esta corrida es de Fondo de Riesgo General'),
                     (SANTA_FE, ERP_GENERAL, 'son de Fondo de Riesgo General y esta corrida es de FERF Prov. Santa Fe'),
                     (SANTA_FE, ERP_SANTA_FE + ERP_GENERAL[1:], 'mezclan los dos fondos')]
            for i, (fondo, erp, mensaje) in enumerate(casos):
                with self.subTest(fondo=fondo):
                    entradas = {'sga': [sga], 'erp': [xlsx_sintetico(d / f'erp{i}.xlsx', [('Datos', erp)])]}
                    with self.assertRaisesRegex(ValueError, mensaje):
                        correr(entradas, d / f'salida{i}', alcance='completo', fondo=fondo)

    def test_sin_filas_del_fondo_en_sga_corta(self):
        with carpeta_temporal() as d:
            entradas = {'sga': [xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA[:2])])], 'erp': [xlsx_sintetico(d / 'erp.xlsx', [('Datos', ERP_SANTA_FE)])]}
            with self.assertRaisesRegex(ValueError, 'no tiene movimientos de FERF Prov. Santa Fe'):
                correr(entradas, d / 'salida', alcance='completo', fondo=SANTA_FE)


class ReconocimientoTests(unittest.TestCase):
    def test_fondo_por_asientos(self):
        self.assertEqual(detectores.fondo_por_asientos(['SaFe-1', 'MIG-2', 'CV-3']), SANTA_FE)
        self.assertEqual(detectores.fondo_por_asientos(['Ventas-1', 'CV-3', '']), GENERAL)
        self.assertEqual(detectores.fondo_por_asientos(['SaFe-1', 'Ventas-1']), detectores.MEZCLA_DE_FONDOS)
        self.assertIsNone(detectores.fondo_por_asientos(['CV-1', 'PC-2']))

    def test_al_agregar_un_erp_se_guarda_su_fondo(self):
        with carpeta_temporal() as d:
            dom = Dominio(d / 'datos')
            c = dom.crear_cierre('2026-10', '2026-10-31')
            sf = dom.agregar_archivo(c['id'], 'erp_sf.xlsx', origen=xlsx_sintetico(d / 'erp_sf.xlsx', [('Sheet1', ERP_SANTA_FE)]))
            general = dom.agregar_archivo(c['id'], 'erp.xlsx', origen=xlsx_sintetico(d / 'erp.xlsx', [('Sheet1', ERP_GENERAL)]))
            sga = dom.agregar_archivo(c['id'], 'sga.xlsx', origen=xlsx_sintetico(d / 'sga.xlsx', [('Datos', SGA)]))
            self.assertEqual((sf['tipo'], sf['fondo']), ('erp_transacciones', SANTA_FE))
            self.assertEqual(general['fondo'], GENERAL)
            self.assertIsNone(sga.get('fondo'))
            self.assertEqual(valores_columna(d / 'erp_sf.xlsx', 'Sheet1', 'Asiento'), ['SaFe-001', 'SaFe-002', 'SaFe-003'])


class VariantesTests(unittest.TestCase):
    def setUp(self):
        catalogo.cargar()

    def test_versiones_final_y_traslado_por_fondo(self):
        with carpeta_temporal() as d:
            dom = Dominio(d / 'datos')
            c = dom.crear_cierre('2026-10', '2026-10-31')
            g1 = dom.crear_ejecucion(c['id'], 'conciliacion_general')
            s1 = dom.crear_ejecucion(c['id'], 'conciliacion_general', SANTA_FE)
            g2 = dom.crear_ejecucion(c['id'], 'conciliacion_general', GENERAL)
            self.assertEqual([(x['variante'], x['version']) for x in (g1, s1, g2)], [(GENERAL, 1), (SANTA_FE, 1), (GENERAL, 2)])
            self.assertEqual(s1['parametros'], {'fondo': SANTA_FE})  # Opciones arranca con el fondo de la versión
            for x in (g1, s1, g2):
                dom.actualizar_estado(x['id'], 'ok')
            dom.marcar_final(g1['id'])
            dom.marcar_final(s1['id'])
            self.assertTrue(dom.obtener_ejecucion(g1['id'])['final'] and dom.obtener_ejecucion(s1['id'])['final'])
            dom.marcar_final(g2['id'])  # cambia sólo el final del Fondo General
            self.assertEqual([dom.obtener_ejecucion(x['id'])['final'] for x in (g1, s1, g2)], [False, True, True])
            self.assertEqual(dom.version_anterior(g2['id'])['id'], g1['id'])
            s2 = dom.crear_ejecucion(c['id'], 'conciliacion_general', SANTA_FE)
            self.assertEqual(dom.version_anterior(s2['id'])['id'], s1['id'])  # nunca la del otro fondo

    def test_cambiar_el_fondo_en_opciones_pasa_la_version_a_esa_serie(self):
        with carpeta_temporal() as d:
            dom = Dominio(d / 'datos')
            c = dom.crear_cierre('2026-10', '2026-10-31')
            dom.crear_ejecucion(c['id'], 'conciliacion_general', SANTA_FE)
            g = dom.crear_ejecucion(c['id'], 'conciliacion_general')
            g = dom.asignar_parametros(g['id'], {'fondo': SANTA_FE, 'alcance': 'completo'})
            self.assertEqual((g['variante'], g['version']), (SANTA_FE, 2))
            dom.actualizar_estado(g['id'], 'ok')
            with self.assertRaisesRegex(ValueError, 'ya corrió'):
                dom.asignar_parametros(g['id'], {'fondo': GENERAL})

    def test_las_de_antes_son_del_fondo_de_sus_parametros(self):
        with carpeta_temporal() as d:
            dom = Dominio(d / 'datos')
            c = dom.crear_cierre('2026-10', '2026-10-31')
            e = dom.crear_ejecucion(c['id'], 'conciliacion_general')
            vieja = dict(e, parametros={'fondo': GENERAL})
            vieja.pop('variante')
            self.assertEqual(dom.variante_de(vieja), GENERAL)
            otro = dom.crear_ejecucion(c['id'], 'control_mora')
            self.assertIsNone(otro['variante'])


    def test_exportar_e_importar_el_cierre_con_los_dos_fondos(self):
        from unittest import mock
        from app import exportar
        from app.reportes._comun import protocolo
        from app.reportes._comun.salidas import Volcador
        with carpeta_temporal() as d:
            dom = Dominio(d / 'datos')
            c = dom.crear_cierre('2026-10', '2026-10-31')
            for variante in (GENERAL, SANTA_FE):
                e = dom.crear_ejecucion(c['id'], 'conciliacion_general', variante)
                dom.asignar_parametros(e['id'], {'fondo': variante, 'alcance': 'completo'})
                with mock.patch.object(protocolo, 'ACTIVO', False), Volcador(dom.rutas(e['id'])['sqlite']) as v:
                    v.tabla('general', ['Tipo', 'Cliente', 'Comprobante', 'Fondo'], [['FACTURA', '1', 'F1', variante]], clave=['Tipo', 'Cliente', 'Comprobante'])
                dom.actualizar_estado(e['id'], 'ok')
                dom.marcar_final(e['id'])
            otra = Dominio(d / 'otra')  # la herramienta de otra persona
            importado = exportar.importar_cierre(otra, exportar.exportar_cierre(dom, c['id']))
            nuevas = otra.listar_ejecuciones(importado['id'])
            self.assertEqual(sorted((otra.variante_de(x), x['version']) for x in nuevas), [(SANTA_FE, 1), (GENERAL, 1)])

class ApiPorFondoTests(unittest.TestCase):
    def test_resumen_del_cierre_por_fondo_y_erp_de_otro_fondo_rechazado(self):
        with carpeta_temporal() as d:
            s = servidor_de_prueba(d, puerto=7438)
            try:
                c = Cliente(s)
                _, _, cierre = c.post('/api/cierres', {'periodo': '2026-10', 'corte': '2026-10-31'})
                subir = lambda nombre, filas: c.post(f'/api/cierres/{cierre["id"]}/archivos', crudo=xlsx_sintetico(d / nombre, filas).read_bytes(),
                                                     cabeceras={'X-Nombre': quote(nombre), 'Content-Type': 'application/octet-stream'})[2]
                sga = subir('sga.xlsx', [('Datos', SGA)])
                erp_sf = subir('erp_sf.xlsx', [('Sheet1', ERP_SANTA_FE)])
                self.assertEqual(erp_sf['fondo'], SANTA_FE)
                _, _, general = c.post('/api/ejecuciones', {'cierre': cierre['id'], 'reporte': 'conciliacion_general'})
                status, _, r = c.post(f'/api/ejecuciones/{general["id"]}/ejecutar', {'entradas': {'sga': [sga['id']], 'erp': [erp_sf['id']]},
                                                                                     'parametros': {'alcance': 'completo', 'corte': '2026-10-31', 'fondo': GENERAL}})
                self.assertEqual(status, 400)
                self.assertIn('es el ERP de FERF Prov. Santa Fe y esta versión es de Fondo de Riesgo General', r['error'])
                _, _, santa_fe = c.post('/api/ejecuciones', {'cierre': cierre['id'], 'reporte': 'conciliacion_general', 'variante': SANTA_FE})
                self.assertEqual((santa_fe['variante'], santa_fe['version']), (SANTA_FE, 1))
                _, _, resumen = c.get(f'/api/cierres/{cierre["id"]}')
                variantes = resumen['reportes']['conciliacion_general']['variantes']
                self.assertEqual({k: v['versiones'] for k, v in variantes.items()}, {GENERAL: 1, SANTA_FE: 1})
                _, _, estado = c.get('/api/estado')
                conciliacion = next(r for r in estado['reportes'] if r['codigo'] == 'conciliacion_general')
                self.assertEqual([o['valor'] for o in conciliacion['variantes']['opciones']], [GENERAL, SANTA_FE])
                fondo = next(p for p in conciliacion['parametros'] if p['clave'] == 'fondo')
                self.assertEqual((fondo['tipo'], fondo['desplegable'], fondo['no_persistir']), ('opcion', True, True))
            finally:
                s.cerrar()


if __name__ == '__main__':
    unittest.main()
