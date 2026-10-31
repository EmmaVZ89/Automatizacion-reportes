"""Regenera los dorados de Controles SGA corriendo el script del legado sobre el fixture sintético.
Uso (desde la raíz del proyecto): py -3 tests/dorados/controles_sga/generar.py
Deja: fixture_sga.xlsx, <Libro>__<hoja>.csv (una por solapa, valores leídos con openpyxl), marcas.json
(celdas anaranjadas), reglas_propuestas.json y ejecucion.json (sin las claves variables)."""
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
for ruta in (RAIZ, RAIZ / 'vendor'):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

from tests.test_controles_sga import LIBROS, fixture_xlsx, leer_libro, slug  # noqa: E402

LEGADO = RAIZ / 'legado' / 'controles_sga' / 'control_sga.py'


def main():
    fixture = fixture_xlsx(AQUI / 'fixture_sga.xlsx')
    tmp = Path(tempfile.mkdtemp(prefix='dorado_sga_'))
    try:
        subprocess.run([sys.executable, str(LEGADO), str(fixture), '--corte', '2026-10-31', '--salida', str(tmp)], check=True, cwd=str(LEGADO.parent))
        carpeta = next(p for p in tmp.iterdir() if p.is_dir())
        for viejo in AQUI.glob('*.csv'):
            viejo.unlink()
        marcas = {}
        for libro in LIBROS:
            leido = leer_libro(carpeta / f'{libro}.xlsx')
            marcas[libro] = {}
            for hoja, datos in leido.items():
                with (AQUI / f'{libro}__{slug(hoja)}.csv').open('w', encoding='utf-8', newline='') as f:
                    csv.writer(f).writerows(datos['celdas'])
                marcas[libro][hoja] = datos['naranja']
        (AQUI / 'marcas.json').write_text(json.dumps(marcas, ensure_ascii=False, indent=1), encoding='utf-8')
        shutil.copy(carpeta / 'reglas_propuestas.json', AQUI / 'reglas_propuestas.json')
        ejecucion = json.loads((carpeta / 'ejecucion.json').read_text(encoding='utf-8'))
        ejecucion.pop('archivo', None)
        (AQUI / 'ejecucion.json').write_text(json.dumps(ejecucion, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Dorados regenerados en', AQUI)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
