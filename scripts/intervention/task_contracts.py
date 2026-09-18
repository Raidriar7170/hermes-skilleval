"""Source-grounded behavioral task contracts. Not mounted into Agent environments.

Checks examine public output/data, not a chosen patch shape. Public clarifications
are frozen alongside raw issue requests before any ASI outcome is collected.
"""

TRAIN = [
    "sqlite-utils-issue-" + str(i)
    for i in (202, 211, 223, 228, 234, 238, 250, 274, 339, 348)
] + ["csv-diff-issue-18", "csvkit-issue-1264"]
DEV = [
    "sqlite-utils-issue-344",
    "sqlite-utils-issue-400",
    "sqlite-utils-issue-368",
    "csvkit-issue-1225",
]
TEST = ["sqlite-utils-issue-" + str(i) for i in (352, 379, 323, 356)] + [
    "csvkit-issue-1268",
    "csvkit-issue-1263",
    "csv-diff-issue-23",
    "csv-diff-issue-15",
]

# Explicit interface choices are in the PUBLIC requirements, never hidden checks.
CLARIFY = {
    "sqlite-utils-issue-202": "Support insert --csv -f COLUMN (repeatable) to enable FTS on imported columns; ordinary import remains unchanged.",
    "sqlite-utils-issue-228": "Support insert with --csv/--tsv --no-headers. Preserve every input row; use generated column names (their spelling is unspecified).",
    "sqlite-utils-issue-234": "With alter=True, insert_all must add columns first encountered in later batches and preserve earlier rows. Without alter=True, existing behavior may remain.",
    "sqlite-utils-issue-274": "Provide dump PATH which emits executable SQL preserving table schema and rows. Whitespace and statement formatting are unspecified.",
    "sqlite-utils-issue-339": "Support table.lookup(lookup_values, extra_values): populate extra values only when inserting a new lookup record; an existing match is returned without overwriting it.",
    "sqlite-utils-issue-348": "Provide create-database PATH creating a valid empty SQLite file; a repeated invocation may succeed or report that the file exists. Never destroy existing data.",
    "sqlite-utils-issue-352": "Support insert --extract COLUMN (repeatable), using existing Python extracts behavior. Replace repeated text values by references into the extracted lookup table while preserving rows.",
    "sqlite-utils-issue-379": "Support create-index PATH TABLE COLUMN --analyze, running SQLite ANALYZE after creating the index.",
    "sqlite-utils-issue-323": "table.convert(column, function) must use a unique temporary SQLite function name without clobbering existing UDFs, and unregister it after returning. The converted data and ordinary DB operations must still work.",
    "sqlite-utils-issue-356": 'Support insert PATH TABLE FILE --convert CODE. Evaluate CODE per incoming JSON object as the documented conversion mechanism; e.g. row["n"] = int(row["n"]) + 1. Preserve all input objects.',
    "csv-diff-issue-23": "Extend load_csv(fp, key=...) so a list or tuple of column names is accepted as a composite key. Preserve ordinary single-column keys and compare behavior; internal composite key representation is unspecified.",
    "csv-diff-issue-15": 'For this scoped API task, support load_csv(fp, key="__rowid__") to match rows by their data-row position (header excluded), rather than hashing their contents. Preserve other key modes. The internal row-key representation and starting number are unspecified.',
    "sqlite-utils-issue-368": "Support python -m sqlite_utils as a working CLI entrypoint, with the same commands and behavior as the console CLI. This resolves the historical package/submodule ambiguity explicitly for this development task.",
}

TARGET = {
    202: """
from sqlite_utils import Database
from sqlite_utils.cli import cli
from click.testing import CliRunner
p=str(tmp_path/'data.db')
r=CliRunner().invoke(cli,['insert',p,'articles','-','--csv','-f','title','-f','body'],input='id,title,body\\n1,alpha,bravo\\n2,charlie,delta\\n')
assert r.exit_code==0,r.output
db=Database(p)
for term in ['alpha','bravo']:
 rows=list(db['articles'].search(term));assert len(rows)==1 and str(rows[0]['id'])=='1'
assert len(list(db['articles'].rows))==2
""",
    211: """
from sqlite_utils import Database
db=Database(memory=True);db['items'].insert({'id':1})
for name in ['on_add','on_delete']:
 db.execute('CREATE TRIGGER {} AFTER {} ON items BEGIN SELECT 1; END'.format(name,'INSERT' if name=='on_add' else 'DELETE'))
v=db['items'].triggers_dict
assert set(v)=={'on_add','on_delete'}
assert all('CREATE TRIGGER' in sql.upper() for sql in v.values())
db['empty'].create({'id':int});assert db['empty'].triggers_dict=={}
""",
    223: """
from sqlite_utils import Database
from sqlite_utils.cli import cli
from click.testing import CliRunner
for sep in [';', '|']:
 p=str(tmp_path/('data'+str(ord(sep))+'.db'))
 r=CliRunner().invoke(cli,['insert',p,'items','-','--delimiter',sep],input=f'id{sep}name\\n1{sep}alpha\\n2{sep}beta\\n')
 assert r.exit_code==0,r.output
 assert [{k:str(v) for k,v in row.items()} for row in Database(p)['items'].rows]==[{'id':'1','name':'alpha'},{'id':'2','name':'beta'}]
""",
    228: """
from sqlite_utils import Database
from sqlite_utils.cli import cli
from click.testing import CliRunner
for sep,opt in [(',', '--csv'),('\\t','--tsv')]:
 p=str(tmp_path/('data'+str(ord(sep))+'.db'))
 r=CliRunner().invoke(cli,['insert',p,'items','-',opt,'--no-headers'],input=f'alpha{sep}17\\nbeta{sep}29\\n')
 assert r.exit_code==0,r.output
 rows=list(Database(p)['items'].rows)
 assert len(rows)==2 and list(map(str,rows[0].values()))==['alpha','17'] and list(map(str,rows[1].values()))==['beta','29']
""",
    234: """
from sqlite_utils import Database
for batch in [1,2]:
 db=Database(memory=True)
 rows=[{'id':1},{'id':2},{'id':3,'extra':'new'},{'id':4,'extra':'last'}]
 db['items'].insert_all(rows,pk='id',batch_size=batch,alter=True)
 actual=list(db['items'].rows)
 assert len(actual)==4 and actual[2]['extra']=='new' and actual[3]['extra']=='last'
 assert actual[0]['extra'] is None
""",
    238: """
from sqlite_utils import Database
for column in ['Reported by ID','reporter id']:
 db=Database(memory=True);db['People'].insert({'id':1,'name':'alpha'},pk='id')
 db['Reports'].insert({'id':2,column:1},pk='id')
 db['Reports'].add_foreign_key(column,'People','id')
 assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 fk=db.execute('PRAGMA foreign_key_list(Reports)').fetchone()
 assert fk[2:5]==('People',column,'id')
 assert list(db['Reports'].rows)[0][column]==1
""",
    250: """
from sqlite_utils import Database
from sqlite_utils.cli import cli
from click.testing import CliRunner
for mark in ['\\ufeff','']:
 p=str(tmp_path/('bom.db' if mark else 'plain.db'))
 r=CliRunner().invoke(cli,['insert',p,'items','-','--csv'],input=mark+'id,name\\n1,alpha\\n2,beta\\n')
 assert r.exit_code==0,r.output
 assert [{k:str(v) for k,v in row.items()} for row in Database(p)['items'].rows]==[{'id':'1','name':'alpha'},{'id':'2','name':'beta'}]
""",
    274: """
from sqlite_utils import Database
from sqlite_utils.cli import cli
from click.testing import CliRunner
import sqlite3
p=str(tmp_path/'original.db');db=Database(p)
db['items'].insert_all([{'id':1,'text':"a'b"},{'id':2,'text':'你好'}],pk='id')
r=CliRunner().invoke(cli,['dump',p]);assert r.exit_code==0,r.output
restored=sqlite3.connect(':memory:');restored.executescript(r.output)
assert restored.execute('select id,text from items order by id').fetchall()==[(1,"a'b"),(2,'你好')]
info={r[1]:(r[2].upper(),r[5]) for r in restored.execute('pragma table_info(items)')}
assert info=={'id':('INTEGER',1),'text':('TEXT',0)}
try:
 restored.execute('insert into items values (1, "duplicate")')
except sqlite3.IntegrityError:
 pass
else:
 raise AssertionError('dump lost primary-key behavior')
""",
    339: """
from sqlite_utils import Database
db=Database(memory=True)
a=db['people'].lookup({'name':'alpha'},{'age':17})
b=db['people'].lookup({'name':'alpha'},{'age':99})
c=db['people'].lookup({'name':'beta'},{'age':29})
assert a==b and c!=a
rows=list(db['people'].rows);assert len(rows)==2
assert {r['name']:r['age'] for r in rows}=={'alpha':17,'beta':29}
""",
    348: """
from sqlite_utils.cli import cli
from click.testing import CliRunner
import sqlite3
p=tmp_path/'empty.db';runner=CliRunner()
r=runner.invoke(cli,['create-database',str(p)]);assert r.exit_code==0,r.output
assert p.exists()
c=sqlite3.connect(p);c.execute('create table protected (n integer)');c.execute('insert into protected values (17)');c.commit();c.close()
runner.invoke(cli,['create-database',str(p)])
assert sqlite3.connect(p).execute('select n from protected').fetchall()==[(17,)]
""",
    352: """
from sqlite_utils import Database
from sqlite_utils.cli import cli
from click.testing import CliRunner
import json
p=str(tmp_path/'data.db')
r=CliRunner().invoke(cli,['insert',p,'items','-','--extract','category','--extract','region'],input=json.dumps([{'id':1,'category':'A','region':'X'},{'id':2,'category':'A','region':'Y'},{'id':3,'category':'B','region':'X'}]))
assert r.exit_code==0,r.output
db=Database(p);fk=db.execute('pragma foreign_key_list(items)').fetchall();assert len(fk)==2
for column,expected in [('category',[(1,'A'),(2,'A'),(3,'B')]),('region',[(1,'X'),(2,'Y'),(3,'X')])]:
 row=next(r for r in fk if r[3]==column)
 sql='select i.id, c.value from items i join "{}" c on i."{}"=c."{}" order by i.id'.format(row[2],row[3],row[4])
 assert db.execute(sql).fetchall()==expected
 assert db.execute('select count(*) from "{}"'.format(row[2])).fetchone()==(2,)
 refs=db.execute('select "{}" from items order by id'.format(column)).fetchall()
 assert refs[0]==refs[1 if column=='category' else 2]
""",
    379: """
from sqlite_utils import Database
from sqlite_utils.cli import cli
from click.testing import CliRunner
p=str(tmp_path/'data.db');db=Database(p);db['items'].insert_all([{'id':i,'label':'a'} for i in range(30)])
r=CliRunner().invoke(cli,['create-index',p,'items','label','--analyze']);assert r.exit_code==0,r.output
stats=db.execute('select tbl,idx,stat from sqlite_stat1').fetchall();assert any(row[0]=='items' and row[1] and row[2] for row in stats)
assert db['items'].count==30
""",
    323: """
from sqlite_utils import Database
db=Database(memory=True);db['items'].insert_all([{'n':'2'},{'n':'7'}])
db.conn.create_function('convert_value',1,lambda v:'sentinel')
db.conn.create_function('transform_value',1,lambda v:'other-sentinel')
before={r[0] for r in db.execute('pragma function_list')}
def transform_value(v):
 return str(int(v)+3)
db['items'].convert('n',transform_value)
assert db.execute("select convert_value(2), transform_value(2)").fetchone()==('sentinel','other-sentinel')
assert [str(r['n']) for r in db['items'].rows]==['5','10']
after={r[0] for r in db.execute('pragma function_list')}
# sqlite retains an unregistered function name, but invoking it must fail.
for name in after-before:
 try:
  db.execute('select "{}"(?)'.format(name),['2']).fetchone()
 except Exception:
  pass
 else:
  raise AssertionError('temporary conversion UDF still callable')
assert db.execute('select 1').fetchone()==(1,)
""",
    356: """
from sqlite_utils import Database
from sqlite_utils.cli import cli
from click.testing import CliRunner
import json
p=str(tmp_path/'data.db')
r=CliRunner().invoke(cli,['insert',p,'items','-','--convert','row["n"] = int(row["n"]) + 1'],input=json.dumps([{'n':'2','keep':'a'},{'n':'7','keep':'b'}]))
assert r.exit_code==0,r.output
assert list(Database(p)['items'].rows)==[{'n':3,'keep':'a'},{'n':8,'keep':'b'}]
""",
}

CSV_DIFF_TARGET = {
    18: """
from csv_diff import load_csv,compare
from io import StringIO
empty=load_csv(StringIO('id,name\\n'),key='id');full=load_csv(StringIO('id,name\\n1,a\\n2,b\\n'),key='id')
a=compare(empty,full);b=compare(full,empty);c=compare(empty,empty)
assert sorted(a['added'],key=lambda r:r['id'])==[{'id':'1','name':'a'},{'id':'2','name':'b'}]
assert sorted(b['removed'],key=lambda r:r['id'])==a['added']
assert not c['added'] and not c['removed'] and not c['changed']
""",
    23: """
from csv_diff import load_csv,compare
from io import StringIO
for key in [('a','b'),['a','b']]:
 before=load_csv(StringIO('a,b,value\\n1,x,old\\n1,y,keep\\n2,x,other\\n'),key=key)
 after=load_csv(StringIO('a,b,value\\n1,x,new\\n1,y,keep\\n2,x,other\\n'),key=key)
 assert len(before)==3 and len(after)==3
 d=compare(before,after);assert len(d['changed'])==1 and not d['added'] and not d['removed']
 assert d['changed'][0]['changes']['value']==['old','new']
""",
    15: """
from csv_diff import load_csv,compare
from io import StringIO
before=load_csv(StringIO('name,age\\nalpha,17\\nbeta,29\\n'),key='__rowid__')
after=load_csv(StringIO('name,age\\nALPHA,17\\nbeta,29\\n'),key='__rowid__')
d=compare(before,after);assert len(d['changed'])==1 and not d['added'] and not d['removed']
assert d['changed'][0]['changes']['name']==['alpha','ALPHA']
assert len(before)==2 and len(after)==2
""",
}

CSVKIT_TARGET = {
    1264: """
from csvkit.utilities.csvcut import CSVCut
from io import StringIO
import csv
for option,expected in [('2-', [['b','c','d'],['B','C','D']]),('3-', [['c','d'],['C','D']])]:
 src=tmp_path/'in.csv';src.write_text('a,b,c,d\\nA,B,C,D\\n')
 out=StringIO();CSVCut(['-c',option,str(src)],output_file=out).run()
 assert list(csv.reader(StringIO(out.getvalue())))==expected
""",
    1263: """
from csvkit.utilities.csvgrep import CSVGrep
from io import StringIO
import csv
src=tmp_path/'in.csv';src.write_text('id,first-name\\n1,alpha\\n2,beta\\n')
out=StringIO();CSVGrep(['-c','first-name','-m','alpha',str(src)],output_file=out).run()
assert list(csv.reader(StringIO(out.getvalue())))==[['id','first-name'],['1','alpha']]
""",
    1268: """
from csvkit.utilities.csvjoin import CSVJoin
from io import StringIO
import csv,os,threading
first=tmp_path/'first.csv';first.write_text('A,B,C\\na,b,key\\n')
pipe=tmp_path/'second.csv';os.mkfifo(pipe)
def writer():
 with open(pipe,'w') as f:f.write('C,D,E\\nkey,d,e\\n')
thread=threading.Thread(target=writer,daemon=True);thread.start()
out=StringIO();CSVJoin(['-c','C',str(first),str(pipe)],output_file=out).run();thread.join(timeout=5)
assert list(csv.reader(StringIO(out.getvalue())))==[['A','B','C','D','E'],['a','b','key','d','e']]
""",
}

REGRESSION = {
    "sqlite-utils": """
from sqlite_utils import Database
from sqlite_utils.cli import cli
from click.testing import CliRunner
db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
assert CliRunner().invoke(cli,['--help']).exit_code==0
""",
    "csv-diff": """
from csv_diff import load_csv,compare
from io import StringIO
a=load_csv(StringIO('id,n\\n1,a\\n2,b\\n'),key='id');b=load_csv(StringIO('id,n\\n1,A\\n2,b\\n'),key='id')
d=compare(a,b);assert len(d['changed'])==1 and not d['added'] and not d['removed']
""",
    "csvkit": """
from csvkit.utilities.csvcut import CSVCut
from io import StringIO
import csv
src=tmp_path/'in.csv';src.write_text('a,b\\n1,alpha\\n2,beta\\n')
out=StringIO();CSVCut(['-c','2',str(src)],output_file=out).run()
assert list(csv.reader(StringIO(out.getvalue())))==[['b'],['alpha'],['beta']]
""",
}
