"""Regenera los dorados sintéticos de Conciliación general.

    py -3 tests/dorados/conciliacion_general/generar.py

Por cada caso deja:
  <caso>/entradas/       los libros sintéticos (las salidas llevan su SHA-256, por eso se guardan juntos);
  <caso>/legado_1_4/     las salidas del script de legado/ (v1.4);
  <caso>/                las salidas del motor actual (v1.5): Conciliacion_general.csv, Resumen.json y cada hoja
                         del XLSX como xlsx_<hoja>.csv.
El test verifica que el motor siga dando los dorados v1.5 y que toda diferencia con el legado esté explicada por
los cambios acordados (herramientas/cambios_conciliacion.py). Regenerar sólo cuando un cambio de reglas lo pida,
y revisar el diff de los dorados antes de aceptarlo.

Casos: `unificado` (1 SGA + 1 ERP), `separado` (1 SGA + 3 ERP por tipo) y `reglas_1_5` (los casos de los cambios de
la v1.5: pendiente de un FI-P, recibos RC-X/RC-R y orden de pago OP-X por subrecibo, ausentes en ERP con saldo cero
y distinto de cero). Datos inventados: nunca reales."""
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
for ruta in (RAIZ, RAIZ / 'vendor', RAIZ / 'legado' / 'conciliacion_general'):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

from tests.fixtures import xlsx_sintetico  # noqa: E402
from tests.test_conciliacion_general import (FONDO, E, SGA_FILAS, ERP_FILAS, SGA_REGLAS_15, ERP_REGLAS_15,  # noqa: E402
                                             hojas_xlsx_a_csv, Silencio)
from app.reportes.conciliacion_general import motor  # noqa: E402
import conciliar  # noqa: E402  (legado)

CASOS = {
    'unificado': lambda c: (xlsx_sintetico(c / 'cualquier_sga.xlsx', [('Resumen', [['Saldo', 'Importe']]), ('Original', SGA_FILAS)]),
                            xlsx_sintetico(c / 'erp_12345.xlsx', [('FAC', [['Factura', 'Saldo2']]), ('Original', [E] + ERP_FILAS)])),
    'separado': lambda c: (xlsx_sintetico(c / 'cualquier_sga.xlsx', [('Resumen', [['Saldo', 'Importe']]), ('Original', SGA_FILAS)]),
                           *[xlsx_sintetico(c / f'descarga_{i}.xlsx', [('Datos', [E] + [r for r in ERP_FILAS if r[6] == tx])])
                             for i, tx in enumerate(['Cliente', 'Pago', 'Diario general'])]),
    'reglas_1_5': lambda c: (xlsx_sintetico(c / 'sga_reglas.xlsx', [('Datos', SGA_REGLAS_15)]),
                             xlsx_sintetico(c / 'erp_reglas.xlsx', [('Datos', [E] + ERP_REGLAS_15)])),
}


def entradas_de(caso):
    e = AQUI / caso / 'entradas'
    archivos = sorted(e.iterdir())
    sga = [p for p in archivos if 'sga' in p.name]
    return {'sga': sga, 'erp': [p for p in archivos if p not in sga]}


def generar(caso):
    destino = AQUI / caso
    if destino.exists():
        shutil.rmtree(destino)
    (destino / 'entradas').mkdir(parents=True)
    CASOS[caso](destino / 'entradas')
    with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
        base = Path(tmp)
        (base / 'configuracion.json').write_text(json.dumps({'fondo': FONDO}), encoding='utf-8')
        salida = conciliar.run(base, destino / 'entradas', 'abiertos', '2026-10-31')
        legado = destino / 'legado_1_4'
        legado.mkdir()
        shutil.copy(salida / 'Respaldo_tecnico' / 'Conciliacion_general.csv', legado / 'Conciliacion_general.csv')
        shutil.copy(salida / 'Respaldo_tecnico' / 'Resumen.json', legado / 'Resumen.json')
        hojas_xlsx_a_csv(salida / 'Conciliacion_general.xlsx', legado)
    with tempfile.TemporaryDirectory() as tmp:
        motor.run(entradas_de(caso), Path(tmp), 'abiertos', '2026-10-31', FONDO, informar=Silencio())
        shutil.copy(Path(tmp) / 'Respaldo_tecnico' / 'Conciliacion_general.csv', destino / 'Conciliacion_general.csv')
        shutil.copy(Path(tmp) / 'Respaldo_tecnico' / 'Resumen.json', destino / 'Resumen.json')
        hojas_xlsx_a_csv(Path(tmp) / 'Conciliacion_general.xlsx', destino)
    print(caso, 'listo')


if __name__ == '__main__':
    for nombre in CASOS:
        generar(nombre)
