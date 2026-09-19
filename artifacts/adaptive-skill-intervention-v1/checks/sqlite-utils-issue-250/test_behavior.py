import pytest

def test_target(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    for mark in ['\ufeff','']:
     p=str(tmp_path/('bom.db' if mark else 'plain.db'))
     src=tmp_path/('bom.csv' if mark else 'plain.csv');src.write_bytes((mark+'id,name\n1,alpha\n2,beta\n').encode('utf-8'))
     r=CliRunner().invoke(cli,['insert',p,'items',str(src),'--csv'])
     assert r.exit_code==0,r.output
     assert [{k:str(v) for k,v in row.items()} for row in Database(p)['items'].rows]==[{'id':'1','name':'alpha'},{'id':'2','name':'beta'}]

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
