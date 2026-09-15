"""Fresh code-editing trial through inherited isolated Codex transport."""

import argparse
from hermes_skilleval._maintenance.execution import run_agent
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from hermes_skilleval._maintenance import container_runner
from hermes_skilleval.runtime_utility import load_registry
from hermes_skilleval.repository_maintenance import manifest
from hermes_skilleval.repository_profile import profile_for
from hermes_skilleval._maintenance.finalize import binding, finalize


def write(p, obj):
    p.write_text(json.dumps(obj, indent=2) + "\n")


p = argparse.ArgumentParser(description=__doc__)
for name in [
    "task-root",
    "registry",
    "skill-assets",
    "output",
    "workspace-root",
    "private-root",
    "canary",
    "qualification",
    "public-request",
]:
    p.add_argument("--" + name, type=Path, required=True)
p.add_argument("--profile", type=Path)
p.add_argument("--cache", type=Path)
p.add_argument("--fixed-config", type=Path)
p.add_argument("--route", type=Path)
p.add_argument("--arm", choices=["N", "O", "F", "S", "T"], default="N")
p.add_argument("--policy", choices=["native", "fixed", "strong", "repo-aware", "auto"])
p.add_argument("--routing-config", type=Path)
p.add_argument("--run-id", required=True)
p.add_argument("--timeout", type=int, default=600)
a = p.parse_args()
pipeline_started = time.monotonic()
if not a.run_id.replace("-", "").replace("_", "").isalnum():
    raise ValueError("unsafe run id")
if a.output.exists():
    raise ValueError("preserve prior run")
task = json.loads((a.task_root / "task.json").read_text())
qualification = json.loads(a.qualification.read_text())
if (
    task.get("public_request_sha256")
    and hashlib.sha256(a.public_request.read_bytes()).hexdigest()
    != task["public_request_sha256"]
):
    raise ValueError("public input changed")
if a.timeout <= 0:
    raise ValueError("positive timeout required")
if (
    not qualification["qualified"]
    or qualification["base_commit"] != task["base_commit"]
):
    raise ValueError("unqualified task")
if manifest(a.task_root / "base") != qualification["base_manifest"]:
    raise ValueError("base changed")
if qualification["qualification_binding"] != binding(a.task_root):
    raise ValueError("qualification changed")
canary = json.loads(a.canary.read_text())
container_runner.IMAGE = profile_for(task).image
if (
    not canary["passed"]
    or subprocess.check_output(
        ["docker", "image", "inspect", "--format", "{{.Id}}", container_runner.IMAGE],
        text=True,
    ).strip()
    != canary["images"][container_runner.IMAGE]
):
    raise ValueError("isolation changed")
registry, skills = load_registry(a.registry, a.skill_assets)
ids = [s.id for s in skills] if a.arm == "N" else qualification["oracle_ids"]
if a.arm == "F":
    if not a.fixed_config:
        raise ValueError("fixed configuration required")
    from hermes_skilleval.fixed_baseline import fixed_ids

    ids = fixed_ids(
        task["repository"], json.loads(a.fixed_config.read_text()), registry
    )
if a.arm in ["S", "T"]:
    if not a.route:
        if a.arm != "S" or not a.profile:
            raise ValueError("strong route or online profile required")
        from hermes_skilleval.maintenance_cli import recommend

        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.route = a.output.parent / (a.run_id + "-online-route.json")
        recommend(
            argparse.Namespace(
                registry=a.registry,
                assets=a.skill_assets,
                arm="S",
                profile=a.profile,
                request=a.public_request,
                cache=a.cache,
                output=a.route,
            )
        )
    from hermes_skilleval.skill_selection import select, SelectionConfig

    route = json.loads(a.route.read_text())
    public = a.public_request.read_text()
    if (
        route["input_prompt_hash"] != hashlib.sha256(public.encode()).hexdigest()
        or route["registry_id"] != registry["registry_id"]
    ):
        raise ValueError("route input binding mismatch")
    selected = select(
        prompt=public,
        snapshot=route,
        registry=registry,
        policy="topk" if a.arm == "S" else "complementary",
        k=2,
        config=SelectionConfig(**route["selection"]["policy_config"]),
    )
    if selected["skill_ids"] != route["skill_ids"]:
        raise ValueError("route selection mismatch")
    ids = route["skill_ids"]
elif a.route:
    raise ValueError("N/O/F do not accept route overrides")
routing = None
public_request = a.public_request.read_text()
if a.policy:
    if not a.routing_config or a.arm != "N" or a.route:
        raise ValueError(
            "new policy requires routing config and no legacy arm/route override"
        )
    from hermes_skilleval.repo_routing.policy import route, read_config

    routing = route(
        a.task_root / "base",
        public_request,
        {"network": "disabled", "python": "executor image " + profile_for(task).image},
        registry,
        a.policy,
        read_config(a.routing_config),
        repository=task["repository"],
    )
    ids = routing["skill_ids"]
    public_request = routing["agent_public_request"]
    # Persist the decision before the actual Agent launch.
    a.output.parent.mkdir(parents=True, exist_ok=True)
    write(a.output.parent / (a.run_id + "-decision.json"), routing)
record = run_agent(
    base=a.task_root / "base",
    public_request=public_request,
    profile=profile_for(task),
    registry=registry,
    ids=ids,
    skill_assets=a.skill_assets,
    output=a.output,
    workspace_root=a.workspace_root,
    private_root=a.private_root,
    run_id=a.run_id,
    task_id=task["task_id"],
    arm=routing["action"] if routing else a.arm,
    timeout=a.timeout,
    metadata={
        "split": task["split"],
        "base_commit": task["base_commit"],
        "qualification_sha256": hashlib.sha256(
            a.qualification.read_bytes()
        ).hexdigest(),
    },
)
if routing:
    write(a.output / "routing.json", routing)
if a.route:
    shutil.copyfile(a.route, a.output / "route.json")
if not record["cleanup_confirmed"]:
    raise RuntimeError("executor cleanup unconfirmed; do not capture while running")
record = finalize(
    a.output / "executor.json", a.task_root, a.qualification, a.output / "verification"
)
if routing:
    record["routing"] = {
        k: routing[k]
        for k in (
            "action",
            "requested_policy",
            "calls",
            "timing",
            "decision",
            "context_digest",
        )
    }
record["pipeline_wall_seconds"] = time.monotonic() - pipeline_started
write(a.output / "run.json", record)
print(
    json.dumps(
        {
            k: record.get(k)
            for k in [
                "run_id",
                "execution_status",
                "resolved",
                "changed_files",
                "usage",
                "error",
            ]
        },
        indent=2,
    )
)
