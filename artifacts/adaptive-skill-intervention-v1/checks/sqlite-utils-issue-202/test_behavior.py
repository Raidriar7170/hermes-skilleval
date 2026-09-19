import pytest

def test_target(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    p=str(tmp_path/'data.db')
    src=tmp_path/'articles.csv';src.write_text('id,title,body\n1,alpha,bravo\n2,charlie,delta\n',encoding='utf-8')
    r=CliRunner().invoke(cli,['insert',p,'articles',str(src),'--csv','-f','title','-f','body'])
    assert r.exit_code==0,r.output
    db=Database(p)
    for term in ['alpha','bravo']:
     rows=list(db['articles'].search(term));assert len(rows)==1 and str(rows[0]['id'])=='1'
    assert len(list(db['articles'].rows))==2

def test_regression(tmp_path):
    from sqlite_utils import Database
    from sqlite_utils.cli import cli
    from click.testing import CliRunner
    db=Database(memory=True);db['items'].insert_all([{'id':1,'n':'alpha'},{'id':2,'n':'beta'}],pk='id')
    assert db['items'].count==2 and db['items'].get(1)['n']=='alpha'
    assert CliRunner().invoke(cli,['--help']).exit_code==0
