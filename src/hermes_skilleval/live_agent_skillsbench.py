from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from hermes_skilleval.live_agent_runtime import (
    AgentRunner,
    AgentRequest,
    AgentVerifier,
    FakeAgentRunner,
    FakeVerifier,
    LiveAgentSkill,
    build_condition,
    execute_live_agent,
    prepare_live_agent_workspace,
)
from hermes_skilleval.provenance import _reject_sensitive_values
from hermes_skilleval.release_manifest import sha256_file


PLAN_SCHEMA = "v0.3.skillsbench-live-plan.v1"
REPORT_SCHEMA = "v0.3.skillsbench-live-matrix-report.v1"
SEED = 20260625
CONDITIONS = ("no-skill", "routed-skill", "oracle-skill")
CONTROLLED_NETWORKS = {"none", "controlled"}


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
    ) -> None:
        self.data_root = Path(data_root)
        self.upstream_ref = upstream_ref
        self.license_note = license_note

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
            if task.requires_private_credentials:
                errors.append(f"task requires private credentials: {task.task_id}")
            if task.network not in CONTROLLED_NETWORKS:
                errors.append(f"uncontrolled network requirement: {task.task_id}")
            for skill_id in task.oracle_skill_ids:
                if skill_id not in skills:
                    errors.append(f"missing skill definition: {task.task_id} -> {skill_id}")

        if self.upstream_ref == "FILL_BEFORE_RUN":
            errors.append("upstream_ref must be set before SkillsBench validation")
        if self.license_note == "FILL_BEFORE_RUN":
            errors.append("license_note must be set before SkillsBench validation")
        return {
            "schema_version": "v0.3.skillsbench-validation.v1",
            "benchmark_id": "skillsbench",
            "status": "INVALID" if errors else "PASS",
            "errors": errors,
            "task_count": len(tasks),
            "skill_count": len(skills),
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
) -> dict[str, Any]:
    mode = _mode(mode)
    adapter = SkillsBenchAdapter(
        data_root=data_root,
        upstream_ref=upstream_ref,
        license_note=license_note,
    )
    validation = adapter.validate()
    if validation["status"] != "PASS":
        raise ValueError("SkillsBench validation failed")
    tasks_by_id = {task.task_id: task for task in adapter.load_tasks()}
    selected_ids = list(selected_task_ids) or sorted(tasks_by_id)
    selected_tasks = [_selected_task(tasks_by_id, task_id) for task_id in selected_ids]
    skills = adapter.load_skills()
    routed_predictions = _read_predictions(Path(routed_predictions_path))
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

    registry_ids: set[str] = set()
    for task in selected_tasks:
        registry_ids.update(task.oracle_skill_ids)
        routed_ids = routed_predictions.get(task.task_id, [])
        if not routed_ids:
            raise ValueError(f"missing routed predictions for task: {task.task_id}")
        registry_ids.update(routed_ids)
    missing_skills = sorted(skill_id for skill_id in registry_ids if skill_id not in skills)
    if missing_skills:
        raise ValueError("missing skill definition: " + ", ".join(missing_skills))

    registry = {
        skill_id: _skill_to_plan(skills[skill_id])
        for skill_id in sorted(registry_ids)
    }
    matrix = []
    for task in selected_tasks:
        condition_hashes = []
        for condition_name in CONDITIONS:
            routed_for_condition = (
                [skills[skill_id] for skill_id in routed_predictions[task.task_id]]
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

    plan = {
        "schema_version": PLAN_SCHEMA,
        "benchmark_id": "skillsbench",
        "run_id": _non_empty(run_id, "run_id"),
        "mode": mode,
        "seed": SEED,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "data_root": str(data_root),
        "adapter_provenance": adapter.provenance(validation),
        "routed_predictions": _file_record(Path(routed_predictions_path)),
        "oracle_qualification": (
            _file_record(Path(oracle_qualification_path))
            if oracle_qualification_path
            else None
        ),
        "validation": validation,
        "selected_tasks": [_task_to_plan(task) for task in selected_tasks],
        "global_skill_registry": registry,
        "matrix": matrix,
        "matrix_output_path": str(matrix_output_path) if matrix_output_path else None,
        "workspace_root": str(workspace_root) if workspace_root else None,
        "oracle_qualification_records": qualifications,
        "overlap_report": _overlap_report(selected_tasks),
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
    _reject_sensitive_values(plan)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def run_skillsbench_matrix(
    *,
    plan_path: Path | str,
    output_path: Path | str,
    runner: AgentRunner | None = None,
    verifier: AgentVerifier | None = None,
) -> dict[str, Any]:
    plan_file = Path(plan_path)
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise ValueError("unsupported SkillsBench plan schema")
    _verify_plan_inputs(plan)
    output = Path(output_path)
    if plan.get("matrix_output_path") and str(output) != str(plan["matrix_output_path"]):
        raise ValueError("matrix output path does not match frozen plan")
    selected_runner = runner or FakeAgentRunner(
        exit_code=0,
        events=[{"type": "final", "message": "fixture matrix run"}],
    )
    selected_verifier = verifier or FakeVerifier(pass_=True, details={"mode": "fixture"})
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
        "plan_path": str(plan_file),
        "skill_inventory": plan["global_skill_registry"],
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
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("routed predictions must be an object")
    return {str(task_id): _string_list(value, "routed prediction") for task_id, value in data.items()}


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
    for record in records:
        path = Path(record["path"])
        if not path.exists():
            raise ValueError(f"frozen input missing: {path}")
        if path.stat().st_size != int(record["size_bytes"]) or sha256_file(path) != record["sha256"]:
            raise ValueError(f"frozen input changed: {path}")


def _file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _selected_task(tasks_by_id: dict[str, SkillsBenchTask], task_id: str) -> SkillsBenchTask:
    if task_id not in tasks_by_id:
        raise ValueError(f"selected task does not exist: {task_id}")
    return tasks_by_id[task_id]


def _task_to_plan(task: SkillsBenchTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "prompt": task.prompt,
        "verifier": task.verifier,
        "oracle_skill_ids": task.oracle_skill_ids,
        "network": task.network,
        "metadata": task.metadata,
    }


def _skill_to_plan(skill: LiveAgentSkill) -> dict[str, Any]:
    return {
        "skill_id": skill.skill_id,
        "name": skill.name,
        "description": skill.description or "",
        "body": skill.body,
    }


def _routed_ids(plan: dict[str, Any], task_id: str) -> list[str]:
    predictions = json.loads(Path(plan["routed_predictions"]["path"]).read_text(encoding="utf-8"))
    return [str(skill_id) for skill_id in predictions[task_id]]


def _overlap_report(tasks: list[SkillsBenchTask]) -> dict[str, Any]:
    ids = sorted(
        {
            str(task.metadata["skillrouter_task_id"])
            for task in tasks
            if task.metadata.get("skillrouter_task_id")
        }
    )
    return {
        "schema_version": "v0.3.skillrouter-skillsbench-overlap.v1",
        "skillsbench_task_count": len(tasks),
        "skillrouter_task_refs": ids,
        "exact_id_overlap": ids,
        "high_similarity_diagnostics": {
            "status": "UNAVAILABLE",
            "reason": "high-similarity diagnostics not selected in PR-6",
        },
    }


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


def _non_empty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty")
    return value


def _safe_run_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)
