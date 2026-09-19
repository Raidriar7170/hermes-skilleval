import pytest

def test_target(tmp_path):
    from sqlite_utils import Database
    for column in ['Reported by ID','reporter id']:
     db=Database(memory=True);db['People'].insert({'id':1,'name':'alpha'},pk='id')
     db['Reports'].insert({'id':2,column:1},pk='id')
     db['Reports'].add_foreign_key(column,'People','id')
     assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
     fk=db.execute('PRAGMA foreign_key_list(Reports)').fetchone()
     assert fk[2:5]==('People',column,'id')
     assert list(db['Reports'].rows)[0][column]==1

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
