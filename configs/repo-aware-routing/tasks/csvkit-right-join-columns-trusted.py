import io
import csv
from csvkit.utilities.csvstack import CSVStack
from csvkit.utilities.csvsql import CSVSQL
from csvkit.utilities.csvformat import CSVFormat
from csvkit.utilities.csvjoin import CSVJoin

def run(klass, args):
    output=io.StringIO()
    klass(args, output_file=output).run()
    return output.getvalue()

def test_regression(tmp_path):
    source=tmp_path / "simple.csv"
    source.write_text("name,count\nCleo,2\n")
    assert list(csv.reader(io.StringIO(run(CSVFormat,[str(source)])))) == [["name","count"],["Cleo","2"]]

def test_target(tmp_path):
    left=tmp_path / "left.csv"; left.write_text("key,leftval\na,L\n")
    right=tmp_path / "right.csv"; right.write_text("rightval,key\nR,a\nS,b\n")
    rows=list(csv.reader(io.StringIO(run(CSVJoin,["--right","-c","1,2",str(left),str(right)]))))
    assert len(rows) == 3
    assert any("L" in row and "R" in row for row in rows[1:])
    assert any("S" in row and "b" in row for row in rows[1:])
