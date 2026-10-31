import unittest,tempfile,json,csv,contextlib,io
from pathlib import Path
from zipfile import ZipFile
from xml.sax.saxutils import escape
from decimal import Decimal as D
from conciliar import run,detect_sources,comparison_status,FUND

S=['FondoDeRiesgo','CodigoEmpresa','NumeroFactura','Importe','GrupoConceptoFacturacion','Subrecibo','NumeroComprobanteImputacion','CUIT','RazonSocial']
E=['Saldo2','Cuenta de cliente','Factura','Número de recibo','Número de Recibo global','Asiento','Tipo de transacción']

def fixture(path,sheets):
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with ZipFile(path,'w') as z:
        z.writestr('xl/workbook.xml','<workbook xmlns="'+ns+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{name}" sheetId="{i}" r:id="r{i}"/>' for i,(name,_) in enumerate(sheets,1))+'</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="r{i}" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1))+'</Relationships>')
        for i,(_,rows) in enumerate(sheets,1):
            # Celdas sin atributo r, como las exportaciones ERP.
            data=''.join(f'<row r="{n}">'+''.join('<c t="inlineStr"><is><t>'+escape(str(v))+'</t></is></c>' for v in row)+'</row>' for n,row in enumerate(rows,1))
            z.writestr(f'xl/worksheets/sheet{i}.xml','<worksheet xmlns="'+ns+'"><sheetData>'+data+'</sheetData></worksheet>')

def setup(root,separate=False):
    (root/'entradas').mkdir()
    (root/'configuracion.json').write_text(json.dumps({'fondo':FUND}))
    srows=[S,[FUND,'1','F1','100','Otros','','','201','Socio'],[FUND,'1','F1','-20','Otros','','','201','Socio'],[FUND,'1','F2','50','Otros','','','201','Socio'],[FUND,'1','F0','20','Otros','','','201','Socio'],[FUND,'1','F0','-20','Otros','','','201','Socio'],[FUND,'1','','-2','Movimientos Pendientes','','NC-1','201','Socio'],[FUND,'1','','-10','Movimientos Pendientes','SR-1','','201','Socio'],[FUND,'1','FC-X1','1','Otros','','','201','Socio']]
    fixture(root/'entradas'/'cualquier_sga.xlsx',[('Resumen',[['Saldo','Importe']]),('Original',srows)])
    erows=[['80','1','F1','','','','Cliente'],['30','2','F3','','','','Cliente'],['-2','1','NC-1','','','','Cliente'],['-10','1','','SR-1','OP-X1','','Pago'],['7','1','','','','REH1','Pago'],['1','1','FC-X1','','','','Diario general']]
    if separate:
        for i,tx in enumerate(['Cliente','Pago','Diario general']):fixture(root/'entradas'/f'descarga_{i}.xlsx',[('Datos',[E]+[r for r in erows if r[6]==tx])])
    else:fixture(root/'entradas'/'erp_12345.xlsx',[('FAC',[['Factura','Saldo2']]),('Original',[E]+erows)])

def read(out,name):
    with (out/'Respaldo_tecnico'/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f,delimiter=';'))

class General(unittest.TestCase):
    def test_opx_usa_socio_y_subrecibo_no_numero_global(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            p=Path(tmp);setup(p)
            fixture(p/'entradas'/'cualquier_sga.xlsx',[('Datos',[S,
                [FUND,'1','','-30','Movimientos Pendientes','SR-1','','201','Uno'],
                [FUND,'2','','-40','Movimientos Pendientes','SR-1','','202','Dos']])])
            fixture(p/'entradas'/'erp_12345.xlsx',[('Datos',[E,
                ['-10','1','','SR-1','OP-X111','','Pago'],
                ['-20','1','','SR-1','OP-X222','','Pago'],
                ['-40','2','','SR-1','OP-X111','','Pago'],
                ['-7','3','','','OP-X333','','Pago']])])
            out=run(p,scope='abiertos')
            body=[r for r in read(out,'Conciliacion_general.csv') if r['Tipo']!='CONTROL']
            self.assertEqual(len(body),3)
            self.assertTrue(all(r['Tipo']=='OP-X' for r in body))
            pairs=[r for r in body if r['Comprobante']=='SR-1']
            self.assertEqual({r['Cliente'] for r in pairs},{'1','2'})
            self.assertTrue(all(r['Resultado']=='COINCIDE' for r in pairs))
            no_sr=next(r for r in body if r['Comprobante']=='OP-X333')
            self.assertEqual(no_sr['Saldo SGA'],'')
            self.assertEqual(no_sr['Resultado'],'SOLO EN ERP — REVISAR EN SGA')

    def test_todos_los_importes_y_una_sola_salida(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            p=Path(tmp);setup(p)
            # Reemplaza SGA con casos excluidos por la versión anterior.
            rows=[S,[FUND,'1','F1','80','Otros','','','201','Socio'],[FUND,'1','F2','50','Otros','','','201','Socio'],[FUND,'1','F0','0','Otros','','','201','Socio'],[FUND,'1','','-2','Movimientos Pendientes','','NC-1','201','Socio'],[FUND,'1','','-10','Movimientos Pendientes','SR-1','','201','Socio'],[FUND,'1','FC-X1','1','Otros','','','201','Socio'],[FUND,'1','','-153.32','Otros','','','201','Socio'],[FUND,'1','','153.32','Otros','SR-999','OP-X999','201','Socio'],[FUND,'1','','-100','Otros','','','201','Socio'],[FUND,'1','FI-P1','-300','Aportes','','','201','Socio'],[FUND,'1','','300','Movimientos Pendientes','','FI-P1','201','Socio']]
            fixture(p/'entradas'/'cualquier_sga.xlsx',[('Resumen',[['Otra cosa']]),('Original',rows)])
            o=run(p,scope='abiertos');data=read(o,'Conciliacion_general.csv')
            body=[r for r in data if r['Tipo']!='CONTROL'];controls=[r for r in data if r['Tipo']=='CONTROL']
            self.assertEqual([f.name for f in o.iterdir() if f.is_file()],['Conciliacion_general.xlsx'])
            self.assertEqual(sum(D(r['Saldo SGA']) for r in body if r['Saldo SGA']),D(19))
            self.assertEqual(sum(D(r['Saldo ERP']) for r in body if r['Saldo ERP']),D(106))
            unidentified=[r for r in body if r['Resultado'].startswith('SIN COMPROBANTE EN SGA')]
            self.assertEqual(len(unidentified),3)
            self.assertEqual({r['Saldo SGA'] for r in unidentified},{'-153.32','153.32','-100.00'})
            reh=next(r for r in body if r['Tipo']=='REH');self.assertEqual(reh['Saldo ERP'],'7.00');self.assertEqual(reh['Saldo SGA'],'')
            fip=next(r for r in body if r['Comprobante']=='FI-P1')
            self.assertEqual(fip['Saldo SGA'],'0.00');self.assertEqual(fip['Filas SGA'],'2')
            absent=next(r for r in body if r['Comprobante']=='F2')
            self.assertEqual(absent['Saldo ERP'],'');self.assertEqual(absent['Diferencia SGA menos ERP'],'')
            self.assertEqual(next(r for r in body if r['Comprobante']=='F0')['Resultado'],'NO EVALUADO - ERP SOLO ABIERTOS')
            op=next(r for r in body if r['Comprobante']=='SR-1')
            self.assertEqual(op['Tipo'],'OP-X');self.assertEqual(op['Resultado'],'COINCIDE')
            from conciliar import sheet_names,xlsx_rows
            self.assertEqual(sheet_names(o/'Conciliacion_general.xlsx'),['Resumen','Conciliación general'])
            xrows=list(xlsx_rows(o/'Conciliacion_general.xlsx','Conciliación general'))
            self.assertEqual(len(xrows),len(body)+1)
            self.assertFalse(any(r.get(0)=='CONTROL' for _,r in xrows))
            summary=json.loads((o/'Respaldo_tecnico/Resumen.json').read_text())
            self.assertEqual(summary['cobertura_salida']['SGA']['filas_fuente'],len(rows)-1)
            self.assertEqual(summary['cobertura_salida']['SGA']['filas_fuente'],sum(int(r['Filas SGA']) for r in body))
            self.assertEqual(summary['cobertura_salida']['ERP']['filas_fuente'],sum(int(r['Filas ERP']) for r in body))
            total=next(r for r in controls if r['Comprobante']=='TOTAL GENERAL POR COMPROBANTE')
            self.assertEqual(total['Diferencia SGA menos ERP'],'-87.00')

    def test_separados_equivalen_unificado(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b,contextlib.redirect_stdout(io.StringIO()):
            pa,pb=Path(a),Path(b);setup(pa);setup(pb,True)
            oa=run(pa,scope='abiertos');ob=run(pb,scope='abiertos')
            def comparable(out):
                return [(r['Tipo'],r['Cliente'],r['Comprobante'],r['Saldo SGA'],r['Saldo ERP'],r['Resultado']) for r in read(out,'Conciliacion_general.csv') if r['Tipo']!='CONTROL']
            self.assertEqual(comparable(oa),comparable(ob))

    def test_no_oculta_redondeo_por_comprobante(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            p=Path(tmp);setup(p)
            fixture(p/'entradas'/'cualquier_sga.xlsx',[('Datos',[S,[FUND,'1','A','0.005','Otros','','','201','Socio'],[FUND,'1','B','0.005','Otros','','','201','Socio']])])
            out=run(p,scope='completo');data=read(out,'Conciliacion_general.csv')
            ctrl=next(r for r in data if r['Comprobante']=='DIFERENCIA DE REDONDEO')
            self.assertEqual(ctrl['Saldo SGA'],'-0.01')

    def test_rechaza_mezcla_superpuesta(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            p=Path(tmp);setup(p)
            fixture(p/'entradas'/'extra.xlsx',[('Datos',[E,['80','1','F1','','','','Cliente']])])
            with self.assertRaisesRegex(ValueError,'repetido'):run(p,scope='abiertos')
            self.assertFalse(any((p/'resultados').rglob('COMPLETADO.txt')))

if __name__=='__main__':unittest.main()

