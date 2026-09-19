import pytest

def test_target(tmp_path):
    from csvkit.utilities.csvjoin import CSVJoin
    from io import StringIO
    import csv,os,threading
    first=tmp_path/'first.csv';first.write_text('A,B,C\na,b,key\n')
    pipe=tmp_path/'second.csv';os.mkfifo(pipe)
    def writer():
     with open(pipe,'w') as f:f.write('C,D,E\nkey,d,e\n')
    thread=threading.Thread(target=writer,daemon=True);thread.start()
    out=StringIO();CSVJoin(['-c','C',str(first),str(pipe)],output_file=out).run();thread.join(timeout=5)
    assert list(csv.reader(StringIO(out.getvalue())))==[['A','B','C','D','E'],['a','b','key','d','e']]

def test_regression(tmp_path):
    from csvkit.utilities.csvcut import CSVCut
    from io import StringIO
    import csv
    src=tmp_path/'in.csv';src.write_text('a,b\n1,alpha\n2,beta\n')
    out=StringIO();CSVCut(['-c','2',str(src)],output_file=out).run()
    assert list(csv.reader(StringIO(out.getvalue())))==[['b'],['alpha'],['beta']]
