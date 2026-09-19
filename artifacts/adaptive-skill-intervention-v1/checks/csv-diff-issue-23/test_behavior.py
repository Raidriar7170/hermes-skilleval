import pytest

def test_target(tmp_path):
    from csv_diff import load_csv,compare
    from io import StringIO
    for key in [('a','b'),['a','b']]:
     before=load_csv(StringIO('a,b,value\n1,x,old\n1,y,keep\n2,x,other\n'),key=key)
     after=load_csv(StringIO('a,b,value\n1,x,new\n1,y,keep\n2,x,other\n'),key=key)
     assert len(before)==3 and len(after)==3
     d=compare(before,after);assert len(d['changed'])==1 and not d['added'] and not d['removed']
     assert d['changed'][0]['changes']['value']==['old','new']

def test_regression(tmp_path):
    from csv_diff import load_csv,compare
    from io import StringIO
    a=load_csv(StringIO('id,n\n1,a\n2,b\n'),key='id');b=load_csv(StringIO('id,n\n1,A\n2,b\n'),key='id')
    d=compare(a,b);assert len(d['changed'])==1 and not d['added'] and not d['removed']
