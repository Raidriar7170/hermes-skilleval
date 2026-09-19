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
        exec('from click.testing import CliRunner\nfrom sqlite_utils.cli import cli\nfrom sqlite_utils import Database\nr=CliRunner()\nwith r.isolated_filesystem():\n x=r.invoke(cli,["create-table","test.db","t","id","integer","--if-not-exists"]);assert x.exit_code==0,x.output\n db=Database("test.db");db["t"].insert({"id":5});db.conn.close()\n x=r.invoke(cli,["create-table","test.db","t","id","integer","--if-not-exists"]);assert x.exit_code==0,x.output\n assert list(Database("test.db")["t"].rows)==[{"id":5}]', globals(), {})
    except Exception as exc:
        pytest.fail(str(exc))

def test_regression(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    try:
        exec('from click.testing import CliRunner\nfrom sqlite_utils.cli import cli\nr=CliRunner()\nwith r.isolated_filesystem():\n assert r.invoke(cli,["create-table","a.db","t","id","integer"]).exit_code==0\n assert r.invoke(cli,["create-table","a.db","t","id","integer"]).exit_code!=0', globals(), {})
    except Exception as exc:
        pytest.fail(str(exc))
