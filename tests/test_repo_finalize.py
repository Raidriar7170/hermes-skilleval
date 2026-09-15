import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/repo_workflow'))
import finalize as controller
from hermes_skilleval.repository_maintenance import manifest


def fixture(tmp_path,monkeypatch):
    task=tmp_path/'task';(task/'base').mkdir(parents=True);(task/'base/a.py').write_text('base\n')
    obj={'task_id':'t','base_commit':'abc','target_selector':'target','regression_selector':'regression','trusted_test_file':'test_task.py'}
    (task/'task.json').write_text(json.dumps(obj));(task/'trusted').mkdir()
    q=tmp_path/'q.json';q.write_text(json.dumps({**obj,'qualified':True,'qualification_binding':{},'base_manifest':manifest(task/'base'),'test_ids':{'target':['a::target'],'regression':['a::regression']}}))
    work=tmp_path/'work';work.mkdir();(work/'a.py').write_text('agent patch\n')
    exe=tmp_path/'executor.json';exe.write_text(json.dumps({'task_id':'t','base_commit':'abc','run_id':'run','workspace':str(work),'execution_status':'STARTED'}))
    monkeypatch.setattr(controller,'binding',lambda _:{});monkeypatch.setattr(controller,'stopped',lambda _:None)
    monkeypatch.setattr(controller,'check',lambda candidate,trusted,output,selector,**kw:{'valid':True,'passed':True,'cases':[{'id':'a::'+selector}]})
    return task,q,work,exe


def test_task_mismatch_fails_closed(tmp_path,monkeypatch):
    task,q,work,exe=fixture(tmp_path,monkeypatch)
    r=json.loads(exe.read_text());r['task_id']='other';exe.write_text(json.dumps(r))
    result=controller.finalize(exe,task,q,tmp_path/'out')
    assert result['resolved'] is None and 'binding mismatch' in result['error']


def test_base_mutation_fails_closed(tmp_path,monkeypatch):
    task,q,work,exe=fixture(tmp_path,monkeypatch);(task/'base/a.py').write_text('different base')
    result=controller.finalize(exe,task,q,tmp_path/'out')
    assert result['resolved'] is None and 'base changed' in result['error']


def test_reverification_uses_saved_patch(tmp_path,monkeypatch):
    task,q,work,exe=fixture(tmp_path,monkeypatch)
    first=controller.finalize(exe,task,q,tmp_path/'first');assert first['resolved'] is True
    (work/'a.py').write_text('late unrelated edit\n')
    second=controller.finalize(exe,task,q,tmp_path/'second')
    assert second['resolved'] is True and second['patch_sha256']==first['patch_sha256']
    assert (tmp_path/'second/rebuilt/a.py').read_text()=='agent patch\n'
