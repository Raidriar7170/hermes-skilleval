"""Reuse existing isolation probe against this study's derived image."""

import json
import runpy
import sys
import subprocess
from pathlib import Path
from hermes_skilleval._maintenance import container_runner

image_arg = sys.argv.index("--image") if "--image" in sys.argv else None
container_runner.IMAGE = (
    sys.argv[image_arg + 1] if image_arg is not None else "hermes-repo-workflow:v2"
)
if image_arg is not None:
    del sys.argv[image_arg : image_arg + 2]
runpy.run_module("hermes_skilleval._maintenance.environment", run_name="__main__")
output = Path(sys.argv[sys.argv.index("--output") + 1])
r = json.loads(output.read_text())
r["images"][container_runner.IMAGE] = subprocess.check_output(
    ["docker", "image", "inspect", "--format", "{{.Id}}", container_runner.IMAGE],
    text=True,
).strip()
output.write_text(json.dumps(r, indent=2) + "\n")
