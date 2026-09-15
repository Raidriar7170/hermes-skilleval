"""Freeze R's actual model files, adapter configuration, code and policy identity."""

import argparse
import hashlib
import json
from pathlib import Path
from hermes_skilleval.repo_routing.policy import routing_version, read_config
from hermes_skilleval.routers.skillrouter_open import asset_identity

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--config", type=Path, required=True)
p.add_argument("--registry", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
c = read_config(a.config)
registry = json.loads(a.registry.read_text())
c["model_files"] = {
    k: asset_identity(Path(c[k + "_path"]), c[k + "_revision"])["files"]
    for k in ("encoder", "reranker")
}
c["adapter_sha256"] = hashlib.sha256(
    (Path(c["adapter"]) / "adapter_model.safetensors").read_bytes()
).hexdigest()
c["adapter_config_sha256"] = hashlib.sha256(
    (Path(c["adapter"]) / "adapter_config.json").read_bytes()
).hexdigest()
c["r_version"] = routing_version(c, registry)
with a.output.open("x") as stream:
    json.dump(c, stream, indent=2)
print(
    json.dumps(
        {
            "r_version": c["r_version"],
            "frozen": "R",
            "registry_id": registry["registry_id"],
        }
    )
)
