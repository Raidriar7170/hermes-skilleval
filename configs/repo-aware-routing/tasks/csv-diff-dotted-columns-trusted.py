import io
from csv_diff import compare, load_csv

def test_regression():
    value=load_csv(io.StringIO("id,name\n1,Cleo\n"),key="id")
    result=compare(value,value)
    assert result["added"] == []
    assert result["removed"] == []
    assert result["changed"] == []

def test_target():
    old=load_csv(io.StringIO("id,foo.bar,foo.baz\n1,Dog,Cat\n"),key="id")
    new=load_csv(io.StringIO("id,foo.bar,foo.baz\n1,Dog,Beaver\n"),key="id")
    result=compare(old,new)
    assert result["changed"] == [{"key":"1","changes":{"foo.baz":["Cat","Beaver"]}}]
