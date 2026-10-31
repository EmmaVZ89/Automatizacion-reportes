import json
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

from app.dominio import Dominio
from app.reportes._comun import protocolo
from app.reportes._comun.salidas import Volcador
from tests.fixtures import carpeta_temporal, xlsx_sintetico


class Reloj:
    def __init__(self):
        self.t = 1_760_000_000.0

    def __call__(self):
        self.t += 1
        return self.t


def reconocer_falso(ruta):
    return {'tipo': 'historico_sga', 'hoja': 'Datos', 'filas': 10, 'aviso': None}


def volcar(ruta, filas):
    with mock.patch.object(protocolo, 'ACTIVO', False), Volcador(ruta) as v:
        v.tabla('general', ['Tipo', 'Cliente', 'Comprobante', 'Saldo'], filas, clave=['Tipo', 'Cliente', 'Comprobante'])


def ejecucion_ok(dom, cierre_id, reporte, filas):
    e = dom.crear_ejecucion(cierre_id, reporte)
    volcar(dom.rutas(e['id'])['sqlite'], filas)
    dom.actualizar_estado(e['id'], 'ok')
    return e


class DominioTests(unittest.TestCase):
    def test_crear_cierre_periodo_unico_y_formato(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj(), reconocer=reconocer_falso)
            c = dom.crear_cierre('2026-10', '2026-10-31')
            self.assertEqual(c['nombre'], 'Cierre 2026-10')
            self.assertTrue((d / 'cierres' / c['id'] / 'archivos').is_dir())
            with self.assertRaises(ValueError):
                dom.crear_cierre('2026-10', '2026-10-31')
            with self.assertRaises(ValueError):
                dom.crear_cierre('10/2026', '2026-10-31')
            with self.assertRaises(ValueError):
                dom.crear_cierre('2026-11', '2026-11-31')
            dom.crear_cierre('2026-09', '2026-09-30', 'Septiembre')
            self.assertEqual([x['periodo'] for x in dom.listar_cierres()], ['2026-10', '2026-09'])
            self.assertEqual(dom.editar_cierre(c['id'], corte='2026-10-30', notas='n')['corte'], '2026-10-30')

    def test_agregar_archivo_dedup_por_sha256_y_reconoce(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj(), reconocer=reconocer_falso)
            c = dom.crear_cierre('2026-10', '2026-10-31')
            origen = xlsx_sintetico(d / 'Reporte (7).xlsx', [('Datos', [['a', 'b', 'c'], ['1', '2', '3']])])
            a1 = dom.agregar_archivo(c['id'], 'C:\\bajadas\\Reporte (7).xlsx', origen=origen)
            self.assertEqual(a1['nombre'], 'Reporte (7).xlsx')
            self.assertEqual(a1['tipo'], 'historico_sga')
            self.assertEqual(a1['hoja'], 'Datos')
            self.assertEqual(Path(a1['ruta']).name, 'Reporte (7).xlsx')
            self.assertEqual(Path(a1['ruta']).parent.name, a1['sha256'][:8])
            self.assertEqual(a1['bytes'], origen.stat().st_size)
            a2 = dom.agregar_archivo(c['id'], 'otro nombre.xlsx', bytes_iter=iter([origen.read_bytes()[:100], origen.read_bytes()[100:]]))
            self.assertEqual(a2['id'], a1['id'])
            self.assertEqual(len(dom.archivos_de(c['id'])), 1)
            self.assertEqual(len([p for p in (d / 'cierres' / c['id'] / 'archivos').rglob('*.xlsx')]), 1)

    def test_archivo_no_reconocible_queda_con_error(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj())  # reconocedor real
            c = dom.crear_cierre('2026-10', '2026-10-31')
            a = dom.agregar_archivo(c['id'], 'x.xlsx', bytes_iter=iter([b'no soy excel']))
            self.assertIsNone(a['tipo'])
            self.assertIn('Excel', a['error'])

    def test_quitar_archivo_referenciado_falla(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj(), reconocer=reconocer_falso)
            c = dom.crear_cierre('2026-10', '2026-10-31')
            a = dom.agregar_archivo(c['id'], 'a.xlsx', bytes_iter=iter([b'contenido']))
            e = dom.crear_ejecucion(c['id'], 'control_mora')
            dom.asignar_entradas(e['id'], {'sga': [a['id']]})
            with self.assertRaises(ValueError):
                dom.quitar_archivo(c['id'], a['id'])
            with self.assertRaises(ValueError):
                dom.asignar_entradas(e['id'], {'sga': ['inexistente']})
            dom.asignar_entradas(e['id'], {})
            dom.quitar_archivo(c['id'], a['id'])
            self.assertEqual(dom.archivos_de(c['id']), [])
            self.assertFalse(Path(a['ruta']).exists())

    def test_version_incrementa_por_cierre_y_reporte(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj(), reconocer=reconocer_falso)
            c = dom.crear_cierre('2026-10', '2026-10-31')
            c2 = dom.crear_cierre('2026-11', '2026-11-30')
            e1 = dom.crear_ejecucion(c['id'], 'control_mora')
            e2 = dom.crear_ejecucion(c['id'], 'control_mora')
            e3 = dom.crear_ejecucion(c['id'], 'control_cheques')
            e4 = dom.crear_ejecucion(c2['id'], 'control_mora')
            self.assertEqual([e1['version'], e2['version'], e3['version'], e4['version']], [1, 2, 1, 1])
            self.assertEqual(e1['estado'], 'borrador')
            self.assertEqual(len(dom.listar_ejecuciones(c['id'])), 3)
            self.assertEqual(len(dom.listar_ejecuciones(reporte='control_mora')), 3)
            dom.asignar_parametros(e1['id'], {'cuentas': ['1']})
            self.assertEqual(json.loads(dom.rutas(e1['id'])['parametros'].read_text(encoding='utf-8')), {'cuentas': ['1']})

    def test_marcar_final_desmarca_anteriores_y_borrar(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj(), reconocer=reconocer_falso)
            c = dom.crear_cierre('2026-10', '2026-10-31')
            e1 = ejecucion_ok(dom, c['id'], 'control_mora', [['A', '1', 'X', Decimal(1)]])
            e2 = ejecucion_ok(dom, c['id'], 'control_mora', [['A', '1', 'X', Decimal(1)]])
            e3 = dom.crear_ejecucion(c['id'], 'control_mora')
            with self.assertRaises(ValueError):
                dom.marcar_final(e3['id'])
            dom.marcar_final(e1['id'])
            dom.marcar_final(e2['id'])
            self.assertFalse(dom.obtener_ejecucion(e1['id'])['final'])
            self.assertTrue(dom.obtener_ejecucion(e2['id'])['final'])
            with self.assertRaises(ValueError):
                dom.borrar_ejecucion(e2['id'])
            dom.borrar_ejecucion(e1['id'])
            self.assertIsNone(dom.obtener_ejecucion(e1['id']))
            self.assertFalse(dom.rutas(e1['id'])['carpeta'].exists())
            with self.assertRaises(ValueError):
                dom.borrar_cierre(c['id'])
            dom.borrar_cierre(c['id'], forzar=True)
            self.assertEqual(dom.listar_cierres(), [])
            self.assertEqual(dom.listar_ejecuciones(), [])

    def test_trasladar_revision_usa_version_anterior_y_cuenta_sin_destino(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj(), reconocer=reconocer_falso)
            c = dom.crear_cierre('2026-10', '2026-10-31')
            e1 = ejecucion_ok(dom, c['id'], 'conciliacion_general', [['F', '1', 'A', Decimal(1)], ['F', '1', 'B', Decimal(2)], ['F', '1', 'C', Decimal(3)]])
            t1 = dom.tablas(e1['id'])
            t1.marcar('general', [0], 'revisada')
            t1.marcar('general', [1], 'omitida', obs='histórica')
            t1.marcar('general', [2], 'omitida')
            resumen = dom.guardar_triage(e1['id'])
            self.assertEqual(resumen, {'pendientes': 0, 'revisadas': 1, 'omitidas': 2})
            self.assertEqual(dom.obtener_ejecucion(e1['id'])['revision']['omitidas'], 2)
            self.assertTrue(dom.rutas(e1['id'])['triage'].exists())
            e2 = ejecucion_ok(dom, c['id'], 'conciliacion_general', [['F', '1', 'A', Decimal(1)], ['F', '1', 'B', Decimal(5)], ['F', '1', 'D', Decimal(3)]])
            self.assertEqual(dom.version_anterior(e2['id'])['id'], e1['id'])
            r = dom.trasladar_revision(e2['id'])
            self.assertEqual(r, {'aplicadas': 2, 'sin_destino': 1, 'desde': 1})
            filas = dom.tablas(e2['id']).consultar('general')['filas']
            self.assertEqual([f['_estado'] for f in filas], ['revisada', 'omitida', 'pendiente'])
            self.assertEqual(filas[1]['_obs'], 'histórica')
            self.assertEqual(dom.obtener_ejecucion(e2['id'])['traslado']['aplicadas'], 2)
            self.assertEqual(dom.trasladar_revision(e1['id']), {'aplicadas': 0, 'sin_destino': 0, 'desde': None})

    def test_traer_revision_cierre_anterior_solo_omitidas(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj(), reconocer=reconocer_falso)
            c9 = dom.crear_cierre('2026-09', '2026-09-30')
            c10 = dom.crear_cierre('2026-10', '2026-10-31')
            filas = [['F', '1', 'A', Decimal(1)], ['F', '1', 'B', Decimal(2)]]
            e9a = ejecucion_ok(dom, c9['id'], 'conciliacion_general', filas)
            e9b = ejecucion_ok(dom, c9['id'], 'conciliacion_general', filas)
            dom.tablas(e9b['id']).marcar('general', [0], 'revisada')
            dom.tablas(e9b['id']).marcar('general', [1], 'omitida', obs='siempre')
            dom.guardar_triage(e9b['id'])
            dom.tablas(e9a['id']).marcar('general', [0], 'omitida')
            dom.guardar_triage(e9a['id'])
            dom.marcar_final(e9b['id'])
            e10 = ejecucion_ok(dom, c10['id'], 'conciliacion_general', filas)
            r = dom.traer_revision_cierre_anterior(e10['id'])
            self.assertEqual(r, {'aplicadas': 1, 'sin_destino': 0, 'desde': '2026-09'})
            f = dom.tablas(e10['id']).consultar('general')['filas']
            self.assertEqual([x['_estado'] for x in f], ['pendiente', 'omitida'])
            self.assertEqual(f[1]['_origen'], 'cierre')
            e9c = ejecucion_ok(dom, c9['id'], 'control_mora', filas)
            self.assertEqual(dom.traer_revision_cierre_anterior(e9c['id'])['desde'], None)

    def test_limpiar_archivos_no_referenciados(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj(), reconocer=reconocer_falso)
            c = dom.crear_cierre('2026-10', '2026-10-31')
            a = dom.agregar_archivo(c['id'], 'a.xlsx', bytes_iter=iter([b'1234']))
            b = dom.agregar_archivo(c['id'], 'b.xlsx', bytes_iter=iter([b'56789']))
            e = ejecucion_ok(dom, c['id'], 'control_mora', [['A', '1', 'X', Decimal(1)]])
            dom.asignar_entradas(e['id'], {'sga': [a['id']]})
            dom.marcar_final(e['id'])
            self.assertEqual(dom.limpiar_archivos_no_referenciados(), 5)
            self.assertEqual([x['id'] for x in dom.archivos_de(c['id'])], [a['id']])
            self.assertFalse(Path(b['ruta']).exists())

    def test_configuracion_defaults_y_guardado(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj(), reconocer=reconocer_falso)
            conf = dom.leer_configuracion()
            self.assertEqual((conf['tema'], conf['limiteMB'], conf['reportes']), ('claro', 200, {}))
            dom.guardar_configuracion({'tema': 'oscuro', 'limiteMB': 5, 'otra': 'x', 'reportes': {'control_mora': {'parametros': {'cuentas': ['1']}}}})
            conf = dom.leer_configuracion()
            self.assertEqual(conf['tema'], 'oscuro')
            self.assertEqual(conf['limiteMB'], 10)
            self.assertNotIn('otra', conf)
            self.assertEqual(conf['reportes']['control_mora']['parametros'], {'cuentas': ['1']})
            dom.guardar_configuracion({'tema': 'violeta'})
            self.assertEqual(dom.leer_configuracion()['tema'], 'oscuro')

    def test_bienvenida_arranca_sin_ver_y_se_guarda(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj(), reconocer=reconocer_falso)
            self.assertIs(dom.leer_configuracion()['bienvenida'], False)
            dom.guardar_configuracion({'bienvenida': 1})
            self.assertIs(dom.leer_configuracion()['bienvenida'], True)

    def test_espacio_de_herramienta_unico_y_fuera_de_los_cierres(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj(), reconocer=reconocer_falso)
            dom.crear_cierre('2026-10', '2026-10-31')
            h1 = dom.espacio_herramienta('descarga_facturas')
            h2 = dom.espacio_herramienta('descarga_facturas')
            self.assertEqual(h1['id'], h2['id'])
            self.assertEqual(h1['herramienta'], 'descarga_facturas')
            self.assertTrue((d / 'cierres' / h1['id'] / 'archivos').is_dir())
            self.assertEqual([c['periodo'] for c in dom.listar_cierres()], ['2026-10'])
            self.assertIsNotNone(dom.obtener_cierre(h1['id']))

    def test_tablas_informativas_no_suman_a_la_revision(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj(), reconocer=reconocer_falso)
            c = dom.crear_cierre('2026-10', '2026-10-31')
            e = dom.crear_ejecucion(c['id'], 'control_cheques')
            with mock.patch.object(protocolo, 'ACTIVO', False), Volcador(dom.rutas(e['id'])['sqlite']) as v:
                v.tabla('revisar', ['ID SGA', 'Motivo'], [['1', 'a'], ['2', 'b']], clave=['ID SGA', 'Motivo'])
                v.tabla('resumen', ['Concepto', 'Valor'], [['x', '1'], ['y', '2'], ['z', '3']], clave=['Concepto'])
            dom.actualizar_estado(e['id'], 'ok')
            self.assertEqual(dom.tablas_informativas(e['id']), {'resumen'})
            self.assertEqual(dom.resumen_revision(e['id']), {'pendientes': 2, 'revisadas': 0, 'omitidas': 0})
            dom.tablas(e['id']).marcar('revisar', [0, 1], 'revisada')
            self.assertEqual(dom.guardar_triage(e['id']), {'pendientes': 0, 'revisadas': 2, 'omitidas': 0})


if __name__ == '__main__':
    unittest.main()
