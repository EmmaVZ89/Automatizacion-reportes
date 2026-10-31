"""Lado motor: vuelca cada tabla de salida a resultados.sqlite para que la interfaz pueda paginar,
filtrar y revisar sin cargar todo. Las salidas originales (XLSX/CSV) se escriben aparte, intactas.

Esquema por tabla `t_<nombre>`: _fila (orden original), _clave (clave de negocio para trasladar la
revisión), _estado, _obs, _origen, _fecha, _marcas (JSON de columnas resaltadas) y c0..cN con los
valores originales como texto. `_columnas` guarda nombre, posición y tipo detectado por columna."""
import json
import re
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from . import protocolo

SEP_CLAVE = '\x1f'
_RE_NUMERO = re.compile(r'^-?\d+(?:[.,]\d+)?$')
_RE_TABLA = re.compile(r'^[a-z][a-z0-9_]{0,60}$')


def texto_de(valor):
    if valor is None:
        return ''
    if isinstance(valor, bool):
        return 'Sí' if valor else 'No'
    if isinstance(valor, Decimal):
        return format(valor, 'f')
    if isinstance(valor, float):
        return repr(valor) if valor != int(valor) or abs(valor) > 1e15 else str(int(valor))
    if isinstance(valor, datetime):
        return valor.strftime('%Y-%m-%d %H:%M:%S') if (valor.hour or valor.minute or valor.second) else valor.strftime('%Y-%m-%d')
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


def _tipo(valores):
    vistos = [v for v in valores if v != '']
    if not vistos:
        return 'texto'
    if all(_RE_NUMERO.match(v) for v in vistos):
        return 'numero'
    if all(re.match(r'^\d{4}-\d{2}-\d{2}', v) for v in vistos):
        return 'fecha'
    return 'texto'


def preparar(ruta):
    """Crea (o abre) el sqlite con la tabla de metadatos."""
    con = sqlite3.connect(str(ruta))
    con.execute('CREATE TABLE IF NOT EXISTS _columnas(tabla TEXT, posicion INTEGER, nombre TEXT, tipo TEXT, PRIMARY KEY(tabla, posicion))')
    con.execute('CREATE TABLE IF NOT EXISTS _tablas(tabla TEXT PRIMARY KEY, titulo TEXT, orden INTEGER, filas INTEGER)')
    con.commit()
    return con


class Volcador:
    def __init__(self, ruta_sqlite):
        self.ruta = Path(ruta_sqlite)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        if self.ruta.exists():
            self.ruta.unlink()
        self.con = preparar(self.ruta)
        self._orden = 0

    def tabla(self, nombre, columnas, filas, clave, marcas=(), titulo=None):
        """columnas: nombres; filas: iterable de listas (valores en el orden de columnas);
        clave: nombres de columnas que forman la clave de negocio; marcas: (indice_fila, nombre_columna)."""
        if not _RE_TABLA.match(nombre):
            raise ValueError(f'Nombre de tabla no válido: {nombre!r}')
        columnas = [str(c) for c in columnas]
        indices_clave = [columnas.index(c) for c in clave if c in columnas]
        if clave and not indices_clave:
            raise ValueError(f'{nombre}: ninguna columna de la clave {clave} está en {columnas}')
        marcas_por_fila = {}
        for fila, col in marcas:
            marcas_por_fila.setdefault(int(fila), []).append(str(col))
        cols_sql = ', '.join(f'c{i} TEXT' for i in range(len(columnas)))
        self.con.execute(f'DROP TABLE IF EXISTS t_{nombre}')
        self.con.execute(f'CREATE TABLE t_{nombre}(_fila INTEGER PRIMARY KEY, _clave TEXT, _estado TEXT NOT NULL DEFAULT \'pendiente\', _obs TEXT NOT NULL DEFAULT \'\', _origen TEXT NOT NULL DEFAULT \'\', _fecha TEXT NOT NULL DEFAULT \'\', _marcas TEXT{", " + cols_sql if cols_sql else ""})')
        marcadores = ', '.join(['?'] * (3 + len(columnas)))
        sql = f'INSERT INTO t_{nombre}(_fila, _clave, _marcas{"".join(f", c{i}" for i in range(len(columnas)))}) VALUES({marcadores})'
        lote = []
        total = 0
        muestras = [[] for _ in columnas]
        for i, fila in enumerate(filas):
            valores = [texto_de(v) for v in fila]
            valores += [''] * (len(columnas) - len(valores))
            valores = valores[:len(columnas)]
            if total < 200:
                for j, v in enumerate(valores):
                    muestras[j].append(v)
            clave_txt = SEP_CLAVE.join(valores[j] for j in indices_clave)
            m = marcas_por_fila.get(i)
            lote.append((i, clave_txt, json.dumps(m, ensure_ascii=False) if m else None, *valores))
            total += 1
            if len(lote) >= 5000:
                self.con.executemany(sql, lote)
                lote.clear()
        if lote:
            self.con.executemany(sql, lote)
        self.con.execute(f'CREATE INDEX ix_{nombre}_clave ON t_{nombre}(_clave)')
        self.con.execute(f'CREATE INDEX ix_{nombre}_estado ON t_{nombre}(_estado)')
        self.con.executemany('INSERT INTO _columnas VALUES(?,?,?,?)', [(nombre, j, c, _tipo(muestras[j])) for j, c in enumerate(columnas)])
        self.con.execute('INSERT OR REPLACE INTO _tablas VALUES(?,?,?,?)', (nombre, titulo or nombre, self._orden, total))
        self._orden += 1
        self.con.commit()
        protocolo.tabla(nombre, total)
        return total

    def cerrar(self):
        self.con.commit()
        self.con.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cerrar()
