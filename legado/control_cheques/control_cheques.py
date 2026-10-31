"""Control de estados de cheques SGA contra ERP. Requiere openpyxl."""
import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import sys


def texto(valor):
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def id_erp(valor):
    valor = texto(valor)
    return 'gtz-' + valor[5:] if valor.startswith('10000') else valor


def leer(path, requeridas):
    from openpyxl import load_workbook
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


def controlar(sga, erp, destino):
    equivalencias = {'rechazado': 'rechazado', 'depositado': 'depositado', 'en cartera': 'acreditado'}
    indice = defaultdict(list)
    resumen = Counter()
    for dato, fila in leer(erp, ['Id de Transacción', 'Estado', 'Pagado a']):
        resumen['Filas ERP'] += 1
        clave = texto(dato['Id de Transacción'])
        if clave:
            indice[clave].append((dato, fila))
        else:
            resumen['Filas ERP sin ID (no se pueden cruzar)'] += 1
    revisiones = []
    def agregar(dato, fila, clave, motivo, encontrados):
        revisiones.append({
            'Motivo': motivo, 'ID ERP': clave, 'ID SGA': texto(dato['IdCheque']),
            'Empresa': texto(dato.get('RazonSocial')), 'CUIT': texto(dato.get('Cuit')),
            'Numero cheque': texto(dato.get('NumeroCheque')), 'Importe SGA': dato.get('Importe'),
            'Estado SGA': texto(dato['Estado']),
            'Estado ERP': ' / '.join(texto(x[0]['Estado']) for x in encontrados),
            'Fila SGA': fila, 'Filas ERP': ' / '.join(str(x[1]) for x in encontrados)})
    for dato, fila in leer(sga, ['IdCheque', 'Estado']):
        resumen['Filas SGA'] += 1
        if texto(dato['IdCheque']).startswith('563'):
            resumen['Validos: ID historico 563'] += 1
            continue
        clave = id_erp(dato['IdCheque'])
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
            if estado in ('debitado', 'entregado') or texto(registro['Pagado a']):
                resumen['Excluidos: Pago a Proveedores'] += 1
                continue
            if estado == 'canjeado':
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
        agregar(dato, fila, clave, motivo, encontrados)
    resumen['Total para revisar'] = len(revisiones)
    destino.mkdir(parents=True, exist_ok=False)
    campos = ['Motivo', 'ID ERP', 'ID SGA', 'Empresa', 'CUIT', 'Numero cheque', 'Importe SGA', 'Estado SGA', 'Estado ERP', 'Fila SGA', 'Filas ERP']
    with (destino / 'Cheques_para_revisar.csv').open('w', encoding='utf-8-sig', newline='') as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos, delimiter=';')
        escritor.writeheader()
        for dato in revisiones:
            if isinstance(dato['Importe SGA'], (int, float)):
                dato['Importe SGA'] = f"{dato['Importe SGA']:.2f}".replace('.', ',')
            escritor.writerow(dato)
    with (destino / 'Resumen.txt').open('w', encoding='utf-8') as archivo:
        archivo.write(f'CONTROL DE CHEQUES\nSGA: {sga}\nERP: {erp}\n\n')
        for etiqueta, cantidad in resumen.items():
            archivo.write(f'{etiqueta}: {cantidad:,}\n')
        archivo.write('\nAlcance: estados de los cheques presentes en SGA. No compara importes ni fechas.\nLos ID se comparan exactamente, conservando ceros, tras reemplazar el prefijo 10000 por gtz-.\nNo se usa IdCheque2 ni las columnas auxiliares. No se exige que todos los registros ERP aparezcan en SGA.\nLos ID duplicados en ERP se revisan sin elegir arbitrariamente una coincidencia.\n')
    return resumen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sga', type=Path)
    parser.add_argument('--erp', type=Path)
    parser.add_argument('--salida', type=Path, default=Path(__file__).resolve().parent / 'resultados')
    args = parser.parse_args()
    if bool(args.sga) != bool(args.erp):
        parser.error('Indicar ambos archivos --sga y --erp, o ninguno para usar entrada.')
    if not args.sga:
        from openpyxl import load_workbook
        entrada = Path(__file__).resolve().parent / 'entrada'
        entrada.mkdir(exist_ok=True)
        candidatos = {'sga': [], 'erp': []}
        for archivo in sorted(entrada.iterdir()):
            if not archivo.is_file() or archivo.suffix.lower() != '.xlsx' or archivo.name.startswith('~$'):
                continue
            libro = load_workbook(archivo, read_only=True, data_only=True)
            try:
                tipos = set()
                for hoja in libro:
                    columnas = {texto(v) for v in next(hoja.iter_rows(values_only=True), ())}
                    if {'IdCheque', 'Estado'}.issubset(columnas):
                        tipos.add('sga')
                    if {'Id de Transacción', 'Estado', 'Pagado a'}.issubset(columnas):
                        tipos.add('erp')
                if len(tipos) > 1:
                    raise ValueError(f'{archivo.name}: contiene datos de SGA y ERP. Usar archivos separados.')
                for tipo in tipos:
                    candidatos[tipo].append(archivo)
            finally:
                libro.close()
        for tipo, archivos in candidatos.items():
            if len(archivos) != 1:
                raise ValueError(f'En entrada debe haber un solo reporte {tipo.upper()}. Detectados: {len(archivos)}. Dejar los dos Excel del cierre que se quiere controlar.')
        args.sga = candidatos['sga'][0]
        args.erp = candidatos['erp'][0]
    print(f'SGA: {args.sga.name}\nERP: {args.erp.name}\nProcesando, por favor espera...', flush=True)
    destino = args.salida / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    resumen = controlar(args.sga.resolve(), args.erp.resolve(), destino)
    print('\n'.join(f'{k}: {v:,}' for k, v in resumen.items()))
    print(f'\nResultados guardados en: {destino.resolve()}')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'No se pudo completar el control: {error}', file=sys.stderr)
        sys.exit(1)
