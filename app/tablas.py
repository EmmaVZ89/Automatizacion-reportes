"""Lado server: consulta paginada de las tablas de una ejecución (resultados.sqlite), revisión
(triage) por fila y traslado de la revisión por clave de negocio."""
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from .reportes._comun.salidas import SEP_CLAVE, preparar

ESTADOS = ('pendiente', 'revisada', 'omitida')
MAX_CANTIDAD = 500


class Tablas:
    def __init__(self, ruta_sqlite, ahora=time.time):
        self.ruta = Path(ruta_sqlite)
        self.ahora = ahora

    def existe(self):
        return self.ruta.exists()

    def _con(self):
        if not self.ruta.exists():
            raise FileNotFoundError('Esta ejecución no tiene resultados para mostrar.')
        con = sqlite3.connect(str(self.ruta))
        con.row_factory = sqlite3.Row
        return con

    def columnas(self, tabla, con=None):
        propio = con is None
        con = con or self._con()
        try:
            filas = con.execute('SELECT posicion, nombre, tipo FROM _columnas WHERE tabla=? ORDER BY posicion', (tabla,)).fetchall()
        finally:
            if propio:
                con.close()
        if not filas:
            raise ValueError('No existe esa tabla en los resultados.')
        return [{'posicion': r['posicion'], 'nombre': r['nombre'], 'tipo': r['tipo']} for r in filas]

    def listar(self):
        if not self.ruta.exists():
            return []
        con = self._con()
        try:
            salida = []
            for t in con.execute('SELECT tabla, titulo, filas FROM _tablas ORDER BY orden').fetchall():
                cols = self.columnas(t['tabla'], con)
                estados = {e: 0 for e in ESTADOS}
                for r in con.execute(f'SELECT _estado, COUNT(*) n FROM t_{t["tabla"]} GROUP BY _estado'):
                    estados[r['_estado']] = r['n']
                salida.append({'tabla': t['tabla'], 'titulo': t['titulo'], 'filas': t['filas'], 'columnas': [c['nombre'] for c in cols], 'tipos': [c['tipo'] for c in cols], 'estados': estados})
            return salida
        finally:
            con.close()

    def consultar(self, tabla, desde=0, cantidad=100, orden=None, descendente=False, filtro='', estado=None, columna_filtro=None):
        con = self._con()
        try:
            cols = self.columnas(tabla, con)
            nombres = [c['nombre'] for c in cols]
            where, params = [], []
            if estado in ESTADOS:
                where.append('_estado=?')
                params.append(estado)
            filtro = str(filtro or '').strip()
            if filtro:
                patron = '%' + filtro.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
                if columna_filtro:
                    if columna_filtro not in nombres:
                        raise ValueError('No existe esa columna.')
                    where.append(f'c{nombres.index(columna_filtro)} LIKE ? ESCAPE \'\\\'')
                    params.append(patron)
                else:
                    partes = [f'c{i} LIKE ? ESCAPE \'\\\'' for i in range(len(nombres))] + ['_obs LIKE ? ESCAPE \'\\\'']
                    where.append('(' + ' OR '.join(partes) + ')')
                    params.extend([patron] * (len(nombres) + 1))
            sql_where = (' WHERE ' + ' AND '.join(where)) if where else ''
            if orden:
                if orden in ('_estado', '_obs', '_fila'):
                    expr = orden
                elif orden in nombres:
                    i = nombres.index(orden)
                    expr = f'CAST(REPLACE(c{i}, ",", ".") AS REAL)' if cols[i]['tipo'] == 'numero' else f'c{i}'
                else:
                    raise ValueError('No existe esa columna.')
                sql_orden = f' ORDER BY {expr} {"DESC" if descendente else "ASC"}, _fila'
            else:
                sql_orden = ' ORDER BY _fila'
            cantidad = max(1, min(int(cantidad), MAX_CANTIDAD))
            desde = max(0, int(desde))
            total = con.execute(f'SELECT COUNT(*) FROM t_{tabla}{sql_where}', params).fetchone()[0]
            filas = []
            for r in con.execute(f'SELECT * FROM t_{tabla}{sql_where}{sql_orden} LIMIT ? OFFSET ?', (*params, cantidad, desde)):
                filas.append({'_fila': r['_fila'], '_estado': r['_estado'], '_obs': r['_obs'], '_origen': r['_origen'],
                              '_marcas': json.loads(r['_marcas']) if r['_marcas'] else [],
                              'valores': [r[f'c{i}'] for i in range(len(nombres))]})
            return {'filas': filas, 'total': total, 'columnas': nombres, 'tipos': [c['tipo'] for c in cols]}
        finally:
            con.close()

    def marcar(self, tabla, filas, estado, obs=None, origen='manual'):
        if estado is not None and estado not in ESTADOS:
            raise ValueError('Estado de revisión no válido.')
        filas = [int(f) for f in filas]
        if not filas:
            return 0
        con = self._con()
        try:
            self.columnas(tabla, con)
            fecha = datetime.fromtimestamp(self.ahora()).strftime('%Y-%m-%d %H:%M:%S')
            n = 0
            for i in range(0, len(filas), 500):
                lote = filas[i:i + 500]
                marcadores = ','.join('?' * len(lote))
                sets, params = ['_fecha=?', '_origen=?'], [fecha, origen]
                if estado is not None:
                    sets.append('_estado=?')
                    params.append(estado)
                if obs is not None:
                    sets.append('_obs=?')
                    params.append(str(obs)[:2000])
                cur = con.execute(f'UPDATE t_{tabla} SET {", ".join(sets)} WHERE _fila IN ({marcadores})', (*params, *lote))
                n += cur.rowcount
            con.commit()
            return n
        finally:
            con.close()

    def triage(self):
        """Lo revisado u omitido (o con observación), por tabla y clave de negocio."""
        if not self.ruta.exists():
            return {}
        con = self._con()
        try:
            salida = {}
            for t in con.execute('SELECT tabla FROM _tablas ORDER BY orden').fetchall():
                nombre = t['tabla']
                marcas = {}
                for r in con.execute(f'SELECT _clave, _estado, _obs, _fecha, _origen FROM t_{nombre} WHERE _estado<>\'pendiente\' OR _obs<>\'\' ORDER BY _fila'):
                    if r['_clave'] in marcas:
                        continue
                    marcas[r['_clave']] = {'estado': r['_estado'], 'obs': r['_obs'], 'fecha': r['_fecha'], 'origen': r['_origen']}
                salida[nombre] = marcas
            return salida
        finally:
            con.close()

    def aplicar_triage(self, triage, origen, solo_estados=None):
        """Aplica marcas por clave. Devuelve cuántas filas recibieron marca y cuántas claves no existen."""
        aplicadas = 0
        sin_destino = 0
        if not self.ruta.exists():
            return {'aplicadas': 0, 'sin_destino': sum(len(v) for v in (triage or {}).values())}
        con = self._con()
        try:
            existentes = {r['tabla'] for r in con.execute('SELECT tabla FROM _tablas')}
            fecha = datetime.fromtimestamp(self.ahora()).strftime('%Y-%m-%d %H:%M:%S')
            for tabla, marcas in (triage or {}).items():
                if tabla not in existentes:
                    sin_destino += len(marcas)
                    continue
                for clave, m in marcas.items():
                    estado = m.get('estado', 'pendiente')
                    if solo_estados and estado not in solo_estados:
                        continue
                    if estado not in ESTADOS:
                        continue
                    cur = con.execute(f'UPDATE t_{tabla} SET _estado=?, _obs=?, _origen=?, _fecha=? WHERE _clave=? AND _estado=\'pendiente\' AND _obs=\'\'',
                                      (estado, str(m.get('obs', ''))[:2000], origen, fecha, clave))
                    if cur.rowcount:
                        aplicadas += cur.rowcount
                    else:
                        sin_destino += 1
            con.commit()
            return {'aplicadas': aplicadas, 'sin_destino': sin_destino}
        finally:
            con.close()

    def filas_completas(self, tabla, incluir_omitidas=True):
        con = self._con()
        try:
            nombres = [c['nombre'] for c in self.columnas(tabla, con)]
            where = '' if incluir_omitidas else " WHERE _estado<>'omitida'"
            for r in con.execute(f'SELECT * FROM t_{tabla}{where} ORDER BY _fila'):
                yield {'_fila': r['_fila'], '_estado': r['_estado'], '_obs': r['_obs'],
                       '_marcas': json.loads(r['_marcas']) if r['_marcas'] else [],
                       'valores': [r[f'c{i}'] for i in range(len(nombres))]}
        finally:
            con.close()

    def resumen_revision(self, excluir=()):
        """Pendientes, revisadas y omitidas de las tablas que se revisan (`excluir`: tablas sólo informativas)."""
        totales = {e: 0 for e in ESTADOS}
        for t in self.listar():
            if t['tabla'] in excluir:
                continue
            for e in ESTADOS:
                totales[e] += t['estados'][e]
        return {'pendientes': totales['pendiente'], 'revisadas': totales['revisada'], 'omitidas': totales['omitida']}


def clave_de(valores, indices):
    return SEP_CLAVE.join(valores[i] for i in indices)


def crear_vacio(ruta):
    con = preparar(ruta)
    con.close()
