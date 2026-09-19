import pytest

def test_target(tmp_path):
    from csvkit.utilities.csvcut import CSVCut
    from io import StringIO
    import csv
    for option,expected in [('2-', [['b','c','d'],['B','C','D']]),('3-', [['c','d'],['C','D']])]:
     src=tmp_path/'in.csv';src.write_text('a,b,c,d\nA,B,C,D\n')
     out=StringIO();CSVCut(['-c',option,str(src)],output_file=out).run()
     assert list(csv.reader(StringIO(out.getvalue())))==expected

def test_regression(tmp_path):
    from csvkit.utilities.csvcut import CSVCut
    from io import StringIO
    import csv
    src=tmp_path/'in.csv';src.write_text('a,b\n1,alpha\n2,beta\n')
    out=StringIO();CSVCut(['-c','2',str(src)],output_file=out).run()
    assert list(csv.reader(StringIO(out.getvalue())))==[['b'],['alpha'],['beta']]
