"""Almacén JSON: un archivo {version, entradas} cargado en memoria, escritura atómica
(tmp + rename) y backup fechado en <carpeta>/backup antes de cada escritura separada de la
anterior por más de N minutos."""
import json
import os
import time
from datetime import datetime
from pathlib import Path


class AlmacenCorrupto(Exception):
    def __init__(self, ruta, motivo):
        super().__init__(f'{ruta} está dañado y no se escribe nada hasta arreglarlo ({motivo})')
        self.ruta = ruta
        self.motivo = motivo


def escribir_json_atomico(ruta, objeto):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(objeto, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, ruta)


def leer_json(ruta, default=None):
    ruta = Path(ruta)
    if not ruta.exists():
        return default
    try:
        return json.loads(ruta.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return default


def _sello(segundos):
    return datetime.fromtimestamp(segundos).strftime('%Y%m%d-%H%M%S')


class Almacen:
    def __init__(self, ruta, ahora=time.time, max_backups=30, minutos_entre_backups=10):
        self.ruta = Path(ruta)
        self.ahora = ahora
        self.max_backups = max_backups
        self.segundos_entre_backups = minutos_entre_backups * 60
        self.dir_backup = self.ruta.parent / 'backup'
        self.base = self.ruta.stem
        self.ultimo_backup = None
        self.solo_lectura = False
        self.motivo = None
        self.datos = self._cargar()

    def _cargar(self):
        if not self.ruta.exists():
            return {'version': 1, 'entradas': []}
        try:
            datos = json.loads(self.ruta.read_text(encoding='utf-8'))
        except (ValueError, OSError) as e:
            self.solo_lectura = True
            self.motivo = f'JSON inválido: {e}'
            return {'version': 1, 'entradas': []}
        if not isinstance(datos, dict) or not isinstance(datos.get('entradas'), list):
            self.solo_lectura = True
            self.motivo = 'falta la lista "entradas"'
            return {'version': 1, 'entradas': []}
        datos.setdefault('version', 1)
        return datos

    def recargar(self):
        self.solo_lectura = False
        self.motivo = None
        self.datos = self._cargar()

    @property
    def entradas(self):
        return self.datos['entradas']

    def guardar(self):
        if self.solo_lectura:
            raise AlmacenCorrupto(self.ruta, self.motivo)
        self._respaldar_si_corresponde()
        escribir_json_atomico(self.ruta, self.datos)

    def _respaldar_si_corresponde(self):
        if not self.ruta.exists():
            return
        t = self.ahora()
        if self.ultimo_backup is not None and t - self.ultimo_backup < self.segundos_entre_backups:
            return
        self.dir_backup.mkdir(parents=True, exist_ok=True)
        destino = self.dir_backup / f'{self.base}-{_sello(t)}.json'
        destino.write_bytes(self.ruta.read_bytes())
        self.ultimo_backup = t
        self._podar()

    def _podar(self):
        propios = sorted(p for p in self.dir_backup.glob(f'{self.base}-*.json'))
        for p in propios[:max(0, len(propios) - self.max_backups)]:
            try:
                p.unlink()
            except OSError:
                pass
