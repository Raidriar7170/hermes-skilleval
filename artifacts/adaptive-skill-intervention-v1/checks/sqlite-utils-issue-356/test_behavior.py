import pytest

def test_target(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    import json
    p=str(tmp_path/'data.db')
    r=CliRunner().invoke(cli,['insert',p,'items','-','--convert','row["n"] = int(row["n"]) + 1'],input=json.dumps([{'n':'2','keep':'a'},{'n':'7','keep':'b'}]))
    assert r.exit_code==0,r.output
    assert list(Database(p)['items'].rows)==[{'n':3,'keep':'a'},{'n':8,'keep':'b'}]

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
