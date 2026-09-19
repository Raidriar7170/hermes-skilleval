import pytest

def test_target(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    import json
    p=str(tmp_path/'data.db')
    r=CliRunner().invoke(cli,['insert',p,'items','-','--extract','category','--extract','region'],input=json.dumps([{'id':1,'category':'A','region':'X'},{'id':2,'category':'A','region':'Y'},{'id':3,'category':'B','region':'X'}]))
    assert r.exit_code==0,r.output
    db=Database(p);fk=db.execute('pragma foreign_key_list(items)').fetchall();assert len(fk)==2
    for column,expected in [('category',[(1,'A'),(2,'A'),(3,'B')]),('region',[(1,'X'),(2,'Y'),(3,'X')])]:
     row=next(r for r in fk if r[3]==column)
     sql='select i.id, c.value from items i join "{}" c on i."{}"=c."{}" order by i.id'.format(row[2],row[3],row[4])
     assert db.execute(sql).fetchall()==expected
     assert db.execute('select count(*) from "{}"'.format(row[2])).fetchone()==(2,)
     refs=db.execute('select "{}" from items order by id'.format(column)).fetchall()
     assert refs[0]==refs[1 if column=='category' else 2]

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
