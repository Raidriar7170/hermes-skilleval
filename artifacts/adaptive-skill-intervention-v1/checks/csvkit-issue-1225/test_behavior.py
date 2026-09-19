import subprocess,sys,json,pytest
BOOTSTRAP="import importlib.abc,importlib.machinery,sys,runpy\nclass Candidate(importlib.abc.MetaPathFinder):\n def find_spec(self,fullname,path=None,target=None):\n  if fullname in ('sqlite_utils','csvkit'):\n   spec=importlib.machinery.PathFinder.find_spec(fullname,['/input'])\n   if spec is None:raise ImportError(fullname)\n   return spec\nsys.meta_path.insert(0,Candidate())\n"
def candidate_run(args, **kwargs):
    tail = args[3:] if args[:3] == [sys.executable, '-m', 'sqlite_utils'] else args[1:]
    if args[0] == 'in2csv':
        body = "from csvkit.utilities.in2csv import launch_new_instance; launch_new_instance()"
    elif args[0] == 'sqlite-utils':
        body = "from sqlite_utils.cli import cli; cli()"
    else:
        body = "runpy.run_module('sqlite_utils',run_name='__main__')"
    code = BOOTSTRAP + '\nsys.argv=' + repr([args[0],*tail]) + '\n' + body
    return subprocess.run([sys.executable,'-I','-c',code], **kwargs)


def test_target(tmp_path, monkeypatch):
    import csv
    from pathlib import Path
    monkeypatch.chdir(tmp_path)
    data=Path('/trusted/dummy.xlsx').read_bytes()
    r=candidate_run(['in2csv','-f','xlsx','--write-sheets','-'],input=data,capture_output=True)
    assert r.returncode==0,r.stderr
    files=list(tmp_path.glob('*.csv'))
    assert len(files)==1
    with files[0].open(newline='') as stream:
        assert list(csv.reader(stream))==[['a','b','c'],['True','2','3']]

def test_regression(tmp_path):
    import csv,io
    r=candidate_run(['in2csv','-f','xlsx','/trusted/dummy.xlsx'],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    assert list(csv.reader(io.StringIO(r.stdout)))==[['a','b','c'],['True','2','3']]

def test_target_multisheet(tmp_path, monkeypatch):
    import csv,json
    from pathlib import Path
    monkeypatch.chdir(tmp_path)
    r=candidate_run(['in2csv','-f','xlsx','--write-sheets','-'],input=Path('/trusted/multisheet.xlsx').read_bytes(),capture_output=True)
    assert r.returncode==0,r.stderr
    matrices=[]
    for file in tmp_path.glob('*.csv'):
        with file.open(newline='') as stream:
            matrices.append(list(csv.reader(stream)))
    assert sorted(map(json.dumps,matrices))==sorted(map(json.dumps,[[['name', 'value'], ['alpha', 'red'], ['alpha', 'red']], [['label', 'note'], ['beta', 'blue,green'], ['gamma', 'quoted "text"']]]))
