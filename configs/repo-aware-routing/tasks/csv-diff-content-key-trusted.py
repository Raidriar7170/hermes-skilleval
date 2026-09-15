import io
from csv_diff import compare, load_csv

def test_regression():
    value=load_csv(io.StringIO("id,name\n1,Cleo\n"),key="id")
    result=compare(value,value)
    assert result["added"] == []
    assert result["removed"] == []
    assert result["changed"] == []

def test_target():
    old=load_csv(io.StringIO("id,name\n1,Cleo\n2,Bob\n"))
    new=load_csv(io.StringIO("id,name\n1,Cleo\n2,Alice\n"))
    result=compare(old,new)
    assert result["added"] == [{"id":"2","name":"Alice"}]
    assert result["removed"] == [{"id":"2","name":"Bob"}]
