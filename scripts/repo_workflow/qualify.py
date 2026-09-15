"""Run all four trusted qualification cells; no Agent or selector calls."""
import argparse,json,hashlib
from pathlib import Path
from check import check
from hermes_skilleval.repository_maintenance import manifest
p=argparse.ArgumentParser();p.add_argument('--task-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--oracle',nargs='+',required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
task=json.loads((a.task_root/'task.json').read_text());cells={}
for variant in ['base','reference']:
 for kind in ['target','regression']:
  cells[variant+'-'+kind]=check(a.task_root/variant,a.task_root/'trusted',a.output/(variant+'-'+kind),task[kind+'_selector'],test_file=task['trusted_test_file'])
qualified=all(c['valid'] for c in cells.values()) and not cells['base-target']['passed'] and all(cells[k]['passed'] for k in ['reference-target','base-regression','reference-regression'])
for kind in ['target','regression']:
 qualified=qualified and sorted(c['id'] for c in cells['base-'+kind]['cases'])==sorted(c['id'] for c in cells['reference-'+kind]['cases'])
r=dict(task,qualification_binding={'task_sha256':hashlib.sha256((a.task_root/'task.json').read_bytes()).hexdigest(),'trusted_manifest':{str(p.relative_to(a.task_root/'trusted')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (a.task_root/'trusted').rglob('*') if p.is_file()},'image_id':cells['base-target']['image_id'],'harness_sha256':hashlib.sha256(Path(__file__).with_name('trusted_harness.py').read_bytes()).hexdigest()},qualified=qualified,base_manifest=manifest(a.task_root/'base'),oracle_ids=a.oracle,test_ids={n:sorted(c['id'] for c in cells['reference-'+n]['cases']) for n in ['target','regression']})
(a.output/'qualified.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'qualified':qualified,'cells':{k:{'valid':v['valid'],'passed':v['passed'],'tests':len(v['cases'])} for k,v in cells.items()}},indent=2))
