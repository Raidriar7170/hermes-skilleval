import pytest

def test_target(tmp_path):
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

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
