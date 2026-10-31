"""Arma el ZIP para instalar la herramienta en otra PC: dist/Reportes-de-cierre-<versión>.zip.
Lleva el programa, vendor, los BAT, el LEEME y las reglas; no lleva datos, tests, legado ni el .venv."""
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from app.version import VERSION  # noqa: E402

EXCLUIR_CARPETAS = {'datos', '.venv', 'tests', 'legado', '.git', '__pycache__', 'dist', '.claude', '.agent', 'sesion_chrome', '.playwright-mcp'}
EXCLUIR_SUFIJOS = {'.pyc', '.sqlite', '.tmp', '.log'}
EXCLUIR_DOCS = {'superpowers'}


def incluir(ruta):
    partes = ruta.relative_to(RAIZ).parts
    if any(p in EXCLUIR_CARPETAS for p in partes[:-1]):
        return False
    if partes[0] == 'docs' and len(partes) > 1 and partes[1] in EXCLUIR_DOCS:
        return False
    if ruta.suffix.lower() in EXCLUIR_SUFIJOS:
        return False
    if ruta.name.startswith('.') and ruta.name != '.gitignore':
        return False
    return True


def empaquetar(destino=None):
    destino = Path(destino) if destino else RAIZ / 'dist' / f'Reportes-de-cierre-{VERSION}.zip'
    destino.parent.mkdir(parents=True, exist_ok=True)
    raiz_zip = f'Reportes de cierre {VERSION}'
    cantidad = 0
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as z:
        for ruta in sorted(RAIZ.rglob('*')):
            if ruta.is_file() and incluir(ruta) and ruta != destino:
                z.write(ruta, f'{raiz_zip}/{ruta.relative_to(RAIZ).as_posix()}')
                cantidad += 1
    print(f'{destino} ({cantidad} archivos, {destino.stat().st_size // 1024} KB)')
    return destino


if __name__ == '__main__':
    empaquetar(sys.argv[1] if len(sys.argv) > 1 else None)
