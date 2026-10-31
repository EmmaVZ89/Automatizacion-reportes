import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for ruta in (RAIZ, RAIZ / 'vendor'):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))
