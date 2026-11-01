"""Regresión de Conciliación general v1.5 contra el legado v1.4.

Desde la v1.5 la salida difiere del legado a propósito (tres cambios pedidos por la responsable funcional, ver
docs/reglas/conciliacion_general.md). Este módulo reconstruye, a partir de cada fila del legado, la fila que la v1.5
debería producir aplicando esas reglas, y la compara con la salida nueva. Toda diferencia que las reglas no
explican se informa. La lógica está escrita aparte del motor a propósito: es el oráculo, no una copia.

    explicar(csv_legado, csv_nuevo, alcance) -> (no_explicadas: list[str], explicadas: Counter)
    explicar_resumen(json_legado, json_nuevo, cantidad_pendientes) -> list[str]
    xlsx_consistente(xlsx_nuevo, csv_nuevo) -> list[str]
"""
import csv
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

RE_PRINCIPAL = re.compile(r'^([A-Z]{2,3}-[A-Z])')
RE_TIPO_PRINCIPAL = re.compile(r'^(?:[A-Z]{2,3}-[A-Z])(?: / [A-Z]{2,3}-[A-Z])*$|^SUBRECIBO$')
NOTA_ABIERTOS = 'No figura en el ERP de saldos abiertos: se toma saldo ERP 0,00.'
NOTA_PENDIENTE = 'Movimiento pendiente de imputación de SGA referido a este comprobante: se informa en una fila aparte y no se suma al saldo del comprobante.'
NOTA_SIN_PRINCIPAL = 'No se identificó el comprobante principal (recibo u orden de pago) del subrecibo.'
NOTA_VARIOS_PRINCIPALES = 'El subrecibo figura con comprobantes principales de distinto tipo: revisar.'
NOTA_MP_OTRO_LEGADO = 'Incluye movimiento pendiente identificado por comprobante; revisar su clasificación por separado.'
SIN_IDENTIFICAR = ('SIN COMPROBANTE EN SGA', 'REVISAR IDENTIFICACION')


COLUMNAS_NUEVAS = ('Fecha SGA', 'Fecha ERP')  # informativas, desde el 01/11/2026: el legado no las tiene


def leer_csv(ruta, con_nuevas=False):
    with Path(ruta).open(encoding='utf-8-sig', newline='') as f:
        filas = list(csv.DictReader(f, delimiter=';'))
    if not con_nuevas:  # para comparar con el legado
        for r in filas:
            for c in COLUMNAS_NUEVAS:
                r.pop(c, None)
    return [r for r in filas if r['Tipo'] != 'CONTROL'], [r for r in filas if r['Tipo'] == 'CONTROL']


def dinero(valor):
    v = Decimal(valor).quantize(Decimal('.01'))
    return format(abs(v) if v == 0 else v, '.2f')


def clave(fila, nuevo):
    tipo = fila['Tipo']
    subrecibo = (tipo == 'OP-X') if not nuevo else bool(RE_TIPO_PRINCIPAL.match(tipo))
    return ('SUBRECIBO' if subrecibo else tipo, fila['Cliente'], fila['Comprobante'])


def _tipo_por_principales(detalle):
    tipos = sorted({m.group(1) for a in detalle.split(' | ') for m in [RE_PRINCIPAL.match(a.strip())] if m})
    return ' / '.join(tipos) if tipos else 'SUBRECIBO'


def _aplicar_abiertos(esperada, alcance, contador, etiqueta):
    if alcance != 'abiertos' or esperada['Filas ERP'] != '0' or esperada['Saldo SGA'] == '':
        return []
    if esperada['Resultado'].startswith(SIN_IDENTIFICAR):
        return []
    esperada['Saldo ERP'] = '0.00'
    esperada['Diferencia SGA menos ERP'] = esperada['Saldo SGA']
    esperada['Resultado'] = 'COINCIDE' if Decimal(esperada['Saldo SGA']) == 0 else 'DIFERENCIA'
    contador[f'{etiqueta}abiertos_{esperada["Resultado"].lower()}'] += 1
    return [NOTA_ABIERTOS]


def _comparar(esperada, nueva, contexto):
    errores = []
    for col, valor in esperada.items():
        if nueva.get(col) != valor:
            errores.append(f'{contexto}: columna {col!r}: se esperaba {valor!r}, salió {nueva.get(col)!r}')
    return errores


def explicar(csv_legado, csv_nuevo, alcance):
    datos_l, control_l = leer_csv(csv_legado)
    datos_n, control_n = leer_csv(csv_nuevo)
    no_explicadas = []
    explicadas = Counter()
    pendientes = defaultdict(list)
    for r in datos_n:
        if r['Tipo'] == 'PENDIENTE':
            pendientes[(r['Cliente'], r['Comprobante'])].append(r)
    nuevas = {clave(r, True): r for r in datos_n if r['Tipo'] != 'PENDIENTE'}
    if len(nuevas) + sum(len(v) for v in pendientes.values()) != len(datos_n):
        no_explicadas.append('La salida nueva tiene claves repetidas.')
    usadas = set()
    pendientes_usados = set()
    for l in datos_l:
        k = clave(l, False)
        n = nuevas.get(k)
        contexto = ' / '.join(k)
        if n is None:
            no_explicadas.append(f'{contexto}: la fila del legado no está en la salida nueva')
            continue
        usadas.add(k)
        esperada = dict(l)
        # El motor arma Observaciones uniendo notas con un espacio y las notas nuevas van al final.
        notas = [l['Observaciones']] if l['Observaciones'] else []
        # Cambio 2: el pendiente referido a la factura sale en su propia fila.
        p_lista = pendientes.get((l['Cliente'], l['Comprobante'])) if l['Tipo'] == 'FACTURA' else None
        if p_lista:
            if len(p_lista) != 1:
                no_explicadas.append(f'{contexto}: más de una fila PENDIENTE para el comprobante')
            p = p_lista[0]
            pendientes_usados.add(id(p))
            explicadas['pendiente_separado'] += 1
            esperada['Saldo SGA'] = dinero(Decimal(l['Saldo SGA']) - Decimal(p['Saldo SGA']))
            esperada['Filas SGA'] = str(int(l['Filas SGA']) - int(p['Filas SGA']))
            refs_l = [x for x in l['Origen SGA (primeras 5)'].split(' | ') if x]
            refs_p = [x for x in p['Origen SGA (primeras 5)'].split(' | ') if x]
            if len(refs_l) < 5:
                esperada['Origen SGA (primeras 5)'] = ' | '.join(x for x in refs_l if x not in refs_p)
            else:
                esperada.pop('Origen SGA (primeras 5)')
            texto = l['Observaciones'].replace(NOTA_MP_OTRO_LEGADO, '').replace('  ', ' ').strip()
            notas = [texto] if texto else []
            # La fila PENDIENTE: mismo cliente y comprobante, sin ERP.
            esp_p = {'Tipo': 'PENDIENTE', 'Cliente': l['Cliente'], 'Comprobante': l['Comprobante'], 'CUIT': l['CUIT'], 'Razon social': l['Razon social'],
                     'Saldo ERP': '', 'Diferencia SGA menos ERP': '', 'Filas ERP': '0', 'Origen ERP (primeras 5)': '', 'Estado revision': '',
                     'Fondo': l['Fondo'], 'Detalle identificacion': '', 'Saldo SGA': p['Saldo SGA'], 'Filas SGA': p['Filas SGA'],
                     'Resultado': 'NO EVALUADO - ERP SOLO ABIERTOS' if alcance == 'abiertos' else ('PENDIENTE NUEVA DESCARGA ERP' if Decimal(p['Saldo SGA']) != 0 else 'SOLO SGA SALDO CERO - REVISAR')}
            notas_p = [NOTA_PENDIENTE] + _aplicar_abiertos(esp_p, alcance, explicadas, 'pendiente_')
            esp_p['Observaciones'] = ' '.join(notas_p)
            no_explicadas += _comparar(esp_p, p, contexto + ' / PENDIENTE')
        # Cambio 3: Tipo por comprobante principal; el detalle suma el principal del lado SGA.
        if l['Tipo'] == 'OP-X':
            det_l = {x for x in l['Detalle identificacion'].split(' | ') if x}
            det_n = {x for x in n['Detalle identificacion'].split(' | ') if x}
            extra = det_n - det_l
            if det_l <= det_n and all(RE_PRINCIPAL.match(x) for x in extra):
                esperada['Detalle identificacion'] = n['Detalle identificacion']
                if extra:
                    explicadas['detalle_con_principal_sga'] += 1
            tipo = _tipo_por_principales(esperada['Detalle identificacion'])
            esperada['Tipo'] = tipo
            if tipo != 'OP-X':
                explicadas[f'tipo_{tipo}'] += 1
            if tipo == 'SUBRECIBO':
                notas.append(NOTA_SIN_PRINCIPAL)
            elif ' / ' in tipo:
                notas.append(NOTA_VARIOS_PRINCIPALES)
        # Cambio 1: abiertos, ausente en ERP = ERP 0,00.
        notas += _aplicar_abiertos(esperada, alcance, explicadas, '')
        esperada['Observaciones'] = ' '.join(x for x in notas if x)
        no_explicadas += _comparar(esperada, n, contexto)
    for k in set(nuevas) - usadas:
        no_explicadas.append(f'{" / ".join(k)}: fila nueva que no está en el legado')
    for lista in pendientes.values():
        for p in lista:
            if id(p) not in pendientes_usados:
                no_explicadas.append(f'{p["Cliente"]} / {p["Comprobante"]}: fila PENDIENTE sin factura en el legado')
    no_explicadas += _comparar_controles(control_l, control_n, datos_n)
    return no_explicadas, explicadas


def _comparar_controles(control_l, control_n, datos_n):
    errores = []
    por_l = defaultdict(list)
    por_n = defaultdict(list)
    for r in control_l:
        if not r['Comprobante'].startswith('CANTIDAD: '):
            por_l[r['Comprobante']].append(r)
    for r in control_n:
        if not r['Comprobante'].startswith('CANTIDAD: '):
            por_n[r['Comprobante']].append(r)
    for etiqueta in sorted(set(por_l) | set(por_n)):
        if por_l.get(etiqueta) != por_n.get(etiqueta):
            errores.append(f'Control {etiqueta!r}: distinto del legado')
    recuento = Counter(r['Resultado'] for r in datos_n)
    cantidades = {r['Comprobante'][len('CANTIDAD: '):]: int(r['Resultado']) for r in control_n if r['Comprobante'].startswith('CANTIDAD: ')}
    if cantidades != dict(recuento):
        errores.append(f'Controles CANTIDAD no coinciden con las filas: {cantidades} vs {dict(recuento)}')
    return errores


def explicar_resumen(json_legado, json_nuevo, cantidad_pendientes, datos_nuevos=None):
    l = json.loads(Path(json_legado).read_text(encoding='utf-8-sig'))
    n = json.loads(Path(json_nuevo).read_text(encoding='utf-8-sig'))
    errores = []
    if n.get('version') != '1.5':
        errores.append(f'Resumen: versión {n.get("version")!r}, se esperaba "1.5"')
    if n.get('registros_datos') != l.get('registros_datos', 0) + cantidad_pendientes:
        errores.append(f'Resumen: registros_datos {n.get("registros_datos")} vs legado {l.get("registros_datos")} + {cantidad_pendientes} pendientes')
    if datos_nuevos is not None and n.get('conteos') != dict(Counter(r['Resultado'] for r in datos_nuevos)):
        errores.append('Resumen: conteos no coinciden con las filas')

    def sin_variables(d):
        d = {k: v for k, v in d.items() if k not in ('version', 'registros_datos', 'conteos')}
        d['fuentes'] = [{k: v for k, v in f.items() if k not in ('fecha_descarga',)} for f in d.get('fuentes', [])]
        return d
    if sin_variables(l) != sin_variables(n):
        claves = sorted(k for k in set(sin_variables(l)) | set(sin_variables(n)) if sin_variables(l).get(k) != sin_variables(n).get(k))
        errores.append(f'Resumen: difiere en {claves}')
    return errores


def xlsx_consistente(xlsx_nuevo, csv_nuevo):
    """La hoja de detalle del Excel nuevo tiene exactamente las filas de datos del CSV nuevo."""
    import openpyxl
    datos, _ = leer_csv(csv_nuevo, con_nuevas=True)
    libro = openpyxl.load_workbook(xlsx_nuevo, read_only=True)
    errores = []
    try:
        hoja = libro['Conciliación general']
        filas = hoja.iter_rows(values_only=True)
        encabezado = [str(v) for v in next(filas)]
        numericas = {'Saldo SGA', 'Saldo ERP', 'Diferencia SGA menos ERP', 'Filas SGA', 'Filas ERP'}
        cantidad = 0
        for i, x in enumerate(filas, 2):
            if not any(v not in (None, '') for v in x):
                continue
            cantidad += 1
            if cantidad > len(datos) or len(errores) > 20:
                continue
            c = datos[cantidad - 1]
            for col, v in zip(encabezado, x):
                esperado = c[col]
                if col in numericas and esperado != '':
                    ok = v is not None and Decimal(str(v)) == Decimal(esperado)
                elif col in COLUMNAS_NUEVAS and hasattr(v, 'date'):
                    ok = v.date().isoformat() == esperado  # en el Excel son fechas reales
                else:
                    ok = ('' if v is None else str(v)) == esperado
                if not ok:
                    errores.append(f'Excel fila {i} columna {col!r}: {v!r} vs CSV {esperado!r}')
                    break
        if cantidad != len(datos):
            errores.append(f'Excel: {cantidad} filas de detalle vs {len(datos)} en el CSV')
    finally:
        libro.close()
    return errores
