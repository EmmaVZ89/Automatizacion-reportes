"""Control de estados de cheques SGA contra ERP. Requiere openpyxl (vendor/).

Es el script de legado/control_cheques con los cambios mínimos: parámetros explícitos en lugar de
constantes, entradas en uno o más tramos y mensajes por `informar` (el módulo protocolo)."""
import csv
from collections import Counter, defaultdict
from pathlib import Path

from .._comun import protocolo

CAMPOS = ['Motivo', 'ID ERP', 'ID SGA', 'Empresa', 'CUIT', 'Numero cheque', 'Importe SGA', 'Estado SGA', 'Estado ERP', 'Fila SGA', 'Filas ERP']
COLUMNAS_SGA = ['IdCheque', 'Estado']
COLUMNAS_ERP = ['Id de Transacción', 'Estado', 'Pagado a']
PARAMETROS_DEFAULT = {
    'prefijos_historicos': ['563'],
    'prefijo_sga': '10000',
    'prefijo_erp': 'gtz-',
    'equivalencias': [{'erp': 'rechazado', 'sga': 'rechazado'}, {'erp': 'depositado', 'sga': 'depositado'}, {'erp': 'en cartera', 'sga': 'acreditado'}],
    'estados_proveedores': ['debitado', 'entregado'],
    'estados_validos': ['canjeado'],
}


def texto(valor):
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def id_erp(valor, prefijo_sga, prefijo_erp):
    valor = texto(valor)
    return prefijo_erp + valor[len(prefijo_sga):] if valor.startswith(prefijo_sga) else valor


def leer(path, requeridas):
    from openpyxl import load_workbook
    path = Path(path)
    libro = load_workbook(path, read_only=True, data_only=True)
    try:
        candidatas = []
        for hoja in libro:
            encabezado = next(hoja.iter_rows(values_only=True), ())
            nombres = [texto(v) for v in encabezado]
            if set(requeridas).issubset(nombres):
                candidatas.append((hoja, nombres))
        if len(candidatas) != 1:
            raise ValueError(f'{path.name}: se esperaba una única hoja con columnas {requeridas}; se encontraron {len(candidatas)}.')
        hoja, nombres = candidatas[0]
        for fila, valores in enumerate(hoja.iter_rows(min_row=2, values_only=True), 2):
            if any(v is not None for v in valores):
                yield dict(zip(nombres, valores)), fila
    finally:
        libro.close()


def leer_tramos(paths, requeridas):
    """Lee los tramos en secuencia: (dato, fila, nombre_de_archivo)."""
    for path in paths:
        path = Path(path)
        for dato, fila in leer(path, requeridas):
            yield dato, fila, path.name


def _lista(valores):
    return [texto(v).casefold() for v in (valores or []) if texto(v)]


def controlar(sga, erp, destino, parametros=None, informar=protocolo):
    """sga, erp: listas de rutas (tramos ya ordenados). Escribe Cheques_para_revisar.csv y Resumen.txt en destino.
    Devuelve el Counter del resumen."""
    sga = [Path(p) for p in (sga if isinstance(sga, (list, tuple)) else [sga])]
    erp = [Path(p) for p in (erp if isinstance(erp, (list, tuple)) else [erp])]
    destino = Path(destino)
    p = dict(PARAMETROS_DEFAULT)
    p.update({k: v for k, v in (parametros or {}).items() if v is not None})
    prefijos_historicos = tuple(texto(x) for x in (p['prefijos_historicos'] or []) if texto(x))
    prefijo_sga = texto(p['prefijo_sga'])
    prefijo_erp = texto(p['prefijo_erp'])
    equivalencias = {texto(e.get('erp')).casefold(): texto(e.get('sga')).casefold() for e in (p['equivalencias'] or []) if texto(e.get('erp'))}
    estados_proveedores = _lista(p['estados_proveedores'])
    estados_validos = _lista(p['estados_validos'])
    varios_sga = len(sga) > 1
    varios_erp = len(erp) > 1

    informar.paso('Leyendo ERP')
    indice = defaultdict(list)
    resumen = Counter()
    for dato, fila, archivo in leer_tramos(erp, COLUMNAS_ERP):
        resumen['Filas ERP'] += 1
        if resumen['Filas ERP'] % 20000 == 0:
            informar.progreso(0.3, f"{resumen['Filas ERP']:,} filas ERP".replace(',', '.'))
        clave = texto(dato['Id de Transacción'])
        if clave:
            indice[clave].append((dato, fila, archivo))
        else:
            resumen['Filas ERP sin ID (no se pueden cruzar)'] += 1
    revisiones = []
    def agregar(dato, fila, archivo, clave, motivo, encontrados):
        revision = {
            'Motivo': motivo, 'ID ERP': clave, 'ID SGA': texto(dato['IdCheque']),
            'Empresa': texto(dato.get('RazonSocial')), 'CUIT': texto(dato.get('Cuit')),
            'Numero cheque': texto(dato.get('NumeroCheque')), 'Importe SGA': dato.get('Importe'),
            'Estado SGA': texto(dato['Estado']),
            'Estado ERP': ' / '.join(texto(x[0]['Estado']) for x in encontrados),
            'Fila SGA': fila, 'Filas ERP': ' / '.join(str(x[1]) for x in encontrados)}
        if varios_sga:
            revision['Archivo SGA'] = archivo
        if varios_erp:
            revision['Archivos ERP'] = ' / '.join(x[2] for x in encontrados)
        revisiones.append(revision)
    informar.paso('Controlando SGA')
    for dato, fila, archivo in leer_tramos(sga, COLUMNAS_SGA):
        resumen['Filas SGA'] += 1
        if resumen['Filas SGA'] % 20000 == 0:
            informar.progreso(0.7, f"{resumen['Filas SGA']:,} filas SGA".replace(',', '.'))
        if prefijos_historicos and texto(dato['IdCheque']).startswith(prefijos_historicos):
            resumen['Validos: ID historico 563'] += 1
            continue
        clave = id_erp(dato['IdCheque'], prefijo_sga, prefijo_erp)
        encontrados = indice.get(clave, [])
        motivo = ''
        if not clave:
            motivo = 'Falta ID en SGA'
        elif not encontrados:
            motivo = 'ID no encontrado en ERP'
        elif len(encontrados) > 1:
            motivo = 'ID duplicado en ERP: revisar antes de comparar'
        else:
            registro = encontrados[0][0]
            estado = texto(registro['Estado']).casefold()
            if estado in estados_proveedores or texto(registro['Pagado a']):
                resumen['Excluidos: Pago a Proveedores'] += 1
                continue
            if estado in estados_validos:
                resumen['Validos: Canjeado historico'] += 1
                continue
            if estado == 'cancelado':
                motivo = 'Cancelado en ERP presente en SGA'
            elif estado not in equivalencias:
                motivo = 'Estado ERP sin regla definida'
            elif texto(dato['Estado']).casefold() != equivalencias[estado]:
                motivo = 'Diferencia de estado'
            else:
                resumen['Estados coincidentes'] += 1
                continue
        resumen[motivo] += 1
        agregar(dato, fila, archivo, clave, motivo, encontrados)
    resumen['Total para revisar'] = len(revisiones)
    informar.paso('Escribiendo resultados')
    destino.mkdir(parents=True, exist_ok=True)
    campos = list(CAMPOS)
    if varios_sga:
        campos.insert(campos.index('Fila SGA') + 1, 'Archivo SGA')
    if varios_erp:
        campos.insert(campos.index('Filas ERP') + 1, 'Archivos ERP')
    with (destino / 'Cheques_para_revisar.csv').open('w', encoding='utf-8-sig', newline='') as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos, delimiter=';')
        escritor.writeheader()
        for dato in revisiones:
            if isinstance(dato['Importe SGA'], (int, float)):
                dato['Importe SGA'] = f"{dato['Importe SGA']:.2f}".replace('.', ',')
            escritor.writerow(dato)
    with (destino / 'Resumen.txt').open('w', encoding='utf-8') as archivo:
        archivo.write(f"CONTROL DE CHEQUES\nSGA: {' / '.join(x.name for x in sga)}\nERP: {' / '.join(x.name for x in erp)}\n\n")
        for etiqueta, cantidad in resumen.items():
            archivo.write(f'{etiqueta}: {cantidad:,}\n')
        archivo.write(f'\nAlcance: estados de los cheques presentes en SGA. No compara importes ni fechas.\nLos ID se comparan exactamente, conservando ceros, tras reemplazar el prefijo {prefijo_sga} por {prefijo_erp}.\nNo se usa IdCheque2 ni las columnas auxiliares. No se exige que todos los registros ERP aparezcan en SGA.\nLos ID duplicados en ERP se revisan sin elegir arbitrariamente una coincidencia.\n')
    for etiqueta, cantidad in resumen.items():
        informar.log(f'{etiqueta}: {cantidad:,}')
    return resumen
