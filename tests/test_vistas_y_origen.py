"""Filas para revisar, filtros por valores, vistas de columnas, exportación de la vista, copias de consulta de
Excel y Excel de origen de una fila."""
import contextlib
import io
import json
import shutil
import time
import unittest
from pathlib import Path
from unittest import mock

from app import catalogo, exportar
from app.dominio import Dominio
from app.origenes import Origenes, SinOrigen, ruta_cache
from app.reportes._comun import cache_filas, protocolo
from app.reportes._comun.salidas import Volcador
from app.reportes.conciliacion_general import ejecutar as ejecutar_conciliacion
from app.reportes.conciliacion_general import motor, origen
from app.tablas import Tablas
from tests.fixtures import carpeta_temporal
from tests.test_tablas import volcar_ejemplo

REGLA = {'general': {'columna': 'Resultado', 'salvo': ['COINCIDE']}}
DORADO = Path(__file__).resolve().parent / 'dorados' / 'conciliacion_general' / 'reglas_1_5' / 'entradas'
CONSULTA = dict(orden=None, descendente=False, filtro='', estado=None, columna_filtro=None, filtros=None, estados=None, con_obs=False, requiere=False)


class Reloj:
    def __init__(self):
        self.t = 1_760_000_000.0

    def __call__(self):
        self.t += 1
        return self.t


class FilasParaRevisarTests(unittest.TestCase):
    def test_las_filas_que_coinciden_no_cuentan_ni_son_pendientes(self):
        with carpeta_temporal() as d:
            volcar_ejemplo(d / 'r.sqlite')
            t = Tablas(d / 'r.sqlite', reglas=REGLA)
            general = t.listar()[0]
            self.assertEqual((general['filas'], general['aRevisar']), (4, 2))
            self.assertEqual(general['estados'], {'pendiente': 2, 'revisada': 0, 'omitida': 0})
            pendientes = t.consultar('general', estado='pendiente')
            self.assertEqual([f['valores'][2] for f in pendientes['filas']], ['F2', 'REH9'])
            todas = t.consultar('general')
            self.assertEqual([f['_req'] for f in todas['filas']], [False, True, False, True])
            self.assertEqual(t.consultar('general', requiere=True)['total'], 2)
            t.marcar('general', [0], 'revisada')  # una fila que coincide se puede marcar, pero no suma
            self.assertEqual(t.resumen_revision({'resumen'}), {'pendientes': 2, 'revisadas': 0, 'omitidas': 0})
            sin_regla = Tablas(d / 'r.sqlite')
            self.assertEqual(sin_regla.listar()[0]['estados']['pendiente'], 3)

    def test_filtros_por_valores_estados_observacion_y_distintos(self):
        with carpeta_temporal() as d:
            volcar_ejemplo(d / 'r.sqlite', [['FACTURA', '1', 'F1', '1', 'COINCIDE'], ['FACTURA', '1', 'F2', '2', 'DIFERENCIA'],
                                            ['NC', '2', 'N1', '3', 'DIFERENCIA'], ['REH', '3', 'R1', '4', '']])
            t = Tablas(d / 'r.sqlite', reglas=REGLA)
            self.assertEqual(t.contar('general', **dict(CONSULTA, filtros={'Resultado': ['DIFERENCIA']})), 2)
            self.assertEqual(t.contar('general', **dict(CONSULTA, filtros={'Resultado': ['']})), 1)
            self.assertEqual(t.contar('general', **dict(CONSULTA, filtros={'Resultado': []})), 0)
            with self.assertRaises(ValueError):
                t.contar('general', **dict(CONSULTA, filtros={'Inventada': ['x']}))
            t.marcar('general', [1], 'omitida', obs='ya visto')
            self.assertEqual(t.contar('general', **dict(CONSULTA, estados=['omitida'])), 1)
            self.assertEqual(t.contar('general', **dict(CONSULTA, con_obs=True)), 1)
            with self.assertRaises(ValueError):
                t.contar('general', **dict(CONSULTA, estados=['inventado']))
            d1 = t.distintos('general', 'Resultado')
            self.assertEqual(d1['valores'][0], {'valor': 'DIFERENCIA', 'cantidad': 2})
            self.assertTrue(d1['completo'])
            self.assertFalse(t.distintos('general', 'Comprobante', limite=2)['completo'])
            orden = [f['valores'][2] for f in t.filas_vista('general', **dict(CONSULTA, orden='Saldo', descendente=True))]
            self.assertEqual(orden, ['R1', 'N1', 'F2', 'F1'])
            self.assertEqual(t.fila('general', 2)['Comprobante'], 'N1')
            with self.assertRaises(ValueError):
                t.fila('general', 99)


class FiltroDeEncabezadoTests(unittest.TestCase):
    def _tabla(self, d):
        volcar_ejemplo(d / 'r.sqlite', [['FACTURA', '1', 'F1', '0.00', 'COINCIDE'], ['FACTURA', '1', 'F2', '-1500.50', 'DIFERENCIA'],
                                        ['NC', '2', 'N1', '3000000.00', 'DIFERENCIA'], ['REH', '3', 'R1', '', 'SOLO EN ERP'],
                                        ['NC', '4', 'N2', '0.10', '']])
        return Tablas(d / 'r.sqlite', reglas=REGLA)

    def test_condiciones_de_numero(self):
        with carpeta_temporal() as d:
            t = self._tabla(d)
            def comprobantes(**cond):
                return [f['valores'][2] for f in t.filas_vista('general', **dict(CONSULTA, condiciones={'Saldo': cond}))]
            self.assertEqual(comprobantes(op='distinto_cero'), ['F2', 'N1', 'N2'])  # la celda vacía no cuenta como cero
            self.assertEqual(comprobantes(op='igual', a=0.1), ['N2'])
            self.assertEqual(comprobantes(op='igual', a=0), ['F1'])
            self.assertEqual(comprobantes(op='mayor', a=0), ['N1', 'N2'])
            self.assertEqual(comprobantes(op='menor', a=0), ['F2'])
            self.assertEqual(comprobantes(op='entre', a=1, b=-2000), ['F1', 'F2', 'N2'])
            with self.assertRaises(ValueError):
                comprobantes(op='parecido', a=1)
            with self.assertRaises(ValueError):
                comprobantes(op='mayor', a='mucho')
            with self.assertRaises(ValueError):
                comprobantes(op='entre', a=1)

    def test_excluir_valores_y_lista_como_excel(self):
        with carpeta_temporal() as d:
            t = self._tabla(d)
            sin = [f['valores'][2] for f in t.filas_vista('general', **dict(CONSULTA, filtros={'Resultado': {'excluir': ['DIFERENCIA', '']}}))]
            self.assertEqual(sin, ['F1', 'R1'])
            self.assertEqual(t.contar('general', **dict(CONSULTA, filtros={'Resultado': {'excluir': []}})), 5)
            # la lista de una columna se recalcula con los otros filtros (acá: Tipo NC)
            d1 = t.distintos('general', 'Resultado', por_valor=True, **dict(CONSULTA, filtros={'Tipo': ['NC']}))
            self.assertEqual(d1['valores'], [{'valor': '', 'cantidad': 1}, {'valor': 'DIFERENCIA', 'cantidad': 1}])
            d2 = t.distintos('general', 'Comprobante', buscar='n', por_valor=True, **CONSULTA)
            self.assertEqual([x['valor'] for x in d2['valores']], ['N1', 'N2'])
            d3 = t.distintos('general', 'Resultado', **dict(CONSULTA, condiciones={'Saldo': {'op': 'distinto_cero'}}))
            self.assertEqual(d3['valores'][0], {'valor': 'DIFERENCIA', 'cantidad': 2})

    def test_describir_condiciones_y_exclusiones(self):
        texto = exportar.describir_consulta(dict(CONSULTA, filtros={'Tipo': {'excluir': ['NC']}},
                                                 condiciones={'Saldo': {'op': 'entre', 'a': -1500.5, 'b': 3000000}, 'Otro': {'op': 'distinto_cero'}}))
        self.assertEqual(texto, 'Filtros: Tipo: todos menos NC; Saldo entre -1.500,5 y 3.000.000; Otro distinto de cero.')


class VistasTests(unittest.TestCase):
    def test_vista_guardada_por_reporte_y_tabla_con_validacion(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj())
            self.assertEqual(dom.leer_configuracion()['vistas'], {})
            dom.guardar_configuracion({'vistas': {'conciliacion_general': {'general': {'orden': ['Resultado', 'Tipo', 3], 'ocultas': ['Fondo']}},
                                                  'MAL CODIGO': {'x': {'orden': []}}}})
            vistas = dom.leer_configuracion()['vistas']
            self.assertEqual(vistas, {'conciliacion_general': {'general': {'orden': ['Resultado', 'Tipo'], 'ocultas': ['Fondo']}}})
            dom.guardar_configuracion({'vistas': {'conciliacion_general': {'general': None}}})
            self.assertEqual(dom.leer_configuracion()['vistas'], {})

    def test_la_definicion_de_la_conciliacion_trae_regla_vista_y_origen(self):
        catalogo.cargar()
        general = next(s for s in catalogo.obtener('conciliacion_general')['salidas'] if s['tabla'] == 'general')
        self.assertEqual(general['revisar'], {'columna': 'Resultado', 'salvo': ['COINCIDE']})
        self.assertEqual(general['vista']['primero'], ['Resultado'])
        for c in ('Filas SGA', 'Filas ERP', 'Origen SGA (primeras 5)', 'Origen ERP (primeras 5)', 'Fondo'):
            self.assertIn(c, general['vista']['ocultas'])
        self.assertTrue(general['origen'])
        self.assertTrue(set(general['vista']['primero'] + general['vista']['ocultas']) <= set(motor.HEAD + ['Fondo', 'Detalle identificacion']))


def _conciliacion_corrida(d, archivos=None):
    """Dominio con una corrida real de la conciliación sobre los archivos del dorado reglas_1_5, o sobre `archivos`
    ([(clave, ruta)], en orden)."""
    catalogo.cargar()
    dom = Dominio(d / 'datos', ahora=Reloj())
    c = dom.crear_cierre('2026-10', '2026-10-31')
    e = dom.crear_ejecucion(c['id'], 'conciliacion_general')
    entradas = {}
    for clave, ruta in archivos or (('sga', DORADO / 'sga_reglas.xlsx'), ('erp', DORADO / 'erp_reglas.xlsx')):
        a = dom.agregar_archivo(c['id'], ruta.name, origen=ruta)
        entradas.setdefault(clave, []).append({'ruta': a['ruta'], 'nombre': ruta.name, 'sha256': a['sha256']})
    rutas = dom.rutas(e['id'])
    rutas['carpeta'].mkdir(parents=True, exist_ok=True)
    rutas['entradas'].write_text(json.dumps(entradas), encoding='utf-8')
    with mock.patch.object(protocolo, 'ACTIVO', False), contextlib.redirect_stdout(io.StringIO()):
        motor.run({k: [Path(x['ruta']) for x in v] for k, v in entradas.items()}, rutas['salidas'], 'abiertos', '2026-10-31', informar=protocolo)
        ejecutar_conciliacion.volcar(rutas['salidas'], rutas['sqlite'])
    dom.actualizar_estado(e['id'], 'ok')
    dom.guardar_triage(e['id'])
    return dom, dom.obtener_ejecucion(e['id'])


class ExportarVistaTests(unittest.TestCase):
    def test_exporta_lo_que_se_ve_con_resumen_y_no_requiere(self):
        import openpyxl
        with carpeta_temporal() as d:
            dom, e = _conciliacion_corrida(d)
            self.assertEqual(e['revisionV'], 2)
            info = next(t for t in dom.tablas(e['id']).listar() if t['tabla'] == 'general')
            self.assertLess(info['aRevisar'], info['filas'])
            datos, nombre = exportar.exportar_vista(dom, e, 'general', dict(CONSULTA, orden='Comprobante'), ['Resultado', 'Comprobante', 'Inventada'], True)
            self.assertEqual(nombre, 'Conciliacion_general.xlsx')
            libro = openpyxl.load_workbook(io.BytesIO(datos), read_only=True)
            self.assertEqual(libro.sheetnames, ['Resumen', 'Conciliación general'])
            filas = [f for f in libro['Conciliación general'].iter_rows(values_only=True)]
            self.assertEqual(filas[1][0], 'Todas las filas.')
            self.assertEqual(list(filas[3][:4]), ['Revisión', 'Resultado', 'Comprobante', 'Observaciones de la revisión'])
            cuerpo = [f for f in filas[4:] if f and f[0]]
            self.assertEqual(len(cuerpo), info['filas'])
            self.assertEqual([f[2] for f in cuerpo], sorted(f[2] for f in cuerpo))
            self.assertEqual({f[0] for f in cuerpo if f[1] == 'COINCIDE'}, {'No requiere'})
            self.assertEqual({f[0] for f in cuerpo if f[1] != 'COINCIDE'}, {'Pendiente'})
            datos, _ = exportar.exportar_vista(dom, e, 'general', dict(CONSULTA, requiere=True), None, False)
            hoja = openpyxl.load_workbook(io.BytesIO(datos), read_only=True).worksheets[0]
            filas = [f for f in hoja.iter_rows(values_only=True)]
            self.assertIn('sólo las filas para revisar', filas[1][0])
            self.assertEqual(len([f for f in filas[4:] if f and f[0]]), info['aRevisar'])

    def test_describir_consulta(self):
        texto = exportar.describir_consulta(dict(CONSULTA, requiere=True, estados=['pendiente'], con_obs=True, filtros={'Resultado': ['', 'DIFERENCIA']}, filtro='FI-P'))
        self.assertEqual(texto, 'Filtros: sólo las filas para revisar; revisión: pendiente; con observación; Resultado: (vacío), DIFERENCIA; búsqueda «FI-P».')


class CacheFilasTests(unittest.TestCase):
    def test_copia_conserva_valores_formatos_y_anchos(self):
        import openpyxl
        with carpeta_temporal() as d:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = 'Datos'
            ws.append(['Cliente', 'Fecha', 'Importe', 'Nota'])
            for i in range(1, 301):
                ws.append([f'C{i}', 46000 + i, i * 1.5, '=no es formula' if i == 7 else ('' if i == 8 else 'texto')])
            for fila in ws.iter_rows(min_row=2, min_col=2, max_col=2):
                fila[0].number_format = 'dd/mm/yyyy'
            for fila in ws.iter_rows(min_row=2, min_col=3, max_col=3):
                fila[0].number_format = '#,##0.00'
            ws.cell(row=8, column=4).value = '=no es formula'
            ws.cell(row=8, column=4).data_type = 's'
            ws.column_dimensions['A'].width = 31
            wb.save(d / 'libro.xlsx')
            avances = []
            n = cache_filas.construir(d / 'libro.xlsx', 'Datos', d / 'copia.sqlite', avances.append)
            self.assertEqual(n, 301)
            self.assertEqual(avances[-1], 1.0)
            c = cache_filas.CacheFilas(d / 'copia.sqlite')
            self.assertTrue(c.lista())
            filas = c.leer([1, 2, 8, 300, 301, 999])
            self.assertEqual(sorted(filas), [1, 2, 8, 300, 301])
            self.assertEqual([v for _, v, _ in filas[1]], ['Cliente', 'Fecha', 'Importe', 'Nota'])
            self.assertEqual(filas[2], [(0, 'C1', 'General'), (1, 46001, 'dd/mm/yyyy'), (2, 1.5, '#,##0.00'), (3, 'texto', 'General')])
            self.assertIn((3, '=no es formula', 'General'), filas[8])
            self.assertEqual(c.primeras(2)[0][0], 1)
            self.assertEqual(c.anchos()[0], 31.0)
            with self.assertRaises(ValueError):
                cache_filas.construir(d / 'libro.xlsx', 'No existe', d / 'otra.sqlite')
            self.assertFalse(cache_filas.CacheFilas(d / 'otra.sqlite').lista())


class OrigenTests(unittest.TestCase):
    def test_filas_de_por_tipo_visible(self):
        self.assertEqual(origen.tipos_internos('PENDIENTE'), ['MP'])
        self.assertEqual(origen.tipos_internos('FACTURA'), ['FACTURA'])
        self.assertEqual(origen.tipos_internos('RC-X'), ['SR', 'OPX'])
        self.assertEqual(origen.tipos_internos('RC-X / OP-X'), ['SR', 'OPX'])

    def test_excel_de_origen_de_una_fila(self):
        import openpyxl
        with carpeta_temporal() as d:
            dom, e = _conciliacion_corrida(d)
            o = Origenes(dom)
            self.assertFalse(o.estado(e)['listo'])
            o.preparar(e)
            for _ in range(200):
                st = o.estado(e)
                if st['listo'] or st.get('error'):
                    break
                time.sleep(0.1)
            self.assertTrue(st['listo'], st)
            t = dom.tablas(e['id'])
            filas = t.consultar('general', cantidad=500)['filas']
            columnas = t.consultar('general', cantidad=1)['columnas']
            def valor(f, c):
                return f['valores'][columnas.index(c)]
            pendiente = next(f for f in filas if valor(f, 'Tipo') == 'PENDIENTE')
            datos, nombre = o.libro(e, 'general', pendiente['_fila'])
            self.assertEqual(nombre, f'Origen {valor(pendiente, "Comprobante")}.xlsx')
            hoja = openpyxl.load_workbook(io.BytesIO(datos)).active
            filas_xlsx = [[c.value for c in r] for r in hoja.iter_rows()]
            self.assertTrue(motor.COLUMNAS_SGA <= {str(v) for v in filas_xlsx[0] if v})
            self.assertEqual(len([f for f in filas_xlsx if any(v is not None for v in f)]), 2)  # encabezado SGA + su fila
            ambos = next(f for f in filas if int(valor(f, 'Filas SGA') or 0) and int(valor(f, 'Filas ERP') or 0))
            hoja = openpyxl.load_workbook(io.BytesIO(o.libro(e, 'general', ambos['_fila'])[0])).active
            filas_xlsx = [[c.value for c in r] for r in hoja.iter_rows()]
            vacias = [i for i, f in enumerate(filas_xlsx) if all(v is None for v in f)]
            self.assertEqual(len(vacias), 2)  # SGA, dos filas libres, ERP
            self.assertTrue(motor.COLUMNAS_ERP <= {str(v) for v in filas_xlsx[vacias[-1] + 1] if v})
            self.assertEqual(len(filas_xlsx) - vacias[-1] - 2, int(valor(ambos, 'Filas ERP')))
            self.assertEqual(vacias[0] - 1, int(valor(ambos, 'Filas SGA')))

    def test_excel_de_origen_con_el_erp_en_dos_tramos(self):
        """Un comprobante con filas en dos archivos del ERP: un bloque por archivo, cada uno con su encabezado."""
        import openpyxl
        from tests.fixtures import xlsx_sintetico
        from tests.test_conciliacion_general import E, FONDO, S
        with carpeta_temporal() as d:
            archivos = [('sga', xlsx_sintetico(d / 'sga.xlsx', [('Datos', [S, [FONDO, '1', 'F1', '100', 'Otros', '', '', '201', 'Socio']])])),
                        ('erp', xlsx_sintetico(d / 'erp_1.xlsx', [('Datos', [E, ['80', '1', 'F1', '', '', '', 'Cliente']])])),
                        ('erp', xlsx_sintetico(d / 'erp_2.xlsx', [('Datos', [E, ['5', '1', 'F1', '', '', '', 'Pago'], ['7', '2', 'F2', '', '', '', 'Pago']])]))]
            dom, e = _conciliacion_corrida(d, archivos)
            o = Origenes(dom)
            o.preparar(e)
            for _ in range(200):
                st = o.estado(e)
                if st['listo'] or st.get('error'):
                    break
                time.sleep(0.1)
            self.assertTrue(st['listo'], st)
            t = dom.tablas(e['id'])
            r = t.consultar('general', cantidad=50)
            f1 = next(f for f in r['filas'] if f['valores'][r['columnas'].index('Comprobante')] == 'F1')
            self.assertEqual(f1['valores'][r['columnas'].index('Filas ERP')], '2')
            hoja = openpyxl.load_workbook(io.BytesIO(o.libro(e, 'general', f1['_fila'])[0])).active
            filas_xlsx = [[c.value for c in fila] for fila in hoja.iter_rows()]
            encabezados_erp = [i for i, f in enumerate(filas_xlsx) if motor.COLUMNAS_ERP <= {str(v) for v in f if v}]
            self.assertEqual(len(encabezados_erp), 2)  # erp_1 y erp_2, cada uno con su encabezado
            saldos = [f[0] for i, f in enumerate(filas_xlsx) if i - 1 in encabezados_erp]
            self.assertEqual([str(v) for v in saldos], ['80', '5'])
            self.assertEqual(len([f for f in filas_xlsx if all(v is None for v in f)]), 4)  # SGA, 2 libres, ERP 1, 2 libres, ERP 2

    def test_netos_baja_la_fila_del_historico_con_las_celdas_observadas(self):
        import openpyxl
        from app.reportes.controles_sga import ejecutar as ejecutar_sga
        from app.reportes.controles_sga import motor as motor_sga
        from tests.test_controles_sga import CORTE, fixture_xlsx
        with carpeta_temporal() as d:
            catalogo.cargar()
            dom = Dominio(d / 'datos', ahora=Reloj())
            c = dom.crear_cierre('2026-10', '2026-10-31')
            e = dom.crear_ejecucion(c['id'], 'controles_sga')
            a = dom.agregar_archivo(c['id'], 'historico.xlsx', origen=fixture_xlsx(d / 'historico.xlsx'))
            rutas = dom.rutas(e['id'])
            rutas['carpeta'].mkdir(parents=True, exist_ok=True)
            rutas['entradas'].write_text(json.dumps({'sga': [{'ruta': a['ruta'], 'nombre': 'historico.xlsx'}]}), encoding='utf-8')
            parametros = {'corte': '2026-10-31'}
            with mock.patch.object(protocolo, 'ACTIVO', False), contextlib.redirect_stdout(io.StringIO()):
                reports, _, _ = motor_sga.ejecutar([Path(a['ruta'])], rutas['salidas'], CORTE, parametros, protocolo, nombres=['historico.xlsx'])
                ejecutar_sga.volcar(reports, parametros, rutas['sqlite'])
            dom.actualizar_estado(e['id'], 'ok')
            e = dom.obtener_ejecucion(e['id'])
            o = Origenes(dom)
            o.preparar(e)
            for _ in range(200):
                if o.estado(e)['listo']:
                    break
                time.sleep(0.1)
            t = dom.tablas(e['id'])
            pagina = t.consultar('netos_mora')
            fila = next(f for f in pagina['filas'] if 'ImporteNetoGravado' in f['_marcas'])
            valores = dict(zip(pagina['columnas'], fila['valores']))
            datos, nombre = o.libro(e, 'netos_mora', fila['_fila'])
            self.assertEqual(nombre, f'Origen {valores["NumeroFactura"]}.xlsx')
            hoja = openpyxl.load_workbook(io.BytesIO(datos)).active
            encabezado = [c.value for c in hoja[1]]
            self.assertTrue({'CodigoEmpresa', 'NumeroFactura', 'ImporteNetoGravado'} <= set(encabezado))
            self.assertEqual(hoja.max_row, 2)  # encabezado + la fila del histórico
            pintadas = {encabezado[c.column - 1] for c in hoja[2] if c.fill and c.fill.fgColor and c.fill.fgColor.rgb == 'FFF4B183'}
            self.assertEqual(pintadas, {m for m in fila['_marcas'] if m in encabezado})
            self.assertIn('ImporteNetoGravado', pintadas)
            self.assertEqual(str(hoja.cell(row=2, column=encabezado.index('NumeroFactura') + 1).value), valores['NumeroFactura'])

    def test_avisa_el_avance_por_eventos_y_lo_lista_en_curso(self):
        class Bus:
            def __init__(self):
                self.eventos = []

            def emitir(self, tipo, datos):
                self.eventos.append((tipo, dict(datos)))
        with carpeta_temporal() as d:
            dom, e = _conciliacion_corrida(d)
            bus = Bus()
            o = Origenes(dom, bus=bus)
            o.preparar(e)
            for _ in range(200):
                if o.estado(e)['listo']:
                    break
                time.sleep(0.1)
            for _ in range(50):
                if any(x[1].get('listo') for x in bus.eventos):
                    break
                time.sleep(0.05)
            tipos = {x[0] for x in bus.eventos}
            self.assertEqual(tipos, {'origen'})
            self.assertEqual(bus.eventos[0][1], {'ejecucionId': e['id'], 'progreso': 0.0})
            self.assertTrue(bus.eventos[-1][1].get('listo'))
            self.assertEqual(o.en_curso(), [])

    def test_pedir_la_copia_mientras_se_arma_no_traba_la_herramienta(self):
        # Al terminar una corrida la copia arranca sola; si en ese rato se entra a Resultados, la pantalla la pide de
        # nuevo. Ese segundo pedido se quedaba esperando para siempre (tomaba un candado y, sin soltarlo, pedía el
        # estado, que toma el mismo) y con él toda la herramienta: el estado, el visor de Tareas y la copia misma.
        import threading
        with carpeta_temporal() as d:
            dom, e = _conciliacion_corrida(d)
            o = Origenes(dom)
            seguir = threading.Event()
            original = o._correr

            def correr_lento(*args):
                seguir.wait(10)
                return original(*args)
            with mock.patch.object(o, '_correr', side_effect=correr_lento):
                o.preparar(e)  # la copia que arranca sola
                respuestas = []
                segundo = threading.Thread(target=lambda: respuestas.append(o.preparar(e)), daemon=True)
                segundo.start()  # la pantalla la pide mientras se arma
                segundo.join(3)
                trabado = segundo.is_alive()
                seguir.set()
                self.assertFalse(trabado, 'el segundo pedido de la copia se quedó esperando')
                self.assertTrue(respuestas[0]['preparando'])
                self.assertEqual([x['ejecucionId'] for x in o.en_curso()], [e['id']])
                for _ in range(200):
                    if o.estado(e)['listo']:
                        break
                    time.sleep(0.1)
                self.assertTrue(o.estado(e)['listo'])

    def test_sin_trazabilidad_o_sin_archivo_avisa_en_lenguaje_llano(self):
        with carpeta_temporal() as d:
            dom, e = _conciliacion_corrida(d)
            o = Origenes(dom)
            entradas = json.loads(dom.rutas(e['id'])['entradas'].read_text(encoding='utf-8'))
            sga = Path(entradas['sga'][0]['ruta'])
            shutil.move(sga, sga.with_suffix('.movido'))
            st = o.estado(e)
            self.assertFalse(st['listo'])
            self.assertIn('limpieza', st['error'])
            with self.assertRaises(SinOrigen):
                o.libro(e, 'general', 0)
            shutil.move(sga.with_suffix('.movido'), sga)
            (dom.rutas(e['id'])['salidas'] / 'Respaldo_tecnico' / 'trazabilidad.sqlite').unlink()
            self.assertIn('volvé a correrla', o.estado(e)['error'])

    def test_limpieza_borra_las_copias_junto_al_archivo(self):
        with carpeta_temporal() as d:
            dom = Dominio(d, ahora=Reloj())
            carpeta = d / 'x'
            carpeta.mkdir()
            (carpeta / 'libro.xlsx').write_bytes(b'x')
            ruta_cache(carpeta / 'libro.xlsx', 'Datos').write_bytes(b'y')
            dom._borrar_archivo_fisico(str(carpeta / 'libro.xlsx'))
            self.assertFalse(carpeta.exists())


class VersionAnteriorTests(unittest.TestCase):
    def test_servicios_en_su_seccion_y_version_vieja_avisada_y_trasladada(self):
        from tests.cliente import Cliente, servidor_de_prueba
        defs = {s['tabla']: s for s in catalogo.obtener('controles_sga')['salidas']}
        self.assertEqual([t for t in defs if t.startswith('servicios_')], ['servicios_mes', 'servicios_noexigibles', 'servicios_historico'])
        self.assertEqual({defs[t]['seccion'] for t in defs if t.startswith('servicios_')}, {'Control de servicios administrativos'})
        self.assertEqual(defs['abiertos']['seccion'], 'Comprobantes abiertos')
        cols = ['FondoDeRiesgo', 'CodigoEmpresa', 'NumeroDeAporte', 'Control']
        with carpeta_temporal() as d:
            s = servidor_de_prueba(d, puerto=7391)
            try:
                dom = s.dominio
                c = dom.crear_cierre('2026-10', '2026-10-31')
                vieja = dom.crear_ejecucion(c['id'], 'controles_sga')
                with mock.patch.object(protocolo, 'ACTIVO', False), Volcador(dom.rutas(vieja['id'])['sqlite']) as v:
                    v.tabla('servicios_anio', cols, [['G', '1', 'A1', 'S']], clave=cols, titulo='Servicios administrativos · Año en curso')
                    v.tabla('servicios_historico', cols, [['G', '1', 'A2', 'S']], clave=cols, titulo='Servicios administrativos · Histórico')
                dom.actualizar_estado(vieja['id'], 'ok')
                status, _, r = Cliente(s).get(f"/api/ejecuciones/{vieja['id']}/tablas")
                self.assertEqual(status, 200)
                por_tabla = {t['tabla']: t for t in r['tablas']}
                self.assertTrue(por_tabla['servicios_anio']['anterior'])
                self.assertFalse(por_tabla['servicios_historico']['anterior'])
                self.assertEqual(por_tabla['servicios_anio']['seccion'], 'Control de servicios administrativos')
                self.assertEqual(por_tabla['servicios_anio']['hoja'], 'Año en curso')
                dom.tablas(vieja['id']).marcar('servicios_anio', [0], 'omitida', obs='visto')
                dom.guardar_triage(vieja['id'])
                nueva = dom.crear_ejecucion(c['id'], 'controles_sga')
                with mock.patch.object(protocolo, 'ACTIVO', False), Volcador(dom.rutas(nueva['id'])['sqlite']) as v:
                    for tabla in ('servicios_mes', 'servicios_noexigibles', 'servicios_historico'):
                        v.tabla(tabla, cols, [['G', '1', 'A1', 'S']] if tabla == 'servicios_noexigibles' else [], clave=cols)
                self.assertEqual(dom.trasladar_revision(nueva['id'])['aplicadas'], 1)
                fila = dom.tablas(nueva['id']).consultar('servicios_noexigibles')['filas'][0]
                self.assertEqual((fila['_estado'], fila['_obs']), ('omitida', 'visto'))
                status, _, r = Cliente(s).get(f"/api/ejecuciones/{nueva['id']}/tablas")
                self.assertFalse(any(t['anterior'] for t in r['tablas']))
            finally:
                s.cerrar()


class FirmaCodigoTests(unittest.TestCase):
    def test_cambia_si_cambia_un_archivo_del_codigo(self):
        from app.servidor import firma_codigo
        with carpeta_temporal() as d:
            (d / 'app').mkdir()
            (d / 'app' / 'a.py').write_text('x = 1', encoding='utf-8')
            antes = firma_codigo(d)
            self.assertEqual(firma_codigo(d), antes)
            (d / 'app' / 'a.py').write_text('x = 22', encoding='utf-8')
            self.assertNotEqual(firma_codigo(d), antes)


if __name__ == '__main__':
    unittest.main()
