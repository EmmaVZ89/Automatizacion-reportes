"""Conciliación General v1.5 (motor). Python 3.10+, sin paquetes adicionales.
No modifica fuentes. Decimal exacto; suma antes de redondear ROUND_HALF_UP.

Copia de legado/conciliacion_general/conciliar.py (v1.4) con los cambios mínimos del patrón de la herramienta
(sin input(), sin rutas propias, parámetros explícitos, tramos, avisos por `informar`) y los tres cambios de
negocio de la v1.5, pedidos por la responsable funcional (ver docs/reglas/conciliacion_general.md):
  1. ERP de saldos abiertos: un comprobante de SGA ausente en ERP se compara contra ERP 0,00
     (saldo SGA cero = COINCIDE; distinto de cero = DIFERENCIA, con saldo y diferencia informados).
  2. Los Movimientos Pendientes de SGA referidos a una factura (FI-, FC-, ND-) se informan en una fila
     propia (Tipo PENDIENTE) y no se suman al saldo del comprobante.
  3. Tipo de los subrecibos = tipo del comprobante principal (RC-X, RC-R, OP-X...); el cruce sigue por subrecibo.
El resto (matemática, orden de filas, textos y formato) es el del legado.
"""
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, getcontext
from collections import defaultdict, Counter
from datetime import datetime
import csv, hashlib, json, re, sqlite3, itertools

from .._comun import protocolo
from .excel import export_excel, label

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
FUND = 'Fondo de Riesgo General'  # default del parámetro `fondo`
ZERO = Decimal(0)
CENT = Decimal('.01')
# Los libros guardados por Excel pueden contener residuos de precisión binaria
# con muchos decimales. Mantenerlos hasta sumar, sin redondear las filas.
getcontext().prec = 80
HEAD = ['Tipo', 'Cliente', 'Comprobante', 'CUIT', 'Razon social', 'Saldo SGA',
        'Saldo ERP', 'Diferencia SGA menos ERP', 'Resultado', 'Filas SGA',
        'Filas ERP', 'Origen SGA (primeras 5)', 'Origen ERP (primeras 5)',
        'Estado revision', 'Observaciones']
COLUMNAS_SGA = {'FondoDeRiesgo','CodigoEmpresa','NumeroFactura','Importe','GrupoConceptoFacturacion','Subrecibo','NumeroComprobanteImputacion','CUIT','RazonSocial'}
COLUMNAS_ERP = {'Saldo2','Cuenta de cliente','Factura','Número de recibo','Número de Recibo global','Asiento','Tipo de transacción'}
ENTRADAS = (('sga', 'SGA'), ('erp', 'ERP'))
VERSION = '1.5'
# Tipo visible del comprobante principal de un subrecibo: RC-X, RC-R, RC-O, OP-X...
RE_PRINCIPAL = re.compile(r'^([A-Z]{2,3}-[A-Z])')
NOTA_ABIERTOS = 'No figura en el ERP de saldos abiertos: se toma saldo ERP 0,00.'
NOTA_PENDIENTE = 'Movimiento pendiente de imputación de SGA referido a este comprobante: se informa en una fila aparte y no se suma al saldo del comprobante.'
NOTA_SIN_PRINCIPAL = 'No se identificó el comprobante principal (recibo u orden de pago) del subrecibo.'
NOTA_VARIOS_PRINCIPALES = 'El subrecibo figura con comprobantes principales de distinto tipo: revisar.'

def tipo_visible(kind, principales):
    """Tipo que se muestra: el del comprobante principal para subrecibos y OP-X; PENDIENTE para los
    movimientos pendientes referidos a una factura; el tipo interno para el resto."""
    if kind=='MP':return 'PENDIENTE'
    if kind not in ('SR','OPX'):return kind
    tipos=sorted({m.group(1) for p in principales for m in [RE_PRINCIPAL.match(p)] if m})
    return ' / '.join(tipos) if tipos else 'SUBRECIBO'

def rounded(n):
    return n.quantize(CENT, rounding=ROUND_HALF_UP)

def text(v):
    return str(v or '').strip()

def cell_text(c, strings):
    t = c.get('t'); v = c.find(NS+'v')
    if t == 'inlineStr': return ''.join(x.text or '' for x in c.iter(NS+'t'))
    if v is None: return ''
    if t == 'e': return 'ERROR_EXCEL:'+str(v.text)
    return strings[int(v.text)] if t == 's' else v.text or ''

def sheet_names(path):
    with ZipFile(path) as z:
        book=ET.fromstring(z.read('xl/workbook.xml'))
        return [s.get('name') for s in book.find(NS+'sheets')]

def xlsx_rows(path, sheet=None):
    """Lee una hoja conservando números XML y números de fila originales."""
    with ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            with z.open('xl/sharedStrings.xml') as f:
                root=None
                for event,e in ET.iterparse(f, events=('start','end')):
                    if root is None: root=e
                    if event=='end' and e.tag==NS+'si':
                        strings.append(''.join(x.text or '' for x in e.iter(NS+'t')))
                        root.clear()
        book=ET.fromstring(z.read('xl/workbook.xml'))
        sheets=book.find(NS+'sheets')
        if sheets is None or not len(sheets): raise ValueError(f'{path.name}: sin hojas')
        selected=sheets[0] if sheet is None else next((s for s in sheets if s.get('name')==sheet),None)
        if selected is None:raise ValueError(f'{path.name}: no existe la hoja {sheet}')
        rid=selected.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target=next(x.get('Target') for x in rels if x.get('Id')==rid)
        target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
        with z.open(target) as f:
            root=None
            for event,e in ET.iterparse(f,events=('start','end')):
                if root is None:root=e
                if event!='end' or e.tag!=NS+'row':continue
                out={}
                next_col=0
                for c in e:
                    if c.tag!=NS+'c':continue
                    ref=c.get('r',''); col=0
                    for ch in ref:
                        if not ch.isalpha():break
                        col=col*26+ord(ch.upper())-64
                    idx=col-1 if ref else next_col
                    out[idx]=cell_text(c,strings)
                    next_col=idx+1
                n=int(e.get('r','0'))
                yield n,out
                e.clear();root.clear()

def number(v, where):
    # Los Excel de origen usan punto decimal en el XML. No inferir separadores.
    try:
        d=Decimal(text(v))
        if not d.is_finite():raise InvalidOperation()
        return d
    except InvalidOperation:
        raise ValueError(f'{where}: importe vacío o inválido {v!r}. No se reemplazó por cero.')

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def writer(path,header):
    f=path.open('w',encoding='utf-8-sig',newline='')
    w=csv.writer(f,delimiter=';');w.writerow(header)
    return f,w

def safe(v):
    # Evitar fórmulas al abrir texto externo en Excel.
    if isinstance(v,str) and v.startswith(('=','+','-','@')):return "'"+v
    return v

def identificar(p):
    """[(lado, hoja, fila_encabezado)] de las hojas de datos originales de un libro, sin depender de su nombre."""
    try:
        hojas=sheet_names(p)
    except (BadZipFile, KeyError) as e:
        raise ValueError(f'{p.name}: no es un libro de Excel (.xlsx) o está dañado.') from e
    matches=[]
    for hoja in hojas:
        it=xlsx_rows(p,hoja)
        try:
            # No convertir tablas dinámicas/resúmenes en fuentes. Solo encabezados completos.
            for n,h in itertools.islice(it,10):
                headers={text(v):k for k,v in h.items() if text(v)}
                sga=COLUMNAS_SGA<=headers.keys()
                erp=COLUMNAS_ERP<=headers.keys()
                if sga or erp:
                    if sga and erp:raise ValueError(f'{p.name}, hoja {hoja}: esquema ambiguo')
                    matches.append(('SGA' if sga else 'ERP',hoja,n))
                    break
        finally:it.close()
    return matches

def detectar_tipo(path):
    """'SGA' | 'ERP' | None según la única hoja de datos originales del libro."""
    matches=identificar(Path(path))
    return matches[0][0] if len(matches)==1 else None

def detect_sources(entradas, informar=protocolo):
    """Identifica la hoja de datos original de cada archivo. `entradas` = {'sga': [tramos del histórico SGA],
    'erp': [ERP unificado, separados por tipo o tramos]}, cada lista ya ordenada. Devuelve [(lado, spec, path)]
    en el orden de lectura: SGA y después ERP."""
    found=[]
    for clave,expected in ENTRADAS:
        for p in entradas.get(clave) or []:
            p=Path(p)
            if not p.is_file():raise ValueError(f'No existe el archivo de entrada: {p.name}')
            informar.log('Identificando '+p.name)
            matches=identificar(p)
            if len(matches)!=1:
                raise ValueError(f'{p.name}: se esperaba una sola hoja de datos originales; encontradas {len(matches)}: {matches}. Conserve una única fuente original por libro.')
            side,hoja,headerrow=matches[0]
            if side!=expected:raise ValueError(f'{p.name}: es un archivo de {side} y se lo indicó como {expected}.')
            spec={'archivo':p.name,'reporte':'Historico' if side=='SGA' else 'ERP automático','hoja':hoja,'fila_encabezado':headerrow,'fecha_descarga':'NO INFORMADA'}
            found.append((side,spec,p))
            informar.log('  '+side+' -> '+p.name+' / '+hoja)
    if not any(x[0]=='SGA' for x in found):raise ValueError('Se requiere al menos un archivo de SGA.')
    if not any(x[0]=='ERP' for x in found):raise ValueError('Se requiere un ERP unificado, reportes ERP separados por tipo o sus tramos.')
    return found


def comparison_status(sv, ev, scope, kind='FACTURA'):
    if sv is not None and ev is not None:
        return 'COINCIDE' if sv==ev else 'DIFERENCIA'
    if scope=='abiertos':
        # v1.5: el ERP de abiertos sólo trae saldos pendientes; si el comprobante no figura, su saldo ERP es cero.
        if sv is not None:
            return 'COINCIDE' if sv==0 else 'DIFERENCIA'
        return 'SOLO ERP - REVISAR' if ev!=0 else 'NO EVALUADO - ERP SOLO ABIERTOS'
    if sv is not None:return 'PENDIENTE NUEVA DESCARGA ERP' if sv!=0 else 'SOLO SGA SALDO CERO - REVISAR'
    return 'SOLO ERP - REVISAR' if ev!=0 else ('SOLO ERP SALDO CERO - VERIFICAR ANTIGUEDAD' if kind=='FACTURA' else 'SOLO ERP SALDO CERO - REVISAR')

def run(entradas, salida, alcance, corte=None, fondo=FUND, informar=protocolo):
    """Escribe Conciliacion_general.xlsx y Respaldo_tecnico/ en `salida` y devuelve el resumen (lo que va a Resumen.json)."""
    scope=alcance;cutoff=corte or None
    if scope not in ('abiertos','completo'):raise ValueError('Indique el alcance del reporte ERP: abiertos o completo')
    if cutoff:
        try:datetime.strptime(cutoff,'%Y-%m-%d')
        except (TypeError,ValueError):raise ValueError('Fecha de corte inválida. Use AAAA-MM-DD.')
    fondo=text(fondo)
    if not fondo:raise ValueError('Indique el fondo de riesgo.')
    paths=[];hashes=set()
    # El fondo llega como parámetro; los archivos se detectan por encabezados.
    for side,spec,p in detect_sources(entradas,informar):
        digest=sha(p)
        if digest in hashes:raise ValueError(f'Archivo duplicado por contenido: {p.name}. Revisar tramos.')
        hashes.add(digest);paths.append((side,spec,p,digest))
    out=Path(salida);out.mkdir(parents=True,exist_ok=True)
    backup=out/'Respaldo_tecnico';backup.mkdir(exist_ok=True)
    traza=backup/'trazabilidad.sqlite'
    if traza.exists():traza.unlink()
    db=sqlite3.connect(traza)
    try:
        db.execute('CREATE TABLE filas(sistema TEXT,categoria TEXT,tipo TEXT,cliente TEXT,comprobante TEXT,importe TEXT,archivo TEXT,fila INTEGER,cuit TEXT,razon TEXT,factura TEXT,subrecibo TEXT,recibo_global TEXT,asiento TEXT,grupo TEXT)')
        stats=Counter();totals=defaultdict(Decimal);manifest=[];issues=[];special=[];type_sources={}
        for i,(side,spec,p,digest) in enumerate(paths):
            informar.paso('Leyendo '+side+' '+spec.get('reporte','')+' '+p.name)
            informar.progreso(i/(len(paths)+1),p.name)
            origin=p.name+' ['+spec['hoja']+']'
            it=xlsx_rows(p,spec['hoja'])
            for n,h in it:
                if n==spec['fila_encabezado']:break
            else:raise ValueError('Encabezado desaparecido en '+origin)
            headers={text(v):k for k,v in h.items()}
            if len([text(v) for v in h.values() if text(v)])!=len(set(text(v) for v in h.values() if text(v))):raise ValueError(f'{p.name}: encabezados duplicados')
            required=(['FondoDeRiesgo','GrupoConceptoFacturacion','Importe','CodigoEmpresa','NumeroFactura','Subrecibo','NumeroComprobanteImputacion','CUIT','RazonSocial'] if side=='SGA' else ['Saldo2','Cuenta de cliente','Factura','Número de recibo','Número de Recibo global','Asiento','Tipo de transacción'])
            missing=[x for x in required if x not in headers]
            if missing:raise ValueError(f'{p.name}: faltan columnas: {", ".join(missing)}')
            count=0;included=0;subtotal=ZERO;batch=[];types=Counter()
            for n,row in it:
                if not any(text(v) for v in row.values()):continue
                count+=1
                def g(k):return text(row.get(headers.get(k,-1),''))
                if any(g(k).startswith('ERROR_EXCEL:') for k in required):raise ValueError(f'{origin}, fila {n}: error Excel en una columna requerida')
                if side=='SGA' and g('FondoDeRiesgo')!=fondo:continue
                included+=1
                amount=number(g('Importe' if side=='SGA' else 'Saldo2'),f'{p.name}, fila {n}')
                client=g('CodigoEmpresa' if side=='SGA' else 'Cuenta de cliente')
                if not client:raise ValueError(f'{p.name}, fila {n}: cliente vacío')
                if side=='SGA':
                    fact=g('NumeroFactura');sr=g('Subrecibo');imp=g('NumeroComprobanteImputacion');group=g('GrupoConceptoFacturacion');rc='';seat=''
                    if group.casefold()=='movimientos pendientes':
                        if sr and imp.startswith('NC-'):
                            category=kind='AMBIGUO';doc=f'{p.name}:fila:{n}'
                            issues.append([side,p.name,n,client,imp,'NC y subrecibo simultáneos',str(amount)])
                        elif imp.startswith('NC-'):category=kind='NC';doc=imp
                        elif sr:category=kind='SR';doc=sr
                        else:
                            category=kind='MP_OTRO';doc=imp or f'{p.name}:fila:{n}'
                    elif fact:category=kind='NC' if fact.startswith('NC-') else 'FACTURA';doc=fact
                    else:category=kind='SIN_FACTURA';doc=f'{p.name}:fila:{n}'
                    # v1.5: el comprobante principal del subrecibo (RC-X, OP-X...) define el Tipo visible.
                    if category=='SR':rc=imp
                    cuit=g('CUIT');razon=g('RazonSocial')
                    if kind in ('MP_OTRO','SIN_FACTURA'):
                        issues.append([side,p.name,n,client,imp or fact,'Movimiento sin cruce automático',str(amount)])
                else:
                    fact=g('Factura');sr=g('Número de recibo');rc=g('Número de Recibo global');seat=g('Asiento');group='';cuit='';razon=''
                    tx=g('Tipo de transacción');types[tx]+=1
                    if tx.casefold() not in ('cliente','pago','diario general'):
                        raise ValueError(f'{origin}, fila {n}: tipo de transacción vacío o no reconocido: {tx!r}')
                    # Varios archivos con el mismo tipo son tramos de una misma descarga: se concatenan y se avisa.
                    owners=type_sources.setdefault(tx.casefold(),(tx,[]))[1]
                    if p.name not in owners:owners.append(p.name)
                    if scope=='abiertos' and amount==0:stats['ERP_filas_saldo2_cero']+=1
                    if rc.startswith('OP-X'):
                        category='OPX';kind='SR' if sr.startswith('SR-') else 'OPX';doc=sr if kind=='SR' else rc
                        if fact:issues.append([side,p.name,n,client,rc,'OPX también tiene factura: revisar prioridad',str(amount)])
                    elif seat.startswith('REH'):category=kind='REH';doc=seat
                    elif fact:category=kind='NC' if fact.startswith('NC-') else 'FACTURA';doc=fact
                    elif sr.startswith('SR-'):category=kind='SR';doc=sr
                    else:category=kind='OTRO';doc=seat or f'{p.name}:fila:{n}'
                    if category=='OTRO' and amount:
                        issues.append([side,p.name,n,client,doc,'Saldo sin identificador de conciliación',str(amount)])
                if side=='SGA' and category=='MP_OTRO':
                    # v1.5: el pendiente referido a una factura va a su propia fila (no se suma al comprobante).
                    if imp.startswith(('FI-','FC-','ND-')):
                        kind='MP';doc=imp
                    elif imp.startswith('NC-'):
                        kind='NC';doc=imp
                    elif imp.startswith('REH'):
                        kind='REH';doc=imp
                batch.append((side,category,kind,client,doc,str(amount),origin,n,cuit,razon,fact,sr,rc,seat,group))
                stats[side+'_'+category]+=1;totals[side+'_'+category]+=amount;totals[side]+=amount;subtotal+=amount
                if len(batch)>=5000:
                    db.executemany('INSERT INTO filas VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',batch);batch.clear()
                if included%100000==0:informar.log('  '+str(included)+' filas procesadas')
            if batch:db.executemany('INSERT INTO filas VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',batch)
            db.commit()
            manifest.append({'sistema':side,'reporte':spec.get('reporte','Historico'),'archivo':p.name,'hoja':spec['hoja'],'sha256':digest,'filas_archivo':count,'filas_incluidas':included,'total_exacto':str(subtotal),'integridad':'NO CONFIRMADA' if side=='ERP' else 'SEGUN ARCHIVO RECIBIDO','fecha_descarga':spec.get('fecha_descarga','NO INFORMADA'),'tipos':dict(types)})
            if side=='ERP' and count==450000:issues.append([side,p.name,'','','','Alerta: exactamente 450000 filas. Posible descarga recortada',''])
        for tx,owners in type_sources.values():
            if len(owners)>1:issues.append(['ERP','','','',tx,'Tramos del mismo tipo de transacción: '+', '.join(owners)+'. Verificar que sean partes de una misma descarga',''])
        informar.paso('Preparando conciliación general de todos los movimientos...')
        informar.progreso(len(paths)/(len(paths)+1),'Conciliando')
        db.execute('CREATE INDEX ix_clave ON filas(sistema,tipo,cliente,comprobante)');db.commit()
        def aggregates(side):
            cur=db.execute('SELECT tipo,cliente,comprobante,importe,archivo,fila,cuit,razon,categoria,subrecibo,recibo_global FROM filas WHERE sistema=? ORDER BY tipo,cliente,comprobante',(side,))
            for key,rows in itertools.groupby(cur,lambda r:r[:3]):
                amount=ZERO;count=0;refs=[];cuit='';razon='';categories=set();aliases=set();principales=set()
                for r in rows:
                    amount+=Decimal(r[3]);count+=1
                    if len(refs)<5:refs.append(f'{r[4]}:{r[5]}')
                    cuit=cuit or r[6];razon=razon or r[7];categories.add(r[8])
                    if r[9]:aliases.add(r[9])
                    if r[10]:aliases.add(r[10]);principales.add(r[10])
                # Se retiene el saldo exacto para el control independiente de cobertura.
                yield key,(amount,count,' | '.join(refs),cuit,razon,categories,aliases,principales)
        sga=dict(aggregates('SGA'));erp=dict(aggregates('ERP'))
        counts=Counter();display_totals=defaultdict(Decimal);exact_totals=defaultdict(Decimal);included_rows=Counter()
        general_path=backup/'Conciliacion_general.csv'
        headers=HEAD+['Fondo','Detalle identificacion']
        full_f,full=writer(general_path,headers)
        allkeys=sorted(sga.keys()|erp.keys())
        unidentified={'SIN_FACTURA','SIN_ID_MP','MP_OTRO','AMBIGUO','OTRO'}
        def money(v):
            v=rounded(v)
            return format(abs(v) if v==0 else v,'.2f')
        for key in allkeys:
            kind,client,doc=key;sa=sga.get(key);ea=erp.get(key)
            sv=rounded(sa[0]) if sa is not None else None
            ev=rounded(ea[0]) if ea is not None else None
            status=comparison_status(sv,ev,scope,kind)
            notes=[]
            # v1.5: en abiertos, el comprobante de SGA que no figura en ERP se compara contra ERP 0,00.
            erp_cero=scope=='abiertos' and sa is not None and ea is None and kind not in unidentified
            if erp_cero:ev=ZERO
            delta=sv-ev if sv is not None and ev is not None else None
            if kind in unidentified:
                status='REVISAR IDENTIFICACION - '+('SGA' if sa is not None else 'ERP')
                notes.append('No se asigna una contraparte automáticamente; se conserva el movimiento y su fila de origen.')
            if kind=='REH':
                notes.append('Asiento REH incluido en el saldo general; no se concilia por importe ni por estado de cheque.')
            if kind=='MP':
                notes.append(NOTA_PENDIENTE)
            elif (sa is not None and 'MP_OTRO' in sa[5]):
                notes.append('Incluye movimiento pendiente identificado por comprobante; revisar su clasificación por separado.')
            if (sa is not None and 'OPX' in sa[5]) or (ea is not None and 'OPX' in ea[5]):
                notes.append('OPX incluida una sola vez; si hay subrecibo, el cruce se hace por ese identificador.')
            principales=(sa[7] if sa is not None else set())|(ea[7] if ea is not None else set())
            tipo=tipo_visible(kind,principales)
            if kind in ('SR','OPX'):
                if tipo=='SUBRECIBO':notes.append(NOTA_SIN_PRINCIPAL)
                elif ' / ' in tipo:notes.append(NOTA_VARIOS_PRINCIPALES)
            if erp_cero:notes.append(NOTA_ABIERTOS)
            aliases=set()
            for side,a in [('SGA',sa),('ERP',ea)]:
                if a is not None:
                    exact_totals[side]+=a[0];display_totals[side]+=rounded(a[0]);included_rows[side]+=a[1];aliases.update(a[6])
            status=label(status)
            counts[status]+=1
            row=[tipo,client,doc,(sa or ea)[3],(sa or ea)[4],money(sv) if sv is not None else '',money(ev) if ev is not None else '',money(delta) if delta is not None else '',status,sa[1] if sa else 0,ea[1] if ea else 0,sa[2] if sa else '',ea[2] if ea else '', '', ' '.join(notes),fondo,' | '.join(sorted(aliases))]
            full.writerow([safe(v) if i not in (5,6,7) else v for i,v in enumerate(row)])
        controls={}
        for side in ('SGA','ERP'):
            source_count=db.execute('SELECT COUNT(*) FROM filas WHERE sistema=?',(side,)).fetchone()[0]
            if exact_totals[side]!=totals[side] or included_rows[side]!=source_count:
                raise AssertionError('La salida general no cubre todos los movimientos de '+side)
            controls[side]={'filas_fuente':source_count,'filas_incluidas_resultado':included_rows[side],'total_fuente_exacto':str(totals[side]),'total_resultado_exacto':str(exact_totals[side]),'total_fuente_redondeado':money(totals[side]),'suma_saldos_por_comprobante':money(display_totals[side]),'diferencia_redondeo':money(rounded(totals[side])-display_totals[side])}
        missing_types=sorted(set(('cliente','pago','diario general'))-set(type_sources))
        if missing_types:issues.append(['ERP','','','','','Sin filas de estos tipos: '+', '.join(missing_types)+'. Verificar cobertura.',''])
        if stats['ERP_filas_saldo2_cero']:issues.append(['ERP','','','','','Modo abiertos: filas con Saldo2 cero: '+str(stats['ERP_filas_saldo2_cero'])+'. Se conservaron; revisar filtro y divisas.',''])
        def footer(label,saldo_sga='',saldo_erp='',difference='',result='',detail=''):
            row=['']*len(headers);row[0]='CONTROL';row[2]=label;row[5]=saldo_sga;row[6]=saldo_erp;row[7]=difference;row[8]=result;row[14]=detail;row[15]=fondo
            full.writerow([safe(v) if i not in (5,6,7) else v for i,v in enumerate(row)])
        # Los controles están al final y se distinguen por Tipo=CONTROL. No son
        # comprobantes y no deben sumarse otra vez con las filas de datos.
        footer('TOTAL GENERAL POR COMPROBANTE',money(display_totals['SGA']),money(display_totals['ERP']),money(display_totals['SGA']-display_totals['ERP']),'TOTAL INFORMATIVO','Suma del detalle de Conciliación general. Estos totales se muestran solo en Resumen. No certifica integridad ni resuelve ausentes.')
        footer('TOTAL FUENTES RECIBIDAS',money(totals['SGA']),money(totals['ERP']),money(totals['SGA']-totals['ERP']),'TOTAL INFORMATIVO','Totales calculados desde todas las filas incluidas de los originales.')
        footer('DIFERENCIA DE REDONDEO',controls['SGA']['diferencia_redondeo'],controls['ERP']['diferencia_redondeo'],result='CONTROL DE REDONDEO',detail='Total fuente redondeado menos suma de saldos redondeados por comprobante; no se oculta ni se ajusta.')
        footer('COBERTURA DE MOVIMIENTOS',result='TODOS LOS MOVIMIENTOS INCLUIDOS',detail='SGA: '+str(included_rows['SGA'])+' filas. ERP: '+str(included_rows['ERP'])+' filas. Cada fila se incluyó una sola vez en el resultado.')
        footer('ALCANCE Y CORTE',result='PRUEBA PRELIMINAR',detail='ERP: '+scope+'. Corte declarado: '+(cutoff or 'NO CONFIRMADO')+'. Integridad ERP no confirmada. El corte no reconstruye saldos históricos.')
        for status,count in sorted(counts.items()):footer('CANTIDAD: '+status,result=str(count),detail='Cantidad de filas de datos de este resultado; no incluye controles.')
        for x in issues:footer('ALERTA',result='REVISAR',detail=' | '.join(str(v) for v in x if str(v)))
        for x in manifest:footer('FUENTE '+x['sistema'],detail=x['archivo']+' / hoja '+x['hoja']+' / filas incluidas '+str(x['filas_incluidas'])+' / SHA256 '+x['sha256'])
        full_f.close()
        summary={'version':VERSION,'alcance_erp':scope,'fecha_corte':cutoff or 'NO CONFIRMADA','fondo':fondo,'estado':'PRUEBA PRELIMINAR - INTEGRIDAD ERP NO CONFIRMADA','salida_principal':'Conciliacion_general.xlsx','registros_datos':len(allkeys),'conteos':dict(counts),'cobertura_salida':controls,'fuentes':manifest,'tipos_erp_ausentes':missing_types,'alertas':issues}
        (backup/'Resumen.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        db.close()
    excel_path=out/'Conciliacion_general.xlsx'
    exported=export_excel(general_path,excel_path)
    if exported!=len(allkeys):raise AssertionError('Cantidad de comprobantes en Excel incorrecta')
    (backup/'COMPLETADO.txt').write_text('Cálculo completado. La conciliación general incluye todos los movimientos recibidos; revisar estados y alcance antes de validar el cierre.\n',encoding='utf-8')
    informar.progreso(1.0,'Listo')
    informar.log('Resultado: '+excel_path.name)
    informar.log('Abra Conciliacion_general.xlsx: Resumen contiene controles; Conciliación general contiene solo comprobantes.')
    return summary
