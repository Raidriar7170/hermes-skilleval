import pytest

def test_target(tmp_path):
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    import sqlite3
    p=tmp_path/'empty.db';runner=CliRunner()
    r=runner.invoke(cli,['create-database',str(p)]);assert r.exit_code==0,r.output
    assert p.exists()
    c=sqlite3.connect(p);c.execute('create table protected (n integer)');c.execute('insert into protected values (17)');c.commit();c.close()
    runner.invoke(cli,['create-database',str(p)])
    assert sqlite3.connect(p).execute('select n from protected').fetchall()==[(17,)]

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
