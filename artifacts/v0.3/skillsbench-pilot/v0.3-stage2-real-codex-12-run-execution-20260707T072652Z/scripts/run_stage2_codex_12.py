from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
ARTIFACT_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[5]
RUNTIME_ROOT = Path(
    "/Users/Shared/hermes-skilleval-runtime/"
    "stage2-real-codex-12-run-execution-20260707T072652Z"
)

sys.path.insert(0, str(REPO_ROOT / "src"))

from hermes_skilleval.live_agent_runtime import (  # noqa: E402
    AgentRequest,
    AgentResult,
    CodexCliRunner,
    CodexCliRunnerConfig,
    LiveAgentSkill,
    RunnerOutput,
    _parse_events,
    _safe_path_part,
    _sha256_text,
    build_condition,
    prepare_live_agent_workspace,
)
from hermes_skilleval.live_agent_skillsbench import (  # noqa: E402
    _validate_real_runner_preflight,
)
from hermes_skilleval.release_manifest import sha256_file  # noqa: E402


TIMESTAMP = "20260707T072652Z"
FROZEN_PLAN_PATH = (
    REPO_ROOT
    / "artifacts/v0.3/skillsbench-pilot/"
    "v0.3-stage2-pilot-freeze-20260707T025315Z/"
    "stage2-pilot-plan.frozen.json"
)
FROZEN_PLAN_SHA256 = (
    "aaa0f4c4d1939cff9bcba08ce6549284726353ed199d7bedd31614be970f579b"
)
INPUT_PACKAGE_ROOT = (
    REPO_ROOT
    / "artifacts/v0.3/skillsbench-pilot/"
    "v0.3-stage2-input-package-candidate-20260701T010000Z"
)
INPUT_PACKAGE_PATH = INPUT_PACKAGE_ROOT / "stage2-real-pilot-input-package.json"
INPUT_PACKAGE_SHA256 = (
    "235a48830bc25f324f071582a42ed42a3074342d3b6f6f914d0ea99fb26a8739"
)
ROUTED_PREDICTIONS_PATH = INPUT_PACKAGE_ROOT / "routed_predictions.strict.json"
ROUTED_PREDICTIONS_SHA256 = (
    "28c4d20f0e535aa8c6a2b1f8603a99df385dffae8794be1abe86c0669feb9ea1"
)
ISOLATED_AUTH_SMOKE_PATH = (
    REPO_ROOT
    / "artifacts/v0.3/skillsbench-pilot/"
    "v0.3-codex-real-runner-isolated-auth-smoke-preflight-20260706T093453Z/"
    "codex-real-runner-isolated-auth-smoke-preflight.json"
)
ISOLATED_AUTH_SMOKE_SHA256 = (
    "881d47b6a6b667c90a1caf98adae5688f43438006e6c8b218a9ed47afd89f1b7"
)
RUN_ORDER_SHA256 = (
    "86a7f74febf47ce31601b3238d2785267fbc84bb0b4dc1021680f33897af25fb"
)
EXPECTED_TASKS = [
    "bike-rebalance",
    "dialogue-parser",
    "offer-letter-generator",
    "powerlifting-coef-calc",
]
EXPECTED_CONDITIONS = ["no-skill", "routed-skill", "oracle-skill"]
EXPECTED_RUN_IDS = [
    "stage2-freeze-01-bike-rebalance-no-skill-trial-01",
    "stage2-freeze-02-bike-rebalance-routed-skill-trial-01",
    "stage2-freeze-03-bike-rebalance-oracle-skill-trial-01",
    "stage2-freeze-04-dialogue-parser-no-skill-trial-01",
    "stage2-freeze-05-dialogue-parser-routed-skill-trial-01",
    "stage2-freeze-06-dialogue-parser-oracle-skill-trial-01",
    "stage2-freeze-07-offer-letter-generator-no-skill-trial-01",
    "stage2-freeze-08-offer-letter-generator-routed-skill-trial-01",
    "stage2-freeze-09-offer-letter-generator-oracle-skill-trial-01",
    "stage2-freeze-10-powerlifting-coef-calc-no-skill-trial-01",
    "stage2-freeze-11-powerlifting-coef-calc-routed-skill-trial-01",
    "stage2-freeze-12-powerlifting-coef-calc-oracle-skill-trial-01",
]

COMMAND_OUTPUT_DIR = ARTIFACT_ROOT / "command-output"
CODEX_OUTPUT_DIR = ARTIFACT_ROOT / "codex-output"
VERIFIER_OUTPUT_DIR = ARTIFACT_ROOT / "verifier-output"
TRACE_DIR = ARTIFACT_ROOT / "traces"
WORKSPACE_ROOT = RUNTIME_ROOT / "workspaces"
CODEX_HOME_BASE = RUNTIME_ROOT / "codex-home-base"
PROGRESS_PATH = ARTIFACT_ROOT / "progress.json"
EXECUTION_ARTIFACT_PATH = ARTIFACT_ROOT / "stage2-real-codex-12-run-execution.json"
MATRIX_REPORT_PATH = ARTIFACT_ROOT / "stage2-real-codex-12-run-matrix-report.json"
RUNTIME_MANIFEST_PATH = ARTIFACT_ROOT / "isolated-runtime-manifest.json"
MANIFEST_PATH = ARTIFACT_ROOT / "manifest.json"

CODEX_TIMEOUT_SECONDS = int(os.environ.get("HERMES_STAGE2_CODEX_TIMEOUT_SECONDS", "1200"))
CODEX_STDIO_LIMIT = int(os.environ.get("HERMES_STAGE2_CODEX_STDIO_LIMIT", "20000"))

DOCKER_IMAGES = {
    "bike-rebalance": "hermes-pr13-zero-bike-rebalance:20260702T113533Z",
    "dialogue-parser": "hermes-pr13-zero-dialogue-parser:20260702T113533Z",
    "offer-letter-generator": "hermes-pr13-zero-offer-letter-generator:20260702T113533Z",
    "powerlifting-coef-calc": "hermes-pr13-zero-powerlifting-coef-calc:20260702T113533Z",
}

AUTH_FAILURE_RE = re.compile(
    r"\b(401|unauthorized|not logged in|authentication|auth failed|invalid auth)\b",
    re.IGNORECASE,
)


def main() -> int:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    for path in [
        COMMAND_OUTPUT_DIR,
        CODEX_OUTPUT_DIR,
        VERIFIER_OUTPUT_DIR,
        TRACE_DIR,
        WORKSPACE_ROOT,
        CODEX_HOME_BASE,
    ]:
        path.mkdir(parents=True, exist_ok=True)

    progress = load_progress()
    if progress.get("terminal") is True:
        print(f"terminal status already recorded: {progress.get('status')}")
        return 0

    try:
        plan, runs = load_and_verify_plan()
        package = load_and_verify_input_package()
        routed_predictions = load_and_verify_routed_predictions()
        codex_evidence = collect_codex_cli_evidence()
        verify_runtime_parent_chain()
        verify_docker_images()
        source_auth_record = find_source_auth_record()
    except Exception as exc:
        record_blocker(
            status="BLOCKED_STAGE2_EXECUTION_PREFLIGHT_BEFORE_CODEX_EXEC",
            reason=str(exc),
            progress=progress,
            codex_evidence=None,
            source_auth_record=None,
            run_records=progress.get("run_records", []),
        )
        print(f"blocked before Codex execution: {exc}")
        return 2

    task_by_id = {
        str(task["task_id"]): task
        for task in package["data_root_package"]["selected_tasks"]
    }
    skill_by_id = load_skills(package)
    run_records = list(progress.get("run_records", []))
    completed_ids = {str(record.get("run_id")) for record in run_records}

    runner = CodexCliRunner(
        CodexCliRunnerConfig(
            codex_binary=codex_evidence["path"],
            codex_home_mode="isolated",
            codex_home_base=CODEX_HOME_BASE,
            isolate_home=True,
            sandbox="workspace-write",
            approval_policy="never",
            max_stdout_chars=CODEX_STDIO_LIMIT,
            max_stderr_chars=CODEX_STDIO_LIMIT,
            max_event_chars=CODEX_STDIO_LIMIT,
            skip_git_repo_check=True,
        )
    )

    write_runtime_manifest(source_auth_record=source_auth_record)
    write_all_artifacts(
        status="IN_PROGRESS",
        plan=plan,
        runs=runs,
        codex_evidence=codex_evidence,
        source_auth_record=source_auth_record,
        run_records=run_records,
        blocker=None,
    )

    for run in runs:
        run_id = str(run["run_id"])
        if run_id in completed_ids:
            print(f"skip completed {run_id}")
            continue
        if (WORKSPACE_ROOT / _safe_path_part(run_id)).exists():
            blocker = {
                "status": "BLOCKED_RUN_WORKSPACE_EXISTS_BEFORE_RESUME",
                "reason": "run workspace exists for an incomplete run",
                "run_id": run_id,
                "workspace_path": str(WORKSPACE_ROOT / _safe_path_part(run_id)),
            }
            write_all_artifacts(
                status=blocker["status"],
                plan=plan,
                runs=runs,
                codex_evidence=codex_evidence,
                source_auth_record=source_auth_record,
                run_records=run_records,
                blocker=blocker,
                terminal=True,
            )
            print(f"blocked: {blocker['reason']}: {run_id}")
            return 2

        try:
            record = execute_one_run(
                run=run,
                runner=runner,
                task=task_by_id[str(run["task_id"])],
                skills=skill_by_id,
                routed_predictions=routed_predictions,
                codex_evidence=codex_evidence,
                source_auth_record=source_auth_record,
            )
        except SafetyBlocker as exc:
            blocker = exc.payload
            write_all_artifacts(
                status=str(blocker["status"]),
                plan=plan,
                runs=runs,
                codex_evidence=codex_evidence,
                source_auth_record=source_auth_record,
                run_records=run_records,
                blocker=blocker,
                terminal=True,
            )
            print(f"blocked: {blocker['status']}: {blocker['reason']}")
            return 2

        run_records.append(record)
        completed_ids.add(run_id)
        write_all_artifacts(
            status="IN_PROGRESS",
            plan=plan,
            runs=runs,
            codex_evidence=codex_evidence,
            source_auth_record=source_auth_record,
            run_records=run_records,
            blocker=None,
        )
        print(
            f"completed {run_id}: verifier_passed={record['verifier']['passed']} "
            f"process_exit_code={record['codex']['process_exit_code']}"
        )

    final_status = "STAGE2_REAL_CODEX_12_RUN_EXECUTION_COMPLETED_VERIFIER_RECORDED"
    write_all_artifacts(
        status=final_status,
        plan=plan,
        runs=runs,
        codex_evidence=codex_evidence,
        source_auth_record=source_auth_record,
        run_records=run_records,
        blocker=None,
        terminal=True,
    )
    print(final_status)
    return 0


class SafetyBlocker(RuntimeError):
    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(str(payload.get("reason", payload.get("status"))))
        self.payload = payload


def load_and_verify_plan() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if sha256_file(FROZEN_PLAN_PATH) != FROZEN_PLAN_SHA256:
        raise ValueError("frozen plan hash mismatch")
    plan = read_json(FROZEN_PLAN_PATH)
    shape = plan.get("pilot_shape")
    if not isinstance(shape, dict):
        raise ValueError("frozen plan missing pilot_shape")
    runs = shape.get("runs")
    if not isinstance(runs, list):
        raise ValueError("frozen plan missing pilot_shape.runs")
    run_ids = [str(run.get("run_id")) for run in runs]
    if run_ids != EXPECTED_RUN_IDS:
        raise ValueError("frozen run order mismatch")
    if shape.get("run_order_sha256") != RUN_ORDER_SHA256:
        raise ValueError("frozen run order hash mismatch")
    if shape.get("tasks") != EXPECTED_TASKS:
        raise ValueError("frozen task list mismatch")
    if [item.get("condition_id") for item in shape.get("conditions", [])] != EXPECTED_CONDITIONS:
        raise ValueError("frozen condition list mismatch")
    if int(shape.get("total_planned_runs", 0)) != 12:
        raise ValueError("frozen total planned runs mismatch")
    if int(shape.get("trials_per_task_condition", 0)) != 1:
        raise ValueError("frozen trial count mismatch")
    return plan, runs


def load_and_verify_input_package() -> dict[str, Any]:
    if sha256_file(INPUT_PACKAGE_PATH) != INPUT_PACKAGE_SHA256:
        raise ValueError("input package hash mismatch")
    package = read_json(INPUT_PACKAGE_PATH)
    selected = package.get("data_root_package", {}).get("selected_tasks")
    if not isinstance(selected, list):
        raise ValueError("input package missing selected tasks")
    task_ids = [str(task.get("task_id")) for task in selected]
    if task_ids != EXPECTED_TASKS:
        raise ValueError("input package task order mismatch")
    return package


def load_and_verify_routed_predictions() -> dict[str, list[str]]:
    if sha256_file(ROUTED_PREDICTIONS_PATH) != ROUTED_PREDICTIONS_SHA256:
        raise ValueError("routed prediction hash mismatch")
    routed = read_json(ROUTED_PREDICTIONS_PATH).get("predictions")
    if not isinstance(routed, dict):
        raise ValueError("routed predictions missing predictions object")
    result: dict[str, list[str]] = {}
    for task_id in EXPECTED_TASKS:
        ids = routed.get(task_id)
        if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
            raise ValueError(f"routed predictions missing task: {task_id}")
        result[task_id] = ids
    return result


def load_skills(package: dict[str, Any]) -> dict[str, LiveAgentSkill]:
    raw = package.get("global_skill_registry_package", {}).get("skills")
    if not isinstance(raw, dict):
        raise ValueError("input package missing global skill registry")
    skills: dict[str, LiveAgentSkill] = {}
    for skill_id, record in raw.items():
        if not isinstance(record, dict):
            raise ValueError(f"malformed skill record: {skill_id}")
        skills[str(skill_id)] = LiveAgentSkill(
            skill_id=str(record["skill_id"]),
            name=str(record["name"]),
            description=str(record.get("description", "")),
            body=str(record["body"]),
        )
    return skills


def collect_codex_cli_evidence() -> dict[str, Any]:
    which = run_command_artifact("codex-path", ["which", "codex"])
    codex_path = read_text_ref(which["stdout"]).strip()
    version = run_command_artifact("codex-version", [codex_path, "--version"])
    help_ = run_command_artifact("codex-exec-help", [codex_path, "exec", "--help"])
    help_text = read_text_ref(help_["stdout"])
    required = [
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "--cd",
        "--output-last-message",
    ]
    present = {flag: flag in help_text for flag in required}
    if not all(present.values()):
        missing = [flag for flag, ok in present.items() if not ok]
        raise ValueError("Codex CLI help missing required flags: " + ", ".join(missing))
    return {
        "path": codex_path,
        "which": which,
        "version": version,
        "exec_help": help_,
        "required_help_flags_present": present,
        "supports_skip_git_repo_check": "--skip-git-repo-check" in help_text,
    }


def verify_runtime_parent_chain() -> None:
    for parent in [RUNTIME_ROOT, *RUNTIME_ROOT.parents]:
        skill_dir = parent / ".agents" / "skills"
        if skill_dir.exists() and visible_child_count(skill_dir):
            raise ValueError(f"runtime parent skill leakage detected: {skill_dir}")


def verify_docker_images() -> None:
    for task_id, image in DOCKER_IMAGES.items():
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        write_text_file(COMMAND_OUTPUT_DIR / f"docker-image-inspect-{task_id}.stdout.txt", result.stdout)
        write_text_file(COMMAND_OUTPUT_DIR / f"docker-image-inspect-{task_id}.stderr.txt", result.stderr)
        if result.returncode != 0:
            raise ValueError(f"missing docker image for verifier: {image}")


def find_source_auth_record() -> dict[str, Any]:
    source_env = os.environ.get("HERMES_CODEX_AUTH_JSON") or os.environ.get("CODEX_AUTH_JSON")
    if source_env:
        source = Path(source_env).expanduser()
        category = "explicit_auth_json_env"
    else:
        source_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
        source = source_home / "auth.json"
        category = "local_user_codex_home"
    if not source.is_file():
        raise ValueError(f"allowlisted auth.json not found: {source}")
    stat = source.stat()
    return {
        "exists": True,
        "name": "auth.json",
        "source_codex_home_category": category,
        "source_codex_home_path": str(source.parent),
        "path_recorded_without_content": str(source),
        "size_bytes": stat.st_size,
        "mode_octal": oct(stat.st_mode & 0o777),
        "sha256": None,
        "sha256_withheld_reason": "secret-bearing auth file fingerprint not committed",
        "raw_secret_contents_committed": False,
    }


def materialize_auth_for_run(run_id: str, source_auth_record: dict[str, Any]) -> dict[str, Any]:
    source = Path(str(source_auth_record["path_recorded_without_content"]))
    target_home = CODEX_HOME_BASE / _safe_path_part(run_id)
    target = target_home / "auth.json"
    target_home.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(0o600)
    stat = target.stat()
    forbidden = [
        "config.toml",
        "skills",
        "plugins",
        "prompts",
        "rules",
        "sessions",
        "logs",
    ]
    copied_forbidden = [name for name in forbidden if (target_home / name).exists()]
    if copied_forbidden:
        raise SafetyBlocker(
            {
                "status": "BLOCKED_ISOLATED_CODEX_HOME_FORBIDDEN_MATERIALIZATION",
                "reason": "forbidden non-auth material exists in isolated CODEX_HOME",
                "run_id": run_id,
                "forbidden_entries": copied_forbidden,
                "codex_exec_invoked": False,
            }
        )
    return {
        "allowlisted_materialized_files": ["auth.json"],
        "config_toml_copied": False,
        "skills_or_plugins_prompts_rules_sessions_logs_copied": False,
        "raw_secret_contents_committed": False,
        "source_auth_record": {
            key: value
            for key, value in source_auth_record.items()
            if key != "path_recorded_without_content"
        },
        "materialized_auth_record": {
            "exists": True,
            "path": str(target),
            "size_bytes": stat.st_size,
            "mode_octal": oct(stat.st_mode & 0o777),
            "sha256": None,
            "sha256_withheld_reason": "secret-bearing auth file fingerprint not committed",
        },
    }


def execute_one_run(
    *,
    run: dict[str, Any],
    runner: CodexCliRunner,
    task: dict[str, Any],
    skills: dict[str, LiveAgentSkill],
    routed_predictions: dict[str, list[str]],
    codex_evidence: dict[str, Any],
    source_auth_record: dict[str, Any],
) -> dict[str, Any]:
    run_id = str(run["run_id"])
    task_id = str(run["task_id"])
    condition_id = str(run["condition_id"])
    prompt = str(task["prompt"])
    prompt_hash = str(task["prompt_hash"])
    if _sha256_text(prompt) != prompt_hash:
        raise SafetyBlocker(
            {
                "status": "BLOCKED_TASK_PROMPT_HASH_MISMATCH_BEFORE_CODEX_EXEC",
                "reason": "task prompt hash mismatch",
                "run_id": run_id,
                "codex_exec_invoked": False,
            }
        )

    routed_skills = (
        [skills[skill_id] for skill_id in routed_predictions[task_id]]
        if condition_id == "routed-skill"
        else []
    )
    oracle_skills = (
        [skills[skill_id] for skill_id in task["oracle_skill_ids"]]
        if condition_id == "oracle-skill"
        else []
    )
    condition = build_condition(
        task_id=task_id,
        prompt=prompt,
        condition=condition_id,
        routed_skills=routed_skills,
        oracle_skills=oracle_skills,
    )
    workspace = prepare_live_agent_workspace(
        base_dir=WORKSPACE_ROOT,
        run_id=run_id,
        mounted_skills=condition.mounted_skills,
    )
    populate_workspace_inputs(task_id=task_id, workspace=workspace.workspace_path)
    auth_record = materialize_auth_for_run(run_id, source_auth_record)
    request = AgentRequest.from_condition(
        run_id=run_id,
        condition=condition,
        workspace=workspace,
        timeout_seconds=CODEX_TIMEOUT_SECONDS,
        metadata={
            "frozen_plan": path_ref(FROZEN_PLAN_PATH),
            "input_package": path_ref(INPUT_PACKAGE_PATH),
            "routed_predictions": path_ref(ROUTED_PREDICTIONS_PATH),
            "isolated_auth_smoke_preflight": path_ref(ISOLATED_AUTH_SMOKE_PATH),
            "future_expected_success_source": "deterministic verifier output only",
            "process_exit_code_is_task_success": False,
            "llm_judge_is_task_success": False,
            "performance_claim_made": False,
        },
    )

    safe_command_line = safe_codex_command_line(
        codex_path=str(codex_evidence["path"]),
        run_id=run_id,
        workspace=workspace.workspace_path,
        prompt_hash=prompt_hash,
        supports_skip_git_repo_check=bool(codex_evidence["supports_skip_git_repo_check"]),
    )
    output = run_codex_or_block(runner=runner, request=request)
    stdout_ref = write_text_ref(CODEX_OUTPUT_DIR / run_id / "codex-stdout.txt", output.stdout)
    stderr_ref = write_text_ref(CODEX_OUTPUT_DIR / run_id / "codex-stderr.txt", output.stderr)

    try:
        events, skill_use, final_message = _parse_events(output.events, request)
        _validate_real_runner_preflight(events)
    except Exception as exc:
        raise SafetyBlocker(
            {
                "status": "BLOCKED_REAL_RUNNER_PREFLIGHT_VALIDATION_AFTER_CODEX_RETURN",
                "reason": str(exc),
                "run_id": run_id,
                "codex_exec_invoked": True,
                "process_exit_code": output.exit_code,
                "timed_out": output.timed_out,
                "stdout": stdout_ref,
                "stderr": stderr_ref,
            }
        ) from exc

    if is_auth_failure(output):
        raise SafetyBlocker(
            {
                "status": "BLOCKED_ISOLATED_CODEX_HOME_AUTH_FAILURE_DURING_STAGE2_EXECUTION",
                "reason": "Codex returned authentication failure signal in isolated CODEX_HOME",
                "run_id": run_id,
                "codex_exec_invoked": True,
                "process_exit_code": output.exit_code,
                "timed_out": output.timed_out,
                "stdout": stdout_ref,
                "stderr": stderr_ref,
            }
        )

    verifier = run_docker_verifier(task_id=task_id, workspace=workspace.workspace_path, run_id=run_id)
    result = AgentResult(
        request=request,
        process_exit_code=output.exit_code,
        timed_out=output.timed_out,
        verifier_passed=bool(verifier["passed"]),
        verifier_details=verifier,
        task_success=bool(verifier["passed"]),
        stdout=output.stdout,
        stderr=output.stderr,
        stdout_truncated=False,
        stderr_truncated=False,
        events=events,
        skill_use=skill_use,
        final_message=final_message,
        usage=None,
        cost=None,
    )
    trace_path = TRACE_DIR / f"{run_id}.json"
    write_json_file(trace_path, result.to_trace())
    final_message_ref = None
    last_message = CODEX_HOME_BASE / _safe_path_part(run_id) / "runner-output" / "codex-last-message.txt"
    if last_message.exists():
        final_message_ref = path_ref(last_message)

    return {
        "record_status": "COMPLETED_VERIFIER_RECORDED",
        "run_id": run_id,
        "run_index": int(run["run_index"]),
        "task_id": task_id,
        "condition": condition_id,
        "trial_index": int(run["trial_index"]),
        "frozen_run_id": run_id,
        "codex": {
            "codex_exec_invoked": True,
            "safe_command_line": safe_command_line,
            "process_exit_code": output.exit_code,
            "process_exit_code_is_task_success": False,
            "timed_out": output.timed_out,
            "stdout": stdout_ref,
            "stderr": stderr_ref,
            "final_message": final_message_ref,
        },
        "workspace": {
            "path": str(workspace.workspace_path),
            "sha256_tree_manifest": write_workspace_inventory(run_id, workspace.workspace_path),
            "mounted_skills": workspace.mounted_skills,
        },
        "isolated_runtime": {
            "codex_home": str(CODEX_HOME_BASE / _safe_path_part(run_id)),
            "home": str(CODEX_HOME_BASE / _safe_path_part(run_id) / "home"),
            "auth": auth_record,
            "skill_inventory": preflight_inventory(events),
        },
        "inputs": {
            "task_prompt_sha256": prompt_hash,
            "selected_stage2_task_prompt_used": True,
            "input_files": input_file_refs(task_id, workspace.workspace_path),
        },
        "verifier": verifier,
        "trace": path_ref(trace_path),
        "success_source": {
            "task_success_source": "deterministic verifier output only",
            "verifier_output_is_only_task_success_source": True,
            "process_exit_code_is_task_success": False,
            "llm_judge_used": False,
            "llm_judge_is_task_success": False,
            "task_success": bool(verifier["passed"]),
        },
    }


def run_codex_or_block(*, runner: CodexCliRunner, request: AgentRequest) -> RunnerOutput:
    try:
        return runner.run(request)
    except Exception as exc:
        raise SafetyBlocker(
            {
                "status": "BLOCKED_REAL_RUNNER_BEFORE_CODEX_EXEC_OR_DURING_PREFLIGHT",
                "reason": str(exc),
                "run_id": request.run_id,
                "codex_exec_invoked": False,
            }
        ) from exc


def populate_workspace_inputs(*, task_id: str, workspace: Path) -> None:
    source_root = INPUT_PACKAGE_ROOT / "candidate-data" / "environment-snapshots" / task_id
    if task_id == "bike-rebalance":
        shutil.copy2(source_root / "data.json", workspace / "data.json")
    elif task_id == "dialogue-parser":
        shutil.copy2(source_root / "script.txt", workspace / "script.txt")
    elif task_id == "offer-letter-generator":
        shutil.copy2(source_root / "employee_data.json", workspace / "employee_data.json")
        shutil.copy2(source_root / "offer_letter_template.docx", workspace / "offer_letter_template.docx")
    elif task_id == "powerlifting-coef-calc":
        data_dir = workspace / "data"
        data_dir.mkdir()
        shutil.copy2(source_root / "openipf_cleaned.xlsx", data_dir / "openipf.xlsx")
        shutil.copy2(source_root / "data-readme.md", data_dir / "data-readme.md")
    else:
        raise ValueError(f"unsupported task: {task_id}")


def run_docker_verifier(*, task_id: str, workspace: Path, run_id: str) -> dict[str, Any]:
    verifier_dir = INPUT_PACKAGE_ROOT / "candidate-data" / "verifier-artifacts" / task_id
    logs_dir = VERIFIER_OUTPUT_DIR / run_id
    logs_dir.mkdir(parents=True, exist_ok=True)
    mount_point = "/app" if task_id == "dialogue-parser" else "/root"
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "-v",
        f"{workspace}:{mount_point}:ro",
        "-v",
        f"{verifier_dir}:/verifier:ro",
        "-v",
        f"{logs_dir}:/logs",
        "-w",
        mount_point,
        DOCKER_IMAGES[task_id],
        "/bin/bash",
        "/verifier/test.sh",
    ]
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_ref = write_text_ref(logs_dir / "docker-run-stdout.txt", result.stdout)
    stderr_ref = write_text_ref(logs_dir / "docker-run-stderr.txt", result.stderr)
    reward_path = logs_dir / "verifier" / "reward.txt"
    ctrf_path = logs_dir / "verifier" / "ctrf.json"
    reward = reward_path.read_text(encoding="utf-8").strip() if reward_path.exists() else ""
    ctrf = read_json(ctrf_path) if ctrf_path.exists() else {}
    summary = ctrf.get("results", {}).get("summary", {}) if isinstance(ctrf, dict) else {}
    failed = int(summary.get("failed", 999999)) if isinstance(summary, dict) else 999999
    tests = int(summary.get("tests", 0)) if isinstance(summary, dict) else 0
    passed_count = int(summary.get("passed", 0)) if isinstance(summary, dict) else 0
    passed = reward == "1" and tests > 0 and failed == 0 and passed_count == tests
    return {
        "command_line": safe_join(command),
        "docker_exit_code": result.returncode,
        "docker_exit_code_is_task_success": False,
        "stdout": stdout_ref,
        "stderr": stderr_ref,
        "reward": path_ref(reward_path) if reward_path.exists() else None,
        "ctrf": path_ref(ctrf_path) if ctrf_path.exists() else None,
        "reward_value": reward,
        "ctrf_summary": summary,
        "passed": passed,
        "success_source": "deterministic verifier output only",
        "llm_judge_used": False,
    }


def is_auth_failure(output: RunnerOutput) -> bool:
    if output.exit_code == 0 and not output.timed_out:
        return False
    combined = f"{output.stdout}\n{output.stderr}"
    return bool(AUTH_FAILURE_RE.search(combined))


def safe_codex_command_line(
    *,
    codex_path: str,
    run_id: str,
    workspace: Path,
    prompt_hash: str,
    supports_skip_git_repo_check: bool,
) -> str:
    output_path = CODEX_HOME_BASE / _safe_path_part(run_id) / "runner-output" / "codex-last-message.txt"
    command = [
        codex_path,
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "workspace-write",
        "--config",
        'approval_policy="never"',
        "--cd",
        str(workspace),
        "--output-last-message",
        str(output_path),
    ]
    if supports_skip_git_repo_check:
        command.append("--skip-git-repo-check")
    command.extend(["--", f"<stage2 task prompt sha256:{prompt_hash}>"])
    return safe_join(command)


def preflight_inventory(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in events:
        if event.get("type") == "preflight":
            inventory = event.get("global_capability_inventory")
            return inventory if isinstance(inventory, dict) else None
    return None


def write_workspace_inventory(run_id: str, workspace: Path) -> dict[str, Any]:
    records = []
    for path in sorted(item for item in workspace.rglob("*") if item.is_file()):
        records.append(
            {
                "path": str(path.relative_to(workspace)),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    output = ARTIFACT_ROOT / "workspace-inventory" / f"{run_id}.json"
    write_json_file(output, {"workspace": str(workspace), "files": records})
    return path_ref(output)


def input_file_refs(task_id: str, workspace: Path) -> list[dict[str, Any]]:
    candidates: dict[str, list[Path]] = {
        "bike-rebalance": [workspace / "data.json"],
        "dialogue-parser": [workspace / "script.txt"],
        "offer-letter-generator": [
            workspace / "employee_data.json",
            workspace / "offer_letter_template.docx",
        ],
        "powerlifting-coef-calc": [
            workspace / "data" / "openipf.xlsx",
            workspace / "data" / "data-readme.md",
        ],
    }
    return [path_ref(path) for path in candidates[task_id]]


def write_runtime_manifest(*, source_auth_record: dict[str, Any]) -> None:
    manifest = {
        "schema_version": "v0.3.stage2-real-codex-runtime-manifest.v1",
        "runtime_root": str(RUNTIME_ROOT),
        "workspace_root": str(WORKSPACE_ROOT),
        "codex_home_base": str(CODEX_HOME_BASE),
        "auth_handling": {
            "allowlisted_materialized_files": ["auth.json"],
            "source_auth_record": {
                key: value
                for key, value in source_auth_record.items()
                if key != "path_recorded_without_content"
            },
            "config_toml_copied": False,
            "skills_plugins_prompts_rules_sessions_logs_copied": False,
            "auth_file_contents_committed": False,
            "secret_bearing_auth_hashes_withheld": True,
        },
        "runtime_parent_chain_check": {
            "status": "PASS",
            "checked_root": str(RUNTIME_ROOT),
            "visible_parent_skill_entries": 0,
        },
    }
    write_json_file(RUNTIME_MANIFEST_PATH, manifest)


def write_all_artifacts(
    *,
    status: str,
    plan: dict[str, Any],
    runs: list[dict[str, Any]],
    codex_evidence: dict[str, Any] | None,
    source_auth_record: dict[str, Any] | None,
    run_records: list[dict[str, Any]],
    blocker: dict[str, Any] | None,
    terminal: bool = False,
) -> None:
    completed = len(run_records)
    attempted = sum(1 for record in run_records if record.get("codex", {}).get("codex_exec_invoked") is True)
    verifier_passed = sum(1 for record in run_records if record.get("verifier", {}).get("passed") is True)
    verifier_failed = sum(1 for record in run_records if record.get("verifier", {}).get("passed") is False)
    base = {
        "schema_version": "v0.3.stage2-real-codex-12-run-execution.v1",
        "artifact_type": "stage2-real-codex-12-run-execution",
        "created_at_utc": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "artifact_timestamp": TIMESTAMP,
        "status": status,
        "blocker": blocker,
        "human_authorization": "explicit Stage 2 real Codex 12-run execution approval",
        "frozen_plan": path_ref(FROZEN_PLAN_PATH),
        "input_package": path_ref(INPUT_PACKAGE_PATH),
        "routed_predictions": path_ref(ROUTED_PREDICTIONS_PATH),
        "codex_isolated_auth_smoke_preflight": path_ref(ISOLATED_AUTH_SMOKE_PATH),
        "pilot_shape": {
            "tasks": EXPECTED_TASKS,
            "conditions": EXPECTED_CONDITIONS,
            "trials_per_task_condition": 1,
            "total_planned_runs": 12,
            "run_order_sha256": RUN_ORDER_SHA256,
            "frozen_run_ids": EXPECTED_RUN_IDS,
        },
        "summary": {
            "runs_planned": 12,
            "runs_attempted_codex_exec_invoked": attempted,
            "runs_completed_with_verifier_output": completed,
            "verifier_passed_count": verifier_passed,
            "verifier_failed_count": verifier_failed,
            "pass_fail_counts_are_verifier_output_facts_only": True,
        },
        "boundaries": {
            "stage2_pilot_run": completed == 12 and blocker is None,
            "real_codex_12_run_execution": completed == 12 and blocker is None,
            "exact_frozen_4x3x1_plan_used": True,
            "task_traces_created": completed > 0,
            "evidence_gate_rerun": False,
            "oracle_qualification_rerun": False,
            "verifier_outputs_rewritten": False,
            "routed_predictions_changed": False,
            "task_manifests_or_public_prompts_changed": False,
            "scorer_matrix_router_evidence_gate_semantics_modified": False,
            "performance_claim_made": False,
            "router_promoted": False,
            "process_exit_code_used_as_task_success": False,
            "llm_judge_used": False,
            "llm_judge_used_as_task_success": False,
            "task_success_source": "deterministic verifier output only",
            "execution_readiness": False,
            "can_be_used_as_real_stage2_input_package_now": False,
        },
        "codex_cli_evidence": codex_evidence,
        "isolated_runtime": {
            "runtime_manifest": path_ref(RUNTIME_MANIFEST_PATH) if RUNTIME_MANIFEST_PATH.exists() else None,
            "runtime_root": str(RUNTIME_ROOT),
            "workspace_root": str(WORKSPACE_ROOT),
            "codex_home_base": str(CODEX_HOME_BASE),
            "source_auth_record": None
            if source_auth_record is None
            else {
                key: value
                for key, value in source_auth_record.items()
                if key != "path_recorded_without_content"
            },
        },
        "run_records": run_records,
        "non_claims": {
            "no_performance_claim": True,
            "no_router_promotion": True,
            "no_evidence_gate_rerun": True,
            "raw_verifier_outcomes_only": True,
        },
    }
    write_json_file(EXECUTION_ARTIFACT_PATH, base)
    write_json_file(
        MATRIX_REPORT_PATH,
        {
            "schema_version": "v0.3.stage2-real-codex-12-run-matrix-report.v1",
            "status": status,
            "summary": base["summary"],
            "run_order_sha256": RUN_ORDER_SHA256,
            "runs": [
                {
                    "run_id": record["run_id"],
                    "task_id": record["task_id"],
                    "condition": record["condition"],
                    "process_exit_code": record["codex"]["process_exit_code"],
                    "process_exit_code_is_task_success": False,
                    "verifier_passed": record["verifier"]["passed"],
                    "task_success_source": "deterministic verifier output only",
                    "trace": record["trace"],
                }
                for record in run_records
            ],
            "blocker": blocker,
            "performance_claim_made": False,
            "router_promoted": False,
            "evidence_gate_rerun": False,
        },
    )
    write_json_file(
        PROGRESS_PATH,
        {
            "status": status,
            "terminal": terminal,
            "updated_at_utc": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
            "run_records": run_records,
            "blocker": blocker,
        },
    )
    write_manifest()


def record_blocker(
    *,
    status: str,
    reason: str,
    progress: dict[str, Any],
    codex_evidence: dict[str, Any] | None,
    source_auth_record: dict[str, Any] | None,
    run_records: list[dict[str, Any]],
) -> None:
    plan = read_json(FROZEN_PLAN_PATH) if FROZEN_PLAN_PATH.exists() else {}
    runs = plan.get("pilot_shape", {}).get("runs", []) if isinstance(plan, dict) else []
    write_all_artifacts(
        status=status,
        plan=plan,
        runs=runs if isinstance(runs, list) else [],
        codex_evidence=codex_evidence,
        source_auth_record=source_auth_record,
        run_records=run_records,
        blocker={
            "status": status,
            "reason": reason,
            "codex_exec_invoked": False,
        },
        terminal=True,
    )


def write_manifest() -> None:
    files = []
    for path in sorted(item for item in ARTIFACT_ROOT.rglob("*") if item.is_file()):
        if path == MANIFEST_PATH:
            continue
        files.append(
            {
                "path": rel(path),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    write_json_file(
        MANIFEST_PATH,
        {
            "schema_version": "v0.3.stage2-real-codex-12-run-manifest.v1",
            "artifact_root": rel(ARTIFACT_ROOT),
            "files": files,
        },
    )


def run_command_artifact(name: str, command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_ref = write_text_ref(COMMAND_OUTPUT_DIR / f"{name}.stdout.txt", result.stdout)
    stderr_ref = write_text_ref(COMMAND_OUTPUT_DIR / f"{name}.stderr.txt", result.stderr)
    return {
        "command_line": safe_join(command),
        "exit_code": result.returncode,
        "stdout": stdout_ref,
        "stderr": stderr_ref,
    }


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def write_json_file(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def write_text_file(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if value:
        normalized = "\n".join(line.rstrip() for line in value.splitlines()) + "\n"
    else:
        normalized = ""
    path.write_text(normalized, encoding="utf-8")


def write_text_ref(path: Path, value: str) -> dict[str, Any]:
    write_text_file(path, value)
    return path_ref(path)


def path_ref(path: Path) -> dict[str, Any]:
    return {
        "path": rel(path),
        "sha256": sha256_file(path) if path.exists() else None,
        "size_bytes": path.stat().st_size if path.exists() else None,
    }


def read_text_ref(ref: dict[str, Any]) -> str:
    path = REPO_ROOT / str(ref["path"])
    return path.read_text(encoding="utf-8")


def load_progress() -> dict[str, Any]:
    if not PROGRESS_PATH.exists():
        return {"status": "NOT_STARTED", "terminal": False, "run_records": []}
    return read_json(PROGRESS_PATH)


def safe_join(command: list[str]) -> str:
    return " ".join(shell_quote(part) for part in command)


def shell_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:=@%+,-]+", value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def rel(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def visible_child_count(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for child in path.iterdir():
        if child.name.startswith(".") and not (child.is_dir() and (child / "SKILL.md").is_file()):
            continue
        count += 1
    return count


if __name__ == "__main__":
    raise SystemExit(main())
