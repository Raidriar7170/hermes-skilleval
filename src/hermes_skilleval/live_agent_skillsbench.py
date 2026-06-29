from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from hermes_skilleval.external.skillrouter import ExternalTask, SkillRouterAdapter
from hermes_skilleval.live_agent_runtime import (
    AgentRunner,
    AgentRequest,
    AgentVerifier,
    FakeAgentRunner,
    FakeVerifier,
    LiveAgentSkill,
    _redact_value,
    build_condition,
    execute_live_agent,
    prepare_live_agent_workspace,
)
from hermes_skilleval.provenance import _reject_sensitive_values
from hermes_skilleval.release_manifest import sha256_file


PLAN_SCHEMA = "v0.3.skillsbench-live-plan.v1"
REPORT_SCHEMA = "v0.3.skillsbench-live-matrix-report.v1"
STAGE2_INPUT_PACKAGE_SCHEMA = "v0.3.stage2-real-pilot-input-package.v1"
SEED = 20260625
CONDITIONS = ("no-skill", "routed-skill", "oracle-skill")
CONTROLLED_NETWORKS = {"none", "controlled"}
DEFAULT_ROUTER_TOP_K = 3
EVIDENCE_MODES = {"fixture", "real"}
COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
LABEL_LEAKAGE_TOKENS = ("oracle", "gold", "source-task", "source_task")
VERIFIER_ARTIFACT_ROLES = ("code", "config", "input")


@dataclass(frozen=True)
class SkillsBenchTask:
    task_id: str
    prompt: str
    verifier: dict[str, Any]
    oracle_skill_ids: list[str]
    network: str
    requires_private_credentials: bool
    metadata: dict[str, Any]


class SkillsBenchAdapter:
    def __init__(
        self,
        *,
        data_root: Path | str,
        upstream_ref: str = "FILL_BEFORE_RUN",
        license_note: str = "FILL_BEFORE_RUN",
        allow_non_sha_upstream: bool = False,
        allow_fixture_ref: bool = False,
    ) -> None:
        self.data_root = Path(data_root)
        self.upstream_ref = upstream_ref
        self.license_note = license_note
        self.allow_non_sha_upstream = allow_non_sha_upstream
        self.allow_fixture_ref = allow_fixture_ref or _is_fixture_evidence(
            self.data_root,
            license_note,
        )

    def load_tasks(self) -> list[SkillsBenchTask]:
        tasks = []
        for record in _read_jsonl(self._tasks_path(), role="tasks"):
            task_id = _required_string(record, "task_id")
            prompt = _required_string(record, "prompt")
            verifier = record.get("verifier")
            if not isinstance(verifier, dict):
                raise ValueError(f"task verifier must be an object: {task_id}")
            oracle_skill_ids = _string_list(record.get("oracle_skill_ids"), "oracle_skill_ids")
            network = str(record.get("network", "none"))
            requires_private_credentials = bool(
                record.get("requires_private_credentials", False)
            )
            metadata = {
                key: value
                for key, value in record.items()
                if key
                not in {
                    "task_id",
                    "prompt",
                    "verifier",
                    "oracle_skill_ids",
                    "network",
                    "requires_private_credentials",
                }
            }
            tasks.append(
                SkillsBenchTask(
                    task_id=task_id,
                    prompt=prompt,
                    verifier=dict(verifier),
                    oracle_skill_ids=oracle_skill_ids,
                    network=network,
                    requires_private_credentials=requires_private_credentials,
                    metadata=metadata,
                )
            )
        return tasks

    def load_skills(self) -> dict[str, LiveAgentSkill]:
        skills: dict[str, LiveAgentSkill] = {}
        for record in _read_jsonl(self._skills_path(), role="skills"):
            skill_id = _required_string(record, "skill_id")
            if skill_id in skills:
                raise ValueError(f"duplicate skill id: {skill_id}")
            skills[skill_id] = LiveAgentSkill(
                skill_id=skill_id,
                name=_required_string(record, "name"),
                description=_required_string(record, "description"),
                body=_required_string(record, "body"),
            )
        return skills

    def validate(self) -> dict[str, Any]:
        errors: list[str] = []
        tasks: list[SkillsBenchTask] = []
        skills: dict[str, LiveAgentSkill] = {}
        try:
            tasks = self.load_tasks()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
        try:
            skills = self.load_skills()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))

        seen_tasks: set[str] = set()
        for task in tasks:
            if task.task_id in seen_tasks:
                errors.append(f"duplicate task id: {task.task_id}")
            seen_tasks.add(task.task_id)
            if not task.prompt.strip():
                errors.append(f"empty prompt for task: {task.task_id}")
            if task.verifier.get("type") != "deterministic":
                errors.append(f"missing deterministic verifier: {task.task_id}")
            errors.extend(
                _verifier_artifact_errors(
                    verifier=task.verifier,
                    data_root=self.data_root,
                    task_id=task.task_id,
                )
            )
            if task.requires_private_credentials:
                errors.append(f"task requires private credentials: {task.task_id}")
            if task.network not in CONTROLLED_NETWORKS:
                errors.append(f"uncontrolled network requirement: {task.task_id}")
            for skill_id in task.oracle_skill_ids:
                if skill_id not in skills:
                    errors.append(f"missing skill definition: {task.task_id} -> {skill_id}")
            errors.extend(_task_leakage_errors(task))
        errors.extend(_skill_leakage_errors(tasks, skills.values()))

        if self.upstream_ref == "FILL_BEFORE_RUN":
            errors.append("upstream_ref must be set before SkillsBench validation")
        elif not _is_allowed_upstream_ref(
            self.upstream_ref,
            self.license_note,
            allow_non_sha=self.allow_non_sha_upstream,
            allow_fixture_ref=self.allow_fixture_ref,
        ):
            errors.append("upstream_ref must be an immutable commit SHA for frozen SkillsBench evidence")
        if self.license_note == "FILL_BEFORE_RUN":
            errors.append("license_note must be set before SkillsBench validation")
        leakage_scan = {
            "schema_version": "v0.3.skillsbench-leakage-scan.v1",
            "status": "INVALID" if any("leakage" in error for error in errors) else "PASS",
            "errors": [error for error in errors if "leakage" in error],
        }
        return {
            "schema_version": "v0.3.skillsbench-validation.v1",
            "benchmark_id": "skillsbench",
            "status": "INVALID" if errors else "PASS",
            "errors": errors,
            "task_count": len(tasks),
            "skill_count": len(skills),
            "leakage_scan": leakage_scan,
        }

    def provenance(self, validation: dict[str, Any] | None = None) -> dict[str, Any]:
        files = [_file_record(path) for path in self._core_files()]
        manifest = {
            "schema_version": "v0.3.skillsbench-provenance.v1",
            "adapter": "skillsbench",
            "upstream_ref": self.upstream_ref,
            "license_note": self.license_note,
            "data_root_label": self.data_root.name,
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "files": files,
            "validation_status": (validation or self.validate())["status"],
        }
        _reject_sensitive_values(manifest)
        return manifest

    def _tasks_path(self) -> Path:
        return self.data_root / "tasks.jsonl"

    def _skills_path(self) -> Path:
        return self.data_root / "skills.jsonl"

    def _core_files(self) -> list[Path]:
        return [
            path
            for path in [
                self._tasks_path(),
                self._skills_path(),
                self.data_root / "manifest.json",
            ]
            if path.exists()
        ]


def write_skillsbench_plan(
    *,
    data_root: Path | str,
    output_path: Path | str,
    upstream_ref: str,
    license_note: str,
    run_id: str,
    mode: str,
    selected_task_ids: Iterable[str],
    routed_predictions_path: Path | str,
    oracle_qualification_path: Path | str | None = None,
    matrix_output_path: Path | str | None = None,
    workspace_root: Path | str | None = None,
    router_top_k: int = DEFAULT_ROUTER_TOP_K,
    skillrouter_data_root: Path | str | None = None,
    skillrouter_tasks_path: Path | str | None = None,
) -> dict[str, Any]:
    mode = _mode(mode)
    router_top_k = _positive_int(router_top_k, "router_top_k")
    _validate_overlap_input_choice(skillrouter_data_root, skillrouter_tasks_path)
    allow_fixture_ref = _is_fixture_evidence(data_root, license_note)
    adapter = SkillsBenchAdapter(
        data_root=data_root,
        upstream_ref=upstream_ref,
        license_note=license_note,
        allow_non_sha_upstream=mode == "pilot",
        allow_fixture_ref=allow_fixture_ref,
    )
    validation = adapter.validate()
    if validation["status"] != "PASS":
        raise ValueError("SkillsBench validation failed")
    tasks_by_id = {task.task_id: task for task in adapter.load_tasks()}
    selected_ids = list(selected_task_ids) or sorted(tasks_by_id)
    selected_tasks = [_selected_task(tasks_by_id, task_id) for task_id in selected_ids]
    skills = adapter.load_skills()
    routed_prediction_artifact = _read_routed_prediction_artifact(
        Path(routed_predictions_path)
    )
    routed_predictions = routed_prediction_artifact["predictions"]
    qualifications = (
        _read_oracle_qualification(Path(oracle_qualification_path))
        if oracle_qualification_path
        else {}
    )
    if mode == "frozen":
        missing = [task.task_id for task in selected_tasks if task.task_id not in qualifications]
        if missing:
            raise ValueError(
                "oracle qualification is required for frozen tasks: "
                + ", ".join(sorted(missing))
            )

    derived = _derive_plan_fields(
        run_id=run_id,
        selected_tasks=selected_tasks,
        data_root=Path(data_root),
        skills=skills,
        routed_predictions=routed_predictions,
        routed_prediction_artifact=routed_prediction_artifact,
        qualifications=qualifications,
        router_top_k=router_top_k,
        skillrouter_tasks=_load_skillrouter_tasks(
            data_root=Path(skillrouter_data_root) if skillrouter_data_root else None,
            tasks_path=Path(skillrouter_tasks_path) if skillrouter_tasks_path else None,
        ),
    )

    plan = {
        "schema_version": PLAN_SCHEMA,
        "benchmark_id": "skillsbench",
        "run_id": _non_empty(run_id, "run_id"),
        "mode": mode,
        "evidence_label": _evidence_label(mode, allow_fixture_ref),
        "seed": SEED,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "data_root": str(data_root),
        "selected_task_ids": selected_ids,
        "router_top_k": router_top_k,
        "adapter_provenance": adapter.provenance(validation),
        "routed_predictions": _file_record(Path(routed_predictions_path)),
        "oracle_qualification": (
            _file_record(Path(oracle_qualification_path))
            if oracle_qualification_path
            else None
        ),
        "skillrouter_overlap_input": _overlap_input_record(
            data_root=Path(skillrouter_data_root) if skillrouter_data_root else None,
            tasks_path=Path(skillrouter_tasks_path) if skillrouter_tasks_path else None,
        ),
        "validation": validation,
        "selected_tasks": derived["selected_tasks"],
        "global_skill_registry": derived["global_skill_registry"],
        "global_skill_registry_hash": derived["global_skill_registry_hash"],
        "matrix": derived["matrix"],
        "matrix_output_path": str(matrix_output_path) if matrix_output_path else None,
        "workspace_root": str(workspace_root) if workspace_root else None,
        "oracle_qualification_records": derived["oracle_qualification_records"],
        "routing_provenance": _routing_provenance(
            routed_prediction_artifact,
            router_top_k=router_top_k,
        ),
        "routed_prediction_records": derived["routed_prediction_records"],
        "routing_diagnostics": derived["routing_diagnostics"],
        "overlap_report": derived["overlap_report"],
        "leakage_scan": validation["leakage_scan"],
        "scope_guards": {
            "no_router_training": True,
            "no_threshold_tuning": True,
            "no_hard_negative_mining": True,
            "no_release_promotion": True,
            "no_phase10_changes": True,
            "no_skillrouter_scorer_changes": True,
            "no_negative_hit_rate_without_negative_labels": True,
        },
    }
    plan["derived_hashes"] = _derived_hashes(plan)
    _reject_sensitive_values(plan)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_plan_digest(output)
    return plan


def build_stage2_real_pilot_input_package(
    *,
    data_root: Path | str,
    upstream_ref: str,
    license_note: str,
    run_id: str,
    selected_task_ids: Iterable[str],
    routed_predictions_path: Path | str,
    oracle_qualification_path: Path | str,
    router_top_k: int = 1,
) -> dict[str, Any]:
    """Build a reviewable Stage 2 pilot input package without freezing a plan."""

    data_root_path = Path(data_root)
    if _fixture_path(data_root_path) or license_note == "fixture-only":
        raise ValueError("fixture-only SkillsBench data cannot be used for real input package")

    selected_ids = list(selected_task_ids)
    if len(selected_ids) != 4:
        raise ValueError("stage2 real pilot input package requires exactly 4 selected tasks")
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("stage2 real pilot input package requires unique selected tasks")

    router_top_k = _positive_int(router_top_k, "router_top_k")
    adapter = SkillsBenchAdapter(
        data_root=data_root_path,
        upstream_ref=upstream_ref,
        license_note=license_note,
        allow_non_sha_upstream=True,
    )
    validation = adapter.validate()
    if validation["status"] != "PASS":
        raise ValueError(
            "SkillsBench validation failed: " + "; ".join(validation["errors"])
        )

    tasks_by_id = {task.task_id: task for task in adapter.load_tasks()}
    selected_tasks = [_selected_task(tasks_by_id, task_id) for task_id in selected_ids]
    skills = adapter.load_skills()
    routed_prediction_artifact = _read_routed_prediction_artifact(
        Path(routed_predictions_path)
    )
    routed_predictions = routed_prediction_artifact["predictions"]
    qualifications = _read_oracle_qualification(Path(oracle_qualification_path))

    errors: list[str] = []
    errors.extend(_public_skill_text_leakage_errors(selected_tasks, skills.values()))
    errors.extend(
        _routed_prediction_input_errors(
            selected_tasks=selected_tasks,
            routed_predictions=routed_predictions,
            router=routed_prediction_artifact["router"],
            skills=skills,
            router_top_k=router_top_k,
        )
    )

    selected_task_records = [
        _stage2_input_task_record(
            task,
            data_root=data_root_path,
            license_note=license_note,
        )
        for task in selected_tasks
    ]
    selected_by_id = {task["task_id"]: task for task in selected_task_records}
    verifier_records, verifier_errors = _stage2_verifier_package_records(
        selected_task_records
    )
    errors.extend(verifier_errors)

    global_registry = {
        skill_id: _stage2_skill_registry_record(skill)
        for skill_id, skill in sorted(skills.items())
    }
    global_registry_hash = _canonical_hash(global_registry)
    oracle_records, oracle_errors = _stage2_oracle_package_records(
        selected_tasks=selected_tasks,
        selected_by_id=selected_by_id,
        skills=skills,
        qualifications=qualifications,
    )
    errors.extend(oracle_errors)
    routed_records, routed_errors = _stage2_routed_prediction_records(
        selected_tasks=selected_tasks,
        routed_prediction_artifact=routed_prediction_artifact,
        router_top_k=router_top_k,
        global_skill_registry_hash=global_registry_hash,
    )
    errors.extend(routed_errors)

    if errors:
        raise ValueError(
            "stage2 real pilot input package prerequisites failed: "
            + "; ".join(errors)
        )

    package = {
        "schema_version": STAGE2_INPUT_PACKAGE_SCHEMA,
        "status": "READY_FOR_REVIEW_NOT_EXECUTED",
        "run_id": _non_empty(run_id, "run_id"),
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "evidence_label": "pilot_non_final",
        "pilot_shape": {
            "task_count": 4,
            "conditions": list(CONDITIONS),
            "trials_per_condition": 1,
            "total_runs": 12,
        },
        "data_root_package": {
            "data_root": str(data_root_path),
            "upstream_ref": _non_empty(upstream_ref, "upstream_ref"),
            "license_note": _non_empty(license_note, "license_note"),
            "selected_task_ids": selected_ids,
            "task_count": len(selected_task_records),
            "adapter_provenance": adapter.provenance(validation),
            "selected_tasks": selected_task_records,
        },
        "deterministic_verifier_package": {
            "success_source": "deterministic_verifier_output_only",
            "process_exit_code_success_source": False,
            "llm_judge_accepted": False,
            "records": verifier_records,
        },
        "oracle_qualification_package": {
            "records": oracle_records,
        },
        "routed_predictions_package": {
            "router_id": routed_prediction_artifact["router"].get("router_id"),
            "config_hash": routed_prediction_artifact["router"].get("config_hash"),
            "top_k": router_top_k,
            "global_skill_registry_hash": global_registry_hash,
            "records": routed_records,
        },
        "global_skill_registry_package": {
            "global_skill_registry_hash": global_registry_hash,
            "skills": global_registry,
        },
        "preflight_readiness_checklist": {
            "runner": "--runner codex-cli",
            "evidence_mode": "--evidence-mode real",
            "isolated_home_required": True,
            "isolated_codex_home_required": True,
            "final_evidence_preflight_required": True,
            "clean_user_admin_workspace_skill_inventory_required": True,
            "codex_execution_allowed_in_this_branch": False,
        },
        "non_actions": {
            "stage2_pilot_run": False,
            "codex_cli_run": False,
            "pilot_plan_frozen": False,
            "live_agent_traces_created": False,
            "performance_claims": False,
        },
    }
    _reject_sensitive_values(package)
    return package


def run_skillsbench_matrix(
    *,
    plan_path: Path | str,
    output_path: Path | str,
    runner: AgentRunner | None = None,
    verifier: AgentVerifier | None = None,
    evidence_mode: str = "fixture",
) -> dict[str, Any]:
    evidence_mode = _evidence_mode(evidence_mode)
    plan_file = Path(plan_path)
    _verify_plan_digest(plan_file)
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise ValueError("unsupported SkillsBench plan schema")
    _verify_plan_inputs(plan)
    _verify_derived_fields(plan)
    if evidence_mode == "real":
        _validate_real_evidence_plan(plan)
    output = Path(output_path)
    if plan.get("matrix_output_path") and str(output) != str(plan["matrix_output_path"]):
        raise ValueError("matrix output path does not match frozen plan")
    selected_runner = _select_runner(
        runner=runner,
        evidence_mode=evidence_mode,
    )
    selected_verifier = _select_verifier(
        verifier=verifier,
        evidence_mode=evidence_mode,
    )
    tasks_by_id = {task["task_id"]: task for task in plan["selected_tasks"]}
    skills = {
        skill_id: LiveAgentSkill(
            skill_id=record["skill_id"],
            name=record["name"],
            description=record.get("description"),
            body=record["body"],
        )
        for skill_id, record in plan["global_skill_registry"].items()
    }
    workspace_root = Path(plan.get("workspace_root") or output.parent / "workspaces")
    trace_root = output.parent / "traces"
    trace_root.mkdir(parents=True, exist_ok=True)
    runs = []
    for entry in plan["matrix"]:
        task = tasks_by_id[entry["task_id"]]
        routed = (
            [skills[skill_id] for skill_id in _routed_ids(plan, entry["task_id"])]
            if entry["condition"] == "routed-skill"
            else []
        )
        oracle = (
            [skills[skill_id] for skill_id in task["oracle_skill_ids"]]
            if entry["condition"] == "oracle-skill"
            else []
        )
        condition = build_condition(
            task_id=entry["task_id"],
            prompt=task["prompt"],
            condition=entry["condition"],
            routed_skills=routed,
            oracle_skills=oracle,
        )
        workspace = prepare_live_agent_workspace(
            base_dir=workspace_root,
            run_id=entry["workspace_run_id"],
            mounted_skills=condition.mounted_skills,
        )
        request = AgentRequest.from_condition(
            run_id=entry["run_id"],
            condition=condition,
            workspace=workspace,
            timeout_seconds=1200,
            metadata={
                "benchmark": "skillsbench",
                "plan_path": str(plan_file),
                "mode": plan["mode"],
                "verifier": task["verifier"],
            },
        )
        result = execute_live_agent(
            request=request,
            runner=selected_runner,
            verifier=selected_verifier,
        )
        if evidence_mode == "real":
            _validate_real_runner_preflight(result.events)
        trace_path = trace_root / f"{entry['workspace_run_id']}.json"
        trace_path.write_text(
            json.dumps(result.to_trace(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        runs.append(
            {
                "run_id": entry["run_id"],
                "task_id": entry["task_id"],
                "condition": entry["condition"],
                "prompt_hash": entry["prompt_hash"],
                "trace_path": str(trace_path),
                "task_success": result.task_success,
                "verifier_passed": result.verifier_passed,
                "process_exit_code": result.process_exit_code,
                "timed_out": result.timed_out,
                "skill_use": result.skill_use,
                "verifier": {
                    "passed": result.verifier_passed,
                    "details": _redact_value(result.verifier_details),
                    "source": "deterministic",
                    "config": _redact_value(task["verifier"]),
                },
                "mounted_skill_ids": [
                    record["skill_id"] for record in request.mounted_skills
                ],
                "mounted_skill_count": len(request.mounted_skills),
            }
        )
    report = {
        "schema_version": REPORT_SCHEMA,
        "benchmark_id": "skillsbench",
        "run_id": plan["run_id"],
        "mode": plan["mode"],
        "evidence_mode": evidence_mode,
        "plan_path": str(plan_file),
        "skill_inventory": plan["global_skill_registry"],
        "leakage_scan": plan.get("leakage_scan"),
        "runs": runs,
        "summary": {
            "run_count": len(runs),
            "task_success_source": "verifier_pass_fail",
            "negative_hit_rate": {
                "status": "UNAVAILABLE",
                "reason": "explicit negative labels are not present",
            },
        },
        "overlap_report": plan["overlap_report"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _derive_plan_fields(
    *,
    run_id: str,
    selected_tasks: list[SkillsBenchTask],
    data_root: Path,
    skills: dict[str, LiveAgentSkill],
    routed_predictions: dict[str, list[str]],
    routed_prediction_artifact: dict[str, Any],
    qualifications: dict[str, dict[str, Any]],
    router_top_k: int,
    skillrouter_tasks: list[ExternalTask] | None,
) -> dict[str, Any]:
    registry_ids: set[str] = set()
    routing_diagnostics: dict[str, Any] = {}
    routed_top_k_by_task: dict[str, list[str]] = {}
    for task in selected_tasks:
        registry_ids.update(task.oracle_skill_ids)
        routed_ids = routed_predictions.get(task.task_id, [])
        if not routed_ids:
            raise ValueError(f"missing routed predictions for task: {task.task_id}")
        deduped = _dedupe(routed_ids)
        routed_top_k = deduped[:router_top_k]
        if not routed_top_k:
            raise ValueError(f"empty routed top-k for task: {task.task_id}")
        registry_ids.update(deduped)
        routed_top_k_by_task[task.task_id] = routed_top_k
        routing_diagnostics[task.task_id] = {
            "full_prediction_count": len(routed_ids),
            "deduped_prediction_count": len(deduped),
            "router_top_k": router_top_k,
            "mounted_top_k": routed_top_k,
        }
    missing_skills = sorted(skill_id for skill_id in registry_ids if skill_id not in skills)
    if missing_skills:
        raise ValueError("missing skill definition: " + ", ".join(missing_skills))

    registry = {
        skill_id: _skill_to_plan(skills[skill_id])
        for skill_id in sorted(registry_ids)
    }
    registry_hash = _canonical_hash(registry)
    routed_prediction_records = _routed_prediction_records(
        selected_tasks=selected_tasks,
        routed_predictions=routed_predictions,
        routed_prediction_artifact=routed_prediction_artifact,
        router_top_k=router_top_k,
        global_skill_registry_hash=registry_hash,
    )
    matrix = []
    for task in selected_tasks:
        condition_hashes = []
        for condition_name in CONDITIONS:
            routed_for_condition = (
                [skills[skill_id] for skill_id in routed_top_k_by_task[task.task_id]]
                if condition_name == "routed-skill"
                else []
            )
            oracle_for_condition = (
                [skills[skill_id] for skill_id in task.oracle_skill_ids]
                if condition_name == "oracle-skill"
                else []
            )
            condition = build_condition(
                task_id=task.task_id,
                prompt=task.prompt,
                condition=condition_name,
                routed_skills=routed_for_condition,
                oracle_skills=oracle_for_condition,
            )
            condition_hashes.append(condition.prompt_hash)
            matrix.append(
                {
                    "run_id": f"{run_id}__{task.task_id}__{condition_name}",
                    "task_id": task.task_id,
                    "condition": condition_name,
                    "prompt_hash": condition.prompt_hash,
                    "workspace_run_id": _safe_run_id(
                        f"{run_id}__{task.task_id}__{condition_name}"
                    ),
                    "mounted_skill_ids": [
                        skill.skill_id for skill in condition.mounted_skills
                    ],
                }
            )
        if len(set(condition_hashes)) != 1:
            raise ValueError(f"prompt hash mismatch for task: {task.task_id}")

    return {
        "selected_tasks": [
            _task_to_plan(task, data_root=data_root) for task in selected_tasks
        ],
        "global_skill_registry": registry,
        "global_skill_registry_hash": registry_hash,
        "matrix": matrix,
        "oracle_qualification_records": qualifications,
        "routed_prediction_records": routed_prediction_records,
        "routing_diagnostics": routing_diagnostics,
        "overlap_report": _overlap_report(selected_tasks, skillrouter_tasks),
    }


def _verify_derived_fields(plan: dict[str, Any]) -> None:
    stored_hashes = plan.get("derived_hashes")
    if not isinstance(stored_hashes, dict):
        raise ValueError("missing derived field hashes")
    current_hashes = _derived_hashes(plan)
    if stored_hashes != current_hashes:
        changed = sorted(
            key for key, value in current_hashes.items() if stored_hashes.get(key) != value
        )
        raise ValueError("derived field changed: " + ", ".join(changed))

    adapter = SkillsBenchAdapter(
        data_root=plan["data_root"],
        upstream_ref=plan.get("adapter_provenance", {}).get("upstream_ref", ""),
        license_note=plan.get("adapter_provenance", {}).get("license_note", ""),
        allow_non_sha_upstream=plan.get("mode") == "pilot",
        allow_fixture_ref=plan.get("evidence_label") == "fixture-only",
    )
    tasks_by_id = {task.task_id: task for task in adapter.load_tasks()}
    selected_ids = plan.get("selected_task_ids") or [
        task["task_id"] for task in plan["selected_tasks"]
    ]
    selected_tasks = [_selected_task(tasks_by_id, task_id) for task_id in selected_ids]
    expected = _derive_plan_fields(
        run_id=plan["run_id"],
        selected_tasks=selected_tasks,
        data_root=Path(plan["data_root"]),
        skills=adapter.load_skills(),
        routed_predictions=_read_predictions(Path(plan["routed_predictions"]["path"])),
        routed_prediction_artifact=_read_routed_prediction_artifact(
            Path(plan["routed_predictions"]["path"])
        ),
        qualifications=(
            _read_oracle_qualification(Path(plan["oracle_qualification"]["path"]))
            if plan.get("oracle_qualification")
            else {}
        ),
        router_top_k=int(plan.get("router_top_k", DEFAULT_ROUTER_TOP_K)),
        skillrouter_tasks=_load_skillrouter_tasks_from_record(
            plan.get("skillrouter_overlap_input")
        ),
    )
    for key in (
        "selected_tasks",
        "global_skill_registry",
        "global_skill_registry_hash",
        "matrix",
        "oracle_qualification_records",
        "routed_prediction_records",
        "routing_diagnostics",
        "overlap_report",
    ):
        if _canonical_hash(plan.get(key)) != _canonical_hash(expected[key]):
            raise ValueError(f"derived field changed: {key}")


def _read_jsonl(path: Path, *, role: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"missing {role} file: {path.name}")
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"{role} record must be an object at line {line_number}")
        records.append(record)
    return records


def _read_predictions(path: Path) -> dict[str, list[str]]:
    return _read_routed_prediction_artifact(path)["predictions"]


def _read_routed_prediction_artifact(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("routed predictions must be an object")
    if isinstance(data.get("predictions"), dict):
        predictions = data["predictions"]
        router = data.get("router")
    else:
        predictions = data
        router = {
            "status": "UNAVAILABLE",
            "reason": "legacy routed prediction map has no router metadata",
        }
    if not isinstance(router, dict):
        raise ValueError("routed predictions router metadata must be an object")
    return {
        "path": str(path),
        "router": router,
        "predictions": {
            str(task_id): _string_list(value, "routed prediction")
            for task_id, value in predictions.items()
        },
    }


def _read_oracle_qualification(path: Path) -> dict[str, dict[str, Any]]:
    records = {}
    for record in _read_jsonl(path, role="oracle qualification"):
        task_id = _required_string(record, "task_id")
        if record.get("condition") != "oracle-skill" or record.get("verifier_passed") is not True:
            raise ValueError(f"oracle qualification failed for task: {task_id}")
        records[task_id] = record
    return records


def _verify_plan_inputs(plan: dict[str, Any]) -> None:
    records = [*plan["adapter_provenance"]["files"], plan["routed_predictions"]]
    if plan.get("oracle_qualification"):
        records.append(plan["oracle_qualification"])
    overlap_input = plan.get("skillrouter_overlap_input")
    if isinstance(overlap_input, dict):
        records.extend(overlap_input.get("files", []))
    for record in records:
        path = Path(record["path"])
        if not path.exists():
            raise ValueError(f"frozen input missing: {path}")
        if path.stat().st_size != int(record["size_bytes"]) or sha256_file(path) != record["sha256"]:
            raise ValueError(f"frozen input changed: {path}")


def _write_plan_digest(path: Path) -> None:
    digest = sha256_file(path)
    path.with_name(f"{path.name}.sha256").write_text(
        f"{digest}  {path.name}\n",
        encoding="utf-8",
    )


def _verify_plan_digest(path: Path) -> None:
    digest_path = path.with_name(f"{path.name}.sha256")
    if not digest_path.exists():
        raise ValueError(f"missing plan digest sidecar: {digest_path.name}")
    first = digest_path.read_text(encoding="utf-8").strip().split()
    if not first:
        raise ValueError(f"malformed plan digest sidecar: {digest_path.name}")
    if sha256_file(path) != first[0]:
        raise ValueError("plan digest changed")


def _file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _overlap_input_record(
    *,
    data_root: Path | None,
    tasks_path: Path | None,
) -> dict[str, Any]:
    if data_root is None and tasks_path is None:
        return {
            "status": "UNAVAILABLE",
            "reason": "SkillRouter external task input was not provided",
            "files": [],
        }
    if tasks_path is not None:
        return {
            "status": "PASS",
            "kind": "tasks_path",
            "path": str(tasks_path),
            "files": [_file_record(tasks_path)],
        }
    assert data_root is not None
    adapter = SkillRouterAdapter(data_root=data_root)
    task_path = adapter._tasks_path()
    return {
        "status": "PASS",
        "kind": "data_root",
        "path": str(data_root),
        "files": [_file_record(task_path)],
    }


def _selected_task(tasks_by_id: dict[str, SkillsBenchTask], task_id: str) -> SkillsBenchTask:
    if task_id not in tasks_by_id:
        raise ValueError(f"selected task does not exist: {task_id}")
    return tasks_by_id[task_id]


def _task_to_plan(task: SkillsBenchTask, *, data_root: Path) -> dict[str, Any]:
    base = {
        "task_id": task.task_id,
        "prompt": task.prompt,
        "verifier": task.verifier,
        "oracle_skill_ids": task.oracle_skill_ids,
        "network": task.network,
        "requires_private_credentials": task.requires_private_credentials,
        "metadata": task.metadata,
    }
    return {
        **base,
        "prompt_hash": _sha256_text(task.prompt),
        "task_hash": _canonical_hash(base),
        "verifier_hash": _canonical_hash(task.verifier),
        "verifier_artifacts": _verifier_artifact_records(
            verifier=task.verifier,
            data_root=data_root,
        ),
    }


def _skill_to_plan(skill: LiveAgentSkill) -> dict[str, Any]:
    return {
        "skill_id": skill.skill_id,
        "name": skill.name,
        "description": skill.description or "",
        "body": skill.body,
    }


def _routing_provenance(
    routed_prediction_artifact: dict[str, Any],
    *,
    router_top_k: int,
) -> dict[str, Any]:
    predictions = routed_prediction_artifact["predictions"]
    return {
        "schema_version": "v0.3.skillsbench-routing-provenance.v1",
        "router": routed_prediction_artifact["router"],
        "router_top_k": router_top_k,
        "predictions_hash": _canonical_hash(predictions),
    }


def _routed_prediction_records(
    *,
    selected_tasks: list[SkillsBenchTask],
    routed_predictions: dict[str, list[str]],
    routed_prediction_artifact: dict[str, Any],
    router_top_k: int,
    global_skill_registry_hash: str,
) -> dict[str, Any]:
    router = routed_prediction_artifact["router"]
    router_id = router.get("router_id", "UNAVAILABLE")
    router_config_hash = router.get("config_hash") or _canonical_hash(
        router.get("config", {})
    )
    records = {}
    for task in selected_tasks:
        full_prediction = routed_predictions[task.task_id]
        deduped = _dedupe(full_prediction)
        records[task.task_id] = {
            "task_id": task.task_id,
            "router_id": router_id,
            "router_config_hash": router_config_hash,
            "router_top_k": router_top_k,
            "global_skill_registry_hash": global_skill_registry_hash,
            "full_prediction_count": len(full_prediction),
            "deduped_prediction_count": len(deduped),
            "mounted_top_k": deduped[:router_top_k],
            "prediction_hash": _canonical_hash(full_prediction),
        }
    return records


def _verifier_artifact_records(
    *,
    verifier: dict[str, Any],
    data_root: Path,
) -> dict[str, dict[str, Any]]:
    artifacts = verifier.get("artifacts")
    artifacts = artifacts if isinstance(artifacts, dict) else {}
    records = {}
    for role in VERIFIER_ARTIFACT_ROLES:
        value = artifacts.get(role) or verifier.get(f"{role}_path")
        if not value:
            continue
        path = Path(str(value))
        if not path.is_absolute():
            path = data_root / path
        records[role] = _file_record(path)
    return records


def _verifier_artifact_errors(
    *,
    verifier: dict[str, Any],
    data_root: Path,
    task_id: str,
) -> list[str]:
    artifacts = verifier.get("artifacts")
    artifacts = artifacts if isinstance(artifacts, dict) else {}
    errors = []
    for role in VERIFIER_ARTIFACT_ROLES:
        value = artifacts.get(role) or verifier.get(f"{role}_path")
        if not value:
            continue
        path = Path(str(value))
        if not path.is_absolute():
            path = data_root / path
        if not path.exists():
            errors.append(f"missing verifier {role} artifact for task: {task_id}")
    return errors


def _select_runner(
    *,
    runner: AgentRunner | None,
    evidence_mode: str,
) -> AgentRunner:
    if runner is None:
        if evidence_mode == "real":
            raise ValueError(
                "real evidence mode requires explicit AgentRunner; "
                "FakeAgentRunner is fixture-only"
            )
        return FakeAgentRunner(
            exit_code=0,
            events=[{"type": "final", "message": "fixture matrix run"}],
        )
    if evidence_mode == "real" and isinstance(runner, FakeAgentRunner):
        raise ValueError("FakeAgentRunner cannot be used in real evidence mode")
    return runner


def _select_verifier(
    *,
    verifier: AgentVerifier | None,
    evidence_mode: str,
) -> AgentVerifier:
    if verifier is None:
        if evidence_mode == "real":
            raise ValueError(
                "real evidence mode requires explicit deterministic verifier; "
                "FakeVerifier is fixture-only"
            )
        return FakeVerifier(pass_=True, details={"mode": "fixture"})
    if evidence_mode == "real" and isinstance(verifier, FakeVerifier):
        raise ValueError("FakeVerifier cannot be used in real evidence mode")
    return verifier


def _stage2_input_task_record(
    task: SkillsBenchTask,
    *,
    data_root: Path,
    license_note: str,
) -> dict[str, Any]:
    record = _task_to_plan(task, data_root=data_root)
    source_or_provenance = task.metadata.get("source") or task.metadata.get("provenance")
    return {
        **record,
        "source_or_provenance": source_or_provenance,
        "license_note": license_note,
        "public_prompt_leakage_guard": "PASS",
    }


def _stage2_verifier_package_records(
    selected_task_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    records: dict[str, Any] = {}
    errors: list[str] = []
    for task in selected_task_records:
        task_id = str(task["task_id"])
        verifier = task.get("verifier")
        artifacts = task.get("verifier_artifacts")
        if not isinstance(verifier, dict):
            errors.append(f"missing deterministic verifier: {task_id}")
            continue
        if verifier.get("type") != "deterministic":
            errors.append(f"missing deterministic verifier: {task_id}")
        if not isinstance(artifacts, dict) or set(artifacts) != set(
            VERIFIER_ARTIFACT_ROLES
        ):
            errors.append(f"missing verifier code/config/input hashes: {task_id}")
            continue
        for field in (
            "expected_output_format",
            "constraints",
            "deterministic_assumptions",
        ):
            if not verifier.get(field):
                errors.append(f"missing verifier {field}: {task_id}")
        if verifier.get("success_source") == "process_exit_code":
            errors.append(f"process exit code cannot be task success source: {task_id}")
        if verifier.get("judge") == "llm" or verifier.get("llm_judge") is True:
            errors.append(f"LLM judge cannot be task success source: {task_id}")
        records[task_id] = {
            "task_id": task_id,
            "verifier_hash": task.get("verifier_hash"),
            "code_hash": artifacts["code"]["sha256"],
            "config_hash": artifacts["config"]["sha256"],
            "input_hash": artifacts["input"]["sha256"],
            "artifacts": artifacts,
            "expected_output_format": verifier.get("expected_output_format"),
            "constraints": verifier.get("constraints"),
            "deterministic_assumptions": verifier.get("deterministic_assumptions"),
        }
    return records, errors


def _stage2_skill_registry_record(skill: LiveAgentSkill) -> dict[str, Any]:
    body = skill.body
    description = skill.description or ""
    return {
        "skill_id": skill.skill_id,
        "name": skill.name,
        "description": description,
        "body": body,
        "skill_hash": _canonical_hash(_skill_to_plan(skill)),
        "name_hash": _sha256_text(skill.name),
        "description_hash": _sha256_text(description),
        "body_hash": _sha256_text(body),
        "public_skill_text_leakage_guard": "PASS",
    }


def _stage2_oracle_package_records(
    *,
    selected_tasks: list[SkillsBenchTask],
    selected_by_id: dict[str, dict[str, Any]],
    skills: dict[str, LiveAgentSkill],
    qualifications: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    records: dict[str, Any] = {}
    errors: list[str] = []
    for task in selected_tasks:
        task_record = selected_by_id[task.task_id]
        record = qualifications.get(task.task_id)
        if not isinstance(record, dict):
            errors.append(f"missing oracle qualification: {task.task_id}")
            continue
        expected_skill_hash = _oracle_skill_hash(task, skills)
        if record.get("verifier_passed") is not True:
            errors.append(f"oracle qualification did not pass: {task.task_id}")
        if record.get("task_hash") != task_record.get("task_hash"):
            errors.append(f"oracle qualification task hash mismatch: {task.task_id}")
        if record.get("verifier_hash") != task_record.get("verifier_hash"):
            errors.append(f"oracle qualification verifier hash mismatch: {task.task_id}")
        if record.get("skill_hash") != expected_skill_hash:
            errors.append(f"oracle qualification skill hash mismatch: {task.task_id}")
        if int(record.get("trials", 0)) < 1:
            errors.append(f"missing oracle qualification trials: {task.task_id}")
        if float(record.get("pass_rate", 0.0)) < 1.0:
            errors.append(f"oracle qualification pass rate below 1.0: {task.task_id}")
        if not record.get("constraints"):
            errors.append(f"missing oracle qualification constraints: {task.task_id}")
        if not record.get("qualification_command"):
            errors.append(f"missing oracle qualification command: {task.task_id}")
        if not record.get("output_hash"):
            errors.append(f"missing oracle qualification output hash: {task.task_id}")
        records[task.task_id] = {
            **record,
            "expected_skill_hash": expected_skill_hash,
        }
    return records, errors


def _stage2_routed_prediction_records(
    *,
    selected_tasks: list[SkillsBenchTask],
    routed_prediction_artifact: dict[str, Any],
    router_top_k: int,
    global_skill_registry_hash: str,
) -> tuple[dict[str, Any], list[str]]:
    router = routed_prediction_artifact["router"]
    routed_predictions = routed_prediction_artifact["predictions"]
    records: dict[str, Any] = {}
    errors: list[str] = []
    if not router.get("router_id"):
        errors.append("missing router_id for routed predictions")
    if not router.get("config_hash"):
        errors.append("missing router config_hash for routed predictions")
    if int(router.get("top_k", 0)) != router_top_k:
        errors.append("routed prediction router top_k does not match package")
    for task in selected_tasks:
        full_prediction = routed_predictions.get(task.task_id)
        if not full_prediction:
            errors.append(f"missing routed predictions for task: {task.task_id}")
            continue
        predicted = _dedupe(full_prediction)
        records[task.task_id] = {
            "task_id": task.task_id,
            "router_id": router.get("router_id"),
            "config_hash": router.get("config_hash"),
            "top_k": router_top_k,
            "global_skill_registry_hash": global_skill_registry_hash,
            "predicted_skill_ids": predicted,
            "mounted_top_k": predicted[:router_top_k],
            "prediction_hash": _canonical_hash(full_prediction),
        }
    return records, errors


def _routed_prediction_input_errors(
    *,
    selected_tasks: list[SkillsBenchTask],
    routed_predictions: dict[str, list[str]],
    router: dict[str, Any],
    skills: dict[str, LiveAgentSkill],
    router_top_k: int,
) -> list[str]:
    errors: list[str] = []
    if not router.get("router_id"):
        errors.append("missing router_id for routed predictions")
    if not router.get("config_hash"):
        errors.append("missing router config_hash for routed predictions")
    if int(router.get("top_k", 0)) != router_top_k:
        errors.append("routed prediction router top_k does not match package")
    for task in selected_tasks:
        predictions = routed_predictions.get(task.task_id)
        if not predictions:
            errors.append(f"missing routed predictions for task: {task.task_id}")
            continue
        for skill_id in _dedupe(predictions):
            if skill_id not in skills:
                errors.append(
                    f"unknown routed prediction skill id: {task.task_id} -> {skill_id}"
                )
    return errors


def _oracle_skill_hash(
    task: SkillsBenchTask,
    skills: dict[str, LiveAgentSkill],
) -> str:
    skill_records = [_skill_to_plan(skills[skill_id]) for skill_id in task.oracle_skill_ids]
    if len(skill_records) == 1:
        return _canonical_hash(skill_records[0])
    return _canonical_hash(skill_records)


def _validate_real_evidence_plan(plan: dict[str, Any]) -> None:
    if plan.get("evidence_label") == "fixture-only" or _fixture_path(plan.get("data_root")):
        raise ValueError("fixture-only SkillsBench data cannot be used in real evidence mode")

    selected_tasks = plan.get("selected_tasks")
    matrix = plan.get("matrix")
    if not isinstance(selected_tasks, list) or not isinstance(matrix, list):
        raise ValueError("real evidence mode requires selected tasks and matrix entries")

    errors: list[str] = []
    if plan.get("mode") == "pilot":
        if len(selected_tasks) != 4:
            errors.append("pilot real evidence mode requires exactly 4 selected tasks")
        if len(matrix) != 12:
            errors.append("pilot real evidence mode requires exactly 12 matrix runs")
        expected_conditions = set(CONDITIONS)
        for task in selected_tasks:
            task_conditions = {
                entry.get("condition")
                for entry in matrix
                if entry.get("task_id") == task.get("task_id")
            }
            if task_conditions != expected_conditions:
                errors.append(
                    f"pilot task does not have all three conditions: {task.get('task_id')}"
                )

    tasks_by_id = {
        str(task.get("task_id")): task for task in selected_tasks if isinstance(task, dict)
    }
    for task_id, task in tasks_by_id.items():
        metadata = task.get("metadata")
        if not isinstance(metadata, dict) or not (
            metadata.get("source") or metadata.get("provenance")
        ):
            errors.append(f"missing task source/provenance: {task_id}")
        for field in ("prompt_hash", "task_hash", "verifier_hash"):
            if not isinstance(task.get(field), str) or not task[field]:
                errors.append(f"missing {field}: {task_id}")
        artifacts = task.get("verifier_artifacts")
        if not isinstance(artifacts, dict) or set(artifacts) != set(
            VERIFIER_ARTIFACT_ROLES
        ):
            errors.append(f"missing verifier code/config/input hashes: {task_id}")

    qualifications = plan.get("oracle_qualification_records")
    if not isinstance(qualifications, dict):
        errors.append("missing oracle qualification records")
        qualifications = {}
    for task_id, task in tasks_by_id.items():
        record = qualifications.get(task_id)
        if not isinstance(record, dict):
            errors.append(f"missing oracle qualification: {task_id}")
            continue
        if record.get("verifier_passed") is not True:
            errors.append(f"oracle qualification did not pass: {task_id}")
        if record.get("task_hash") != task.get("task_hash"):
            errors.append(f"oracle qualification task hash mismatch: {task_id}")
        if record.get("verifier_hash") != task.get("verifier_hash"):
            errors.append(f"oracle qualification verifier hash mismatch: {task_id}")
        if not isinstance(record.get("skill_hash"), str) or not record["skill_hash"]:
            errors.append(f"missing oracle qualification skill hash: {task_id}")
        if int(record.get("trials", 0)) < 1:
            errors.append(f"missing oracle qualification trials: {task_id}")
        if float(record.get("pass_rate", 0.0)) < 1.0:
            errors.append(f"oracle qualification pass rate below 1.0: {task_id}")
        if not record.get("constraints"):
            errors.append(f"missing oracle qualification constraints: {task_id}")

    routing = plan.get("routing_provenance")
    router = routing.get("router") if isinstance(routing, dict) else None
    if not isinstance(router, dict) or router.get("status") == "UNAVAILABLE":
        errors.append("missing routed prediction router metadata")
    else:
        if not router.get("router_id"):
            errors.append("missing router_id for routed predictions")
        if not router.get("config_hash"):
            errors.append("missing router config_hash for routed predictions")
        if int(router.get("top_k", 0)) != int(plan.get("router_top_k", 0)):
            errors.append("routed prediction router top_k does not match plan")

    registry_hash = plan.get("global_skill_registry_hash")
    if registry_hash != _canonical_hash(plan.get("global_skill_registry")):
        errors.append("global skill registry hash mismatch")
    routed_records = plan.get("routed_prediction_records")
    if not isinstance(routed_records, dict):
        errors.append("missing routed prediction records")
        routed_records = {}
    for task_id in tasks_by_id:
        record = routed_records.get(task_id)
        if not isinstance(record, dict):
            errors.append(f"missing routed prediction record: {task_id}")
            continue
        if record.get("global_skill_registry_hash") != registry_hash:
            errors.append(f"routed prediction registry hash mismatch: {task_id}")
        if not record.get("prediction_hash"):
            errors.append(f"missing routed prediction hash: {task_id}")
        if not record.get("router_id") or record.get("router_id") == "UNAVAILABLE":
            errors.append(f"missing routed prediction router id: {task_id}")

    if errors:
        raise ValueError("real evidence mode prerequisites failed: " + "; ".join(errors))


def _validate_real_runner_preflight(events: list[dict[str, Any]]) -> None:
    preflight = next(
        (
            event
            for event in events
            if isinstance(event, dict) and event.get("type") == "preflight"
        ),
        None,
    )
    if preflight is None:
        raise ValueError("missing real runner preflight")
    if preflight.get("evidence_mode") != "final-evidence":
        raise ValueError("real runner preflight is not final-evidence mode")
    if preflight.get("codex_home_mode") != "isolated":
        raise ValueError("real runner preflight did not use isolated CODEX_HOME")
    inventory = preflight.get("global_capability_inventory")
    if not isinstance(inventory, dict):
        raise ValueError("real runner preflight missing global_capability_inventory")
    if inventory.get("home_isolated") is not True:
        raise ValueError("real runner preflight did not prove home_isolated")

    user_skill_dir = inventory.get("user_skill_dir")
    if (
        not isinstance(user_skill_dir, dict)
        or user_skill_dir.get("status") != "ISOLATED_HOME"
        or user_skill_dir.get("entry_count") != 0
    ):
        raise ValueError("real runner preflight user_skill_dir is not isolated")

    admin_skill_dirs = inventory.get("admin_skill_dirs")
    if not isinstance(admin_skill_dirs, list):
        raise ValueError("real runner preflight admin_skill_dirs malformed")
    for record in admin_skill_dirs:
        if (
            not isinstance(record, dict)
            or record.get("status") not in {"CLEAR", "ABSENT"}
            or record.get("entry_count") != 0
        ):
            raise ValueError("real runner preflight admin_skill_dirs leaked")

    workspace_skill_dirs = inventory.get("workspace_skill_dirs")
    if not isinstance(workspace_skill_dirs, dict):
        raise ValueError("real runner preflight workspace_skill_dirs malformed")
    parent_checked = workspace_skill_dirs.get("parent_skill_dirs_checked")
    empty_parent = workspace_skill_dirs.get("empty_parent_skill_dirs")
    mounted_entries = workspace_skill_dirs.get("mounted_entry_count")
    if (
        workspace_skill_dirs.get("workspace_status") not in {"CLEAR", "ABSENT"}
        or not _nonnegative_int(parent_checked)
        or not _nonnegative_int(empty_parent)
        or not _nonnegative_int(mounted_entries)
        or empty_parent > parent_checked
    ):
        raise ValueError("real runner preflight workspace_skill_dirs leaked")


def _routed_ids(plan: dict[str, Any], task_id: str) -> list[str]:
    predictions = json.loads(Path(plan["routed_predictions"]["path"]).read_text(encoding="utf-8"))
    if isinstance(predictions, dict) and isinstance(predictions.get("predictions"), dict):
        predictions = predictions["predictions"]
    return _dedupe([str(skill_id) for skill_id in predictions[task_id]])[
        : int(plan.get("router_top_k", DEFAULT_ROUTER_TOP_K))
    ]


def _overlap_report(
    tasks: list[SkillsBenchTask],
    skillrouter_tasks: list[ExternalTask] | None,
) -> dict[str, Any]:
    declared_links = sorted(
        {
            str(task.metadata["skillrouter_task_id"])
            for task in tasks
            if task.metadata.get("skillrouter_task_id")
        }
    )
    if skillrouter_tasks is None:
        return {
            "schema_version": "v0.3.skillrouter-skillsbench-overlap.v1",
            "decision": "UNAVAILABLE",
            "independent_generalization_claim": False,
            "reason": "SkillRouter external task input was not provided",
            "skillrouter_task_count": {
                "status": "UNAVAILABLE",
                "reason": "SkillRouter external task input was not provided",
            },
            "skillsbench_task_count": len(tasks),
            "declared_metadata_links": declared_links,
            "exact_id_overlap": [],
            "normalized_text_hash_overlap": [],
            "high_similarity_diagnostics": {
                "status": "UNAVAILABLE",
                "reason": "high-similarity diagnostics not selected in PR-6",
            },
        }
    skillrouter_by_id = {task.task_id: task for task in skillrouter_tasks}
    skillsbench_by_id = {task.task_id: task for task in tasks}
    sr_hashes: dict[str, list[str]] = {}
    for task in skillrouter_tasks:
        sr_hashes.setdefault(_normalized_hash(task.query), []).append(task.task_id)
    sb_hashes: dict[str, list[str]] = {}
    for task in tasks:
        sb_hashes.setdefault(_normalized_hash(task.prompt), []).append(task.task_id)
    exact_overlap = sorted(set(skillrouter_by_id) & set(skillsbench_by_id))
    text_overlap_records = [
        {
            "hash": value,
            "skillrouter_task_ids": sorted(sr_hashes[value]),
            "skillsbench_task_ids": sorted(sb_hashes[value]),
        }
        for value in sorted(set(sr_hashes) & set(sb_hashes))
    ]
    invalid_links = sorted(link for link in declared_links if link not in skillrouter_by_id)
    if invalid_links:
        decision = "INVALID"
        independent = False
        reason = "declared SkillRouter metadata links do not exist in SkillRouter input"
    elif declared_links or exact_overlap or text_overlap_records:
        decision = "LINKED_TRANSFER"
        independent = False
        reason = "SkillRouter links or overlaps were found"
    else:
        decision = "DISJOINT"
        independent = True
        reason = "no exact ID, normalized text hash, or declared metadata overlap found"
    return {
        "schema_version": "v0.3.skillrouter-skillsbench-overlap.v1",
        "decision": decision,
        "independent_generalization_claim": independent,
        "reason": reason,
        "skillrouter_task_count": len(skillrouter_tasks),
        "skillsbench_task_count": len(tasks),
        "declared_metadata_links": declared_links,
        "invalid_declared_metadata_links": invalid_links,
        "exact_id_overlap": exact_overlap,
        "normalized_text_hash_overlap": [record["hash"] for record in text_overlap_records],
        "normalized_text_hash_overlap_records": text_overlap_records,
        "high_similarity_diagnostics": {
            "status": "UNAVAILABLE",
            "reason": "high-similarity diagnostics not selected in PR-6",
        },
    }


def _load_skillrouter_tasks(
    *,
    data_root: Path | None,
    tasks_path: Path | None,
) -> list[ExternalTask] | None:
    if data_root is None and tasks_path is None:
        return None
    if data_root is not None:
        return SkillRouterAdapter(data_root=data_root).load_tasks()
    assert tasks_path is not None
    return [
        ExternalTask(
            benchmark_id="skillrouter",
            task_id=_required_string(record, "task_id"),
            query=_skillrouter_query_text(record),
            task_type=str(record.get("task_type", "unknown")),
            graded_relevance={},
            tier=str(record.get("tier", "unknown")),
            metadata={},
        )
        for record in _read_task_records(tasks_path)
    ]


def _load_skillrouter_tasks_from_record(record: Any) -> list[ExternalTask] | None:
    if not isinstance(record, dict) or record.get("status") == "UNAVAILABLE":
        return None
    if record.get("kind") == "data_root":
        return _load_skillrouter_tasks(data_root=Path(record["path"]), tasks_path=None)
    if record.get("kind") == "tasks_path":
        return _load_skillrouter_tasks(data_root=None, tasks_path=Path(record["path"]))
    raise ValueError("unsupported SkillRouter overlap input")


def _read_task_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        return _read_jsonl(path, role="SkillRouter tasks")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = payload.get("records") or payload.get("tasks")
    else:
        records = None
    if not isinstance(records, list):
        raise ValueError("SkillRouter tasks file must contain task records")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("SkillRouter task records must be objects")
    return records


def _skillrouter_query_text(record: dict[str, Any]) -> str:
    for field in ("instruction_text", "query", "prompt", "instruction"):
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value
    raise ValueError("SkillRouter task query must be a non-empty string")


def _validate_overlap_input_choice(
    skillrouter_data_root: Path | str | None,
    skillrouter_tasks_path: Path | str | None,
) -> None:
    if skillrouter_data_root and skillrouter_tasks_path:
        raise ValueError("--skillrouter-data-root and --skillrouter-tasks are mutually exclusive")


def _is_fixture_evidence(data_root: Path | str, license_note: str) -> bool:
    path = Path(data_root)
    return license_note == "fixture-only" and _fixture_path(path)


def _fixture_path(path_value: Any) -> bool:
    try:
        parts = Path(str(path_value)).parts
    except TypeError:
        return False
    return "tests" in parts and "fixtures" in parts


def _evidence_label(mode: str, allow_fixture_ref: bool) -> str:
    if allow_fixture_ref:
        return "fixture-only"
    if mode == "pilot":
        return "pilot_non_final"
    return "frozen-final"


def _derived_hashes(plan: dict[str, Any]) -> dict[str, str]:
    selected_tasks = plan.get("selected_tasks", [])
    prompt_verifier = [
        {
            "task_id": task.get("task_id"),
            "prompt": task.get("prompt"),
            "verifier": task.get("verifier"),
        }
        for task in selected_tasks
        if isinstance(task, dict)
    ]
    return {
        "selected_tasks": _canonical_hash(plan.get("selected_tasks")),
        "global_skill_registry": _canonical_hash(plan.get("global_skill_registry")),
        "global_skill_registry_hash": _canonical_hash(
            plan.get("global_skill_registry_hash")
        ),
        "matrix": _canonical_hash(plan.get("matrix")),
        "oracle_qualification_records": _canonical_hash(
            plan.get("oracle_qualification_records")
        ),
        "routed_prediction_records": _canonical_hash(
            plan.get("routed_prediction_records")
        ),
        "task_prompt_verifier": _canonical_hash(prompt_verifier),
        "routing_diagnostics": _canonical_hash(plan.get("routing_diagnostics")),
        "overlap_report": _canonical_hash(plan.get("overlap_report")),
    }


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output = []
    for value in values:
        item = str(value)
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def _normalized_hash(value: str) -> str:
    text = " ".join(str(value).lower().split())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _task_leakage_errors(task: SkillsBenchTask) -> list[str]:
    prompt = task.prompt.lower()
    errors = []
    if task.task_id.lower() in prompt:
        errors.append(f"leakage in prompt for task {task.task_id}: task_id")
    for skill_id in task.oracle_skill_ids:
        if skill_id.lower() in prompt:
            errors.append(f"leakage in prompt for task {task.task_id}: oracle skill id")
    for token in LABEL_LEAKAGE_TOKENS:
        if token in prompt:
            errors.append(f"leakage in prompt for task {task.task_id}: {token}")
    return errors


def _skill_leakage_errors(
    tasks: list[SkillsBenchTask],
    skills: Iterable[LiveAgentSkill],
) -> list[str]:
    task_ids = {task.task_id.lower() for task in tasks}
    oracle_skill_ids = {
        skill_id.lower() for task in tasks for skill_id in task.oracle_skill_ids
    }
    errors = []
    for skill in skills:
        public = f"{skill.name} {skill.description or ''}".lower()
        if any(task_id in public for task_id in task_ids):
            errors.append(f"leakage in public skill metadata for {skill.skill_id}: task_id")
        if any(skill_id in public for skill_id in oracle_skill_ids):
            errors.append(
                f"leakage in public skill metadata for {skill.skill_id}: oracle skill id"
            )
        for token in LABEL_LEAKAGE_TOKENS:
            if token in public:
                errors.append(
                    f"leakage in public skill metadata for {skill.skill_id}: {token}"
                )
    return errors


def _public_skill_text_leakage_errors(
    tasks: list[SkillsBenchTask],
    skills: Iterable[LiveAgentSkill],
) -> list[str]:
    task_ids = {task.task_id.lower() for task in tasks}
    oracle_skill_ids = {
        skill_id.lower() for task in tasks for skill_id in task.oracle_skill_ids
    }
    errors = []
    for skill in skills:
        public = f"{skill.name} {skill.description or ''} {skill.body}".lower()
        if any(task_id in public for task_id in task_ids):
            errors.append(f"leakage in public skill text for {skill.skill_id}: task_id")
        if any(skill_id in public for skill_id in oracle_skill_ids):
            errors.append(
                f"leakage in public skill text for {skill.skill_id}: oracle skill id"
            )
        for token in LABEL_LEAKAGE_TOKENS:
            if token in public:
                errors.append(f"leakage in public skill text for {skill.skill_id}: {token}")
    return errors


def _is_allowed_upstream_ref(
    upstream_ref: str,
    license_note: str,
    *,
    allow_non_sha: bool,
    allow_fixture_ref: bool,
) -> bool:
    if allow_non_sha or COMMIT_SHA_RE.fullmatch(upstream_ref):
        return True
    return allow_fixture_ref and upstream_ref == "fixture-ref" and license_note == "fixture-only"


def _required_string(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    strings = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field} must contain non-empty strings")
        strings.append(item)
    return strings


def _mode(value: str) -> str:
    if value not in {"pilot", "frozen"}:
        raise ValueError("mode must be pilot or frozen")
    return value


def _evidence_mode(value: str) -> str:
    if value not in EVIDENCE_MODES:
        raise ValueError("evidence_mode must be fixture or real")
    return value


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _positive_int(value: int, field: str) -> int:
    if int(value) <= 0:
        raise ValueError(f"{field} must be positive")
    return int(value)


def _non_empty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty")
    return value


def _safe_run_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
