"""Presentacion de resultados SGA y exportacion XLSX portable con la biblioteca estandar."""
import re
import math
import zipfile
from datetime import date
from decimal import Decimal
from xml.sax.saxutils import escape, quoteattr
import control_sga as c

ORIGINAL = ['CodigoEmpresa','CUIT','RazonSocial','CodigoSocio','NumeroDeAporte',
 'Expediente','Operacion','TipoLinea','Linea','Canal','GrupoConceptoFacturacion',
 'Concepto','NumeroFactura','FechaFactura','ConceptoFacturacionImputacion',
 'NumeroComprobanteImputacion','FechaComprobanteImputacion','FechaImputacion',
 'Importe','ImporteNetoGravado','PorcentajeIVA','ImporteIVA','PorcentajeIIBB','ImporteIIBB']
MONEY = {'Importe','ImporteNetoGravado','ImporteIVA','ImporteIIBB','Saldo','Saldo MORA',
 'Neto esperado','Diferencia neto','IVA esperado','Diferencia IVA','IIBB esperado',
 'Diferencia IIBB','Diferencia suma','Saldo neto','Saldo IVA','Saldo IIBB','Importe NC'}
DATEFIELDS={'FechaFactura','FechaComprobanteImputacion','FechaImputacion','Fecha primero','Fecha segundo','FechaComprobante'}
CONTROLS = {
 'DATO_FALTANTE':'Dato obligatorio faltante','DATOS_NO_COINCIDEN':'Datos distintos de la factura',
 'REGLA_SIN_DEFINIR':'Regla pendiente de definir','REFERENCIA_NO_VINCULADA':'Referencia a revisar',
 'REFERENCIA_AMBIGUA':'Referencia ambigua','AGRUPADOR':'Concepto y agrupador',
 'IMPUTACION_FUERA_DE_AGRUPADOR':'Imputacion fuera del agrupador permitido',
 'CONCEPTO_IMPUTACION':'Concepto de imputacion diferente','VINCULACION':'Falta numero de aporte',
 'SEGUNDO_SERVICIO':'Segundo servicio','DUPLICADO':'Servicios duplicados',
 'SIN_ANTECEDENTE':'Antecedente no visible','FACTURA_ANULADA':'Factura anulada por NC',
 'SIN_PRIMER_VIGENTE':'Primer servicio anulado','NC_REFACTURACION':'NC o refacturacion a revisar',
 'FECHA_INVALIDA':'Fecha a revisar',
}

def money(v):
    s=f'{abs(v):,.2f}'.replace(',','X').replace('.',',').replace('X','.')
    return ('-$' if v<0 else '$')+s

def net_message(observations):
    complete=[];correct=[]
    for ob in observations:
        if ob['Control'].startswith('REPLICA_') and not ob['Control'].startswith('REPLICA_SALDO_'):
            label={'NETO':'Neto','IVA':'IVA','IIBB':'IIBB'}[ob['Componente']]
            bucket=complete if ob['Registrado']==0 and ob['Esperado']!=0 else correct
            if label not in bucket:bucket.append(label)
    parts=[]
    order=('Neto','IVA','IIBB')
    if complete:parts.append('Completar '+' + '.join(x for x in order if x in complete))
    if correct:parts.append('Corregir '+' + '.join(x for x in order if x in correct))
    if parts:return '; '.join(parts)
    codes={o['Control'] for o in observations}
    if 'SUMA_POR_LINEA' in codes:parts.append('Revisar suma Neto + IVA + IIBB')
    elif any(x=='SALDO_COMPONENTES' or x.startswith('REPLICA_SALDO_') for x in codes):parts.append('Revisar saldo Neto + impuestos')
    if 'REFERENCIA_NO_VERIFICABLE' in codes:parts.append('Revisar factura de referencia')
    return '; '.join(parts)

def consolidate_data(observations):
    groups={}
    labels={'NumeroDeAporte':'N° de aporte','Expediente':'Expediente','Operacion':'Operación'}
    for ob in observations:
        # El numero de fila mantiene separadas la factura, cada imputacion y
        # tambien dos lineas distintas de una misma imputacion.
        k=(c.key(ob),int(ob['FilaOrigen']))
        groups.setdefault(k,[]).append(ob)
    out=[]
    for obs in groups.values():
        r=dict(obs[0]);parts=[]
        missing=list(dict.fromkeys(o.get('Campo') for o in obs if o['Control']=='DATO_FALTANTE'))
        if missing:parts.append('Completar '+' + '.join(labels.get(f,f) for f in missing))
        mismatch=list(dict.fromkeys(o.get('Campo') for o in obs if o['Control']=='DATOS_NO_COINCIDEN'))
        if mismatch:parts.append('Corregir '+' + '.join(labels.get(f,f) for f in mismatch)+' según factura')
        for ob in obs:
            if ob['Control'] not in ('DATO_FALTANTE','DATOS_NO_COINCIDEN'):
                parts.append({'REGLA_SIN_DEFINIR':'Confirmar datos requeridos por el concepto',
                  'DATO_EXIGIDO_POR_PRECISAR':'Confirmar qué datos requiere el concepto',
                  'REFERENCIA_NO_VINCULADA':'Revisar factura de referencia',
                  'REFERENCIA_AMBIGUA':'Revisar datos de la factura de referencia'}.get(ob['Control'],ob['Motivo']))
        proposed=any('Regla propuesta' in o['Motivo'] for o in obs)
        r['Motivo']='; '.join(dict.fromkeys(parts))+(' (regla propuesta)' if proposed else '')
        r['Control']=' / '.join(dict.fromkeys(CONTROLS.get(o['Control'],o['Control']) for o in obs))
        r['Estado']='ERROR' if any(o['Estado']=='ERROR' for o in obs) else 'REVISAR'
        r['Campo']=' + '.join(dict.fromkeys(labels.get(o['Campo'],o['Campo']) for o in obs if o.get('Campo')))
        r['Esperado']='; '.join(dict.fromkeys(labels.get(o.get('Campo'),str(o.get('Campo')))+': '+str(o['Esperado']) for o in obs if 'Esperado' in o))
        r['Registrado']='; '.join(dict.fromkeys(labels.get(o.get('Campo'),str(o.get('Campo')))+': '+str(o.get('Registrado') or '(vacío)') for o in obs if 'Registrado' in o))
        r['TipoLineaControl']='Factura' if not r.get('NumeroComprobanteImputacion') else 'Imputación'
        out.append(r)
    return out

def typed(v, field):
    if v is None or v=='': return None
    if field in DATEFIELDS:
        d=c.dt(v)
        return (d-date(1899,12,30)).days if d else str(v)
    if isinstance(v,Decimal): return float(v)
    if field in MONEY or field.startswith('Porcentaje'):
        return float(c.num(v))
    if isinstance(v,(int,float)): return v
    return str(v)

def sheet(name, columns, records, note):
    rows=[[typed(r.get(f),f) for f in columns] for r in records]
    formats=['date' if f in DATEFIELDS else 'money' if f in MONEY else 'number' if f.startswith('Porcentaje') else 'text' for f in columns]
    orange=[[i,columns.index(f)] for i,r in enumerate(records) for f in r.get('_orange',[]) if f in columns]
    widths=[]
    for f in columns:
        widths.append(44 if f in ('Qué hay que corregir','Motivo') else 30 if f in ('Control','Estado','Clasificación') else 38 if f in ('RazonSocial','Concepto','ConceptoFacturacionImputacion','Conceptos') else 25 if f in ('NumeroFactura','NumeroComprobanteImputacion','Comprobante','Factura primero','Factura segundo') else 19 if f in MONEY or f in DATEFIELDS else 17)
    return {'name':name,'columns':columns,'rows':rows,'formats':formats,'orange':orange,'widths':widths,'note':note,'freeze':2 if columns[0]=='Control' else 1}

def annual(records, corte, yearof):
    current=[];history=[];future=[]
    for r in records:
        y=yearof(r)
        (current if y==corte.year else future if y is not None and y>corte.year else history).append(r)
    return current,history,future

def build_reports(rows, results, corte):
    idx={int(r['_fila']):r for r in rows}
    current_invoices=set()
    invrows={}
    for r in rows:
        if c.pending(r) or c.excluded(r):continue
        k=c.key(r);invrows.setdefault(k,[]).append(r)
        d=c.dt(r.get('FechaImputacion'))
        if not c.base(r) and d and (d.year,d.month)==(corte.year,corte.month):current_invoices.add(k)
    reports=[]
    net=[]
    for case in results['Control_Netos_Impuestos']:
        raw=case.get('_observaciones',[])
        saldo=[o for o in raw if o['Control']=='SALDO_COMPONENTES' or o['Control'].startswith('REPLICA_SALDO_')]
        lines=[o for o in raw if o not in saldo]
        ids=list(dict.fromkeys(int(o['FilaOrigen']) for o in lines)) or [int(raw[0]['FilaOrigen'])]
        for fid in ids:
            src=idx[fid]
            obs=[o for o in lines if int(o['FilaOrigen'])==fid]+saldo
            row={f:src.get(f) for f in ORIGINAL}
            row['FondoDeRiesgo']=src['FondoDeRiesgo'];row['Fila SGA']=fid
            replica=[o for o in obs if o['Control'].startswith('REPLICA_') and not o['Control'].startswith('REPLICA_SALDO_')]
            labels=[]
            if replica:labels.append('Imputacion de neto o impuestos')
            if any(o['Control']=='SUMA_POR_LINEA' for o in obs):labels.append('Suma de componentes')
            if saldo:labels.append('Saldo por componente')
            if any(o['Control']=='REFERENCIA_NO_VERIFICABLE' for o in obs):labels.append('Referencia a revisar')
            row['Control']='Neto + impuestos' if replica or any(o['Control']=='SUMA_POR_LINEA' for o in obs) else 'Saldo por componente' if saldo else 'Referencia a revisar'
            # Primero la causa comprobada y luego su efecto en el saldo.
            ordered=replica+[o for o in obs if o not in replica and o not in saldo]+saldo
            row['Qué hay que corregir']=net_message(ordered)
            row['_orange']=[]
            for o in replica:
                f,label={'NETO':('ImporteNetoGravado','neto'),'IVA':('ImporteIVA','IVA'),'IIBB':('ImporteIIBB','IIBB')}[o['Componente']]
                row['_orange'].append(f);row[label.upper()+' esperado' if label!='neto' else 'Neto esperado']=o['Esperado']
                row['Diferencia '+label]=o['Registrado']-o['Esperado']
            for o in obs:
                if o['Control']=='SUMA_POR_LINEA':
                    row['Diferencia suma']=o['Diferencia']
                    if not replica:row['_orange'].append('Importe')
            row.update({'Saldo':case['Saldo'],'Saldo neto':case['SaldoNeto'],'Saldo IVA':case['SaldoIVA'],'Saldo IIBB':case['SaldoIIBB']})
            for ob in saldo:
                for field,label in [('SaldoNeto','Saldo neto'),('SaldoIVA','Saldo IVA'),('SaldoIIBB','Saldo IIBB')]:
                    if (ob['Control']=='SALDO_COMPONENTES' and abs(case[field])>case['ToleranciaAcumulada']) or ob['Control']=='REPLICA_SALDO_'+{'SaldoNeto':'NETO','SaldoIVA':'IVA','SaldoIIBB':'IIBB'}[field]:
                        row['_orange'].append(label)
            net.append(row)
    netcols=['Control','Qué hay que corregir']+ORIGINAL+['FondoDeRiesgo','Neto esperado','Diferencia neto','IVA esperado','Diferencia IVA','IIBB esperado','Diferencia IIBB','Diferencia suma','Saldo','Saldo neto','Saldo IVA','Saldo IIBB','Fila SGA']
    mora=[r for r in net if c.norm(r['GrupoConceptoFacturacion'])=='MORA']
    rest=[r for r in net if c.norm(r['GrupoConceptoFacturacion'])!='MORA']
    cur=[r for r in rest if c.key(r) in current_invoices];hist=[r for r in rest if c.key(r) not in current_invoices]
    reports.append({'name':'Control_Netos_Impuestos','sheets':[
        sheet('MORA',netcols,mora,'MORA de todos los años. Anaranjado: celda observada. Columnas SGA originales sin modificar.'),
        sheet('Mes en curso',netcols,cur,f'Otros agrupadores con imputaciones en {corte:%m/%Y}, aunque la factura sea anterior.'),
        sheet('Histórico',netcols,hist,'Otros agrupadores sin imputaciones en el mes de corte. Los saldos son contexto; no sumarlos entre filas de una misma factura.') ]})
    for topic in ('Control_Datos_Obligatorios','Control_Concepto_Agrupador'):
        rec=[]
        source=consolidate_data(results[topic]) if topic=='Control_Datos_Obligatorios' else results[topic]
        for ob in source:
            r=dict(ob);r['Control']=CONTROLS.get(ob['Control'],ob['Control'])
            if topic!='Control_Datos_Obligatorios' and ob['Control']=='DATO_FALTANTE':r['Motivo']='Falta '+str(ob.get('Campo'))+'.'+(' Regla propuesta por confirmar.' if ob['Estado']=='REVISAR' else '')
            if topic!='Control_Datos_Obligatorios' and ob['Control']=='DATOS_NO_COINCIDEN':r['Motivo']=f"{ob.get('Campo')}: la imputacion indica {ob.get('Registrado') or '(vacio)'}; la factura indica {ob.get('Esperado')}."
            if ob['Control']=='IMPUTACION_FUERA_DE_AGRUPADOR':r['Motivo']=f"Este concepto solo se admite para {ob.get('AgrupadorRequerido')}; la factura esta en {ob.get('AgrupadorFactura')}."
            rec.append(r)
        cols=(['Control','Estado','Motivo','TipoLineaControl','Campo','Esperado','Registrado'] if topic=='Control_Datos_Obligatorios' else ['Control','Estado','Motivo'])+['FondoDeRiesgo','CodigoEmpresa','CUIT','RazonSocial','NumeroFactura','FechaFactura','NumeroComprobanteImputacion','FechaImputacion','Concepto','ConceptoFacturacionImputacion','GrupoConceptoFacturacion']
        cols+=['NumeroDeAporte','Expediente','Operacion','FilaOrigen'] if topic=='Control_Datos_Obligatorios' else ['AgrupadorEsperado','AgrupadorRequerido','AgrupadorFactura','FilaOrigen']
        cur,hist,future=annual(rec,corte,lambda r:c.dt(r.get('FechaFactura')).year if c.dt(r.get('FechaFactura')) else None)
        reports.append({'name':topic,'sheets':[sheet('Año en curso',cols,cur,f'Facturas del año {corte.year}. Control, estado y motivo al principio.'),sheet('Histórico',cols,hist,'Facturas de años anteriores. Las fechas vacías se conservan aquí para revisar.')],'future_omitted':len(future)})
    service=[]
    for ob in results['Control_Servicios_Administrativos']:
        r=dict(ob);r['Control']=CONTROLS.get(ob['Control'],ob['Control'])
        k=c.key(ob);same=invrows.get(k,[])
        first=c.norm(ob.get('Concepto'))==c.norm('SERV. ADMINIST. FRG - 1º')
        r.update({'Factura primero':ob['NumeroFactura'] if first else '', 'Fecha primero':ob['FechaFactura'] if first else None,
                  'Factura segundo':ob.get('FacturaSegundo') or ('' if first else ob['NumeroFactura']),
                  'Fecha segundo':ob.get('FechaSegundo') or (None if first else ob['FechaFactura']),
                  'Mes esperado':ob.get('MesEsperado'),'NC aplicada':ob.get('NotasCredito'),'Importe NC':ob.get('ImporteNC')})
        if ob['Control']=='SIN_ANTECEDENTE':r['Motivo']='No se ve el primer servicio en el reporte. Puede estar cancelado y omitido del historico.'
        if ob['Control']=='FACTURA_ANULADA':r['Motivo']='Anulada totalmente por NC aplicada; no cuenta como servicio vigente ni duplicado.'
        r['_year']=int(ob['MesEsperado'][:4]) if ob.get('MesEsperado') else (c.dt(ob['FechaFactura']).year+(1 if first else 0) if c.dt(ob['FechaFactura']) else None)
        service.append(r)
    cur,hist,future=annual(service,corte,lambda r:r['_year'])
    cols=['Control','Estado','Motivo','FondoDeRiesgo','CodigoEmpresa','CUIT','RazonSocial','NumeroDeAporte','Factura primero','Fecha primero','Factura segundo','Fecha segundo','Mes esperado','NC aplicada','Importe NC','FilaOrigen']
    reports.append({'name':'Control_Servicios_Administrativos','sheets':[sheet('Año en curso',cols,cur,f'Segundo servicio correspondiente a {corte.year}. Sin primer visible: se clasifica por fecha del segundo.'),sheet('Histórico',cols,hist,'Servicios correspondientes a años anteriores. Los futuros no exigibles quedan fuera de estas dos vistas.')],'future_omitted':len(future)})
    opened=[]
    for ob in results['Comprobantes_Abiertos']:
        r=dict(ob);r['Clasificación']=r['Clasificacion'];r['Comprobante']=r.get('ComprobanteAbierto','')
        r['Motivo']=r.get('Nota') or r.get('Motivo') or 'Saldo abierto.';r['Conceptos']=r.get('Conceptos') or r.get('Concepto')
        if r.get('ControlFecha')!='OK':r['_orange']=['FechaComprobante']
        opened.append(r)
    cols=['Clasificación','Estado','FondoDeRiesgo','CodigoEmpresa','CUIT','RazonSocial','Comprobante','FechaComprobante','Subrecibo','Conceptos','Saldo','Motivo','ControlFecha','ComprobantesRelacionados']
    reports.append({'name':'Comprobantes_Abiertos','sheets':[sheet('Comprobantes abiertos',cols,opened,'Se excluyen FC-A, FC-B, FE-A y serie Y. Incluye cualquier saldo distinto de cero, de ambos signos.')]})
    reports.append({'name':'Saldo_MORA','sheets':[sheet('Saldo por fondo',['FondoDeRiesgo','Saldo MORA','Líneas incluidas'],[{'FondoDeRiesgo':r['FondoDeRiesgo'],'Saldo MORA':r['SaldoMORA'],'Líneas incluidas':int(r['LineasIncluidas'])} for r in results['Saldo_MORA']],'Todo el histórico del agrupador MORA; facturas, imputaciones y NC con sus signos.')]})
    for report in reports:
        report['cutoff']=corte.isoformat()
    return reports

def col(n):
    s=''
    while n:
        n,r=divmod(n-1,26);s=chr(65+r)+s
    return s

def text(v):
    return escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(v)))

def write_workbook(path, report):
    """Exportador portable para que el usuario ejecute el programa sin paquetes adicionales."""
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    relns='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    styles=f'''<styleSheet xmlns="{ns}"><numFmts count="2"><numFmt numFmtId="164" formatCode="#,##0.00;[Red]-#,##0.00"/><numFmt numFmtId="165" formatCode="dd/mm/yyyy"/></numFmts><fonts count="3"><font><sz val="10"/><name val="Arial"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Arial"/></font><font><b/><sz val="14"/><name val="Arial"/></font></fonts><fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF24445C"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF4B183"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="7"><xf fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="center" wrapText="1"/></xf><xf fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"><alignment vertical="center" horizontal="center" wrapText="1"/></xf><xf fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf fontId="0" fillId="0" borderId="0" numFmtId="164" xfId="0" applyNumberFormat="1"><alignment horizontal="right" vertical="center"/></xf><xf fontId="0" fillId="0" borderId="0" numFmtId="165" xfId="0" applyNumberFormat="1"><alignment vertical="center"/></xf><xf fontId="0" fillId="3" borderId="0" numFmtId="164" xfId="0" applyFill="1" applyNumberFormat="1"><alignment horizontal="right" vertical="center"/></xf><xf fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"><alignment vertical="center" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''
    def cell(address,value,style=0):
        if value is None:return f'<c r="{address}" s="{style}"/>' if style in (5,6) else ''
        if isinstance(value,(int,float)):
            return f'<c r="{address}" s="{style}"><v>{value}</v></c>'
        return f'<c r="{address}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{text(value)}</t></is></c>'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('_rels/.rels',f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{relns}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/styles.xml',styles)
        sheets=[];rels=[];content=[]
        for si,s in enumerate(report['sheets'],1):
            sheets.append(f'<sheet name={quoteattr(s["name"])} sheetId="{si}" r:id="rId{si}"/>')
            rels.append(f'<Relationship Id="rId{si}" Type="{relns}/worksheet" Target="worksheets/sheet{si}.xml"/>')
            content.append(f'<Override PartName="/xl/worksheets/sheet{si}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
            last=col(len(s['columns']));end=len(s['rows'])+5;orange={tuple(p) for p in s['orange']}
            with z.open(f'xl/worksheets/sheet{si}.xml','w') as out:
                def put(v):out.write(v.encode('utf-8'))
                put(f'<worksheet xmlns="{ns}"><dimension ref="A1:{last}{end}"/><sheetViews><sheetView workbookViewId="0" showGridLines="0"><pane xSplit="{s["freeze"]}" ySplit="5" topLeftCell="{col(s["freeze"]+1)}6" activePane="bottomRight" state="frozen"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight="36"/><cols>')
                for i,w in enumerate(s['widths'],1):put(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>')
                put('<'+'/'+'cols><sheetData>')
                put('<row r="2" ht="24" customHeight="1">'+cell('A2',report['name'].replace('_',' '),2)+'</row>')
                put('<row r="3" ht="30" customHeight="1">'+cell('A3',f"Corte {report['cutoff']} · {len(s['rows'])} casos · "+s['note'])+'</row>')
                put('<row r="5" ht="56" customHeight="1">'+''.join(cell(col(i+1)+'5',v,1) for i,v in enumerate(s['columns']))+'</row>')
                for ri,row in enumerate(s['rows']):
                    rn=ri+6
                    lines=max([math.ceil(len(v)/max(12,s['widths'][ci]*.9)) if isinstance(v,str) else 1 for ci,v in enumerate(row)]+[1])
                    height=max(30,min(210,14*lines+8))
                    put(f'<row r="{rn}" ht="{height}" customHeight="1">')
                    for ci,v in enumerate(row):
                        style=3 if s['formats'][ci]=='money' else 4 if s['formats'][ci]=='date' and isinstance(v,(int,float)) else 0
                        if (ri,ci) in orange:style=5 if s['formats'][ci]=='money' else 6
                        put(cell(col(ci+1)+str(rn),v,style))
                    put('</row>')
                put(f'</sheetData><autoFilter ref="A5:{last}{end}"/><mergeCells count="2"><mergeCell ref="A2:{last}2"/><mergeCell ref="A3:{last}3"/></mergeCells></worksheet>')
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="{relns}"><sheets>'+''.join(sheets)+'</sheets></workbook>')
        rels.append(f'<Relationship Id="rId{len(sheets)+1}" Type="{relns}/styles" Target="styles.xml"/>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(rels)+'</Relationships>')
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(content)+'</Types>')
