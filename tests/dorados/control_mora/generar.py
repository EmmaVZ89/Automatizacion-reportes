"""Regenera el dorado del Control de Mora corriendo el script del legado sobre el fixture sintético de
tests/test_control_mora.py. Se corre desde la raíz del proyecto con un Python que tenga openpyxl
(`py -3.12 tests/dorados/control_mora/generar.py`; el vendor/ del proyecto también sirve)."""
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'legado' / 'control_mora'))

import tests  # noqa: E402,F401  (agrega raíz y vendor al path)
from tests.test_control_mora import ARCHIVOS, armar_entradas  # noqa: E402
import control_mora  # noqa: E402

DESTINO = Path(__file__).resolve().parent


def main():
    base = Path(tempfile.mkdtemp(dir=str(RAIZ / 'tests' / '_tmp')))
    try:
        entrada = base / 'entrada'
        entrada.mkdir()
        armar_entradas(entrada)
        generado = control_mora.ejecutar(entrada, base / 'salida')
        for nombre in ARCHIVOS:
            shutil.copyfile(generado / nombre, DESTINO / nombre)
            print(f'dorado: {nombre}')
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == '__main__':
    (RAIZ / 'tests' / '_tmp').mkdir(exist_ok=True)
    main()
