"""Controles SGA: el motor nuevo contra los dorados generados con legado/controles_sga/control_sga.py
sobre un fixture sintético (ver tests/dorados/controles_sga/generar.py), más tramos, reglas confirmadas,
salidas a generar, fórmulas sin valor y el contrato de ejecutar.py."""
import csv
import json
import os
import subprocess
import sqlite3
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from zipfile import ZipFile

from app.reportes.controles_sga import motor
from app.reportes.controles_sga.reporte import LIBROS, SALIDAS
from tests.fixtures import carpeta_temporal, xlsx_sintetico

RAIZ = Path(__file__).resolve().parent.parent
DORADOS = RAIZ / 'tests' / 'dorados' / 'controles_sga'
EJECUTAR = RAIZ / 'app' / 'reportes' / 'controles_sga' / 'ejecutar.py'
CORTE = date(2026, 10, 31)
NARANJA = 'FFF4B183'
COLUMNAS = ['CodigoEmpresa', 'CUIT', 'RazonSocial', 'CodigoSocio', 'NumeroDeAporte', 'Expediente', 'Operacion',
            'TipoLinea', 'Linea', 'Canal', 'GrupoConceptoFacturacion', 'Concepto', 'NumeroFactura', 'FechaFactura',
            'ConceptoFacturacionImputacion', 'NumeroComprobanteImputacion', 'FechaComprobanteImputacion',
            'FechaImputacion', 'Importe', 'ImporteNetoGravado', 'PorcentajeIVA', 'ImporteIVA', 'PorcentajeIIBB',
            'ImporteIIBB', 'Subrecibo', 'FondoDeRiesgo']
S1 = 'SERV. ADMINIST. FRG - 1º'
S2 = 'SERV. ADMINIST. FRG - 2º'


def _linea(emp, concepto, grupo, factura, fecha, importe, neto, iva, iibb, comp='', fcomp='', fimp='', cimp='',
           aporte='', exp='', op='', sub='', fondo='FONDO A'):
    return {'CodigoEmpresa': str(emp), 'CUIT': f'20{emp}0000{emp}', 'RazonSocial': f'Empresa {emp}', 'CodigoSocio': str(emp),
            'NumeroDeAporte': aporte, 'Expediente': exp, 'Operacion': op, 'TipoLinea': 'L', 'Linea': '1', 'Canal': 'C',
            'GrupoConceptoFacturacion': grupo, 'Concepto': concepto, 'NumeroFactura': factura, 'FechaFactura': fecha,
            'ConceptoFacturacionImputacion': cimp, 'NumeroComprobanteImputacion': comp, 'FechaComprobanteImputacion': fcomp,
            'FechaImputacion': fimp, 'Importe': f'{importe:.2f}', 'ImporteNetoGravado': f'{neto:.2f}',
            'PorcentajeIVA': '21' if iva else '', 'ImporteIVA': f'{iva:.2f}', 'PorcentajeIIBB': '', 'ImporteIIBB': f'{iibb:.2f}',
            'Subrecibo': sub, 'FondoDeRiesgo': fondo}


def filas_fixture():
    """~30 líneas sintéticas que cubren los seis controles (sin datos reales)."""
    return [
        # Factura con una imputación proporcional (sin Operacion) y otra desproporcionada en el mes de corte
        _linea(101, 'COMISION FRG', 'COMISIONES', 'FI-0001', '2026-03-10', 1210, 1000, 210, 0, exp='E1', op='O1'),
        _linea(101, 'COMISION FRG', 'COMISIONES', 'FI-0001', '2026-03-10', -605, -500, -105, 0, comp='RC-0001', fcomp='2026-04-05', fimp='2026-04-05', cimp='COMISION FRG', exp='E1', sub='S2'),
        _linea(101, 'COMISION FRG', 'OTROS', 'FI-0001', '2026-03-10', -605, -605, 0, 0, comp='RC-0002', fcomp='2026-10-10', fimp='2026-10-10', cimp='COMISION FRG', exp='E1', op='O1'),
        # NC parcial
        _linea(102, 'COMISION FRG', 'COMISIONES', 'FI-0002', '2025-05-01', 2420, 2000, 420, 0, exp='E2', op='O2'),
        _linea(102, 'COMISION FRG', 'COMISIONES', 'FI-0002', '2025-05-01', -1210, -1000, -210, 0, comp='NC-0001', fcomp='2025-06-01', fimp='2025-06-01', cimp='COMISION FRG', exp='E2', op='O2'),
        # Servicio 1º cancelado con 2º en término histórico
        _linea(103, S1, 'SERVICIOS', 'FC-0003', '2025-02-15', 605, 500, 105, 0, aporte='A103'),
        _linea(103, S1, 'SERVICIOS', 'FC-0003', '2025-02-15', -605, -500, -105, 0, comp='RC-0003', fcomp='2025-03-01', fimp='2025-03-01', cimp=S1, aporte='A103'),
        _linea(103, S2, 'SERVICIOS', 'FC-0004', '2026-02-20', 605, 500, 105, 0, aporte='A103'),
        # Servicio 1º sin 2º (histórico), otro futuro no exigible y otro anulado por NC total
        _linea(104, S1, 'SERVICIOS', 'FC-0005', '2025-01-10', 605, 500, 105, 0, aporte='A104'),
        _linea(104, S1, 'SERVICIOS', 'FC-0006', '2026-04-10', 605, 500, 105, 0, aporte='A105'),
        _linea(104, S1, 'SERVICIOS', 'FC-0007', '2025-08-01', 605, 500, 105, 0, aporte='A106'),
        _linea(104, S1, 'SERVICIOS', 'FC-0007', '2025-08-01', -605, -500, -105, 0, comp='NC-0002', fcomp='2025-08-15', fimp='2025-08-15', cimp=S1, aporte='A106'),
        # Agrupador MORA con imputación desproporcionada
        _linea(105, 'INTERESES MORA', 'MORA', 'FI-0008', '2024-06-01', 100, 100, 0, 0, exp='E5', op='O5'),
        _linea(105, 'INTERESES MORA', 'MORA', 'FI-0008', '2024-06-01', -40, -30, -10, 0, comp='RC-0005', fcomp='2024-07-01', fimp='2024-07-01', cimp='INTERESES MORA', exp='E5', op='O5'),
        # OPX pendiente con subrecibo
        _linea(106, 'MOVIMIENTOS PENDIENTES', 'PENDIENTES', '', '', -300, -300, 0, 0, comp='OPX-0001', fcomp='2026-05-05', fimp='2026-05-05', cimp='ANTICIPO', sub='S1'),
        # FI-P recíproco con contraparte cancelada
        _linea(107, 'DEUDA POR APORTE NO VIGENTE', 'APORTES', 'FI-P-0001', '2025-09-01', 100, 100, 0, 0, comp='FI-P-0002', fcomp='2025-09-01', fimp='2025-09-01', cimp='DEUDA POR APORTE NO VIGENTE - RDO. EJ.'),
        _linea(107, 'DEUDA POR APORTE NO VIGENTE', 'APORTES', 'FI-P-0002', '2025-09-01', 100, 100, 0, 0),
        _linea(107, 'DEUDA POR APORTE NO VIGENTE', 'APORTES', 'FI-P-0002', '2025-09-01', -100, -100, 0, 0, comp='FI-P-0001', fcomp='2025-09-01', fimp='2025-09-01', cimp='DEUDA POR APORTE NO VIGENTE'),
        # Factura oficial con concepto exento y el documento excluido
        _linea(108, 'VENTA BIENES DE USO', 'VENTAS', 'FC-A-0001', '2025-04-01', 1210, 1000, 210, 0),
        _linea(108, 'CHEQUE RECHAZADO', 'CHEQUES', 'CH-20190722105522839', '2019-07-22', 999, 0, 0, 0),
        # Concepto sin regla
        _linea(109, 'GASTOS VARIOS', 'OTROS', 'FI-0009', '2026-01-15', 121, 100, 21, 0),
        # Imputación condicional fuera del agrupador, en otro fondo
        _linea(110, 'INCOBRABLES FRG', 'MORA', 'FI-0010', '2024-02-01', 200, 200, 0, 0, exp='E10', op='O10', fondo='FONDO B'),
        _linea(110, 'INCOBRABLES FRG', 'MORA', 'FI-0010', '2024-02-01', -200, -200, 0, 0, comp='RC-0010', fcomp='2024-03-01', fimp='2024-03-01', cimp='INCOBRABLES PARTICIPES - GTZ', exp='E10', op='O10', fondo='FONDO B'),
        # Segundo servicio fuera de término (regla mensual vigente)
        _linea(112, S1, 'SERVICIOS', 'FC-0011', '2025-10-05', 605, 500, 105, 0, aporte='A112'),
        _linea(112, S2, 'SERVICIOS', 'FC-0012', '2026-09-20', 605, 500, 105, 0, aporte='A112'),
        # Servicio sin número de aporte
        _linea(113, S1, 'SERVICIOS', 'FC-0013', '2026-06-01', 605, 500, 105, 0),
        # Pendiente sin identificador
        _linea(114, 'MOVIMIENTOS PENDIENTES', 'PENDIENTES', '', '', -50, -50, 0, 0),
        # Concepto de imputación distinto
        _linea(115, 'COMISION FRG', 'COMISIONES', 'FI-0015', '2026-02-01', 121, 100, 21, 0, exp='E15', op='O15'),
        _linea(115, 'COMISION FRG', 'COMISIONES', 'FI-0015', '2026-02-01', -121, -100, -21, 0, comp='RC-0015', fcomp='2026-02-10', fimp='2026-02-10', cimp='OTRO CONCEPTO', exp='E15', op='O15'),
        # Suma por línea que no cierra
        _linea(116, 'COMISION FRG', 'COMISIONES', 'FI-0016', '2025-11-01', 1210, 1000, 200, 0, exp='E16', op='O16'),
        # Servicio histórico (2º en 2025) y servicios duplicados
        _linea(117, S1, 'SERVICIOS', 'FC-0017', '2024-03-01', 605, 500, 105, 0, aporte='A117'),
        _linea(117, S2, 'SERVICIOS', 'FC-0018', '2025-03-15', 605, 500, 105, 0, aporte='A117'),
        _linea(118, S1, 'SERVICIOS', 'FC-0019', '2024-05-01', 605, 500, 105, 0, aporte='A118'),
        _linea(118, S1, 'SERVICIOS', 'FC-0020', '2024-05-02', 605, 500, 105, 0, aporte='A118'),
    ]


def tabla_fixture(filas=None):
    return [COLUMNAS] + [[f[c] for c in COLUMNAS] for f in (filas if filas is not None else filas_fixture())]


def fixture_xlsx(path):
    return xlsx_sintetico(path, [('Hoja1', tabla_fixture())])


def fixture_tramos(carpeta, corte_en=15):
    """Dos tramos (mismo encabezado, filas siguientes). Devuelve [(ruta, fila_inicial_en_el_unico)]."""
    filas = filas_fixture()
    a = xlsx_sintetico(carpeta / 'historico_1.xlsx', [('Hoja1', tabla_fixture(filas[:corte_en]))])
    b = xlsx_sintetico(carpeta / 'historico_2.xlsx', [('Hoja1', tabla_fixture(filas[corte_en:]))])
    return [a, b], corte_en


def canon(v):
    if v is None:
        return ''
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, datetime):
        return v.date().isoformat() if not (v.hour or v.minute or v.second) else v.isoformat()
    if isinstance(v, float):
        return repr(v)
    return str(v)


def leer_libro(path):
    """{hoja: {'celdas': [[texto, ...], ...], 'naranja': ['C7', ...]}} con openpyxl."""
    import openpyxl
    wb = openpyxl.load_workbook(path)
    salida = {}
    for ws in wb.worksheets:
        celdas = [[canon(c.value) for c in fila] for fila in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column)]
        naranja = [c.coordinate for fila in ws.iter_rows() for c in fila if c.fill is not None and c.fill.fgColor is not None and c.fill.fgColor.rgb == NARANJA]
        salida[ws.title] = {'celdas': celdas, 'naranja': naranja}
    return salida


def slug(nombre):
    import unicodedata
    s = ''.join(ch for ch in unicodedata.normalize('NFKD', nombre) if not unicodedata.combining(ch))
    return s.replace(' ', '_')


def leer_dorado(libro, hoja):
    with (DORADOS / f'{libro}__{slug(hoja)}.csv').open(encoding='utf-8', newline='') as f:
        return [fila for fila in csv.reader(f)]


class _Silencio:
    """Informador mudo para no ensuciar la salida de los tests."""
    def log(self, m): pass
    def paso(self, m): pass
    def progreso(self, v, m=''): pass


def correr(tramos, salida, parametros=None, nombres=None):
    p = {'salidas_a_generar': list(LIBROS)}
    p.update(parametros or {})
    return motor.ejecutar(tramos, salida, CORTE, p, _Silencio(), nombres=nombres)


def hoja_a_dicts(libro):
    """[{columna: texto}] por hoja a partir de leer_libro (encabezados en la fila 5, datos desde la 6)."""
    salida = {}
    for hoja, d in libro.items():
        celdas = d['celdas']
        enc = celdas[4]
        salida[hoja] = [dict(zip(enc, fila)) for fila in celdas[5:]]
    return salida


SERVICIOS = 'Control_Servicios_Administrativos'
HOJAS_SERVICIOS = ['Mes en curso', 'No exigibles', 'Histórico']


class ControlesSgaDoradoTests(unittest.TestCase):
    def test_igual_a_dorado_seis_libros(self):
        marcas = json.loads((DORADOS / 'marcas.json').read_text(encoding='utf-8'))
        with carpeta_temporal() as d:
            fx = fixture_xlsx(d / 'historico.xlsx')
            reports, _, _ = correr([fx], d / 'salidas')
            for libro in LIBROS:
                leido = leer_libro(d / 'salidas' / f'{libro}.xlsx')
                if libro == SERVICIOS:
                    self._servicios_por_mes(leido, reports)
                    continue
                for hoja, datos in leido.items():
                    with self.subTest(libro=libro, hoja=hoja):
                        esperado = leer_dorado(libro, hoja)
                        self.assertEqual(datos['celdas'], esperado)
                        self.assertEqual(datos['naranja'], marcas[libro][hoja])
            reglas = json.loads((d / 'salidas' / 'reglas_propuestas.json').read_text(encoding='utf-8'))
            self.assertEqual(reglas, json.loads((DORADOS / 'reglas_propuestas.json').read_text(encoding='utf-8')))
            ejecucion = json.loads((d / 'salidas' / 'ejecucion.json').read_text(encoding='utf-8'))
            self.assertEqual(ejecucion.pop('archivo'), 'historico.xlsx')
            self.assertEqual(ejecucion.pop('archivos'), ['historico.xlsx'])
            # Servicios por mes (cambio pedido): los futuros dejan de omitirse y pasan a "No exigibles".
            esperado = json.loads((DORADOS / 'ejecucion.json').read_text(encoding='utf-8'))
            futuros = esperado['futuros_no_exigibles_omitidos'].pop(SERVICIOS)
            esperado['salidas'][SERVICIOS] += futuros
            esperado['solapas'][SERVICIOS] = {s['name']: len(s['rows']) for r in reports if r['name'] == SERVICIOS for s in r['sheets']}
            self.assertEqual(ejecucion, esperado)

    def _servicios_por_mes(self, leido, reports):
        """Las filas del legado (Año en curso + Histórico) están todas, cada una en una sola solapa nueva; las únicas
        de más son las que el legado omitía por futuras, y van a No exigibles. Cada solapa respeta su mes."""
        self.assertEqual(list(leido), HOJAS_SERVICIOS)
        legado = [tuple(f) for hoja in ('Año en curso', 'Histórico') for f in leer_dorado(SERVICIOS, hoja)[5:]]
        nuevas = {hoja: [tuple(f) for f in leido[hoja]['celdas'][5:]] for hoja in HOJAS_SERVICIOS}
        todas = [f for filas in nuevas.values() for f in filas]
        for fila in legado:
            self.assertEqual(todas.count(fila), legado.count(fila), fila)
        extra = [f for f in todas if f not in legado]
        self.assertEqual(len(extra), 2)
        self.assertTrue(all(f in nuevas['No exigibles'] for f in extra))
        self.assertEqual(leido['Mes en curso']['celdas'][4], leer_dorado(SERVICIOS, 'Año en curso')[4])
        servicio = next(r for r in reports if r['name'] == SERVICIOS)
        columnas = servicio['sheets'][0]['columns']
        i_mes, i_estado = columnas.index('Mes esperado'), columnas.index('Estado')
        for hoja in servicio['sheets']:
            for fila in hoja['rows']:
                if fila[i_mes]:
                    mes = fila[i_mes]
                    if hoja['name'] == 'Mes en curso':
                        self.assertEqual(mes, '2026-10')
                    elif hoja['name'] == 'Histórico':
                        self.assertLess(mes, '2026-10')
                    else:
                        self.assertTrue(mes > '2026-10' or fila[i_estado] == 'NO_EXIGIBLE')
            self.assertEqual(leido[hoja['name']]['naranja'], [])

    def test_sin_tramos_cada_hoja_tiene_filas(self):
        with carpeta_temporal() as d:
            reports, rules, summary = correr([fixture_xlsx(d / 'h.xlsx')], d / 's')
            self.assertEqual(summary['lineas'], 34)
            self.assertEqual(summary['lineas_excluidas'], 1)
            for r in reports:
                for s in r['sheets']:
                    self.assertGreater(len(s['rows']), 0, f"{r['name']} / {s['name']}")
            # Servicios administrativos ya no omite los futuros: van a la solapa No exigibles.
            self.assertEqual(summary['futuros_no_exigibles_omitidos'], {})
            self.assertEqual([s['name'] for r in reports if r['name'] == 'Control_Servicios_Administrativos' for s in r['sheets']], HOJAS_SERVICIOS)
            self.assertEqual(rules['COMISION FRG']['datos'], 'EXP_OP')
            self.assertFalse(rules['COMISION FRG']['datos_confirmados'])

    def test_reglas_confirmadas_cambian_estado_a_error(self):
        regla = [{'concepto': 'Comision FRG', 'datos': 'EXP_OP', 'datos_confirmados': 'true', 'agrupador': 'COMISIONES', 'agrupador_confirmado': ''}]
        with carpeta_temporal() as d:
            fx = fixture_xlsx(d / 'h.xlsx')
            correr([fx], d / 'sin_reglas')
            correr([fx], d / 'con_reglas', {'reglas': regla})
            sin = hoja_a_dicts(leer_libro(d / 'sin_reglas' / 'Control_Datos_Obligatorios.xlsx'))['Año en curso']
            con = hoja_a_dicts(leer_libro(d / 'con_reglas' / 'Control_Datos_Obligatorios.xlsx'))['Año en curso']
            fila_sin = next(f for f in sin if f['NumeroComprobanteImputacion'] == 'RC-0001')
            fila_con = next(f for f in con if f['NumeroComprobanteImputacion'] == 'RC-0001')
            self.assertEqual(fila_sin['Estado'], 'ERROR')  # ya hay DATOS_NO_COINCIDEN (ERROR) en la misma fila
            self.assertIn('(regla propuesta)', fila_sin['Motivo'])
            self.assertEqual(fila_con['Estado'], 'ERROR')
            self.assertNotIn('(regla propuesta)', fila_con['Motivo'])
            # El agrupador no se confirmó ('' = False): sigue REVISAR
            agr = hoja_a_dicts(leer_libro(d / 'con_reglas' / 'Control_Concepto_Agrupador.xlsx'))['Año en curso']
            fila_agr = next(f for f in agr if f['NumeroComprobanteImputacion'] == 'RC-0002')
            self.assertEqual(fila_agr['Estado'], 'REVISAR')
            reglas = json.loads((d / 'con_reglas' / 'reglas_propuestas.json').read_text(encoding='utf-8'))
            self.assertEqual(reglas['COMISION FRG'], {'datos': 'EXP_OP', 'datos_confirmados': True, 'agrupador': 'COMISIONES', 'agrupador_confirmado': False})

    def test_agrupador_confirmado_da_error(self):
        regla = [{'concepto': 'COMISION FRG', 'datos': 'EXP_OP', 'datos_confirmados': False, 'agrupador': 'COMISIONES', 'agrupador_confirmado': True}]
        with carpeta_temporal() as d:
            correr([fixture_xlsx(d / 'h.xlsx')], d / 'con_reglas', {'reglas': regla})
            agr = hoja_a_dicts(leer_libro(d / 'con_reglas' / 'Control_Concepto_Agrupador.xlsx'))['Año en curso']
            fila = next(f for f in agr if f['NumeroComprobanteImputacion'] == 'RC-0002')
            self.assertEqual(fila['Estado'], 'ERROR')

    def test_dos_tramos_equivalen_y_agregan_archivo(self):
        with carpeta_temporal() as d:
            uno = fixture_xlsx(d / 'historico.xlsx')
            tramos, corte_en = fixture_tramos(d)
            correr([uno], d / 'uno')
            _, _, resumen = correr(tramos, d / 'dos')
            self.assertEqual(resumen['archivos'], ['historico_1.xlsx', 'historico_2.xlsx'])
            self.assertEqual(resumen['archivo'], 'historico_1.xlsx | historico_2.xlsx')

            def origen_unico(fila):
                # fila del único archivo (encabezado en 1) -> (tramo, fila en el tramo)
                n = int(fila)
                return ('historico_1.xlsx', n) if n - 1 <= corte_en else ('historico_2.xlsx', n - corte_en)

            for libro in LIBROS:
                a = leer_libro(d / 'uno' / f'{libro}.xlsx')
                b = leer_libro(d / 'dos' / f'{libro}.xlsx')
                for hoja in a:
                    with self.subTest(libro=libro, hoja=hoja):
                        ca, cb = a[hoja]['celdas'], b[hoja]['celdas']
                        enc_a, enc_b = ca[4], cb[4]
                        col_fila = next((c for c in ('FilaOrigen', 'Fila SGA') if c in enc_a), None)
                        if col_fila is None:
                            self.assertEqual(enc_a, enc_b)
                            self.assertEqual(ca, cb)
                            self.assertEqual(a[hoja]['naranja'], b[hoja]['naranja'])
                            continue
                        i = enc_a.index(col_fila)
                        self.assertEqual(enc_b, enc_a[:i + 1] + ['Archivo'] + enc_a[i + 1:])
                        self.assertEqual(len(ca), len(cb))
                        self.assertEqual(ca[:4], [f[:len(enc_a)] for f in cb[:4]])  # títulos iguales
                        for fa, fb in zip(ca[5:], cb[5:]):
                            self.assertEqual(fa[:i], fb[:i])
                            self.assertEqual(fa[i + 1:], fb[i + 2:])
                            self.assertEqual(origen_unico(fa[i]), (fb[i + 1], int(fb[i])))
                        # las marcas anaranjadas se corren una columna cuando quedan a la derecha de la fila de origen
                        self.assertEqual(len(a[hoja]['naranja']), len(b[hoja]['naranja']))

    def test_tramo_con_error_nombra_el_archivo(self):
        filas = filas_fixture()
        filas[20]['Importe'] = 'abc'
        with carpeta_temporal() as d:
            a = xlsx_sintetico(d / 'h_1.xlsx', [('Hoja1', tabla_fixture(filas[:15]))])
            b = xlsx_sintetico(d / 'h_2.xlsx', [('Hoja1', tabla_fixture(filas[15:]))])
            with self.assertRaises(ValueError) as cm:
                correr([a, b], d / 's')
            self.assertIn('Fila 7 de h_2.xlsx', str(cm.exception))
            with self.assertRaises(ValueError) as cm:
                correr([xlsx_sintetico(d / 'h.xlsx', [('Hoja1', tabla_fixture(filas))])], d / 's2')
            self.assertEqual(str(cm.exception), "Fila 22: Importe o porcentaje no numerico: 'abc'")

    def test_formula_sin_valor_corta(self):
        with carpeta_temporal() as d:
            ruta = fixture_xlsx(d / 'h.xlsx')
            with ZipFile(ruta) as z:
                partes = {n: z.read(n) for n in z.namelist()}
            hoja = partes['xl/worksheets/sheet1.xml'].decode('utf-8')
            # La celda S3 (Importe de la segunda línea) pasa a ser una fórmula sin resultado guardado.
            inicio = hoja.index('<c r="S3"')
            fin = hoja.index('</c>', inicio) + 4
            hoja = hoja[:inicio] + '<c r="S3"><f>SUM(A1)</f></c>' + hoja[fin:]
            partes['xl/worksheets/sheet1.xml'] = hoja.encode('utf-8')
            roto = d / 'roto.xlsx'
            with ZipFile(roto, 'w') as z:
                for n, b in partes.items():
                    z.writestr(n, b)
            with self.assertRaises(ValueError) as cm:
                correr([roto], d / 's')
            self.assertEqual(str(cm.exception), 'Hay formulas sin resultado guardado. Use el reporte original SGA.')
            self.assertFalse((d / 's' / 'ejecucion.json').exists())

    def test_faltan_columnas_corta(self):
        tabla = tabla_fixture()
        tabla = [[v for v, c in zip(f, COLUMNAS) if c != 'Subrecibo'] for f in tabla]
        with carpeta_temporal() as d:
            ruta = xlsx_sintetico(d / 'h.xlsx', [('Hoja1', tabla)])
            with self.assertRaises(ValueError) as cm:
                correr([ruta], d / 's')
            self.assertEqual(str(cm.exception), 'Faltan columnas: Subrecibo')

    def test_parametros_cambian_las_constantes(self):
        with carpeta_temporal() as d:
            fx = fixture_xlsx(d / 'h.xlsx')
            # Sin documento excluido, la línea CH-... entra y rompe la suma por línea
            _, _, resumen = correr([fx], d / 'a', {'documentos_excluidos': []})
            self.assertEqual(resumen['lineas_excluidas'], 0)
            self.assertEqual(resumen['comprobantes_excluidos'], [])
            netos = hoja_a_dicts(leer_libro(d / 'a' / 'Control_Netos_Impuestos.xlsx'))['Histórico']
            self.assertTrue(any(f['NumeroFactura'] == 'CH-20190722105522839' for f in netos))
            # Con la regla mensual desde 2025-01-01, el segundo servicio de 2026-02 ya no es "histórico"
            _, _, _ = correr([fx], d / 'b', {'inicio_regla_mensual': '2025-01-01'})
            serv = [f for filas in hoja_a_dicts(leer_libro(d / 'b' / 'Control_Servicios_Administrativos.xlsx')).values() for f in filas]
            fila = next(f for f in serv if f['NumeroDeAporte'] == 'A103')
            self.assertEqual(fila['Estado'], 'OK')
            # Si FI- también es oficial, la factura abierta FI-0002 deja de listarse
            _, _, resumen = correr([fx], d / 'c', {'facturas_oficiales': ['FC-A', 'FC-B', 'FE-A', 'FI-0002']})
            abiertos = hoja_a_dicts(leer_libro(d / 'c' / 'Comprobantes_Abiertos.xlsx'))['Comprobantes abiertos']
            self.assertFalse(any(f['Comprobante'] == 'FI-0002' for f in abiertos))
            # Tolerancia amplia: desaparece la suma por línea de FI-0016 (diferencia 10)
            _, _, _ = correr([fx], d / 'd', {'tolerancia': '10'})
            netos = hoja_a_dicts(leer_libro(d / 'd' / 'Control_Netos_Impuestos.xlsx'))['Histórico']
            self.assertFalse(any(f['NumeroFactura'] == 'FI-0016' for f in netos))


class EjecutarTests(unittest.TestCase):
    def _trabajo(self, d, parametros, tramos):
        d.mkdir(parents=True, exist_ok=True)
        (d / 'parametros.json').write_text(json.dumps(parametros, ensure_ascii=False), encoding='utf-8')
        (d / 'entradas.json').write_text(json.dumps({'sga': [{'ruta': str(r), 'nombre': n, 'sha256': ''} for r, n in tramos]}), encoding='utf-8')
        return d

    def _correr(self, trabajo):
        env = dict(os.environ, REPORTES_PROTOCOLO='1', PYTHONIOENCODING='utf-8')
        p = subprocess.run([sys.executable, '-I', str(EJECUTAR), '--trabajo', str(trabajo)], capture_output=True, text=True, encoding='utf-8', env=env, cwd=str(trabajo))
        eventos = [json.loads(l) for l in p.stdout.splitlines() if l.startswith('{')]
        return p, eventos

    def test_ejecutar_vuelca_once_tablas_y_resumen(self):
        with carpeta_temporal() as d:
            fx = fixture_xlsx(d / 'h.xlsx')
            trabajo = self._trabajo(d / 'trabajo', {'corte': '2026-10-31', 'salidas_a_generar': list(LIBROS)}, [(fx, 'historico (1).xlsx')])
            p, eventos = self._correr(trabajo)
            self.assertEqual(p.returncode, 0, p.stderr)
            tablas = [e for e in eventos if e['t'] == 'tabla']
            self.assertEqual([e['tabla'] for e in tablas], [s['tabla'] for s in SALIDAS])
            resumen = next(e for e in eventos if e['t'] == 'resumen')['datos']
            self.assertEqual(resumen['archivo'], 'historico (1).xlsx')
            self.assertIn('COMISION FRG', resumen['reglas_propuestas'])
            self.assertEqual(resumen['lineas'], 34)
            self.assertTrue(all(not os.path.isabs(str(v)) for v in resumen.values() if isinstance(v, str)))
            for nombre in [l + '.xlsx' for l in LIBROS] + ['reglas_propuestas.json', 'ejecucion.json']:
                self.assertTrue((trabajo / 'salidas' / nombre).is_file(), nombre)
            con = sqlite3.connect(str(trabajo / 'resultados.sqlite'))
            nombres = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 't_%'")}
            self.assertEqual(nombres, {'t_' + s['tabla'] for s in SALIDAS})
            cols = [r[2] for r in con.execute("SELECT * FROM _columnas WHERE tabla='netos_mora' ORDER BY posicion")]
            self.assertEqual(cols[:2], ['Control', 'Qué hay que corregir'])
            self.assertIn('Fila SGA', cols)
            fila = con.execute('SELECT * FROM t_netos_mora').fetchone()
            valores = dict(zip(['_fila', '_clave', '_estado', '_obs', '_origen', '_fecha', '_marcas'] + cols, fila))
            self.assertEqual(valores['FechaFactura'], '2024-06-01')
            self.assertEqual(valores['Importe'], '-40')
            self.assertEqual(valores['Fila SGA'], '15')
            self.assertEqual(json.loads(valores['_marcas']), ['ImporteNetoGravado', 'ImporteIVA', 'Saldo neto', 'Saldo IVA'])
            self.assertEqual(valores['_clave'].split('\x1f'), ['FONDO A', '105', 'FI-0008', 'RC-0005', '15'])
            # Las fechas de la solapa de servicios también van en texto ISO
            fechas = [r[0] for t in ('servicios_mes', 'servicios_historico', 'servicios_noexigibles') for r in con.execute(f"SELECT c9 FROM t_{t}")]
            self.assertTrue(all(f == '' or len(f) == 10 for f in fechas), fechas)
            # Comprobantes abiertos: la fecha faltante queda marcada
            marcas = [json.loads(r[0]) for r in con.execute("SELECT _marcas FROM t_abiertos WHERE _marcas IS NOT NULL")]
            self.assertIn(['FechaComprobante'], marcas)
            con.close()

    def test_salidas_a_generar_omite_libros(self):
        with carpeta_temporal() as d:
            fx = fixture_xlsx(d / 'h.xlsx')
            trabajo = self._trabajo(d / 't', {'corte': '2026-10-31', 'salidas_a_generar': ['Saldo_MORA', 'Comprobantes_Abiertos']}, [(fx, 'h.xlsx')])
            p, eventos = self._correr(trabajo)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(sorted(x.name for x in (trabajo / 'salidas').iterdir()), ['Comprobantes_Abiertos.xlsx', 'Saldo_MORA.xlsx', 'ejecucion.json', 'reglas_propuestas.json'])
            self.assertEqual([e['tabla'] for e in eventos if e['t'] == 'tabla'], ['abiertos', 'saldo_mora'])
            resumen = next(e for e in eventos if e['t'] == 'resumen')['datos']
            self.assertEqual(set(resumen['salidas']), set(LIBROS))  # el cálculo se hace igual

    def test_ejecutar_ordena_tramos_por_nombre_y_reporta_error_llano(self):
        with carpeta_temporal() as d:
            tramos, _ = fixture_tramos(d)
            # En el server la ruta lleva un prefijo; el orden sale del nombre original
            (d / 'zz-historico_1.xlsx').write_bytes(tramos[0].read_bytes())
            (d / 'aa-historico_2.xlsx').write_bytes(tramos[1].read_bytes())
            trabajo = self._trabajo(d / 't', {'corte': '2026-10-31'}, [(d / 'aa-historico_2.xlsx', 'historico_2.xlsx'), (d / 'zz-historico_1.xlsx', 'historico_1.xlsx')])
            p, eventos = self._correr(trabajo)
            self.assertEqual(p.returncode, 0, p.stderr)
            resumen = next(e for e in eventos if e['t'] == 'resumen')['datos']
            self.assertEqual(resumen['archivos'], ['historico_1.xlsx', 'historico_2.xlsx'])
            con = sqlite3.connect(str(trabajo / 'resultados.sqlite'))
            cols = [r[2] for r in con.execute("SELECT * FROM _columnas WHERE tabla='datos_anio' ORDER BY posicion")]
            self.assertEqual(cols[-2:], ['FilaOrigen', 'Archivo'])
            con.close()
            # Error esperable: fórmula sin valor -> evento error y salida 1
            roto = d / 'roto.xlsx'
            with ZipFile(tramos[0]) as z:
                partes = {n: z.read(n) for n in z.namelist()}
            hoja = partes['xl/worksheets/sheet1.xml'].decode('utf-8').replace('<c r="S3" t="inlineStr"><is><t>-605.00</t></is></c>', '<c r="S3"><f>SUM(A1)</f></c>')
            self.assertIn('<f>', hoja)
            partes['xl/worksheets/sheet1.xml'] = hoja.encode('utf-8')
            with ZipFile(roto, 'w') as z:
                for n, b in partes.items():
                    z.writestr(n, b)
            trabajo2 = self._trabajo(d / 't2', {'corte': '2026-10-31'}, [(roto, 'roto.xlsx')])
            p, eventos = self._correr(trabajo2)
            self.assertEqual(p.returncode, 1)
            self.assertEqual(next(e for e in eventos if e['t'] == 'error')['m'], 'Hay formulas sin resultado guardado. Use el reporte original SGA.')


if __name__ == '__main__':
    unittest.main()
