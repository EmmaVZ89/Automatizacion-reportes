"""Acceso directo "Reportes de cierre" con el ícono de la herramienta, como el de PedidosIA.

Al abrir la herramienta (`python -m app.arranque`) se asegura un `Reportes de cierre.lnk` en su carpeta y, la primera
vez, otro en el Escritorio. Los dos abren `app/iniciar.vbs` con wscript: la herramienta arranca sin ventana negra. Si la
carpeta de la herramienta se movió, se corrigen los dos; si alguien borró el del Escritorio, no se vuelve a crear solo
(Configuración tiene el botón para crearlo). El ícono es el logo de la pantalla, dibujado acá (sin imágenes en el
repositorio) en la carpeta de datos. Los .lnk se escriben con WScript.Shell desde PowerShell: Python no trae COM."""
import math
import os
import struct
import subprocess
import threading
import zlib
from pathlib import Path

from .almacen import escribir_json_atomico, leer_json

NOMBRE = 'Reportes de cierre.lnk'
ARCHIVO_ESTADO = 'acceso_directo.json'
ARCHIVO_ICONO = 'reportes-de-cierre.ico'
ESCRITORIO = '<escritorio>'
TAMANOS = (16, 24, 32, 48, 64, 256)

# El logo (el favicon de index.html, viewBox 32×32): hoja, banda, anillas y tilde.
HOJA, BANDA, BLANCO = (0x34, 0x45, 0xB4), (0x27, 0x34, 0x8F), (0xFF, 0xFF, 0xFF)


def _rect(px, py, x, y, w, h, r):
    """Distancia con signo (negativa adentro) a un rectángulo de esquinas redondeadas."""
    qx = abs(px - (x + w / 2)) - (w / 2 - r)
    qy = abs(py - (y + h / 2)) - (h / 2 - r)
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r


def _trazo(px, py, puntos, grosor):
    """Distancia con signo a una línea quebrada de puntas redondeadas."""
    d = float('inf')
    for (ax, ay), (bx, by) in zip(puntos, puntos[1:]):
        vx, vy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy)))
        d = min(d, math.hypot(px - ax - t * vx, py - ay - t * vy))
    return d - grosor / 2


CAPAS = [
    (HOJA, lambda x, y: _rect(x, y, 2, 4, 28, 26, 6)),
    (BANDA, lambda x, y: min(_rect(x, y, 2, 4, 28, 8, 6), _rect(x, y, 2, 9, 28, 3, 0))),
    (BANDA, lambda x, y: min(_rect(x, y, 7.3, 0.3, 4.4, 8.4, 2.2), _rect(x, y, 20.3, 0.3, 4.4, 8.4, 2.2))),  # borde de las anillas
    (BLANCO, lambda x, y: min(_rect(x, y, 8, 1, 3, 7, 1.5), _rect(x, y, 21, 1, 3, 7, 1.5))),
    (BLANCO, lambda x, y: _trazo(x, y, [(10, 20), (14, 24), (22, 15)], 3.2)),
]


def pixeles(lado):
    """RGBA del logo en `lado`×`lado` píxeles, con bordes suavizados."""
    escala = lado / 32
    salida = bytearray()
    for j in range(lado):
        for i in range(lado):
            x, y = (i + 0.5) / escala, (j + 0.5) / escala
            r = g = b = a = 0.0
            for color, distancia in CAPAS:
                cobertura = min(1.0, max(0.0, 0.5 - distancia(x, y) * escala))
                if cobertura:
                    nueva = cobertura + a * (1 - cobertura)
                    r, g, b = ((c * cobertura + v * a * (1 - cobertura)) / nueva for c, v in zip(color, (r, g, b)))
                    a = nueva
            salida += bytes((round(r), round(g), round(b), round(a * 255)))
    return bytes(salida)


def _png(lado, rgba):
    def bloque(tipo, datos):
        return struct.pack('>I', len(datos)) + tipo + datos + struct.pack('>I', zlib.crc32(tipo + datos) & 0xFFFFFFFF)
    filas = b''.join(b'\x00' + rgba[f * lado * 4:(f + 1) * lado * 4] for f in range(lado))
    return (b'\x89PNG\r\n\x1a\n' + bloque(b'IHDR', struct.pack('>IIBBBBB', lado, lado, 8, 6, 0, 0, 0))
            + bloque(b'IDAT', zlib.compress(filas, 9)) + bloque(b'IEND', b''))


def icono_ico(tamanos=TAMANOS):
    """Un .ico con una imagen PNG por tamaño (Windows lo lee desde Vista)."""
    imagenes = [_png(t, pixeles(t)) for t in tamanos]
    cabecera = struct.pack('<HHH', 0, 1, len(imagenes))
    desde = 6 + 16 * len(imagenes)
    entradas = b''
    for t, png in zip(tamanos, imagenes):
        entradas += struct.pack('<BBBBHHII', t % 256, t % 256, 0, 0, 1, 32, len(png), desde)
        desde += len(png)
    return cabecera + entradas + b''.join(imagenes)


def _comillas(texto):
    return "'" + str(texto).replace("'", "''") + "'"


def script_powershell(raiz, icono, destinos):
    """PowerShell que crea cada acceso directo y escribe su ruta, una por línea. `ESCRITORIO` es el Escritorio del
    usuario (el que diga Windows, aunque esté en OneDrive)."""
    wscript = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'wscript.exe'
    vbs = '"' + str(Path(raiz) / 'app' / 'iniciar.vbs') + '"'
    rutas = ', '.join(f"(Join-Path ([Environment]::GetFolderPath('Desktop')) {_comillas(NOMBRE)})" if d == ESCRITORIO else _comillas(d)
                      for d in destinos)
    return '; '.join([
        "$ErrorActionPreference = 'Stop'",
        '[Console]::OutputEncoding = [Text.Encoding]::UTF8',  # rutas con tildes o ñ (un usuario "Martín")
        '$shell = New-Object -ComObject WScript.Shell',
        f'foreach ($destino in @({rutas})) {{ $s = $shell.CreateShortcut($destino)',
        f'$s.TargetPath = {_comillas(wscript)}',
        f'$s.Arguments = {_comillas(vbs)}',
        f'$s.WorkingDirectory = {_comillas(raiz)}',
        f'$s.IconLocation = {_comillas(str(icono) + ",0")}',
        '$s.WindowStyle = 1',
        "$s.Description = 'Reportes de cierre'",
        '$s.Save()',
        'Write-Output $destino }',
    ])


def _powershell(script):
    r = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, encoding='utf-8',
                       errors='replace', timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if r.returncode != 0:
        raise OSError((r.stderr or r.stdout or 'PowerShell no pudo crear el acceso directo.').strip()[:500])
    return r.stdout


def _crear(raiz, dir_datos, destinos, ejecutar):
    icono = Path(dir_datos) / ARCHIVO_ICONO
    if not icono.exists():
        icono.write_bytes(icono_ico())
    salida = (ejecutar or _powershell)(script_powershell(raiz, icono, destinos))
    return [linea.strip() for linea in salida.splitlines() if linea.strip()]


def _guardar(raiz, dir_datos, creados, estado):
    raiz = Path(raiz)
    escritorio = next((c for c in creados if Path(c).parent != raiz), estado.get('escritorio'))
    escribir_json_atomico(Path(dir_datos) / ARCHIVO_ESTADO, {'raiz': str(raiz), 'escritorio': escritorio})


def asegurar(raiz, dir_datos, ejecutar=None):
    """Crea o corrige los accesos directos que hagan falta y devuelve las rutas escritas."""
    if os.name != 'nt' and ejecutar is None:
        return []
    raiz = Path(raiz)
    estado = leer_json(Path(dir_datos) / ARCHIVO_ESTADO, {}) or {}
    misma = estado.get('raiz') == str(raiz)
    destinos = []
    if not misma or not (raiz / NOMBRE).exists():
        destinos.append(str(raiz / NOMBRE))
    if 'escritorio' not in estado:
        destinos.append(ESCRITORIO)  # la primera vez
    elif estado.get('escritorio') and not misma and Path(estado['escritorio']).exists():
        destinos.append(estado['escritorio'])  # la herramienta cambió de carpeta: el del Escritorio pasa a abrir ésta
    if not destinos:
        return []
    creados = _crear(raiz, dir_datos, destinos, ejecutar)
    _guardar(raiz, dir_datos, creados, estado)
    return creados


def crear_en_escritorio(raiz, dir_datos, ejecutar=None):
    """Crea (o rehace) el acceso directo del Escritorio y el de la carpeta de la herramienta."""
    if os.name != 'nt' and ejecutar is None:
        raise OSError('El acceso directo sólo se puede crear en Windows.')
    estado = leer_json(Path(dir_datos) / ARCHIVO_ESTADO, {}) or {}
    creados = _crear(raiz, dir_datos, [str(Path(raiz) / NOMBRE), ESCRITORIO], ejecutar)
    _guardar(raiz, dir_datos, creados, estado)
    return creados


def asegurar_en_hilo(raiz, dir_datos, registro=None):
    """Sin demorar la apertura: un error queda en el registro y se reintenta la próxima vez."""
    def tarea():
        try:
            creados = asegurar(raiz, dir_datos)
            if creados and registro:
                registro.info('Acceso directo: %s', ' | '.join(creados))
        except Exception as e:  # nunca impide usar la herramienta
            if registro:
                registro.warning('No se pudo crear el acceso directo: %s', e)
    hilo = threading.Thread(target=tarea, daemon=True)
    hilo.start()
    return hilo
