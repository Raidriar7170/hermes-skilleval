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
    monkeypatch.chdir(tmp_path)
    try:
        exec('import subprocess,sys\nr=candidate_run([sys.executable,"-m","sqlite_utils","--help"],capture_output=True,text=True)\nassert r.returncode==0,r.stderr\nassert "Usage:" in r.stdout', globals(), {})
    except Exception as exc:
        pytest.fail(str(exc))

def test_regression(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    try:
        exec('import subprocess\nr=candidate_run(["sqlite-utils","--help"],capture_output=True,text=True)\nassert r.returncode==0 and "Usage:" in r.stdout', globals(), {})
    except Exception as exc:
        pytest.fail(str(exc))


def test_target_function(tmp_path):
    for entry in ([sys.executable, '-m', 'sqlite_utils'], ['sqlite-utils']):
        r=candidate_run(entry + [':memory:', 'select 17 as value'],capture_output=True,text=True)
        assert r.returncode==0,r.stderr
        assert json.loads(r.stdout)==[{'value':17}]
