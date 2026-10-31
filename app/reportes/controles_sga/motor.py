"""Controles internos SGA (motor). Derivado de legado/controles_sga/control_sga.py v1.5 con los cambios
mínimos: sin input() ni rutas propias, constantes tomadas de los parámetros (mismos defaults), tramos
(cada fila lleva `_archivo` además de `_fila` y `_hoja`) y mensajes por el protocolo.
La matemática, el orden de las filas y los textos no cambian respecto del legado.
"""
import calendar
import csv
import json
import posixpath
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from xml.etree import ElementTree as ET

from .._comun import protocolo

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
D = Decimal
ZERO = D('0')
CENT = D('.01')
VERSION = '1.5'
# Las constantes del legado pasan a ser configuración: `configurar(parametros)` las reasigna al inicio
# de cada corrida (cada corrida es un proceso aparte). Los valores de abajo son los defaults del legado.
TOL = D('.02')
START = date(2026, 10, 1)
# Exclusiones indicadas expresamente por la responsable funcional.
EXCLUDED_DOCUMENTS = {'CH-20190722105522839'}
EXEMPT_CONCEPTS = [
    'VENTA BIENES DE USO','VENTA DE BIENES DE USO','PUBLICIDAD GRAFICA',
    'DEVOLUCION DE COBRANZA','CHEQUE A CANJEAR - FRG',
    'COMISION POR CUENTA DE TERCEROS','DEVOLUCION A LOS FONDOS ESPECIFICOS',
    'DIFERENCIA DE CAMBIO','GASTOS DE ESTUDIO','GASTOS ESCRIBANIA',
    'IMPORTES A RECUPERAR CON IVA','OTROS INGRESOS','REINTEGRO DE GASTOS',
    'RESCATE AVAL POR CGTIA','SINIESTROS A COBRAR','DEUDAS DIVERSAS',
    'SERVICIOS ADMINISTRATIVOS','CHEQUE RECHAZADO',
]
REQUIRES_UNDEFINED_DATA = set()
ALLOWED_DIFFERENT_IMPUTATION = {
    'DEUDA POR APORTE NO VIGENTE - RDO. EJ.',
}
CONDITIONAL_IMPUTATION = {
    'COMISION POR CUENTA DE TERCEROS':'COMISIONES',
    'INCOBRABLES PARTICIPES - GTZ':'COMISIONES',
    'INCOBRABLES PARTICIPES - FRG':'MORA',
    'INCOBRABLES QUITA':'MORA',
}
OFFICIAL_INVOICES = ('FC-A','FC-B','FE-A')
FIELDS = ['CodigoEmpresa','CUIT','RazonSocial','NumeroDeAporte','Expediente',
          'Operacion','GrupoConceptoFacturacion','Concepto','NumeroFactura',
          'FechaFactura','ConceptoFacturacionImputacion','NumeroComprobanteImputacion',
          'FechaComprobanteImputacion','FechaImputacion','Importe','ImporteNetoGravado',
          'PorcentajeIVA','ImporteIVA','PorcentajeIIBB','ImporteIIBB','Subrecibo','FondoDeRiesgo']
LIBROS = ['Control_Netos_Impuestos','Control_Datos_Obligatorios',
          'Control_Servicios_Administrativos','Saldo_MORA','Comprobantes_Abiertos','Control_Concepto_Agrupador']

def norm(v):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(v or ''))
                           if not unicodedata.combining(c)).upper().split())

# NFKD transforma º en o: los conceptos con aporte se comparan normalizados (como en el legado).
APORTE_CONCEPTS = [norm('SERV. ADMINIST. FRG - 1º'), norm('SERV. ADMINIST. FRG - 2º'), 'DEUDA POR APORTE VENCIDO GTZ']

def _fecha(v, default):
    if v in (None, ''):
        return default
    return v if isinstance(v, date) else date.fromisoformat(str(v).strip()[:10])

def _lista(v):
    return [str(x) for x in (v or []) if str(x or '').strip()]

_DEFAULTS = {'TOL': TOL, 'START': START, 'EXCLUDED_DOCUMENTS': set(EXCLUDED_DOCUMENTS), 'EXEMPT_CONCEPTS': list(EXEMPT_CONCEPTS),
             'APORTE_CONCEPTS': list(APORTE_CONCEPTS), 'ALLOWED_DIFFERENT_IMPUTATION': set(ALLOWED_DIFFERENT_IMPUTATION),
             'CONDITIONAL_IMPUTATION': dict(CONDITIONAL_IMPUTATION), 'OFFICIAL_INVOICES': OFFICIAL_INVOICES}

def configurar(parametros):
    """Reasigna las constantes del legado a partir de los parámetros; las que faltan vuelven al default."""
    global TOL, START, EXCLUDED_DOCUMENTS, EXEMPT_CONCEPTS, ALLOWED_DIFFERENT_IMPUTATION
    global CONDITIONAL_IMPUTATION, OFFICIAL_INVOICES, APORTE_CONCEPTS
    p = parametros or {}
    def dado(clave):
        return p.get(clave) not in (None, '')
    t = p.get('tolerancia')
    TOL = D(str(t).strip().replace(',', '.')) if dado('tolerancia') else _DEFAULTS['TOL']
    START = _fecha(p.get('inicio_regla_mensual'), _DEFAULTS['START'])
    EXCLUDED_DOCUMENTS = {norm(x) for x in _lista(p['documentos_excluidos'])} if 'documentos_excluidos' in p else set(_DEFAULTS['EXCLUDED_DOCUMENTS'])
    EXEMPT_CONCEPTS = list(dict.fromkeys(norm(x) for x in _lista(p['conceptos_exentos']))) if 'conceptos_exentos' in p else list(_DEFAULTS['EXEMPT_CONCEPTS'])
    APORTE_CONCEPTS = list(dict.fromkeys(norm(x) for x in _lista(p['conceptos_con_aporte']))) if 'conceptos_con_aporte' in p else list(_DEFAULTS['APORTE_CONCEPTS'])
    ALLOWED_DIFFERENT_IMPUTATION = {norm(x) for x in _lista(p['imputacion_distinta_permitida'])} if 'imputacion_distinta_permitida' in p else set(_DEFAULTS['ALLOWED_DIFFERENT_IMPUTATION'])
    if 'imputacion_condicional' in p:
        CONDITIONAL_IMPUTATION = {norm(f.get('concepto')): norm(f.get('agrupador')) for f in (p['imputacion_condicional'] or [])
                                  if norm(f.get('concepto'))}
    else:
        CONDITIONAL_IMPUTATION = dict(_DEFAULTS['CONDITIONAL_IMPUTATION'])
    OFFICIAL_INVOICES = tuple(norm(x) for x in _lista(p['facturas_oficiales'])) if 'facturas_oficiales' in p else _DEFAULTS['OFFICIAL_INVOICES']

def missing(v):
    return norm(v) in ('', '0', '0.0', '0.00', 'NULL', 'NONE')

def ident(v):
    s = str(v or '').strip()
    return re.sub(r'\.0+$', '', s)

def num(v):
    if v is None or str(v).strip() == '':
        return ZERO
    s = str(v).strip().replace('$','').replace(' ','')
    if ',' in s:
        s = s.replace('.','').replace(',','.')
    try:
        n = D(s)
        if not n.is_finite():
            raise InvalidOperation
        return n
    except InvalidOperation:
        raise ValueError(f'Importe o porcentaje no numerico: {v!r}')

def dt(v):
    s = str(v or '').strip()
    for fmt in ('%Y-%m-%d','%Y-%m-%d %H:%M:%S','%d/%m/%Y','%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    try:
        return date(1899,12,30) + timedelta(days=float(s)) if s else None
    except (ValueError,OverflowError):
        return None

def pending(r):
    return (not str(r.get('NumeroFactura') or '').strip() or
            any('MOVIMIENTOS PENDIENTES' in norm(r.get(f)) for f in
                ('NumeroFactura','GrupoConceptoFacturacion','Concepto')))

def base(r):
    return not str(r.get('NumeroComprobanteImputacion') or '').strip()

def excluded(r):
    return (norm(r.get('NumeroFactura')) in EXCLUDED_DOCUMENTS or
            norm(r.get('NumeroComprobanteImputacion')) in EXCLUDED_DOCUMENTS)

def key(r):
    return (norm(r['FondoDeRiesgo']), ident(r['CodigoEmpresa']), norm(r['NumeroFactura']))

def amount(r, field='Importe'):
    return r['_n'][field]

def read_xlsx(path, informar=protocolo, nombre=None):
    """Lee solo la hoja que contiene las columnas SGA, aunque haya hojas agregadas.
    Cada fila lleva `_archivo` (nombre original del tramo), `_hoja` y `_fila`."""
    path = Path(path)
    nombre = nombre or path.name
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rel = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        targets = {e.get('Id'): e.get('Target') for e in rel}
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        for s in wb.find(NS+'sheets'):
            rid = s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            target = targets[rid]
            target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            headers = None
            with z.open(target) as f:
                for _, e in ET.iterparse(f, events=('end',)):
                    if e.tag != NS+'row':
                        continue
                    cells = {}
                    for c in e:
                        ref = re.match(r'[A-Z]+', c.get('r',''))
                        if not ref:
                            continue
                        idx = 0
                        for ch in ref[0]:
                            idx = idx*26 + ord(ch)-64
                        v = c.find(NS+'v')
                        value = v.text if v is not None else None
                        if c.get('t') == 's' and value is not None:
                            value = strings[int(value)]
                        elif c.get('t') == 'inlineStr':
                            value = ''.join(c.itertext())
                        if c.find(NS+'f') is not None and v is None:
                            raise ValueError('Hay formulas sin resultado guardado. Use el reporte original SGA.')
                        cells[idx-1] = value
                    rownum = int(e.get('r','0'))
                    e.clear()
                    if headers is None:
                        vals = set(cells.values())
                        if {'NumeroFactura','FondoDeRiesgo','Importe','Concepto'} <= vals:
                            headers = cells
                            absent = set(FIELDS)-set(headers.values())
                            if absent:
                                raise ValueError('Faltan columnas: '+', '.join(sorted(absent)))
                            informar.log(f'Hoja SGA: {s.get("name")}')
                        elif rownum > 30:
                            break
                        continue
                    r = {name: cells.get(i) for i,name in headers.items() if name}
                    if all(v is None for v in r.values()):
                        continue
                    r['_fila'] = rownum
                    r['_hoja'] = s.get('name')
                    r['_archivo'] = nombre
                    yield r
            if headers is not None:
                return
        raise ValueError('No se encontro una hoja con encabezados SGA.')

def _donde(r):
    return f'Fila {r["_fila"]}' + (f' de {r["_archivo"]}' if r.get('_varios_tramos') else '')

def prepare(rows):
    # Los porcentajes SGA no participan de ningun calculo ni validacion.
    numeric = ['Importe','ImporteNetoGravado','ImporteIVA','ImporteIIBB']
    for r in rows:
        try:
            r['_n'] = {k:num(r.get(k)) for k in numeric}
        except ValueError as ex:
            raise ValueError(f'{_donde(r)}: {ex}') from ex
        if missing(r.get('FondoDeRiesgo')) or missing(r.get('CodigoEmpresa')):
            raise ValueError(f'{_donde(r)}: falta fondo o CodigoEmpresa; no se puede agrupar con seguridad.')
    return rows

def context(r):
    return {k:r.get(k,'') for k in ['FondoDeRiesgo','CodigoEmpresa','CUIT','RazonSocial',
        'NumeroFactura','FechaFactura','NumeroComprobanteImputacion','FechaImputacion',
        'Subrecibo','Concepto','ConceptoFacturacionImputacion','GrupoConceptoFacturacion',
        'NumeroDeAporte','Expediente','Operacion']} | {'FilaOrigen':r['_fila'],'_archivo':r.get('_archivo','')}

def observation(r, rule, reason, status='REVISAR', **extra):
    return context(r) | {'Control':rule,'Estado':status,'Motivo':reason} | extra

def default_rules(rows):
    stats = defaultdict(Counter)
    groups = defaultdict(Counter)
    for r in rows:
        if not pending(r) and base(r):
            c = norm(r['Concepto'])
            stats[c]['total'] += 1
            stats[c]['APORTE'] += not missing(r['NumeroDeAporte'])
            stats[c]['EXP_OP'] += not missing(r['Expediente']) and not missing(r['Operacion'])
            groups[c][norm(r['GrupoConceptoFacturacion'])] += 1
    out = {}
    for c, st in sorted(stats.items()):
        mode, n = max(((m,st[m]) for m in ('APORTE','EXP_OP')),key=lambda x:x[1])
        exempt = c.startswith('ACCIONES ') or c in EXEMPT_CONCEPTS
        aporte = c in APORTE_CONCEPTS
        expected = 'EXENTO' if exempt else 'APORTE' if aporte else 'REQUIERE_DATO_SIN_DEFINIR' if c in REQUIRES_UNDEFINED_DATA else mode if n/st['total'] >= .8 else 'SIN_DEFINIR'
        out[c] = {'datos':expected,'datos_confirmados':bool(exempt or aporte or c in REQUIRES_UNDEFINED_DATA),
                  'agrupador':groups[c].most_common(1)[0][0], 'agrupador_confirmado':False,
                  'lineas_emision_observadas':st['total'],'con_aporte':st['APORTE'],'con_exp_op':st['EXP_OP']}
    return out

def apply_confirmed_rules(rules):
    """Las reglas confirmadas prevalecen sobre configuraciones de versiones anteriores."""
    out={norm(k):dict(v) for k,v in rules.items()}
    for c in EXEMPT_CONCEPTS:
        out.setdefault(c,{}).update(datos='EXENTO',datos_confirmados=True)
    for c in APORTE_CONCEPTS:
        out.setdefault(c,{}).update(datos='APORTE',datos_confirmados=True)
    for c in REQUIRES_UNDEFINED_DATA:
        out.setdefault(c,{}).update(datos='REQUIERE_DATO_SIN_DEFINIR',datos_confirmados=True)
    return out

def _booleano(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return bool(v)
    return str(v).strip().lower() in ('1', 'true', 'si', 'sí', 'x', 'verdadero')

def reglas_confirmadas(filas):
    """Equivale al `--reglas reglas.json` del legado: {norm(concepto): {datos, datos_confirmados, agrupador, agrupador_confirmado}}."""
    out = {}
    for f in filas or []:
        c = norm(f.get('concepto'))
        if not c:
            continue
        out[c] = {'datos': str(f.get('datos') or ''), 'datos_confirmados': _booleano(f.get('datos_confirmados')),
                  'agrupador': str(f.get('agrupador') or ''), 'agrupador_confirmado': _booleano(f.get('agrupador_confirmado'))}
    return out

COMPONENTS = ('ImporteNetoGravado','ImporteIVA','ImporteIIBB')

def reference_components(candidates):
    if not candidates:
        return None, 'No se logro vincular una linea de emision de referencia; revisar la identificacion del comprobante.'
    totals={f:sum((amount(b,f) for b in candidates),ZERO) for f in ('Importe',)+COMPONENTS}
    if totals['Importe']==ZERO:
        return None, 'La referencia tiene importe total cero; no se puede determinar una proporcion.'
    if abs(totals['Importe']-sum((totals[f] for f in COMPONENTS),ZERO))>TOL*len(candidates):
        return None, 'Los componentes de la referencia no suman su importe; revisar la emision antes de evaluar la proporcion.'
    return totals, None

def targets(r, invoices):
    candidates = invoices.get(key(r), [])
    same = [b for b in candidates if norm(b['Concepto'])==norm(r['ConceptoFacturacionImputacion'])]
    return same or candidates

def reciprocal_fi_reference(r, documents):
    """Verifica un cruce FI reciproco real, sin inventar una cabecera ausente."""
    factura=norm(r.get('NumeroFactura'))
    comp=norm(r.get('NumeroComprobanteImputacion'))
    if not factura.startswith('FI-P') or not comp.startswith('FI-P') or factura==comp:
        return []
    otherkey=key(r)[:2]+(comp,)
    return [other for other in documents.get(otherkey,[])
            if norm(other.get('NumeroComprobanteImputacion'))==factura
            and abs(amount(other)+amount(r))<=TOL]

def consolidate_net(observations, rows, balances):
    """Una fila por factura e imputacion; no sumar diferencias de controles distintos."""
    line_groups=defaultdict(list)
    saldo_groups=defaultdict(list)
    source_groups=defaultdict(list)
    for r in rows:
        if not pending(r) and not excluded(r):
            source_groups[key(r)+(norm(r.get('NumeroComprobanteImputacion')),ident(r.get('Subrecibo')))].append(r)
    for ob in observations:
        k=key(ob)
        if ob['Control']=='SALDO_COMPONENTES' or ob['Control'].startswith('REPLICA_SALDO_'):
            saldo_groups[k].append(ob)
        else:
            line_groups[k+(norm(ob.get('NumeroComprobanteImputacion')),ident(ob.get('Subrecibo')))].append(ob)
    by_invoice=defaultdict(list)
    for k in line_groups:
        by_invoice[k[:3]].append(k)
    for k, saldoobs in saldo_groups.items():
        targets=by_invoice[k] or [k+('','')]
        for target in targets:
            line_groups[target].extend(saldoobs)
    out=[]
    for k, obs in line_groups.items():
        first=next((o for o in obs if norm(o.get('NumeroComprobanteImputacion'))==k[3]),obs[0])
        row={f:v for f,v in first.items() if f in context(first | {'_fila':first['FilaOrigen']})}
        row['NumeroComprobanteImputacion']=first.get('NumeroComprobanteImputacion') if k[3] else ''
        row['Subrecibo']=k[4]
        source=source_groups.get(k,[])
        for field,label in zip(('Importe',)+COMPONENTS,('Importe','Neto','IVA','IIBB')):
            row[label]=sum((amount(r,field) for r in source),ZERO) if source else ''
        row['DiferenciaSuma']=row['Importe']-row['Neto']-row['IVA']-row['IIBB'] if source else ''
        actual=balances.get(k[:3],[])
        for field,label in zip(('Importe',)+COMPONENTS,('Saldo','SaldoNeto','SaldoIVA','SaldoIIBB')):
            row[label]=sum((amount(r,field) for r in actual),ZERO)
        row['Control']=' | '.join(dict.fromkeys(o['Control'] for o in obs))
        row['Estado']='REVISAR'
        row['Motivo']=' | '.join(dict.fromkeys(o['Control']+': '+o['Motivo'] for o in obs))
        row['CantidadObservaciones']=len(obs)
        row['FilaOrigen']=' | '.join(dict.fromkeys(str(o['FilaOrigen']) for o in obs))
        row['TipoCaso']='FACTURA E IMPUTACION' if k[3] else 'FACTURA'
        row['ToleranciaAcumulada']=TOL*len(actual)
        # Cada detalle conserva su fila, componente y valores; nunca se suman
        # diferencias de suma, replica y saldo como si fueran errores independientes.
        details=[]
        for o in obs:
            fields=['Componente','Registrado','Esperado','Diferencia','ImporteFactura','ComponenteFactura']
            parts=[f'fila {o["FilaOrigen"]}',o['Control']]
            parts.extend(f'{f}={o[f]}' for f in fields if f in o)
            details.append('; '.join(parts))
        row['DetalleValidaciones']=' | '.join(details)
        row['_observaciones']=obs
        out.append(row)
    return out

def classification(doc):
    doc=re.sub(r'[\s-]+','',norm(doc))
    if doc.startswith('OPX'): return 'OPX'
    if doc.startswith(('NC','NE')): return 'NOTAS DE CRÉDITO'
    if doc.startswith(('ND','DE')): return 'NOTAS DE DÉBITO'
    if doc.startswith('RC'): return 'RECIBOS'
    return 'FACTURAS INTERNAS' if doc else 'SIN IDENTIFICAR'

def official_invoice(doc):
    doc=norm(doc)
    return doc.startswith(OFFICIAL_INVOICES) or bool(re.match(r'^[A-Z]+-Y',doc))

def open_documents(rows, balances):
    pend=defaultdict(list)
    normal=defaultdict(list)
    concepts=defaultdict(set)
    document_dates=defaultdict(set)
    for r in rows:
        if excluded(r): continue
        scope=key(r)[:2]
        factura=norm(r.get('NumeroFactura'))
        comprobante=norm(r.get('NumeroComprobanteImputacion'))
        if not pending(r) and factura and dt(r.get('FechaFactura')):
            document_dates[scope+(factura,)].add(dt(r['FechaFactura']))
        if comprobante and dt(r.get('FechaComprobanteImputacion')):
            document_dates[scope+(comprobante,)].add(dt(r['FechaComprobanteImputacion']))
    def emission_date(scope, documents):
        values=set()
        for doc in documents:
            dates=document_dates.get(scope+(norm(doc),),set())
            if not dates: return '', 'Fecha no disponible en origen'
            values.update(dates)
        if not values: return '', 'Fecha no disponible en origen'
        if len(values)>1: return '', 'Fechas de emision diferentes; revisar origen'
        return next(iter(values)).isoformat(), 'OK'
    out=[]
    for r in rows:
        if excluded(r): continue
        scope=key(r)[:2]
        comp=norm(r.get('NumeroComprobanteImputacion'))
        if not pending(r) and comp:
            concepts[scope+(comp,)].add(str(r.get('ConceptoFacturacionImputacion') or r.get('Concepto') or ''))
        if pending(r):
            if official_invoice(comp): continue
            sub=ident(r.get('Subrecibo'))
            if sub:
                pend[scope+('SUBRECIBO',sub)].append(r)
            elif comp:
                pend[scope+('COMPROBANTE',comp)].append(r)
            else:
                out.append(observation(r,'SIN_IDENTIFICADOR','No se puede identificar el comprobante pendiente.',Clasificacion='SIN IDENTIFICAR',Saldo=amount(r),ComprobanteAbierto='',FechaComprobante='',ControlFecha='Fecha no disponible en origen'))
        elif not official_invoice(r.get('NumeroFactura')):
            normal[key(r)].append(r)
    represented=set()
    for k,rs in pend.items():
        total=sum((amount(r) for r in rs),ZERO)
        names=sorted({norm(r.get('NumeroComprobanteImputacion')) for r in rs if r.get('NumeroComprobanteImputacion')})
        represented.update(k[:2]+(doc,) for doc in names)
        if total==ZERO: continue
        classes={classification(doc) for doc in names}
        cl=next(iter(classes)) if len(classes)==1 else 'SIN IDENTIFICAR'
        fecha,control_fecha=emission_date(k[:2],names)
        refs=sorted({x for doc in names for x in concepts.get(k[:2]+(doc,),set()) if x})
        out.append(context(rs[0]) | {'Clasificacion':cl,'TipoComprobante':cl,
            'ComprobanteControlado':k[-1],'ComprobanteAbierto':' | '.join(names),
            'FechaComprobante':fecha,'ControlFecha':control_fecha,
            'ComprobantesRelacionados':'',
            'Conceptos':' | '.join(sorted({str(r.get('Concepto') or '') for r in rs})),
            'ConceptosImputadosDeReferencia':' | '.join(refs),
            'Saldo':total,'Estado':'ABIERTO' if len(classes)==1 else 'REVISAR',
            'CriterioAgrupacion':'Fondo + cliente + '+k[2].lower(),
            'Nota':'El saldo pendiente se toma del remanente del reporte. Los conceptos ya imputados son referencia.'})
    for k,rs in normal.items():
        if k in represented: continue  # El remanente pendiente es la representacion del saldo.
        total=sum((amount(r) for r in rs),ZERO)
        if total==ZERO: continue
        hasbase=any(base(r) for r in rs)
        # Un cruce FI reciproco sin emision independiente y con contraparte
        # cancelada no representa por si solo un nuevo comprobante abierto.
        if not hasbase and all(reciprocal_fi_reference(r,balances) for r in rs):
            counterparts={key(r)[:2]+(norm(r['NumeroComprobanteImputacion']),) for r in rs}
            if all(any(base(v) for v in balances.get(other,[])) and
                   sum((amount(v) for v in balances.get(other,[])),ZERO)==ZERO for other in counterparts):
                continue
        cl=classification(k[-1])
        fecha,control_fecha=emission_date(k[:2],[k[-1]])
        out.append(context(rs[0]) | {'Clasificacion':cl,'TipoComprobante':cl,
            'ComprobanteControlado':k[-1],'ComprobanteAbierto':k[-1],
            'FechaComprobante':fecha,'ControlFecha':control_fecha,
            'ComprobantesRelacionados':' | '.join(sorted({str(r.get('NumeroComprobanteImputacion')) for r in rs if r.get('NumeroComprobanteImputacion')})),
            'Conceptos':' | '.join(sorted({str(r.get('Concepto') or '') for r in rs})),
            'Saldo':total,'Estado':'ABIERTO' if hasbase else 'REVISAR',
            'CriterioAgrupacion':'Fondo + cliente + numero de comprobante',
            'Nota':'' if hasbase else 'Sin emision independiente visible. El saldo calculado requiere confirmar integridad del historico.'})
    return out

def service_cancellation(emissions, all_lines, corte):
    total=sum((amount(r) for r in emissions),ZERO)
    emitted_concepts={norm(r.get('Concepto')) for r in emissions}
    applied=[]
    for r in all_lines:
        if norm(r.get('NumeroComprobanteImputacion')).startswith(('NC-','NE-')):
            if (norm(r.get('Concepto')) not in emitted_concepts and
                norm(r.get('ConceptoFacturacionImputacion')) not in emitted_concepts):
                continue
            applied_date=dt(r.get('FechaImputacion')) or dt(r.get('FechaComprobanteImputacion'))
            if applied_date is None or applied_date<=corte:
                applied.append(r)
    credits=sum((amount(r) for r in applied),ZERO)
    full=bool(total and applied and total*credits<ZERO and abs(total+credits)<=TOL)
    return full, credits, sorted({norm(r['NumeroComprobanteImputacion']) for r in applied})

def controls(rows, corte, rules):
    rules=apply_confirmed_rules(rules)
    results = {n:[] for n in ['Control_Netos_Impuestos','Control_Datos_Obligatorios',
        'Control_Servicios_Administrativos','Saldo_MORA','Comprobantes_Abiertos','Control_Concepto_Agrupador']}
    invoices = defaultdict(list)
    balances = defaultdict(list)
    mora = defaultdict(lambda: defaultdict(lambda:ZERO))
    services = defaultdict(lambda:defaultdict(list))
    sub_concepts = defaultdict(set)
    for r in rows:
        if excluded(r):
            continue
        if not pending(r) and not missing(r.get('Subrecibo')):
            sub_concepts[(norm(r['FondoDeRiesgo']),ident(r['CodigoEmpresa']),ident(r['Subrecibo']))].add(str(r['ConceptoFacturacionImputacion'] or r['Concepto'] or ''))
        if not pending(r):
            balances[key(r)].append(r)
            if base(r):
                invoices[key(r)].append(r)
        if norm(r['GrupoConceptoFacturacion'])=='MORA':
            mora[r['FondoDeRiesgo']]['SaldoMORA'] += amount(r)
            mora[r['FondoDeRiesgo']]['Lineas'] += 1
        if base(r) and not pending(r):
            concept = norm(r['Concepto'])
            for stage in (1,2):
                if concept==norm(f'SERV. ADMINIST. FRG - {stage}º'):
                    if not missing(r['NumeroDeAporte']):
                        sk = (norm(r['FondoDeRiesgo']),ident(r['CodigoEmpresa']),ident(r['NumeroDeAporte']))
                        services[sk][stage].append(r)
                    else:
                        results['Control_Servicios_Administrativos'].append(observation(r,'VINCULACION','Falta numero de aporte; no se puede vincular el servicio.'))

    for r in rows:
        if excluded(r):
            continue
        if pending(r):
            continue
        net, iva, iibb = [amount(r,k) for k in ('ImporteNetoGravado','ImporteIVA','ImporteIIBB')]
        diff = amount(r)-net-iva-iibb
        if abs(diff)>TOL:
            results['Control_Netos_Impuestos'].append(observation(r,'SUMA_POR_LINEA','Importe distinto de neto + IVA + IIBB.',Diferencia=diff,Importe=amount(r),Neto=net,IVA=iva,IIBB=iibb))
        if pending(r):
            continue
        bs = targets(r,invoices) if not base(r) else [r]
        if not base(r) and not bs:
            bs=reciprocal_fi_reference(r,balances)
        if not base(r):
            ref,reason=reference_components(bs)
            if ref is None:
                results['Control_Netos_Impuestos'].append(observation(r,'REFERENCIA_NO_VERIFICABLE',reason))
            else:
                for field,label in zip(COMPONENTS,('NETO','IVA','IIBB')):
                    expected=(amount(r)*ref[field]/ref['Importe']).quantize(CENT,rounding=ROUND_HALF_UP)
                    registered=amount(r,field)
                    if abs(registered-expected)>TOL:
                        results['Control_Netos_Impuestos'].append(observation(r,'REPLICA_'+label,'La imputacion no replica proporcionalmente los importes registrados de la factura.',Componente=label,Importe=amount(r),Neto=net,IVA=iva,IIBB=iibb,ImporteFactura=ref['Importe'],ComponenteFactura=ref[field],Registrado=registered,Esperado=expected,Diferencia=registered-expected))

        cfg = rules.get(norm(r['Concepto']),{})
        mode = cfg.get('datos','SIN_DEFINIR')
        required = ['NumeroDeAporte'] if mode=='APORTE' else ['Expediente','Operacion'] if mode=='EXP_OP' else []
        if mode=='SIN_DEFINIR':
            results['Control_Datos_Obligatorios'].append(observation(r,'REGLA_SIN_DEFINIR','Confirmar si el concepto requiere aporte, expediente y operacion o esta exceptuado.'))
        if mode=='REQUIERE_DATO_SIN_DEFINIR':
            results['Control_Datos_Obligatorios'].append(observation(r,'DATO_EXIGIDO_POR_PRECISAR','El concepto requiere datos; falta confirmar si corresponde aporte o expediente y operacion. No se presume una excepcion.'))
        for field in required:
            if missing(r[field]):
                reason = f'Falta {field}.'
                if not cfg.get('datos_confirmados'):
                    reason += ' Regla propuesta por el patron del reporte; pendiente de confirmar.'
                results['Control_Datos_Obligatorios'].append(observation(r,'DATO_FALTANTE',reason,'ERROR' if cfg.get('datos_confirmados') else 'REVISAR',Campo=field))
        if not base(r) and mode!='EXENTO':
            if not bs:
                results['Control_Datos_Obligatorios'].append(observation(r,'REFERENCIA_NO_VINCULADA','No se logro vincular una linea de emision con el mismo fondo, cliente y comprobante. No confirma que falte la factura en SGA.'))
            else:
                for field in ('NumeroDeAporte','Expediente','Operacion'):
                    vals={ident(b[field]) for b in bs if not missing(b[field])}
                    if len(vals)==1 and ident(r[field])!=next(iter(vals)):
                        results['Control_Datos_Obligatorios'].append(observation(r,'DATOS_NO_COINCIDEN',f'{field} de imputacion no coincide con factura.','ERROR',Campo=field,Esperado=next(iter(vals)),Registrado=r[field]))
                    elif len(vals)>1:
                        results['Control_Datos_Obligatorios'].append(observation(r,'REFERENCIA_AMBIGUA',f'La factura tiene varios valores de {field}; revisar vinculo.'))

        expected = cfg.get('agrupador')
        if expected and norm(r['GrupoConceptoFacturacion'])!=norm(expected):
            results['Control_Concepto_Agrupador'].append(observation(r,'AGRUPADOR','Agrupador distinto del propuesto por las lineas de emision.','ERROR' if cfg.get('agrupador_confirmado') else 'REVISAR',AgrupadorEsperado=expected,ReglaConfirmada=cfg.get('agrupador_confirmado',False)))
        if not base(r):
            allbase=invoices.get(key(r),[]) or reciprocal_fi_reference(r,balances)
            allowed={norm(b['Concepto']) for b in allbase}
            ic=norm(r['ConceptoFacturacionImputacion'])
            if not allowed:
                results['Control_Concepto_Agrupador'].append(observation(r,'REFERENCIA_NO_VINCULADA','No se logro vincular la emision de referencia. No confirma que falte la factura en SGA.',ConceptosFactura=''))
            elif ic in CONDITIONAL_IMPUTATION:
                required_group=CONDITIONAL_IMPUTATION[ic]
                selected=targets(r,invoices) or reciprocal_fi_reference(r,balances)
                actual_groups={norm(b['GrupoConceptoFacturacion']) for b in selected}
                if actual_groups!={required_group}:
                    results['Control_Concepto_Agrupador'].append(observation(r,'IMPUTACION_FUERA_DE_AGRUPADOR','El concepto de imputacion solo es valido para el agrupador indicado.',ConceptosFactura=' | '.join(sorted(allowed)),AgrupadorRequerido=required_group,AgrupadorFactura=' | '.join(sorted(actual_groups))))
            elif ic not in allowed and ic not in ALLOWED_DIFFERENT_IMPUTATION:
                results['Control_Concepto_Agrupador'].append(observation(r,'CONCEPTO_IMPUTACION','Concepto de imputacion vacio o distinto de los conceptos emitidos, sin excepcion confirmada.',ConceptosFactura=' | '.join(sorted(allowed))))

    for k, rs in balances.items():
        totals={f:sum((amount(r,f) for r in rs),ZERO) for f in ('Importe','ImporteNetoGravado','ImporteIVA','ImporteIIBB')}
        residual=max(abs(totals[f]) for f in ('ImporteNetoGravado','ImporteIVA','ImporteIIBB'))
        tolerance=TOL*len(rs)
        if abs(totals['Importe'])<=TOL and residual>tolerance:
            results['Control_Netos_Impuestos'].append(observation(rs[0],'SALDO_COMPONENTES','Total cancelado con remanentes de neto o impuestos superiores al margen acumulado.',Saldo=totals['Importe'],SaldoNeto=totals['ImporteNetoGravado'],SaldoIVA=totals['ImporteIVA'],SaldoIIBB=totals['ImporteIIBB'],ToleranciaAcumulada=tolerance))
        ref,_=reference_components(invoices.get(k,[]))
        if abs(totals['Importe'])>TOL and ref is not None:
            for field,label in zip(COMPONENTS,('NETO','IVA','IIBB')):
                expected=(totals['Importe']*ref[field]/ref['Importe']).quantize(CENT,rounding=ROUND_HALF_UP)
                if abs(totals[field]-expected)>tolerance:
                    results['Control_Netos_Impuestos'].append(observation(rs[0],'REPLICA_SALDO_'+label,'El saldo por componente no conserva la proporcion de los importes registrados de la factura.',Componente=label,Saldo=totals['Importe'],ImporteFactura=ref['Importe'],ComponenteFactura=ref[field],Registrado=totals[field],Esperado=expected,Diferencia=totals[field]-expected,ToleranciaAcumulada=tolerance))

    results['Comprobantes_Abiertos']=open_documents(rows,balances)
    results['Control_Netos_Impuestos']=consolidate_net(results['Control_Netos_Impuestos'],rows,balances)

    for fund in sorted({r['FondoDeRiesgo'] for r in rows}):
        vals=mora[fund]
        results['Saldo_MORA'].append({'FondoDeRiesgo':fund,'SaldoMORA':vals['SaldoMORA'],'LineasIncluidas':vals['Lineas'],'Alcance':'Todo el historico del reporte; importe con signo; incluye imputaciones y NC.'})

    for sk, st in services.items():
        annulled=[]
        def unique(stage):
            bydoc={}
            for r in st[stage]:
                doc=norm(r['NumeroFactura'])
                if not doc.startswith(('FC','FE')) or amount(r)<ZERO:
                    continue
                emissions=[v for v in invoices.get(key(r),[]) if norm(v['Concepto'])==norm(r['Concepto'])]
                cancelled,credit,ncs=service_cancellation(emissions,balances.get(key(r),[]),corte)
                if cancelled:
                    if doc not in annulled:
                        annulled.append(doc)
                        results['Control_Servicios_Administrativos'].append(observation(r,'FACTURA_ANULADA','Factura anulada totalmente por NC aplicada; no se cuenta como servicio vigente.','ANULADA POR NC',NotasCredito=' | '.join(ncs),ImporteNC=credit))
                else:
                    bydoc[doc]=r
            return list(bydoc.values())
        first, second=unique(1), unique(2)
        if not first and not second:
            if not annulled:
                ref=(st[1] or st[2])[0]
                results['Control_Servicios_Administrativos'].append(observation(ref,'NC_REFACTURACION','Solo hay NC u otros documentos sin una factura vigente identificable.'))
            continue
        ref=(first or second)[0]
        if len(first)>1 or len(second)>1:
            results['Control_Servicios_Administrativos'].append(observation(ref,'DUPLICADO','Mas de una factura para el mismo aporte y servicio.',CantidadPrimero=len(first),CantidadSegundo=len(second),FacturasPrimero=' | '.join(r['NumeroFactura'] for r in first),FacturasSegundo=' | '.join(r['NumeroFactura'] for r in second)))
        if not first:
            had_first=any(norm(r['NumeroFactura']) in annulled for r in st[1])
            if had_first:
                results['Control_Servicios_Administrativos'].append(observation(ref,'SIN_PRIMER_VIGENTE','El primer servicio visible fue anulado por NC; revisar el antecedente vigente.'))
            else:
                results['Control_Servicios_Administrativos'].append(observation(ref,'SIN_ANTECEDENTE','Segundo servicio sin primero visible. El reporte puede omitir facturas antiguas canceladas.','SIN PRIMER SERVICIO VISIBLE'))
            continue
        if len(first)!=1 or len(second)>1:
            continue
        d=dt(first[0]['FechaFactura'])
        if not d:
            results['Control_Servicios_Administrativos'].append(observation(ref,'FECHA_INVALIDA','No se puede determinar el mes esperado.'))
            continue
        expected=date(d.year+1,d.month,1)
        monthend=date(expected.year,expected.month,calendar.monthrange(expected.year,expected.month)[1])
        sdate=dt(second[0]['FechaFactura']) if second else None
        if second and not sdate:
            status,reason='REVISAR','Fecha del segundo servicio invalida.'
        elif expected<START and second and sdate<=corte:
            status,reason='OK_HISTORICO','Existe segundo servicio; se acepta desfase historico.'
        elif second and sdate<=corte:
            status,reason=('OK','Segundo servicio emitido en el mes correspondiente.') if (sdate.year,sdate.month)==(expected.year,expected.month) else ('FUERA_DE_TERMINO','Segundo servicio emitido fuera del mes correspondiente.')
        elif corte<expected:
            status,reason='NO_EXIGIBLE','El mes de facturacion aun no comenzo.'
        elif corte<monthend:
            status,reason='PENDIENTE_EN_PLAZO','Falta segundo servicio; el mes aun no termino.'
        else:
            status,reason=('FALTANTE_HISTORICO' if expected<START else 'FALTANTE_VENCIDO'),'No hay segundo servicio emitido al corte.'
        results['Control_Servicios_Administrativos'].append(observation(ref,'SEGUNDO_SERVICIO',reason,status,MesEsperado=expected.strftime('%Y-%m'),FechaCorte=corte.isoformat(),FacturaSegundo=second[0]['NumeroFactura'] if second else '',FechaSegundo=second[0]['FechaFactura'] if second else ''))
    return results

def write_csv(path, records):
    cols=list(dict.fromkeys(k for row in records for k in row)) or ['Estado','Motivo']
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=cols,delimiter=';')
        writer.writeheader()
        for row in records:
            safe={}
            for k,v in row.items():
                if isinstance(v,D):
                    safe[k]=format(v,'f').replace('.',',')
                elif isinstance(v,str) and v.startswith(('=','+','@')):
                    safe[k]="'"+v
                else:
                    safe[k]=v
            writer.writerow(safe)


def leer_tramos(tramos, informar=protocolo, nombres=None):
    """Lee los tramos en orden como si fueran un solo reporte. `nombres`: nombres originales (en el
    server los archivos se guardan con otro nombre). Con más de un tramo, los errores de preparación
    nombran también el archivo."""
    tramos = [Path(t) for t in tramos]
    nombres = list(nombres or []) + [t.name for t in tramos[len(nombres or []):]]
    rows = []
    for i, (path, nombre) in enumerate(zip(tramos, nombres), 1):
        if not path.is_file():
            raise ValueError('No se encontro el archivo: '+nombre)
        if len(tramos) > 1:
            informar.paso(f'Leyendo tramo {i} de {len(tramos)}: {nombre}')
        else:
            informar.log('Reporte encontrado: '+nombre)
        leidas = list(read_xlsx(path, informar, nombre))
        for r in leidas:
            r['_varios_tramos'] = len(tramos) > 1
        rows.extend(leidas)
        informar.progreso(i / (len(tramos) + 1), f'{len(rows):,} lineas leidas')
    return rows


def ejecutar(tramos, salida, corte, parametros, informar=protocolo, nombres=None):
    """Corre los seis controles sobre los tramos y escribe en `salida` los libros pedidos,
    reglas_propuestas.json y ejecucion.json. Devuelve (reports, rules, summary)."""
    from .excel import build_reports, write_workbook
    parametros = dict(parametros or {})
    configurar(parametros)
    tramos = [Path(t) for t in tramos]
    salida = Path(salida)
    corte = _fecha(corte, None)
    if corte is None:
        raise ValueError('Falta la fecha de corte.')
    informar.paso('Leyendo el reporte completo...')
    rows = prepare(leer_tramos(tramos, informar, nombres))
    if not rows:
        raise ValueError('El reporte no contiene movimientos.')
    rules = default_rules(rows)
    confirmadas = reglas_confirmadas(parametros.get('reglas'))
    if confirmadas:
        rules.update(confirmadas)
    rules = apply_confirmed_rules(rules)
    informar.paso(f'{len(rows):,} lineas leidas. Ejecutando controles...')
    results = controls(rows, corte, rules)
    salida.mkdir(parents=True, exist_ok=True)
    reports = build_reports(rows, results, corte, varios_tramos=len(tramos) > 1)
    pedidas = parametros.get('salidas_a_generar')
    pedidas = set(pedidas) if pedidas else set(LIBROS)
    for report in reports:
        if report['name'] not in pedidas:
            continue
        write_workbook(salida / (report['name'] + '.xlsx'), report)
        informar.log(f"{report['name']}: " + ', '.join(f"{s['name']} ({len(s['rows']):,} filas)" for s in report['sheets']))
    (salida / 'reglas_propuestas.json').write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding='utf-8')
    nombres = list(nombres or []) + [t.name for t in tramos[len(nombres or []):]]
    # `archivo` conserva el nombre con un tramo (como el legado) y los une con ' | ' con varios; `archivos` lista todos.
    summary = {'version_programa': VERSION, 'archivo': ' | '.join(nombres), 'archivos': nombres, 'lineas': len(rows), 'fecha_corte_servicios': corte.isoformat(),
        'fondos': dict(Counter(r['FondoDeRiesgo'] for r in rows)),
        'salidas': {r['name']: sum(len(s['rows']) for s in r['sheets']) for r in reports},
        'observaciones_por_control': {k: len(v) for k, v in results.items()},
        'control_fechas_abiertos': dict(Counter(r.get('ControlFecha') for r in results['Comprobantes_Abiertos'])),
        'comprobantes_excluidos': sorted(EXCLUDED_DOCUMENTS),
        'lineas_excluidas': sum(excluded(r) for r in rows),
        'replica_impuestos': 'Proporcion de los importes originales registrados; no usa porcentajes de SGA.',
        'netos_consolidados': True, 'netos_sin_movimientos_pendientes': True,
        'formato': 'xlsx', 'futuros_no_exigibles_omitidos': {r['name']: r.get('future_omitted', 0) for r in reports if r.get('future_omitted', 0)}, 'solapas': {r['name']: {s['name']: len(s['rows']) for s in r['sheets']} for r in reports},
        'clasificaciones': dict(Counter(r['Clasificacion'] for r in results['Comprobantes_Abiertos'])),
        'nota': 'Cada salida aplica las exclusiones definidas en el manual. Fecha de corte para servicios y anulaciones. Reglas estadisticas pendientes de validar.'}
    (salida / 'ejecucion.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    informar.progreso(1.0, 'Controles terminados')
    return reports, rules, summary
