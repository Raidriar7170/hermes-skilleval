"""Gold-free maintenance orchestration on an explicit current-source snapshot."""

from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
import tempfile
import uuid

from hermes_skilleval.repository_profile import (
    RepositoryProfile,
    CSVKIT,
    SQLITE_UTILS,
    validate_changes,
)
from hermes_skilleval.repository_maintenance import capture, rebuild
from hermes_skilleval.file_policy import disclosure
from hermes_skilleval._maintenance.assist_snapshot import inspect_source, snapshot
from hermes_skilleval._maintenance.assist_checks import (
    parse_checks,
    freeze_checks,
    run_checks,
    paired_results,
)
from hermes_skilleval._maintenance.execution import run_agent
from hermes_skilleval._maintenance import container_runner
from hermes_skilleval.runtime_utility import load_registry


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def resource_probe(image, argv):
    """Owned no-model container, including timeout/cancellation cleanup."""
    from hermes_skilleval._maintenance.check import stopped

    name = "hermes-assist-preflight-" + uuid.uuid4().hex
    try:
        return subprocess.check_output(
            [
                "docker",
                "run",
                "--name",
                name,
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--memory",
                "512m",
                "--cpus",
                "1",
                image,
                *argv,
            ],
            text=True,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    finally:
        stopped(name)


def preflight(args):
    config = json.loads(args.repository_config.read_text())
    if (
        set(config) - {"version", "profile", "include_untracked", "exclude_input"}
        or config.get("version") != "assist-repository-v1"
    ):
        raise ValueError("unsupported repository configuration")
    profile = RepositoryProfile(**config["profile"])
    known = {p.repository: p for p in (CSVKIT, SQLITE_UTILS)}
    expected = known.get(profile.repository)
    if not expected or any(
        getattr(profile, k) != getattr(expected, k)
        for k in ("packages", "cli_module", "cli_callable", "cli_name")
    ):
        raise ValueError(
            "assist supports the declared csvkit/sqlite-utils layouts only"
        )
    if profile.file_policy is None:
        raise ValueError("assist requires an explicit operations-v1 file policy")
    if (
        not args.repo.is_dir()
        or not args.request.is_file()
        or not args.request.read_text().strip()
    ):
        raise ValueError("repository and nonempty request required")
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(args.repo.resolve()):
        raise ValueError("output must be new and outside input repository")
    if not 1 <= args.timeout <= 7200:
        raise ValueError("Agent timeout must be 1..7200 seconds")
    if not args.model or args.model.startswith("-"):
        raise ValueError("explicit supported model required")
    include, exclude = (
        config.get("include_untracked", []),
        config.get("exclude_input", []),
    )
    state = inspect_source(args.repo, include, exclude)
    for package, location in profile.packages.items():
        if str(Path(location) / package / "__init__.py") not in state["files"]:
            raise ValueError("candidate package missing from source snapshot")
    registry, skills = load_registry(args.registry, args.skill_assets)
    ids = [s.id for s in skills]
    if args.arm == "F":
        from hermes_skilleval.fixed_baseline import fixed_ids

        if args.fixed_config is None:
            raise ValueError("F requires --fixed-config")
        ids = fixed_ids(
            profile.repository, json.loads(args.fixed_config.read_text()), registry
        )
    elif args.fixed_config is not None:
        raise ValueError("N does not accept --fixed-config")
    checks = parse_checks(args.checks)
    for item in checks["checks"]:
        if item["kind"] == "existing":
            filename = item["argv"][3]
            if item["manifest"].get(filename) != state["files"].get(
                "tests/" + filename
            ):
                raise ValueError(
                    "existing check must match the current input tests/ file: "
                    + filename
                )
    missing = []
    auth = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
    if not auth.is_file():
        missing.append("Codex login: auth.json unavailable in the existing CODEX_HOME")
    image_id, version = None, None
    try:
        image_id = subprocess.check_output(
            ["docker", "image", "inspect", "--format", "{{.Id}}", profile.image],
            text=True,
            stderr=subprocess.PIPE,
            timeout=20,
        ).strip()
        version = resource_probe(profile.image, ["codex", "--version"]).strip()
        help_text = resource_probe(profile.image, ["codex", "exec", "--help"])
        from hermes_skilleval.live_agent_runtime import CodexCliRunner

        if any(flag not in help_text for flag in CodexCliRunner.REQUIRED_EXEC_FLAGS):
            missing.append("executor Codex lacks required isolation flags")
        dependencies = (
            "pytest,click,setuptools,agate,agateexcel,agatesql"
            if profile.repository == CSVKIT.repository
            else "pytest,click,sqlite_fts4,tabulate"
        )
        resource_probe(
            profile.image,
            [
                "python",
                "-I",
                "-c",
                "import importlib; [importlib.import_module(n) for n in "
                + repr(dependencies.split(","))
                + "]",
            ],
        )
    except (OSError, subprocess.SubprocessError):
        missing.append(
            "Docker image/client/dependencies unavailable; prepare the documented offline image"
        )
    result = {
        "status": "READY" if not missing else "RESOURCE_BLOCKED",
        "missing": missing,
        "profile": profile.to_dict(),
        "policy": disclosure(profile.file_policy),
        "source": state,
        "arm": args.arm,
        "selected_ids": ids,
        "registry_id": registry["registry_id"],
        "model": args.model,
        "effort": args.effort,
        "timeout": args.timeout,
        "image_id": image_id,
        "codex_version": version,
        "checks": checks,
        "request_sha256": hashlib.sha256(args.request.read_bytes()).hexdigest(),
        "models_loaded": False,
        "resolved": None,
    }
    return result, profile, registry, config


def execute(args):
    start = time.monotonic()
    info, profile, registry, config = preflight(args)
    preflight_seconds = time.monotonic() - start
    if args.plan_only:
        return info, 0 if info["status"] == "READY" else 2
    if info["missing"]:
        return info, 2
    if info.get("image_id"):
        from dataclasses import replace

        profile = replace(profile, image=info["image_id"])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    run_id = "assist-" + uuid.uuid4().hex
    result = {
        "run_id": run_id,
        "engineering": "PARTIAL",
        "resolved": None,
        "source": info["source"],
        "source_unchanged": None,
        "policy_status": "NOT_CHECKED",
        "rebuild": "NOT_RUN",
        "usage": None,
        "dollar_cost": None,
        "timing": {"preflight_seconds": preflight_seconds},
        "checks": {},
        "requirements": {},
        "errors": [],
    }
    baseline_checks, candidate_checks = {}, {}
    checks = info["checks"]
    write(output / "preflight.json", info)
    (output / "request.md").write_text(args.request.read_text())
    try:
        mark = time.monotonic()
        base = output / "source"
        snapshot(
            args.repo,
            base,
            info["source"],
            config.get("include_untracked", []),
            config.get("exclude_input", []),
        )
        checks = freeze_checks(checks, output / "trusted")
        write(output / "checks.json", checks)
        result["timing"]["snapshot_and_checks_seconds"] = time.monotonic() - mark
        # Reuse the existing no-model isolation canary before staging credentials.
        mark = time.monotonic()
        subprocess.run(
            [
                sys.executable,
                "-m",
                "hermes_skilleval._maintenance.canary",
                "--image",
                profile.image,
                "--workspace-root",
                str(output / "canary-work"),
                "--private-root",
                str(output / "private"),
                "--output",
                str(output / "canary.json"),
            ],
            check=True,
            capture_output=True,
            timeout=100,
        )
        if not json.loads((output / "canary.json").read_text())["passed"]:
            raise ValueError("isolation canary rejected")
        result["timing"]["canary_seconds"] = time.monotonic() - mark
        mark = time.monotonic()
        baseline_checks = run_checks(checks, base, output / "baseline-checks", profile)
        result["timing"]["baseline_checks_seconds"] = time.monotonic() - mark
        # Invalid loading/collection is a preflight failure; ordinary baseline test failures are allowed.
        if any(not v.get("valid") for v in baseline_checks.values()):
            raise ValueError(
                "baseline trusted loading/collection invalid; Agent not started"
            )
        container_runner.IMAGE = profile.image
        executor = run_agent(
            base=base,
            public_request=(output / "request.md").read_text(),
            profile=profile,
            registry=registry,
            ids=info["selected_ids"],
            skill_assets=args.skill_assets,
            output=output / "execution",
            workspace_root=Path(tempfile.mkdtemp(prefix="hermes-assist-work-")),
            private_root=output / "private",
            run_id=run_id,
            task_id=run_id,
            arm=args.arm,
            timeout=args.timeout,
            model=args.model,
            effort=args.effort,
        )
        result["execution"] = executor
        if executor.get("error"):
            result["errors"].append("executor: " + executor["error"])
        result["usage"] = executor.get("usage")
        result["timing"]["skill_prepare_seconds"] = executor.get(
            "package_prepare_seconds"
        )
        result["timing"]["agent_seconds"] = executor.get("execution_seconds")
        if not executor["cleanup_confirmed"]:
            raise ValueError("container cleanup unconfirmed; capture forbidden")
        mark = time.monotonic()
        cap = capture(
            base, Path(executor["workspace"]), output / "capture", strict=True
        )
        result["timing"]["capture_seconds"] = time.monotonic() - mark
        write(output / "capture.json", cap)
        result["patch"] = {
            "path": "capture/candidate.patch",
            "sha256": cap["patch_sha256"],
            "changed_files": cap["changed_files"],
        }
        try:
            validate_changes(
                profile,
                cap["changed_files"],
                before=cap["base_manifest"],
                after=cap["candidate_manifest"],
                candidate=output / "capture/snapshot",
            )
        except ValueError:
            result["policy_status"] = "REJECTED_NOT_FUNCTIONALLY_VERIFIED"
            raise
        result["policy_status"] = "ACCEPTED"
        mark = time.monotonic()
        rebuild(
            base,
            output / "capture/candidate.patch",
            output / "candidate",
            cap["candidate_manifest"],
            cap["candidate_modes"],
            strict=True,
        )
        result["rebuild"] = "MATCHED_CAPTURE"
        result["timing"]["rebuild_seconds"] = time.monotonic() - mark
        mark = time.monotonic()
        candidate_checks = run_checks(
            checks, output / "candidate", output / "candidate-checks", profile
        )
        result["timing"]["candidate_checks_seconds"] = time.monotonic() - mark
        if (
            executor.get("exit_code") == 0
            and not executor.get("timed_out")
            and executor.get("execution_status") == "STARTED"
        ):
            result["engineering"] = "COMPLETE"
    except (Exception, KeyboardInterrupt) as exc:
        result["errors"].append(type(exc).__name__ + ": " + str(exc))
    finally:
        result.update(paired_results(checks, baseline_checks, candidate_checks))
        try:
            result["source_unchanged"] = (
                inspect_source(
                    args.repo,
                    config.get("include_untracked", []),
                    config.get("exclude_input", []),
                )
                == info["source"]
            )
        except Exception:
            result["source_unchanged"] = False
        if not result["source_unchanged"]:
            result["engineering"] = "PARTIAL"
            result["errors"].append(
                "source changed during execution; no automatic restoration performed"
            )
        result["timing"]["request_wall_seconds"] = time.monotonic() - start
        result["timing"]["worker_seconds"] = None
        result["timing"]["selection_seconds"] = (
            None  # No retrieval; included in preflight.
        )
        write(output / "result.json", result)
        report = [
            "# Assist result",
            "",
            f"Engineering: {result['engineering']}; resolved: UNKNOWN.",
            f"Policy: {result['policy_status']}; rebuild: {result['rebuild']}; source unchanged: {result['source_unchanged']}",
            "",
            "[Candidate patch](capture/candidate.patch)",
            "",
            "## Declared checks",
        ]
        for key, pair in result["checks"].items():
            report.append(
                f"- {key}: baseline={pair['baseline_passed']}, candidate={pair['candidate_passed']}, new failures={pair['new_failures']}, unknown={pair['unknown']}"
            )
        report += ["", "## Requirements"]
        report += [
            f"- {k}: {v['status']} — {v['description']}"
            for k, v in result["requirements"].items()
        ]
        report += [
            "",
            "Requirements beyond these explicit checks remain NOT_VERIFIED. Agent-authored tests do not replace controller checks.",
            "",
            "## Observed cost",
            "```json",
            json.dumps(
                {
                    "usage": result["usage"],
                    "timing": result["timing"],
                    "dollar_cost": None,
                },
                indent=2,
            ),
            "```",
        ]
        report += ["", "## Errors", *result["errors"]]
        (output / "report.md").write_text("\n".join(report) + "\n")
    passed = result["engineering"] == "COMPLETE" and all(
        p["valid_comparison"] and p["candidate_passed"]
        for p in result["checks"].values()
    )
    return result, 0 if passed else 2
