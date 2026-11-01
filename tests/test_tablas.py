import unittest
from decimal import Decimal
from unittest import mock

from app.reportes._comun import protocolo
from app.reportes._comun.salidas import Volcador
from app.tablas import Tablas
from tests.fixtures import carpeta_temporal


def volcar_ejemplo(ruta, filas=None):
    filas = filas if filas is not None else [
        ['FACTURA', '1', 'F1', Decimal('100.50'), 'COINCIDE'],
        ['FACTURA', '1', 'F2', Decimal('-20'), 'DIFERENCIA'],
        ['OP-X', '2', 'SR-1', Decimal('0'), 'COINCIDE'],
        ['REH', '3', 'REH9', Decimal('7.00'), 'SOLO EN ERP — REVISAR EN SGA'],
    ]
    with mock.patch.object(protocolo, 'ACTIVO', False), Volcador(ruta) as v:
        v.tabla('general', ['Tipo', 'Cliente', 'Comprobante', 'Saldo', 'Resultado'], filas, clave=['Tipo', 'Cliente', 'Comprobante'],
                marcas=[(1, 'Saldo')], titulo='Conciliación general')
        v.tabla('resumen', ['Control', 'Valor'], [['TOTAL', '5'], ['ALERTA', 'x']], clave=['Control'])


class TablasTests(unittest.TestCase):
    def test_volcar_y_listar_conserva_orden_y_nombres_de_columnas(self):
        with carpeta_temporal() as d:
            volcar_ejemplo(d / 'r.sqlite')
            t = Tablas(d / 'r.sqlite')
            lista = t.listar()
            self.assertEqual([x['tabla'] for x in lista], ['general', 'resumen'])
            self.assertEqual(lista[0]['titulo'], 'Conciliación general')
            self.assertEqual(lista[0]['columnas'], ['Tipo', 'Cliente', 'Comprobante', 'Saldo', 'Resultado'])
            self.assertEqual(lista[0]['tipos'][3], 'numero')
            self.assertEqual(lista[0]['estados'], {'pendiente': 4, 'revisada': 0, 'omitida': 0})
            r = t.consultar('general')
            self.assertEqual(r['total'], 4)
            self.assertEqual(r['filas'][0]['valores'], ['FACTURA', '1', 'F1', '100.50', 'COINCIDE'])
            self.assertEqual(r['filas'][1]['_marcas'], ['Saldo'])
            self.assertEqual(r['filas'][3]['valores'][3], '7.00')

    def test_consultar_pagina_filtra_y_ordena(self):
        with carpeta_temporal() as d:
            volcar_ejemplo(d / 'r.sqlite')
            t = Tablas(d / 'r.sqlite')
            p = t.consultar('general', desde=1, cantidad=2)
            self.assertEqual([f['_fila'] for f in p['filas']], [1, 2])
            self.assertEqual(p['total'], 4)
            f = t.consultar('general', filtro='revisar')
            self.assertEqual(f['total'], 1)
            self.assertEqual(f['filas'][0]['valores'][2], 'REH9')
            c = t.consultar('general', filtro='F', columna_filtro='Comprobante')
            self.assertEqual(c['total'], 2)
            o = t.consultar('general', orden='Saldo', descendente=True)
            self.assertEqual([x['valores'][3] for x in o['filas']], ['100.50', '7.00', '0', '-20'])
            o2 = t.consultar('general', orden='Comprobante')
            self.assertEqual([x['valores'][2] for x in o2['filas']], ['F1', 'F2', 'REH9', 'SR-1'])

    def test_marcar_cambia_estado_y_conteos(self):
        with carpeta_temporal() as d:
            volcar_ejemplo(d / 'r.sqlite')
            t = Tablas(d / 'r.sqlite', ahora=lambda: 1_700_000_000)
            self.assertEqual(t.marcar('general', [0, 2], 'revisada'), 2)
            self.assertEqual(t.marcar('general', [1], 'omitida', obs='Ya pedido a Sistemas'), 1)
            self.assertEqual(t.marcar('general', [3], None, obs='sólo nota'), 1)
            lista = t.listar()[0]
            self.assertEqual(lista['estados'], {'pendiente': 1, 'revisada': 2, 'omitida': 1})
            fila = t.consultar('general', estado='omitida')['filas'][0]
            self.assertEqual(fila['_obs'], 'Ya pedido a Sistemas')
            self.assertEqual(t.consultar('general', filtro='sólo nota')['total'], 1)
            # suma las dos tablas: la de resumen tiene 2 filas pendientes
            self.assertEqual(t.resumen_revision(), {'pendientes': 3, 'revisadas': 2, 'omitidas': 1})
            with self.assertRaises(ValueError):
                t.marcar('general', [0], 'inventado')

    def test_triage_y_aplicar_triage_por_clave_con_sin_destino(self):
        with carpeta_temporal() as d:
            volcar_ejemplo(d / 'v1.sqlite')
            t1 = Tablas(d / 'v1.sqlite')
            t1.marcar('general', [0], 'revisada')
            t1.marcar('general', [1], 'omitida', obs='histórica')
            t1.marcar('resumen', [1], 'omitida')
            triage = t1.triage()
            self.assertEqual(set(triage), {'general', 'resumen'})
            self.assertEqual(len(triage['general']), 2)
            clave = next(k for k, v in triage['general'].items() if v['estado'] == 'omitida')
            self.assertEqual(clave, 'FACTURA\x1f1\x1fF2')
            # Versión 2: F2 ya no está, aparece F3; el resumen no cambió.
            volcar_ejemplo(d / 'v2.sqlite', filas=[
                ['FACTURA', '1', 'F1', Decimal('100.50'), 'COINCIDE'],
                ['FACTURA', '1', 'F3', Decimal('1'), 'DIFERENCIA'],
            ])
            t2 = Tablas(d / 'v2.sqlite')
            r = t2.aplicar_triage(triage, origen='version')
            self.assertEqual(r, {'aplicadas': 2, 'sin_destino': 1})
            filas = t2.consultar('general')['filas']
            self.assertEqual(filas[0]['_estado'], 'revisada')
            self.assertEqual(filas[0]['_origen'], 'version')
            self.assertEqual(filas[1]['_estado'], 'pendiente')
            self.assertEqual(t2.consultar('resumen')['filas'][1]['_estado'], 'omitida')
            # Sólo omitidas (de un cierre anterior): la revisada no se aplica.
            volcar_ejemplo(d / 'v3.sqlite')
            r3 = Tablas(d / 'v3.sqlite').aplicar_triage(triage, origen='cierre', solo_estados=('omitida',))
            self.assertEqual(r3['aplicadas'], 2)
            self.assertEqual(Tablas(d / 'v3.sqlite').consultar('general')['filas'][0]['_estado'], 'pendiente')

    def test_marcas_pasan_a_otra_tabla_del_mismo_libro(self):
        # Servicios por mes: la tabla del año en curso ya no existe y una fila del histórico pasó a no exigibles.
        cols = ['Fondo', 'Aporte', 'Control']
        with carpeta_temporal() as d:
            with mock.patch.object(protocolo, 'ACTIVO', False), Volcador(d / 'v1.sqlite') as v:
                v.tabla('servicios_anio', cols, [['G', 'A1', 'S'], ['G', 'A2', 'S']], clave=cols)
                v.tabla('servicios_historico', cols, [['G', 'A3', 'S']], clave=cols)
            t1 = Tablas(d / 'v1.sqlite')
            t1.marcar('servicios_anio', [0], 'omitida', obs='nota')
            t1.marcar('servicios_anio', [1], 'revisada')
            t1.marcar('servicios_historico', [0], 'revisada')
            triage = t1.triage()
            for nombre in ('v2.sqlite', 'v3.sqlite'):
                with mock.patch.object(protocolo, 'ACTIVO', False), Volcador(d / nombre) as v:
                    v.tabla('servicios_mes', cols, [['G', 'A1', 'S']], clave=cols)
                    v.tabla('servicios_noexigibles', cols, [['G', 'A3', 'S']], clave=cols)
                    v.tabla('servicios_historico', cols, [['G', 'A2', 'S']], clave=cols)
            self.assertEqual(Tablas(d / 'v2.sqlite').aplicar_triage(triage, origen='version'), {'aplicadas': 0, 'sin_destino': 3})
            hermanas = {'servicios_anio': ['servicios_mes', 'servicios_noexigibles', 'servicios_historico'],
                        'servicios_historico': ['servicios_mes', 'servicios_noexigibles']}
            t3 = Tablas(d / 'v3.sqlite')
            self.assertEqual(t3.aplicar_triage(triage, origen='version', hermanas=hermanas), {'aplicadas': 3, 'sin_destino': 0})
            estado = lambda tabla: [(f['_estado'], f['_obs']) for f in t3.consultar(tabla)['filas']]
            self.assertEqual(estado('servicios_mes'), [('omitida', 'nota')])
            self.assertEqual(estado('servicios_historico'), [('revisada', '')])
            self.assertEqual(estado('servicios_noexigibles'), [('revisada', '')])

    def test_orden_o_columna_inexistente_lanza_valueerror(self):
        with carpeta_temporal() as d:
            volcar_ejemplo(d / 'r.sqlite')
            t = Tablas(d / 'r.sqlite')
            with self.assertRaises(ValueError):
                t.consultar('general', orden='NoExiste')
            with self.assertRaises(ValueError):
                t.consultar('general', filtro='x', columna_filtro='NoExiste')
            with self.assertRaises(ValueError):
                t.consultar('otra')

    def test_filtro_con_porcentaje_y_guion_bajo_se_escapa(self):
        with carpeta_temporal() as d:
            volcar_ejemplo(d / 'r.sqlite', filas=[['A', '1', 'X_1', Decimal('1'), '100%'], ['A', '1', 'XY1', Decimal('2'), '100']])
            t = Tablas(d / 'r.sqlite')
            self.assertEqual(t.consultar('general', filtro='X_1')['total'], 1)
            self.assertEqual(t.consultar('general', filtro='%')['total'], 1)

    def test_cantidad_se_acota_a_500_y_filas_completas_excluye_omitidas(self):
        with carpeta_temporal() as d:
            volcar_ejemplo(d / 'r.sqlite', filas=[[str(i), '1', f'F{i}', Decimal(i), 'x'] for i in range(700)])
            t = Tablas(d / 'r.sqlite')
            self.assertEqual(len(t.consultar('general', cantidad=9999)['filas']), 500)
            t.marcar('general', [0, 1], 'omitida')
            self.assertEqual(len(list(t.filas_completas('general', incluir_omitidas=False))), 698)
            self.assertEqual(len(list(t.filas_completas('general'))), 700)


if __name__ == '__main__':
    unittest.main()
