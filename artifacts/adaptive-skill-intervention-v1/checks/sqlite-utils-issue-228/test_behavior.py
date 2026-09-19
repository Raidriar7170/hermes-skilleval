import pytest

def test_target(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    for sep,opt in [(',', '--csv'),('\t','--tsv')]:
     p=str(tmp_path/('data'+str(ord(sep))+'.db'))
     src=tmp_path/('input'+str(ord(sep))+'.csv');src.write_text(f'alpha{sep}17\nbeta{sep}29\n',encoding='utf-8')
     r=CliRunner().invoke(cli,['insert',p,'items',str(src),opt,'--no-headers'])
     assert r.exit_code==0,r.output
     rows=list(Database(p)['items'].rows)
     assert len(rows)==2 and list(map(str,rows[0].values()))==['alpha','17'] and list(map(str,rows[1].values()))==['beta','29']

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
