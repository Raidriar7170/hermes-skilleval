"""Reuse existing isolation probe against this study's derived image."""
import json,runpy,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'runtime_utility'))
import container_runner
container_runner.IMAGE='hermes-repo-workflow:v2'
runpy.run_path(str(Path(__file__).resolve().parents[1]/'skill_selection_phase1/environment.py'),run_name='__main__')
output=Path(sys.argv[sys.argv.index('--output')+1]);r=json.loads(output.read_text());r['images'][container_runner.IMAGE]=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',container_runner.IMAGE],text=True).strip();output.write_text(json.dumps(r,indent=2)+'\n')
