import pytest

def test_target(tmp_path):
    from csv_diff import load_csv,compare
    from io import StringIO
    empty=load_csv(StringIO('id,name\n'),key='id');full=load_csv(StringIO('id,name\n1,a\n2,b\n'),key='id')
    a=compare(empty,full);b=compare(full,empty);c=compare(empty,empty)
    assert sorted(a['added'],key=lambda r:r['id'])==[{'id':'1','name':'a'},{'id':'2','name':'b'}]
    assert sorted(b['removed'],key=lambda r:r['id'])==a['added']
    assert not c['added'] and not c['removed'] and not c['changed']

def test_regression(tmp_path):
    from csv_diff import load_csv,compare
    from io import StringIO
    a=load_csv(StringIO('id,n\n1,a\n2,b\n'),key='id');b=load_csv(StringIO('id,n\n1,A\n2,b\n'),key='id')
    d=compare(a,b);assert len(d['changed'])==1 and not d['added'] and not d['removed']
