import pytest

def test_target(tmp_path):
    from sqlite_utils import Database
    db=Database(memory=True);db['items'].insert({'id':1})
    for name in ['on_add','on_delete']:
     db.execute('CREATE TRIGGER {} AFTER {} ON items BEGIN SELECT 1; END'.format(name,'INSERT' if name=='on_add' else 'DELETE'))
    v=db['items'].triggers_dict
    assert set(v)=={'on_add','on_delete'}
    assert all('CREATE TRIGGER' in sql.upper() for sql in v.values())
    db['empty'].create({'id':int});assert db['empty'].triggers_dict=={}

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
