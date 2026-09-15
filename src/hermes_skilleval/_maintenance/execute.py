"""Fresh code-editing trial through inherited isolated Codex transport."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from hermes_skilleval._maintenance import container_runner
from hermes_skilleval._maintenance.prompts import maintenance_prompt
from hermes_skilleval.live_agent_runtime import (
    AgentRequest,
    CodexCliRunnerConfig,
    LiveAgentSkill,
    prepare_live_agent_workspace,
    build_condition,
    parse_codex_usage,
)
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
p.add_argument("--arm", choices=["N", "O", "F", "S", "T"], required=True)
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
mounted = [
    LiveAgentSkill(
        s["id"],
        s["name"],
        s["body"],
        s["description"],
        a.skill_assets / s["package_path"],
        s["package_sha256"],
    )
    for s in registry["skills"]
    if s["id"] in ids
]
a.output.mkdir(parents=True)
if a.route:
    shutil.copyfile(a.route, a.output / "route.json")
source_root = Path(__file__).resolve().parent.parent
shutil.copytree(
    source_root,
    a.output / "executed-source/hermes_skilleval",
    ignore=shutil.ignore_patterns("__pycache__"),
)
package_started = time.monotonic()
ws = prepare_live_agent_workspace(
    base_dir=a.workspace_root.resolve(), run_id=a.run_id, mounted_skills=mounted
)
shutil.copytree(a.task_root / "base", ws.workspace_path, dirs_exist_ok=True)

prompt = maintenance_prompt(a.public_request.read_text(), profile_for(task))

condition = build_condition(
    task_id=task["task_id"],
    prompt=prompt,
    condition="routed-skill",
    routed_skills=mounted,
)
req = AgentRequest.from_condition(
    run_id=a.run_id, condition=condition, workspace=ws, timeout_seconds=a.timeout
)
authroot = a.private_root.resolve() / "auth"
auth = authroot / a.run_id
auth.mkdir(parents=True, mode=0o700)
config = CodexCliRunnerConfig(
    codex_home_base=authroot,
    model="gpt-5.6-sol",
    reasoning_effort="medium",
    restrict_reads=True,
    max_stdout_chars=2000000,
    max_event_chars=2000000,
    max_stderr_chars=20000,
)
record = {
    "run_id": a.run_id,
    "task_id": task["task_id"],
    "arm": a.arm,
    "split": task["split"],
    "base_commit": task["base_commit"],
    "registry_id": registry["registry_id"],
    "selected_ids": ids,
    "mounted_skills": ws.mounted_skills,
    "model": config.model,
    "effort": config.reasoning_effort,
    "timeout": a.timeout,
    "usage": None,
    "package_prepare_seconds": time.monotonic() - package_started,
    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    "workspace": str(ws.workspace_path),
    "qualification_sha256": hashlib.sha256(a.qualification.read_bytes()).hexdigest(),
    "source_sha256": {
        str(f.relative_to(source_root.parent)): hashlib.sha256(
            f.read_bytes()
        ).hexdigest()
        for f in [
            Path(__file__),
            Path(__file__).with_name("check.py"),
            source_root / "repository_maintenance.py",
        ]
    },
}
write(a.output / "started.json", record)
(a.output / "prompt.txt").write_text(prompt)
source = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
started = time.monotonic()
try:
    shutil.copyfile(source, auth / "auth.json")
    (auth / "auth.json").chmod(0o600)
    out = container_runner.ContainerRunner(config).run(req)
    record.update(
        execution_seconds=time.monotonic() - started,
        exit_code=out.exit_code,
        timed_out=out.timed_out,
        usage=parse_codex_usage(out.events),
        execution_status="STARTED"
        if any(
            e.get("type") == "thread.started" for e in out.events if isinstance(e, dict)
        )
        else "NOT_STARTED",
    )
    (a.output / "events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in out.events)
    )
    (a.output / "stderr.txt").write_text(out.stderr)
except Exception as exc:
    record.update(
        execution_seconds=time.monotonic() - started,
        execution_status="EXECUTOR_ERROR",
        error=str(exc),
    )
    write(a.output / "run.json", record)
    raise
finally:
    (auth / "auth.json").unlink(missing_ok=True)
write(a.output / "executor.json", record)
record = finalize(
    a.output / "executor.json", a.task_root, a.qualification, a.output / "verification"
)
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
