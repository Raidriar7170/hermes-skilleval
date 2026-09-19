import pytest

def test_target(tmp_path):
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

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
