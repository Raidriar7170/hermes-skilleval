"""Source-supported final contracts, authored before final policy sampling."""

CONTRACTS = {
    "e6be626": (
        "sqlite-utils",
        "Fix index introspection for table and column identifiers containing double quotes. Table.indexes and Table.xindexes must report the correct index/column metadata without SQL errors. Transforming such a table must preserve its index and data. Keep ordinary identifiers working; index internal names are unspecified unless supplied explicitly.",
        r"""
import pytest
from sqlite_utils import Database

@pytest.mark.parametrize('table,column', [('Go"sh','c"1'),('a"b"c','x"y')])
def test_target(table,column):
    db=Database(memory=True)
    db[table].insert({'id':1,column:2,'other':3},pk='id')
    db[table].create_index([column])
    assert [i.columns for i in db[table].indexes]==[[column]]
    indexes=db[table].xindexes
    assert len(indexes)==1
    assert [c.name for c in indexes[0].columns if c.key]==[column]
    db[table].transform(types={'other':str})
    assert [i.columns for i in db[table].indexes]==[[column]]
    assert list(db[table].rows)==[{'id':1,column:2,'other':'3'}]
    db.close()

def test_regression():
    db=Database(memory=True);db['t'].insert({'id':1,'name':'a'},pk='id');db['t'].create_index(['name'])
    assert [i.columns for i in db['t'].indexes]==[['name']]
    assert db['t'].get(1)['name']=='a';db.close()
""",
    ),
    "c872d27": (
        "sqlite-utils",
        "Use REAL as SQLite floating-point column type consistently in the Python API and CLI, including CSV --detect-types. This must enable floating values in STRICT tables and preserve numeric values on import. Existing FLOAT input aliases remain accepted; normal text/integer/blob handling stays compatible.",
        r"""
import pytest
from sqlite_utils import Database
from sqlite_utils.cli import cli
from click.testing import CliRunner

@pytest.mark.parametrize('strict',[False,True])
def test_target_api(strict):
    db=Database(memory=True)
    db['t'].create({'id':int,'value':float},strict=strict)
    assert {c.name:c.type for c in db['t'].columns}['value']=='REAL'
    db['t'].insert({'id':1,'value':4.5})
    assert list(db['t'].rows)==[{'id':1,'value':4.5}]
    db.close()

def test_target_csv(tmp_path):
    src=tmp_path/'a.csv';src.write_text('name,value\nalpha,4.5\nbeta,6.25\n')
    path=str(tmp_path/'d.db')
    r=CliRunner().invoke(cli,['insert',path,'t',str(src),'--csv','--detect-types'])
    assert r.exit_code==0,r.output
    db=Database(path)
    assert {c.name:c.type for c in db['t'].columns}['value']=='REAL'
    assert list(db['t'].rows)==[{'name':'alpha','value':4.5},{'name':'beta','value':6.25}];db.close()

def test_regression():
    db=Database(memory=True);db['t'].insert({'id':1,'name':'a','raw':b'abc'},pk='id')
    assert db['t'].get(1)=={'id':1,'name':'a','raw':b'abc'};db.close()
""",
    ),
    "b962909": (
        "sqlite-utils",
        "Fix upsert_all() for a table whose only column is also its primary key. Initial and repeated upserts must preserve the distinct key values without invalid SQL or duplicate rows. Keep single-column insert_all and ordinary multi-column upsert updates working.",
        r"""
from sqlite_utils import Database

def test_target():
    db=Database(memory=True);t=db['t']
    t.upsert_all([{'name':'a'},{'name':'b'}],pk='name')
    t.upsert_all([{'name':'a'},{'name':'c'}],pk='name')
    assert sorted(list(t.rows),key=lambda r:r['name'])==[{'name':'a'},{'name':'b'},{'name':'c'}]
    assert t.pks==['name']

def test_regression():
    db=Database(memory=True);db['one'].insert_all([{'name':'a'}],pk='name')
    assert list(db['one'].rows)==[{'name':'a'}]
    db['two'].upsert_all([{'id':1,'name':'a'}],pk='id');db['two'].upsert_all([{'id':1,'name':'b'}],pk='id')
    assert list(db['two'].rows)==[{'id':1,'name':'b'}]
""",
    ),
    "a7b29bf": (
        "sqlite-utils",
        "Fix sqlite-utils upsert --csv with --detect-types (or -d): populated CSV rows should be upserted and their detected integer/floating values retained correctly, including repeat updates using --pk. Preserve ordinary CSV insert with type detection and unaffected values.",
        r"""
import pytest
from sqlite_utils import Database
from sqlite_utils.cli import cli
from click.testing import CliRunner

@pytest.mark.parametrize('flag',['-d','--detect-types'])
def test_target(tmp_path,flag):
    src=tmp_path/'a.csv';src.write_text('id,name,age,weight\n1,Cleo,6,45.5\n2,Dori,1,3.5\n')
    path=str(tmp_path/'d.db');runner=CliRunner()
    r=runner.invoke(cli,['upsert',path,'t',str(src),'--csv','--pk','id',flag])
    assert r.exit_code==0,r.output
    db=Database(path)
    assert list(db['t'].rows)==[{'id':1,'name':'Cleo','age':6,'weight':45.5},{'id':2,'name':'Dori','age':1,'weight':3.5}]
    src.write_text('id,name,age,weight\n1,Cleo,7,46.5\n')
    r=runner.invoke(cli,['upsert',path,'t',str(src),'--csv','--pk','id',flag])
    assert r.exit_code==0,r.output
    assert db['t'].get(1)['age']==7 and db['t'].get(2)['weight']==3.5

def test_regression(tmp_path):
    src=tmp_path/'a.csv';src.write_text('id,n\n1,4.5\n')
    path=str(tmp_path/'d.db');r=CliRunner().invoke(cli,['insert',path,'t',str(src),'--csv','--detect-types'])
    assert r.exit_code==0,r.output
    assert list(Database(path)['t'].rows)==[{'id':1,'n':4.5}]
""",
    ),
    "b2e54cd": (
        "csvkit",
        "Fix in2csv XLSX conversion when worksheet dimension metadata understates actual populated cells. Recalculate the data extent so populated rows/columns are not silently dropped. Preserve valid workbooks, the selected sheet, cell values and row order.",
        r"""
import csv
import io
import re
import zipfile
import pytest
from openpyxl import Workbook
from csvkit.utilities.in2csv import In2CSV

def workbook(tmp_path,broken):
    original=tmp_path/'original.xlsx';wb=Workbook();ws=wb.active;ws.title='Data';ws.append(['id','name']);ws.append([1,'alpha']);ws.append([2,'beta']);wb.save(original)
    if not broken:return original
    changed=tmp_path/'changed.xlsx'
    with zipfile.ZipFile(original) as src,zipfile.ZipFile(changed,'w') as dst:
        for item in src.infolist():
            data=src.read(item.filename)
            if item.filename=='xl/worksheets/sheet1.xml':
                data=re.sub(rb'<dimension ref="[^"]+"',('<dimension ref="'+broken+'"').encode(),data)
            dst.writestr(item,data)
    return changed

def convert(path):
    out=io.StringIO();In2CSV(['-f','xlsx','--sheet','Data',str(path)],output_file=out).run()
    return list(csv.reader(io.StringIO(out.getvalue())))

@pytest.mark.parametrize('dimension',['A1:A1','A1:B2'])
def test_target(tmp_path,dimension):
    assert convert(workbook(tmp_path,dimension))==[['id','name'],['1','alpha'],['2','beta']]

def test_regression(tmp_path):
    assert convert(workbook(tmp_path,False))==[['id','name'],['1','alpha'],['2','beta']]
""",
    ),
    "7bba1bd": (
        "csvkit",
        "Fix csvlook --max-rows so input beyond the requested display row limit is not consumed. A bounded preview must display the requested initial rows without parsing unrelated later records (which can contain very large fields). Preserve --max-rows 0 and normal finite CSV output.",
        r"""
import csv
import io
from csvkit.utilities.csvlook import CSVLook

def look(tmp_path,text,limit):
    p=tmp_path/'a.csv';p.write_text(text)
    out=io.StringIO();CSVLook(['--no-inference','--snifflimit','0','--max-rows',str(limit),str(p)],output_file=out).run();return out.getvalue()

def test_target(tmp_path):
    before=csv.field_size_limit();csv.field_size_limit(131072)
    try:
        text=look(tmp_path,'id,name\n1,alpha\n2,'+'x'*140000+'\n',1)
        assert 'alpha' in text and 'x'*20 not in text
    finally:csv.field_size_limit(before)

def test_regression(tmp_path):
    text=look(tmp_path,'id,name\n1,alpha\n2,beta\n',2)
    assert 'alpha' in text and 'beta' in text
    zero=look(tmp_path,'id,name\n1,alpha\n',0)
    assert 'alpha' not in zero and 'name' in zero
""",
    ),
    "0867890": (
        "csvkit",
        "Fix csvclean --empty-columns on short and long input rows. Do not crash when a row has more fields than the header, and report every empty declared column even if a row omits trailing fields. Preserve the original output rows and normal nonempty-column behavior.",
        r"""
import csv
import io
import contextlib
import pytest
from csvkit.utilities.csvclean import CSVClean

def clean(tmp_path,text):
    p=tmp_path/'a.csv';p.write_text(text);out=io.StringIO();err=io.StringIO();code=0
    with contextlib.redirect_stderr(err):
        try:CSVClean(['--empty-columns',str(p)],output_file=out).run()
        except SystemExit as exc:code=exc.code
    return list(csv.reader(io.StringIO(out.getvalue()))),err.getvalue(),code

@pytest.mark.parametrize('row',[',',',,,'])
def test_target(tmp_path,row):
    rows,error,code=clean(tmp_path,'a,b,c\n'+row+'\n')
    assert rows==[['a','b','c'],row.split(',')]
    assert "Empty columns named 'a', 'b', 'c'" in error
    assert '1,2,3' in error
    assert 'IndexError' not in error

def test_regression(tmp_path):
    rows,error,code=clean(tmp_path,'a,b,c\n1,2,3\n')
    assert rows==[['a','b','c'],['1','2','3']]
    assert not error and code==0
""",
    ),
    "4b0b397": (
        "csvkit",
        "Respect PYTHONIOENCODING as the default input encoding for CSV utilities when set, with an explicit --encoding/-e taking precedence. Non-ASCII data must be read intact. Preserve default UTF-8 input when no environment override is present.",
        r"""
import csv
import io
from csvkit.utilities.csvcut import CSVCut

def cut(tmp_path,data,flags):
    p=tmp_path/'a.csv';p.write_bytes(data);out=io.StringIO();CSVCut(['-c','name',*flags,str(p)],output_file=out).run()
    return list(csv.reader(io.StringIO(out.getvalue())))

def test_target_env(tmp_path,monkeypatch):
    monkeypatch.setenv('PYTHONIOENCODING','latin-1')
    assert cut(tmp_path,'name\ncafé\n'.encode('latin-1'),[])==[['name'],['café']]

def test_target_override(tmp_path,monkeypatch):
    monkeypatch.setenv('PYTHONIOENCODING','ascii')
    assert cut(tmp_path,'name\ncafé\n'.encode('utf-8'),['--encoding','utf-8'])==[['name'],['café']]

def test_regression(tmp_path,monkeypatch):
    monkeypatch.delenv('PYTHONIOENCODING',raising=False)
    assert cut(tmp_path,'name\ncafé\n'.encode('utf-8'),[])==[['name'],['café']]
""",
    ),
}
