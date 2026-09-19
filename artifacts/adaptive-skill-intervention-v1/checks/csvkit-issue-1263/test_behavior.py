import pytest

def test_target(tmp_path):
    from csvkit.utilities.csvgrep import CSVGrep
    from io import StringIO
    import csv
    src=tmp_path/'in.csv';src.write_text('id,first-name\n1,alpha\n2,beta\n')
    out=StringIO();CSVGrep(['-c','first-name','-m','alpha',str(src)],output_file=out).run()
    assert list(csv.reader(StringIO(out.getvalue())))==[['id','first-name'],['1','alpha']]

def test_regression(tmp_path):
    from csvkit.utilities.csvcut import CSVCut
    from io import StringIO
    import csv
    src=tmp_path/'in.csv';src.write_text('a,b\n1,alpha\n2,beta\n')
    out=StringIO();CSVCut(['-c','2',str(src)],output_file=out).run()
    assert list(csv.reader(StringIO(out.getvalue())))==[['b'],['alpha'],['beta']]
