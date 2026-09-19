"""Source-supported public obligations and independent behavioral checks."""

CONTRACTS = {
    "6a47526": (
        "csvkit",
        "Fix csvstack when one of its CSV input files is empty. Preserve the rows and headers from nonempty files in either input order, with no exception from absent fieldnames. Header-only inputs should likewise contribute no data rows. Keep ordinary stacking unchanged.",
        r"""
import csv
import io
import pytest
from csvkit.utilities.csvstack import CSVStack

@pytest.mark.parametrize('empty_first',[False,True])
@pytest.mark.parametrize('empty_content',['','id,name\n'])
def test_target(tmp_path,empty_first,empty_content):
    empty=tmp_path/'empty.csv';data=tmp_path/'data.csv'
    empty.write_text(empty_content);data.write_text('id,name\n1,alpha\n2,beta\n')
    paths=[str(empty),str(data)] if empty_first else [str(data),str(empty)]
    out=io.StringIO();CSVStack(paths,output_file=out).run()
    assert list(csv.DictReader(io.StringIO(out.getvalue())))==[{'id':'1','name':'alpha'},{'id':'2','name':'beta'}]

def test_regression(tmp_path):
    a=tmp_path/'a.csv';b=tmp_path/'b.csv';a.write_text('id,name\n1,a\n');b.write_text('id,name\n2,b\n')
    out=io.StringIO();CSVStack([str(a),str(b)],output_file=out).run()
    assert list(csv.reader(io.StringIO(out.getvalue())))==[['id','name'],['1','a'],['2','b']]
""",
    ),
    "8119565": (
        "csvkit",
        "Fix --maxfieldsize/-z for DictReader-based csvstack and csvpy --dict. Supplying an explicit field-size limit must not be passed as an invalid reader keyword and should allow fields larger than the default up to that limit. Ordinary CSV inputs and the existing field-limit bound must still work.",
        r"""
import csv
import io
import pytest
from csvkit.utilities.csvstack import CSVStack
from csvkit.utilities.csvpy import CSVPy

@pytest.fixture(autouse=True)
def restore_limit():
    before=csv.field_size_limit()
    yield
    csv.field_size_limit(before)

@pytest.mark.parametrize('length',[12,140000])
def test_target_stack(tmp_path,length):
    a=tmp_path/'a.csv';a.write_text('id,text\n1,'+'x'*length+'\n')
    out=io.StringIO();CSVStack(['-z','200000',str(a)],output_file=out).run()
    assert list(csv.DictReader(io.StringIO(out.getvalue())))==[{'id':'1','text':'x'*length}]

def test_target_csvpy_reader(tmp_path):
    a=tmp_path/'a.csv';a.write_text('id,text\n1,'+'x'*140000+'\n')
    utility=CSVPy(['--dict','-z','200000',str(a)],output_file=io.StringIO())
    try:
        with a.open() as stream:
            rows=list(csv.DictReader(stream,**utility.reader_kwargs))
        assert rows==[{'id':'1','text':'x'*140000}]
    finally:
        pass

def test_regression(tmp_path):
    a=tmp_path/'a.csv';a.write_text('a,b\nx,y\n')
    out=io.StringIO();CSVStack([str(a)],output_file=out).run()
    assert list(csv.reader(io.StringIO(out.getvalue())))==[['a','b'],['x','y']]
""",
    ),
    "33e0a59": (
        "csv-diff",
        "Fix JSON records with missing fields. load_json() should represent fields present in some rows but missing in others as None, and comparison/CLI --json must correctly report missing-to-present changes without errors. Preserve nested JSON values and regular keyed JSON diff behavior.",
        r"""
import io
import json
from click.testing import CliRunner
from csv_diff import load_json,compare
from csv_diff.cli import cli

def test_target(tmp_path):
    before=[{'id':1,'name':'a','extra':3},{'id':2,'name':'b'}]
    after=[{'id':1,'name':'a','extra':3},{'id':2,'name':'b','extra':4}]
    a=load_json(io.StringIO(json.dumps(before)),key='id')
    b=load_json(io.StringIO(json.dumps(after)),key='id')
    assert a[2]['extra'] is None
    diff=compare(a,b)
    assert diff['changed']==[{'key':2,'changes':{'extra':[None,4]}}]
    p=tmp_path/'a.json';q=tmp_path/'b.json';p.write_text(json.dumps(before));q.write_text(json.dumps(after))
    result=CliRunner().invoke(cli,[str(p),str(q),'--key','id','--json','--format','json'])
    assert result.exit_code==0,result.output
    assert json.loads(result.output)==diff

def test_regression():
    a=load_json(io.StringIO('[{"id":1,"nested":{"x":3}}]'),key='id')
    b=load_json(io.StringIO('[{"id":1,"nested":{"x":4}}]'),key='id')
    assert compare(a,b)['changed']==[{'key':1,'changes':{'nested':['{"x": 3}','{"x": 4}']}}]
""",
    ),
    "2b0cc04": (
        "sqlite-utils",
        "Fix CSV files containing only a header row with type detection enabled: sqlite-utils insert and memory must not crash by trying to transform an absent table. Header-only input need not create a table. Keep ordinary populated CSV imports and their inferred values working.",
        r"""
import json
import pytest
from click.testing import CliRunner
from sqlite_utils import Database
from sqlite_utils.cli import cli

@pytest.mark.parametrize('detect',[[],['--detect-types']])
def test_target_insert(tmp_path,detect):
    src=tmp_path/'empty.csv';src.write_text('id,name,age\n');dbpath=tmp_path/'data.db'
    r=CliRunner().invoke(cli,['insert',str(dbpath),'items',str(src),'--csv',*detect])
    assert r.exit_code==0,r.output
    db=Database(str(dbpath));assert not db['items'].exists();db.close()

def test_target_memory(tmp_path):
    src=tmp_path/'empty.csv';src.write_text('id,name\n')
    r=CliRunner().invoke(cli,['memory',str(src),'select 1 as n'])
    assert r.exit_code==0,r.output
    assert json.loads(r.output)==[{'n':1}]

def test_regression(tmp_path):
    src=tmp_path/'data.csv';src.write_text('id,name\n1,alpha\n2,beta\n');dbpath=tmp_path/'data.db'
    r=CliRunner().invoke(cli,['insert',str(dbpath),'items',str(src),'--csv'])
    assert r.exit_code==0,r.output
    db=Database(str(dbpath));assert [{k:str(v) for k,v in row.items()} for row in db['items'].rows]==[{'id':'1','name':'alpha'},{'id':'2','name':'beta'}];db.close()
""",
    ),
    "c327a1b": (
        "csvkit",
        "Fix type inference with --date-format: a small decimal number such as 5.5 must remain Number instead of becoming DateTime merely because another column uses a custom date format. Keep custom date parsing working, and preserve explicit --datetime-format precedence.",
        r"""
import io
import json
import pytest
from csvkit.utilities.csvjson import CSVJSON

def convert(tmp_path,text,flags):
    p=tmp_path/'data.csv';p.write_text(text)
    out=io.StringIO();CSVJSON([*flags,str(p)],output_file=out).run()
    return json.loads(out.getvalue())

@pytest.mark.parametrize('number',[5.5,6.5])
def test_target(tmp_path,number):
    rows=convert(tmp_path,'date,value\n13/12/2024,'+str(number)+'\n',['--date-format','%d/%m/%Y'])
    assert rows[0]['value']==number
    assert rows[0]['date']=='2024-12-13'

def test_regression(tmp_path):
    rows=convert(tmp_path,'stamp,value\n202401021234,abc\n',['--datetime-format','%Y%m%d%H%M'])
    assert str(rows[0]['stamp']).startswith('2024-01-02T12:34')
    assert rows[0]['value']=='abc'
""",
    ),
    "0cf7d3c": (
        "csv-diff",
        "Make automatic CSV dialect sniffing recognize semicolon-delimited input files. CLI comparison with --key should return the correct changed records without requiring --format. Preserve comma and tab formats and ordinary unchanged comparisons.",
        r"""
import json
import pytest
from click.testing import CliRunner
from csv_diff.cli import cli

def diff(tmp_path,sep,changed):
    a=tmp_path/'a.csv';b=tmp_path/'b.csv'
    a.write_text(f'id{sep}name\n1{sep}Mark\n')
    b.write_text(f'id{sep}name\n1{sep}'+('Brian' if changed else 'Mark')+'\n')
    r=CliRunner().invoke(cli,[str(a),str(b),'--key','id','--json'])
    assert r.exit_code==0,r.output
    return json.loads(r.output)

@pytest.mark.parametrize('changed',[True,False])
def test_target(tmp_path,changed):
    d=diff(tmp_path,';',changed)
    assert d['changed']==([{'key':'1','changes':{'name':['Mark','Brian']}}] if changed else [])
    assert d['added']==d['removed']==[]

@pytest.mark.parametrize('sep',[',','\t'])
def test_regression(tmp_path,sep):
    assert diff(tmp_path,sep,True)['changed']==[{'key':'1','changes':{'name':['Mark','Brian']}}]
""",
    ),
    "95dc26d": (
        "csvkit",
        "Fix csvformat --out-quoting 2 (non-numeric quoting): infer numeric values so they are emitted unquoted, quote text fields, respect locale and --skip-header. Preserve ordinary quoting modes and output data. This scoped task requires modes 0–3 available on the common Python runtime; new Python-specific modes are outside its acceptance.",
        r"""
import csv
import io
import pytest
from csvkit.utilities.csvformat import CSVFormat

def formatted(tmp_path,flags):
    p=tmp_path/'data.csv';p.write_text('name,value\nalpha,5.5\nbeta,12\n')
    out=io.StringIO();CSVFormat([*flags,str(p)],output_file=out).run();return out.getvalue()

@pytest.mark.parametrize('skip',[False,True])
def test_target(tmp_path,skip):
    text=formatted(tmp_path,['-U','2',*(['--skip-header'] if skip else [])])
    assert '"alpha",5.5' in text and '"beta",12' in text
    assert ('"name","value"' in text)==(not skip)
    rows=list(csv.reader(io.StringIO(text)))
    assert rows[-2:]==[['alpha','5.5'],['beta','12']]

def test_regression(tmp_path):
    assert list(csv.reader(io.StringIO(formatted(tmp_path,['-U','0']))))==[['name','value'],['alpha','5.5'],['beta','12']]
""",
    ),
}
