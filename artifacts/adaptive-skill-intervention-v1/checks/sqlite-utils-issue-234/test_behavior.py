import pytest

def test_target(tmp_path):
    from sqlite_utils import Database
    for batch in [1,2]:
     db=Database(memory=True)
     rows=[{'id':1},{'id':2},{'id':3,'extra':'new'},{'id':4,'extra':'last'}]
     db['items'].insert_all(rows,pk='id',batch_size=batch,alter=True)
     actual=list(db['items'].rows)
     assert len(actual)==4 and actual[2]['extra']=='new' and actual[3]['extra']=='last'
     assert actual[0]['extra'] is None

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
