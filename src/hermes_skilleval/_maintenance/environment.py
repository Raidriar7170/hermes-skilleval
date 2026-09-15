"""Nonsecret runner canary and measured dependency facts; no external skill code."""

import argparse
import json
import subprocess
import uuid
from pathlib import Path
from hermes_skilleval._maintenance.container_runner import ContainerRunner
from hermes_skilleval._maintenance import container_runner
from hermes_skilleval.live_agent_runtime import AgentRequest, CodexCliRunnerConfig

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--workspace-root", type=Path, required=True)
p.add_argument("--private-root", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    raise ValueError("new output required")
canary_id = "canary-" + uuid.uuid4().hex[:12]
root = a.workspace_root.resolve() / canary_id
root.mkdir(parents=True, exist_ok=False)
auth = a.private_root.resolve() / "auth"
home = auth / canary_id
home.mkdir(parents=True, exist_ok=False)
(home / "nonsecret").write_text("canary")
sibling = root.parent / (canary_id + "-sibling")
sibling.mkdir()
(sibling / "nonsecret").write_text("canary")
(root / "escape").symlink_to(home / "nonsecret")
config = CodexCliRunnerConfig(
    codex_home_base=auth,
    model="gpt-5.6-sol",
    reasoning_effort="medium",
    restrict_reads=True,
)
runner = ContainerRunner(config)
req = AgentRequest(canary_id, "canary", "canary", "no-skill", "canary", root, [], 30)
paths = [
    str(home / "nonsecret"),
    str(sibling / "nonsecret"),
    str(root / "escape"),
    "/var/run/docker.sock",
]
code = """import json,platform,shutil,importlib.util,socket
from pathlib import Path
out={'os':platform.system(),'architecture':platform.machine()}
for module in ['pandas','numpy','scipy','openpyxl','xlrd','networkx','pytest','pypdf','torch']:
 out['module:'+module]=importlib.util.find_spec(module) is not None
for command in ['python','node','dot','scala','scalac','java','mvn','git','docker']:
 out['command:'+command]=shutil.which(command) is not None
out['paths']={}
for p in PATHS:
 try:Path(p).read_bytes();out['paths'][p]='READABLE'
 except FileNotFoundError:out['paths'][p]='UNMOUNTED'
 except PermissionError:out['paths'][p]='DENIED'
Path('write-canary').write_text('ok');out['workspace_write']=True
try:
 s=socket.socket();s.settimeout(1);s.connect(('127.0.0.1',80));out['network_allowed']=True
except PermissionError:out['network_allowed']=False
except OSError:out['network_allowed']=None
print(json.dumps(out))
""".replace("PATHS", repr(paths))
cmd = ["codex", "sandbox"]
for item in runner.permission_overrides(req):
    cmd += ["-c", item]
cmd += ["-P", "hermes-task", "-C", str(root), "--", "python", "-c", code]
proc = subprocess.run(
    runner.wrap(req, cmd),
    env=runner._env(req),
    capture_output=True,
    text=True,
    timeout=45,
)
facts = json.loads(proc.stdout) if proc.returncode == 0 else {}
record = {
    "returncode": proc.returncode,
    "stdout": proc.stdout,
    "stderr": proc.stderr,
    "facts": facts,
    "passed": proc.returncode == 0
    and all(v in ("DENIED", "UNMOUNTED") for v in facts.get("paths", {}).values())
    and facts.get("workspace_write")
    and facts.get("network_allowed") is False,
    "images": {
        name: subprocess.check_output(
            ["docker", "image", "inspect", "--format", "{{.Id}}", name], text=True
        ).strip()
        for name in [container_runner.IMAGE]
    },
}
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(record, indent=2))
print(json.dumps(record, indent=2))
if not record["passed"]:
    raise SystemExit(1)
