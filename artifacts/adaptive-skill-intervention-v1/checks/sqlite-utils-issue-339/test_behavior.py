import pytest

def test_target(tmp_path):
    from sqlite_utils import Database
    db=Database(memory=True)
    a=db['people'].lookup({'name':'alpha'},{'age':17})
    b=db['people'].lookup({'name':'alpha'},{'age':99})
    c=db['people'].lookup({'name':'beta'},{'age':29})
    assert a==b and c!=a
    rows=list(db['people'].rows);assert len(rows)==2
    assert {r['name']:r['age'] for r in rows}=={'alpha':17,'beta':29}

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
