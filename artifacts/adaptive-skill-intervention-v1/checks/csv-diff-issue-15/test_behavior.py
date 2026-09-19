import pytest

def test_target(tmp_path):
    from csv_diff import load_csv,compare
    from io import StringIO
    before=load_csv(StringIO('name,age\nalpha,17\nbeta,29\n'),key='__rowid__')
    after=load_csv(StringIO('name,age\nALPHA,17\nbeta,29\n'),key='__rowid__')
    d=compare(before,after);assert len(d['changed'])==1 and not d['added'] and not d['removed']
    assert d['changed'][0]['changes']['name']==['alpha','ALPHA']
    assert len(before)==2 and len(after)==2

def test_regression(tmp_path):
    from csv_diff import load_csv,compare
    from io import StringIO
    a=load_csv(StringIO('id,n\n1,a\n2,b\n'),key='id');b=load_csv(StringIO('id,n\n1,A\n2,b\n'),key='id')
    d=compare(a,b);assert len(d['changed'])==1 and not d['added'] and not d['removed']
