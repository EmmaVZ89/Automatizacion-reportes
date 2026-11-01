"""Lado server: consulta paginada de las tablas de una ejecución (resultados.sqlite), revisión
(triage) por fila y traslado de la revisión por clave de negocio.

Regla de revisión (`reglas`, por tabla): una salida puede decir qué filas no hace falta revisar, por ejemplo
{'columna': 'Resultado', 'salvo': ['COINCIDE']}. Esas filas se muestran y se pueden marcar, pero no cuentan como
pendientes ni aparecen en el filtro "Pendientes"."""
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from .reportes._comun.salidas import SEP_CLAVE, preparar

ESTADOS = ('pendiente', 'revisada', 'omitida')
MAX_CANTIDAD = 500
MAX_DISTINTOS = 2000
# Condiciones de número del filtro de encabezado (como los "Filtros de número" de Excel).
OPERACIONES = ('distinto_cero', 'igual', 'mayor', 'menor', 'entre')


class Tablas:
    def __init__(self, ruta_sqlite, ahora=time.time, reglas=None):
        self.ruta = Path(ruta_sqlite)
        self.ahora = ahora
        self.reglas = reglas or {}

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

    def _requiere(self, tabla, nombres):
        """Expresión SQL que vale 1 cuando la fila necesita revisión según la regla de la tabla."""
        r = self.reglas.get(tabla) or {}
        salvo = [str(v) for v in (r.get('salvo') or [])]
        if r.get('columna') not in nombres or not salvo:
            return '1', []
        i = nombres.index(r['columna'])
        return f'(c{i} IS NULL OR c{i} NOT IN ({",".join("?" * len(salvo))}))', salvo

    def listar(self):
        if not self.ruta.exists():
            return []
        con = self._con()
        try:
            salida = []
            for t in con.execute('SELECT tabla, titulo, filas FROM _tablas ORDER BY orden').fetchall():
                cols = self.columnas(t['tabla'], con)
                nombres = [c['nombre'] for c in cols]
                req, params = self._requiere(t['tabla'], nombres)
                estados = {e: 0 for e in ESTADOS}
                for r in con.execute(f'SELECT _estado, COUNT(*) n FROM t_{t["tabla"]} WHERE {req} GROUP BY _estado', params):
                    estados[r['_estado']] = r['n']
                salida.append({'tabla': t['tabla'], 'titulo': t['titulo'], 'filas': t['filas'], 'columnas': nombres,
                               'tipos': [c['tipo'] for c in cols], 'estados': estados, 'aRevisar': sum(estados.values())})
            return salida
        finally:
            con.close()

    def _consulta(self, con, tabla, orden=None, descendente=False, filtro='', estado=None, columna_filtro=None,
                  filtros=None, estados=None, con_obs=False, requiere=False, condiciones=None):
        """(columnas, nombres, sql_where, params, sql_orden, sql_requiere, params_requiere) de una consulta.

        filtros: {columna: [valores]} deja sólo esos valores ('' es la celda vacía); {columna: {'excluir': [valores]}}
        deja todos menos esos. condiciones: {columna: {'op': distinto_cero|igual|mayor|menor|entre, 'a', 'b'}}."""
        cols = self.columnas(tabla, con)
        nombres = [c['nombre'] for c in cols]
        req, params_req = self._requiere(tabla, nombres)
        where, params = [], []
        if estado in ESTADOS:
            where.append('_estado=?')
            params.append(estado)
            if estado == 'pendiente':
                where.append(req)
                params.extend(params_req)
        if estados:
            validos = [e for e in estados if e in ESTADOS]
            if not validos:
                raise ValueError('Estado de revisión no válido.')
            where.append(f'_estado IN ({",".join("?" * len(validos))})')
            params.extend(validos)
        if requiere:
            where.append(req)
            params.extend(params_req)
        if con_obs:
            where.append("_obs<>''")
        for columna, valores in (filtros or {}).items():
            if columna not in nombres:
                raise ValueError('No existe esa columna.')
            i = nombres.index(columna)
            if isinstance(valores, dict):
                excluir = [str(v) for v in (valores.get('excluir') or [])]
                if excluir:
                    where.append(f"COALESCE(c{i}, '') NOT IN ({','.join('?' * len(excluir))})")
                    params.extend(excluir)
                continue
            valores = [str(v) for v in (valores or [])]
            if not valores:
                where.append('0')
                continue
            where.append(f"COALESCE(c{i}, '') IN ({','.join('?' * len(valores))})")
            params.extend(valores)
        for columna, c in (condiciones or {}).items():
            if columna not in nombres:
                raise ValueError('No existe esa columna.')
            if not isinstance(c, dict) or c.get('op') not in OPERACIONES:
                raise ValueError('La condición del filtro no es válida.')
            i = nombres.index(columna)
            numero = f'CAST(REPLACE(c{i}, ",", ".") AS REAL)'
            con_valor = f"c{i} IS NOT NULL AND TRIM(c{i}) <> ''"
            try:
                a = float(c['a']) if c['op'] != 'distinto_cero' else None
                b = float(c['b']) if c['op'] == 'entre' else None
            except (KeyError, TypeError, ValueError):
                raise ValueError('Escribí un importe válido en el filtro.')
            if c['op'] == 'distinto_cero':
                where.append(f'({con_valor} AND {numero} <> 0)')
            elif c['op'] == 'igual':
                where.append(f'({con_valor} AND ABS({numero} - ?) < 0.005)')
                params.append(a)
            elif c['op'] == 'entre':
                where.append(f'({con_valor} AND {numero} BETWEEN ? AND ?)')
                params.extend(sorted((a, b)))
            else:
                where.append(f'({con_valor} AND {numero} {">" if c["op"] == "mayor" else "<"} ?)')
                params.append(a)
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
        return cols, nombres, sql_where, params, sql_orden, req, params_req

    @staticmethod
    def _fila(r, n_columnas):
        return {'_fila': r['_fila'], '_estado': r['_estado'], '_obs': r['_obs'], '_origen': r['_origen'],
                '_marcas': json.loads(r['_marcas']) if r['_marcas'] else [], '_req': bool(r['_req']),
                'valores': [r[f'c{i}'] for i in range(n_columnas)]}

    def consultar(self, tabla, desde=0, cantidad=100, orden=None, descendente=False, filtro='', estado=None, columna_filtro=None,
                  filtros=None, estados=None, con_obs=False, requiere=False, condiciones=None):
        con = self._con()
        try:
            cols, nombres, sql_where, params, sql_orden, req, params_req = self._consulta(
                con, tabla, orden, descendente, filtro, estado, columna_filtro, filtros, estados, con_obs, requiere, condiciones)
            cantidad = max(1, min(int(cantidad), MAX_CANTIDAD))
            desde = max(0, int(desde))
            total = con.execute(f'SELECT COUNT(*) FROM t_{tabla}{sql_where}', params).fetchone()[0]
            filas = [self._fila(r, len(nombres)) for r in con.execute(
                f'SELECT *, {req} AS _req FROM t_{tabla}{sql_where}{sql_orden} LIMIT ? OFFSET ?', (*params_req, *params, cantidad, desde))]
            return {'filas': filas, 'total': total, 'columnas': nombres, 'tipos': [c['tipo'] for c in cols]}
        finally:
            con.close()

    def contar(self, tabla, **consulta):
        con = self._con()
        try:
            _, _, sql_where, params, _, _, _ = self._consulta(con, tabla, **consulta)
            return con.execute(f'SELECT COUNT(*) FROM t_{tabla}{sql_where}', params).fetchone()[0]
        finally:
            con.close()

    def filas_vista(self, tabla, **consulta):
        """Todas las filas de una consulta (sin paginar), en su orden. Para exportar lo que se ve."""
        con = self._con()
        try:
            _, nombres, sql_where, params, sql_orden, req, params_req = self._consulta(con, tabla, **consulta)
            for r in con.execute(f'SELECT *, {req} AS _req FROM t_{tabla}{sql_where}{sql_orden}', (*params_req, *params)):
                yield self._fila(r, len(nombres))
        finally:
            con.close()

    def fila(self, tabla, numero):
        """Una fila como {columna: valor}, más '_marcas': las columnas observadas (en anaranjado en pantalla)."""
        con = self._con()
        try:
            nombres = [c['nombre'] for c in self.columnas(tabla, con)]
            r = con.execute(f'SELECT * FROM t_{tabla} WHERE _fila=?', (int(numero),)).fetchone()
            if r is None:
                raise ValueError('No existe esa fila.')
            return {**{n: r[f'c{i}'] for i, n in enumerate(nombres)}, '_marcas': json.loads(r['_marcas']) if r['_marcas'] else []}
        finally:
            con.close()

    def distintos(self, tabla, columna, limite=MAX_DISTINTOS, buscar='', por_valor=False, **consulta):
        """Valores distintos de una columna con su cantidad de filas, entre las filas que cumplen `consulta` (como la
        lista de un filtro de Excel, que muestra lo que queda con los otros filtros). `buscar` acota los valores;
        `por_valor` los ordena alfabéticamente (si no, los más frecuentes primero)."""
        con = self._con()
        try:
            _, nombres, sql_where, params, _, _, _ = self._consulta(con, tabla, **consulta)
            if columna not in nombres:
                raise ValueError('No existe esa columna.')
            i = nombres.index(columna)
            buscar = str(buscar or '').strip()
            if buscar:
                patron = '%' + buscar.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
                sql_where += (' AND ' if sql_where else ' WHERE ') + f"COALESCE(c{i}, '') LIKE ? ESCAPE '\\'"
                params = [*params, patron]
            orden = 'v' if por_valor else 'n DESC, v'
            filas = con.execute(f"SELECT COALESCE(c{i}, '') v, COUNT(*) n FROM t_{tabla}{sql_where} GROUP BY v ORDER BY {orden} LIMIT ?", (*params, int(limite) + 1)).fetchall()
            return {'valores': [{'valor': r['v'], 'cantidad': r['n']} for r in filas[:limite]], 'completo': len(filas) <= limite}
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

    def aplicar_triage(self, triage, origen, solo_estados=None, hermanas=None):
        """Aplica marcas por clave. Una clave que no está en su tabla (o cuya tabla ya no existe) se busca en las
        tablas de `hermanas` ({tabla: [tablas del mismo libro]}). Devuelve cuántas filas recibieron marca y cuántas
        claves no existen."""
        aplicadas = 0
        sin_destino = 0
        if not self.ruta.exists():
            return {'aplicadas': 0, 'sin_destino': sum(len(v) for v in (triage or {}).values())}
        con = self._con()
        try:
            existentes = {r['tabla'] for r in con.execute('SELECT tabla FROM _tablas')}
            fecha = datetime.fromtimestamp(self.ahora()).strftime('%Y-%m-%d %H:%M:%S')
            for tabla, marcas in (triage or {}).items():
                destinos = [x for x in [tabla, *(hermanas or {}).get(tabla, [])] if x in existentes]
                if not destinos:
                    sin_destino += len(marcas)
                    continue
                for clave, m in marcas.items():
                    estado = m.get('estado', 'pendiente')
                    if solo_estados and estado not in solo_estados:
                        continue
                    if estado not in ESTADOS:
                        continue
                    for destino in destinos:
                        cur = con.execute(f'UPDATE t_{destino} SET _estado=?, _obs=?, _origen=?, _fecha=? WHERE _clave=? AND _estado=\'pendiente\' AND _obs=\'\'',
                                          (estado, str(m.get('obs', ''))[:2000], origen, fecha, clave))
                        if cur.rowcount:
                            aplicadas += cur.rowcount
                            break
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
        """Pendientes, revisadas y omitidas de las filas que se revisan (`excluir`: tablas sólo informativas)."""
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
