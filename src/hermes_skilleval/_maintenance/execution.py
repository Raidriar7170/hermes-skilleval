"""Fresh code-editing trial through inherited isolated Codex transport."""

import hashlib
import json
import os
import shutil
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


def write(p, obj):
    p.write_text(json.dumps(obj, indent=2) + "\n")


def run_agent(
    *,
    base,
    public_request,
    profile,
    registry,
    ids,
    skill_assets,
    output,
    workspace_root,
    private_root,
    run_id,
    task_id,
    arm,
    timeout=600,
    model="gpt-5.6-sol",
    effort="medium",
    metadata=None,
    scratch=False,
):
    """Shared isolated execution only; callers own replay/assist acceptance contracts."""
    mounted = [
        LiveAgentSkill(
            s["id"],
            s["name"],
            s["body"],
            s["description"],
            skill_assets / s["package_path"],
            s["package_sha256"],
        )
        for s in registry["skills"]
        if s["id"] in ids
    ]
    output.mkdir(parents=True)
    source_root = Path(__file__).resolve().parent.parent
    shutil.copytree(
        source_root,
        output / "executed-source/hermes_skilleval",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    package_started = time.monotonic()
    ws = prepare_live_agent_workspace(
        base_dir=workspace_root.resolve(), run_id=run_id, mounted_skills=mounted
    )
    shutil.copytree(base, ws.workspace_path, dirs_exist_ok=True)

    prompt = maintenance_prompt(public_request, profile)
    if scratch:
        prompt += "\nPut temporary debugging scripts and scratch data only in /tmp/hermes-debug, an isolated ephemeral directory outside the source tree. Final regression tests and fixtures belong in the configured allowed test roots. The complete source patch is captured; forbidden changes will be retained as policy failures."

    condition = build_condition(
        task_id=task_id,
        prompt=prompt,
        condition="routed-skill",
        routed_skills=mounted,
    )
    req = AgentRequest.from_condition(
        run_id=run_id, condition=condition, workspace=ws, timeout_seconds=timeout
    )
    authroot = private_root.resolve() / "auth"
    auth = authroot / run_id
    auth.mkdir(parents=True, mode=0o700)
    config = CodexCliRunnerConfig(
        codex_home_base=authroot,
        model=model,
        reasoning_effort=effort,
        restrict_reads=True,
        max_stdout_chars=2000000,
        max_event_chars=2000000,
        max_stderr_chars=20000,
    )
    record = {
        "run_id": run_id,
        "task_id": task_id,
        "arm": arm,
        "registry_id": registry["registry_id"],
        "selected_ids": ids,
        "mounted_skills": ws.mounted_skills,
        "model": config.model,
        "effort": config.reasoning_effort,
        "timeout": timeout,
        "usage": None,
        "scratch_directory": "/tmp/hermes-debug" if scratch else None,
        "package_prepare_seconds": time.monotonic() - package_started,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "workspace": str(ws.workspace_path),
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
    record.update(metadata or {})
    write(output / "started.json", record)
    (output / "prompt.txt").write_text(prompt)
    source = (
        Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
    )
    started = time.monotonic()
    try:
        shutil.copyfile(source, auth / "auth.json")
        (auth / "auth.json").chmod(0o600)
        runner = container_runner.ContainerRunner(config)
        runner.scratch_enabled = scratch
        out = runner.run(req)
        record.update(
            execution_seconds=time.monotonic() - started,
            exit_code=out.exit_code,
            timed_out=out.timed_out,
            usage=parse_codex_usage(out.events),
            execution_status="STARTED"
            if any(
                e.get("type") == "thread.started"
                for e in out.events
                if isinstance(e, dict)
            )
            else "NOT_STARTED",
        )
        (output / "events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in out.events)
        )
        (output / "stderr.txt").write_text(out.stderr)
    except (Exception, KeyboardInterrupt) as exc:
        record.update(
            execution_seconds=time.monotonic() - started,
            execution_status="EXECUTOR_ERROR",
            error=str(exc),
        )
        write(output / "run.json", record)
    finally:
        (auth / "auth.json").unlink(missing_ok=True)
    from hermes_skilleval._maintenance.check import stopped

    try:
        stopped(container_runner.ContainerRunner(config).name(req))
        record["cleanup_confirmed"] = True
    except Exception:
        record["cleanup_confirmed"] = False
        record["execution_status"] = "CLEANUP_UNCONFIRMED"
    write(output / "executor.json", record)
    return record
