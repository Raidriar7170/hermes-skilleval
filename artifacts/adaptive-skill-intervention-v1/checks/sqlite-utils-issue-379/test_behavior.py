import pytest

def test_target(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    p=str(tmp_path/'data.db');db=Database(p);db['items'].insert_all([{'id':i,'label':'a'} for i in range(30)])
    r=CliRunner().invoke(cli,['create-index',p,'items','label','--analyze']);assert r.exit_code==0,r.output
    stats=db.execute('select tbl,idx,stat from sqlite_stat1').fetchall();assert any(row[0]=='items' and row[1] and row[2] for row in stats)
    assert db['items'].count==30

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
