from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from hermes_skilleval.models import BenchmarkTask, Skill
from hermes_skilleval.skill_index import load_skill_index
from hermes_skilleval.task_loader import load_tasks


POLICY_ID = "router-training-data-v2-qualification-v2"
CANDIDATE_SCHEMA_VERSION = "router-training-data-v2-candidate-v2"
REPORT_SCHEMA_VERSION = "router-training-data-v2-qualification-report-v2"
MANIFEST_SCHEMA_VERSION = "router-training-data-v2-manifest-v2"
QUERY_CONTRACT = MappingProxyType(
    {
        "alternate_query_fields": (),
        "forbidden_primary_query_inputs": (
            "task_id",
            "category",
            "difficulty",
            "robustness_tags",
        ),
        "hash_algorithm": "sha256",
        "hash_field": "prompt_text_sha256",
        "normalization": "loader_normalized",
        "primary_query_field": "query_text",
        "query_text_policy": "prompt_only",
        "source_field": "task.prompt",
    }
)
BLOCKER_CODES = sorted(
    [
        "INDEPENDENT_CALIBRATION_SPLIT_MISSING",
        "MANUAL_ACCEPTANCE_MISSING",
        "PAIR_COUNT_BELOW_MINIMUM",
        "REJECT_EXAMPLES_MISSING",
        "SAME_CATEGORY_NEGATIVES_UNREVIEWED",
        "TARGET_POSITIVE_COVERAGE_INCOMPLETE",
        "TASK_FAMILY_METADATA_MISSING",
        "TASK_FAMILY_SPLIT_NOT_INDEPENDENT",
    ]
)
PROTECTED_DEMO_PATHS = (
    "docs/demo/phase14-finetuned-embedding-router",
    "docs/demo/phase15-held-out-generalization",
    "docs/demo/phase16-blind-validation",
    "docs/demo/phase17-calibrated-release-selector",
    "docs/demo/phase18-ci-release-reproducibility",
)
CANONICAL_TASK_ROOT = "benchmarks/migration-tasks"
CANONICAL_SKILLS_INDEX = "docs/demo/phase9-real-skill-library-migration/skills.json"
CANONICAL_INPUT_SNAPSHOT_SHA256 = (
    "f3585cb91c103c7fa19488f114871f1146fa966ce9a272a3911bb8d0b69d2cd5"
)
CANONICAL_TASK_IDS = frozenset(
    {
        "browser-accessibility-audit",
        "browser-form-regression",
        "browser-local-dashboard",
        "claude-command-routing",
        "claude-mcp-selection",
        "claude-plan-to-tasks",
        "codex-git-hygiene",
        "codex-minimal-diff",
        "codex-worker-handoff",
        "sp-debug-red-green",
        "sp-isolated-worktree",
        "sp-verify-before-claim",
    }
)
CANONICAL_SKILL_IDS = frozenset(
    {
        "accessibility-tree-inspection",
        "apply-patch-discipline",
        "browser-smoke-testing",
        "evidence-backed-final",
        "form-interaction-flow",
        "mcp-tool-routing",
        "plan-mode",
        "slash-command-workflow",
        "subagent-worker-protocol",
        "systematic-debugging",
        "task-tool-delegation",
        "test-driven-development",
        "using-git-worktrees",
        "verification-before-completion",
        "visual-regression-review",
        "workspace-git-hygiene",
    }
)


@dataclass(frozen=True)
class TaskSource:
    task_id: str
    task_yaml_entry: Path
    task_yaml: Path
    prompt_md_entry: Path
    prompt_md: Path
    task_yaml_logical: str
    prompt_md_logical: str


@dataclass(frozen=True)
class InputFileSnapshot:
    logical_path: str
    entry_path: Path
    physical_path: Path
    sha256: str


def qualify_router_training_data_v2(
    *,
    tasks_path: Path | str,
    skills_index_path: Path | str,
    output_dir: Path | str,
    repository_root: Path | str | None = None,
) -> dict[str, Any]:
    """Build the frozen canonical diagnostic v2 qualification pack."""

    return _qualify_router_training_data_v2(
        tasks_path=tasks_path,
        skills_index_path=skills_index_path,
        output_dir=output_dir,
        repository_root=repository_root,
        enforce_canonical=True,
    )


def _qualify_router_training_data_v2(
    *,
    tasks_path: Path | str,
    skills_index_path: Path | str,
    output_dir: Path | str,
    repository_root: Path | str | None = None,
    enforce_canonical: bool,
) -> dict[str, Any]:
    """Private generic builder used by isolated validation fixtures."""

    repo_root = _resolve_repository_root(
        repository_root,
        Path(tasks_path),
        Path(skills_index_path),
    )
    target = _validated_output_target(Path(output_dir), repo_root)
    task_sources = preflight_task_source(Path(tasks_path), repo_root)
    skills_index_entry = Path(skills_index_path).absolute()
    skills_index = skills_index_entry.resolve(strict=True)
    _reject_blind_path(skills_index, "skills index")
    skills_index_logical = _logical_path(skills_index, repo_root, "skills index")
    tasks_root = Path(tasks_path).resolve(strict=True)
    tasks_root_logical = _logical_path(tasks_root, repo_root, "task source")
    input_snapshot = _snapshot_inputs(
        task_sources,
        skills_index_entry,
        skills_index,
        skills_index_logical,
    )
    if enforce_canonical:
        _validate_canonical_snapshot(
            tasks_root_logical=tasks_root_logical,
            skills_index_logical=skills_index_logical,
            input_snapshot=input_snapshot,
        )

    tasks = load_tasks(tasks_root)
    skills = load_skill_index(skills_index)
    _validate_loaded_inputs(tasks, skills, task_sources)
    if enforce_canonical:
        _validate_canonical_ids(tasks, skills)

    source_by_id = {source.task_id: source for source in task_sources}
    rows = _build_candidate_matrix(
        tasks,
        skills,
        source_by_id=source_by_id,
        skills_index_logical=skills_index_logical,
    )
    report = _build_qualification_report(tasks, skills, rows)
    candidate_bytes = _jsonl_bytes(rows)
    report_bytes = _json_bytes(report)
    manifest = _build_manifest(
        repo_root=repo_root,
        tasks_root=tasks_root,
        skills_index_logical=skills_index_logical,
        input_snapshot=input_snapshot,
        report=report,
        output_bytes={
            "candidate-pairs.jsonl": candidate_bytes,
            "qualification-report.json": report_bytes,
        },
    )
    files = {
        "candidate-pairs.jsonl": candidate_bytes,
        "qualification-report.json": report_bytes,
        "manifest.json": _json_bytes(manifest),
    }
    _atomic_publish(target, files, input_snapshot=input_snapshot)
    return report


def preflight_task_source(tasks_path: Path, repository_root: Path) -> list[TaskSource]:
    """Validate path and metadata identity without reading prompt content."""

    try:
        root = tasks_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"task source does not exist: {tasks_path}") from exc
    if not root.is_dir():
        raise ValueError(f"task source is not a directory: {tasks_path}")
    _reject_blind_path(root, "task source")
    _logical_path(root, repository_root, "task source")

    sources: list[TaskSource] = []
    visited: set[Path] = set()
    for current_text, dirnames, filenames in os.walk(root, followlinks=True):
        current = Path(current_text)
        current_real = current.resolve(strict=True)
        _reject_blind_path(current_real, "task directory")
        if _is_blind_identity(current.name) or _is_blind_identity(current_real.name):
            raise ValueError(f"blind task directory is forbidden: {current}")
        if current_real in visited:
            dirnames[:] = []
            continue
        visited.add(current_real)

        retained_dirs: list[str] = []
        for dirname in sorted(dirnames):
            child = current / dirname
            child_real = child.resolve(strict=True)
            _reject_blind_path(child_real, "task directory")
            if _is_blind_identity(dirname) or _is_blind_identity(child_real.name):
                raise ValueError(f"blind task directory is forbidden: {child}")
            retained_dirs.append(dirname)
        dirnames[:] = retained_dirs

        if "task.yaml" not in filenames:
            continue
        task_yaml_entry = (current / "task.yaml").absolute()
        prompt_md_entry = (current / "prompt.md").absolute()
        if not prompt_md_entry.exists():
            raise ValueError(f"missing prompt.md in {current}")
        task_yaml = task_yaml_entry.resolve(strict=True)
        prompt_md = prompt_md_entry.resolve(strict=True)
        _reject_blind_path(task_yaml, "task metadata")
        _reject_blind_path(prompt_md, "task prompt")
        task_yaml_logical = _logical_path(task_yaml, repository_root, "task metadata")
        prompt_md_logical = _logical_path(prompt_md, repository_root, "task prompt")
        raw = _load_metadata(task_yaml)
        task_id = raw.get("id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(
                f"task metadata id must be a non-empty string: {task_yaml}"
            )
        if _is_blind_identity(task_id):
            raise ValueError(f"blind task metadata id is forbidden: {task_id}")
        if "/" in task_id:
            raise ValueError(f"task ID must not contain '/': {task_id}")
        sources.append(
            TaskSource(
                task_id=task_id,
                task_yaml_entry=task_yaml_entry,
                task_yaml=task_yaml,
                prompt_md_entry=prompt_md_entry,
                prompt_md=prompt_md,
                task_yaml_logical=task_yaml_logical,
                prompt_md_logical=prompt_md_logical,
            )
        )

    if not sources:
        raise ValueError(
            f"no benchmark tasks found under {root}; expected task.yaml files"
        )
    task_ids = [source.task_id for source in sources]
    duplicate_ids = sorted(
        task_id for task_id, count in Counter(task_ids).items() if count > 1
    )
    if duplicate_ids:
        raise ValueError(f"duplicate task ID: {', '.join(duplicate_ids)}")
    return sorted(sources, key=lambda source: source.task_id)


def _build_candidate_matrix(
    tasks: list[BenchmarkTask],
    skills: list[Skill],
    *,
    source_by_id: dict[str, TaskSource],
    skills_index_logical: str,
) -> list[dict[str, Any]]:
    skill_by_id = {skill.id: skill for skill in skills}
    rows: list[dict[str, Any]] = []
    for task in sorted(tasks, key=lambda item: item.id):
        gold_category = _gold_category(task, skill_by_id)
        source = source_by_id[task.id]
        query_text = task.prompt
        prompt_hash = _sha256(query_text.encode("utf-8"))
        for skill in sorted(skills, key=lambda item: item.id):
            if skill.id in task.gold_skills:
                candidate_type = "positive"
                label = 1
            elif skill.category == gold_category:
                candidate_type = "same_category_negative_candidate"
                label = 0
            else:
                candidate_type = "cross_category_easy_negative"
                label = 0

            if task.split == "test":
                disposition = "RESERVED_SOURCE_TEST"
            elif candidate_type == "positive":
                disposition = "TRAIN_CANDIDATE_POSITIVE"
            elif candidate_type == "same_category_negative_candidate":
                disposition = "REVIEW_REQUIRED_NEGATIVE_CANDIDATE"
            else:
                disposition = "EXCLUDED_EASY_NEGATIVE"

            rows.append(
                {
                    "accepted_for_training": False,
                    "candidate_type": candidate_type,
                    "disposition": disposition,
                    "label": label,
                    "pair_id": f"{task.id}/{skill.id}",
                    "prompt_text_sha256": prompt_hash,
                    "query_text": query_text,
                    "query_text_policy": "prompt_only",
                    "schema_version": CANDIDATE_SCHEMA_VERSION,
                    "skill_id": skill.id,
                    "skill_text": _skill_text(skill),
                    "source": {
                        "prompt": source.prompt_md_logical,
                        "skills_index": skills_index_logical,
                        "task_metadata": source.task_yaml_logical,
                    },
                    "source_split": task.split,
                    "task_id": task.id,
                }
            )
    return rows


def _build_qualification_report(
    tasks: list[BenchmarkTask],
    skills: list[Skill],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    train_policy = [
        row
        for row in rows
        if row["source_split"] == "dev"
        and row["candidate_type"] in {"positive", "same_category_negative_candidate"}
    ]
    reserved = [row for row in rows if row["disposition"] == "RESERVED_SOURCE_TEST"]
    train_positive_skills = {
        str(row["skill_id"])
        for row in rows
        if row["source_split"] == "dev" and row["candidate_type"] == "positive"
    }
    counts = {
        "accepted_train_pair_count": 0,
        "cross_category_easy_negative_count": sum(
            row["candidate_type"] == "cross_category_easy_negative" for row in rows
        ),
        "matrix_candidate_count": len(rows),
        "positive_count": sum(row["candidate_type"] == "positive" for row in rows),
        "reject_example_count": 0,
        "reserved_matrix_row_count": len(reserved),
        "reserved_positive_or_same_category_count": sum(
            row["candidate_type"] in {"positive", "same_category_negative_candidate"}
            for row in reserved
        ),
        "same_category_negative_candidate_count": sum(
            row["candidate_type"] == "same_category_negative_candidate" for row in rows
        ),
        "source_pair_count": sum(
            len(task.gold_skills) + len(task.negative_skills) for task in tasks
        ),
        "target_skill_count": len(skills),
        "task_count": len(tasks),
        "train_policy_candidate_count": len(train_policy),
        "train_positive_skill_coverage_count": len(train_positive_skills),
    }
    return {
        "artifact_type": "router-training-data-v2-qualification-report",
        "blocker_codes": BLOCKER_CODES,
        "can_start_training": False,
        "checks": {
            "accepted_pair_count_100_to_200": False,
            "human_acceptance_bound_to_hashes": False,
            "independent_nonempty_train_calibration_test": False,
            "reviewed_same_category_negatives": False,
            "reviewed_true_reject_examples": False,
            "target_positive_coverage_complete": len(train_positive_skills)
            == len(skills),
            "task_family_metadata_complete": False,
            "task_family_splits_independent": False,
        },
        "counts": counts,
        "policy_id": POLICY_ID,
        "qualification_status": "REVIEW_REQUIRED",
        "query_contract": _query_contract_payload(),
        "router_decision": "KEEP_BASELINE",
        "schema_version": REPORT_SCHEMA_VERSION,
    }


def _snapshot_inputs(
    task_sources: list[TaskSource],
    skills_index_entry: Path,
    skills_index: Path,
    skills_index_logical: str,
) -> tuple[InputFileSnapshot, ...]:
    paths = [
        (source.task_yaml_logical, source.task_yaml_entry, source.task_yaml)
        for source in task_sources
    ] + [
        (source.prompt_md_logical, source.prompt_md_entry, source.prompt_md)
        for source in task_sources
    ]
    paths.append((skills_index_logical, skills_index_entry, skills_index))
    return tuple(
        InputFileSnapshot(
            logical_path=logical_path,
            entry_path=entry_path,
            physical_path=physical_path,
            sha256=_sha256(physical_path.read_bytes()),
        )
        for logical_path, entry_path, physical_path in sorted(paths)
    )


def _snapshot_records(
    input_snapshot: tuple[InputFileSnapshot, ...],
) -> list[dict[str, str]]:
    return [
        {"path": entry.logical_path, "sha256": entry.sha256} for entry in input_snapshot
    ]


def _snapshot_aggregate_sha256(
    input_snapshot: tuple[InputFileSnapshot, ...],
) -> str:
    payload = json.dumps(
        _snapshot_records(input_snapshot),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256(payload)


def _validate_canonical_snapshot(
    *,
    tasks_root_logical: str,
    skills_index_logical: str,
    input_snapshot: tuple[InputFileSnapshot, ...],
) -> None:
    if tasks_root_logical != CANONICAL_TASK_ROOT:
        raise ValueError(
            f"router-training-data-v2 v2 requires canonical task root: "
            f"{CANONICAL_TASK_ROOT}"
        )
    if skills_index_logical != CANONICAL_SKILLS_INDEX:
        raise ValueError(
            "router-training-data-v2 v2 requires canonical skills index: "
            f"{CANONICAL_SKILLS_INDEX}"
        )
    actual_snapshot = _snapshot_aggregate_sha256(input_snapshot)
    if actual_snapshot != CANONICAL_INPUT_SNAPSHOT_SHA256:
        raise ValueError(
            "router-training-data-v2 v2 canonical input snapshot mismatch: "
            f"expected {CANONICAL_INPUT_SNAPSHOT_SHA256}, got {actual_snapshot}"
        )


def _validate_canonical_ids(
    tasks: list[BenchmarkTask],
    skills: list[Skill],
) -> None:
    task_ids = {task.id for task in tasks}
    if task_ids != CANONICAL_TASK_IDS:
        raise ValueError("router-training-data-v2 v2 canonical task IDs mismatch")
    skill_ids = {skill.id for skill in skills}
    if skill_ids != CANONICAL_SKILL_IDS:
        raise ValueError("router-training-data-v2 v2 canonical skill IDs mismatch")


def _assert_input_snapshot_unchanged(
    input_snapshot: tuple[InputFileSnapshot, ...],
) -> None:
    for entry in input_snapshot:
        try:
            current_target = entry.entry_path.resolve(strict=True)
            if current_target != entry.physical_path:
                raise ValueError(
                    f"input changed during qualification: {entry.logical_path}"
                )
            current_sha256 = _sha256(current_target.read_bytes())
        except OSError as exc:
            raise ValueError(
                f"input changed during qualification: {entry.logical_path}"
            ) from exc
        if current_sha256 != entry.sha256:
            raise ValueError(
                f"input changed during qualification: {entry.logical_path}"
            )


def _build_manifest(
    *,
    repo_root: Path,
    tasks_root: Path,
    skills_index_logical: str,
    input_snapshot: tuple[InputFileSnapshot, ...],
    report: dict[str, Any],
    output_bytes: dict[str, bytes],
) -> dict[str, Any]:
    input_files = _snapshot_records(input_snapshot)
    skills_index_record = next(
        record for record in input_files if record["path"] == skills_index_logical
    )
    return {
        "artifact_type": "router-training-data-v2-qualification-manifest",
        "artifact_version": 2,
        "counts": report["counts"],
        "inputs": {
            "files": input_files,
            "skills_index": {
                "path": skills_index_logical,
                "sha256": skills_index_record["sha256"],
            },
            "task_root": _logical_path(tasks_root, repo_root, "task source"),
        },
        "non_actions": [
            "no_a100_or_gpu_work",
            "no_blind_prompt_read_or_hash",
            "no_calibration_or_model_selection",
            "no_checkpoint_creation",
            "no_historical_evidence_mutation",
            "no_router_promotion",
            "no_training",
            "no_training_pairs_output",
        ],
        "ordering": {
            "candidate_rows": ["task_id", "skill_id"],
            "json_keys": "lexical",
            "line_ending": "LF",
        },
        "outputs": [
            {
                "bytes": len(payload),
                "path": name,
                "sha256": _sha256(payload),
            }
            for name, payload in sorted(output_bytes.items())
        ],
        "policy_id": POLICY_ID,
        "query_contract": _query_contract_payload(),
        "schema_version": MANIFEST_SCHEMA_VERSION,
    }


def _validate_loaded_inputs(
    tasks: list[BenchmarkTask],
    skills: list[Skill],
    task_sources: list[TaskSource],
) -> None:
    task_ids = [task.id for task in tasks]
    for task_id in task_ids:
        if _is_blind_identity(task_id):
            raise ValueError(f"blind loaded task ID is forbidden: {task_id}")
    duplicate_task_ids = sorted(
        task_id for task_id, count in Counter(task_ids).items() if count > 1
    )
    if duplicate_task_ids:
        raise ValueError(f"duplicate task ID: {', '.join(duplicate_task_ids)}")
    source_ids = {source.task_id for source in task_sources}
    if set(task_ids) != source_ids:
        raise ValueError("preflight and loaded task identities differ")

    skill_ids = [skill.id for skill in skills]
    duplicate_skill_ids = sorted(
        skill_id for skill_id, count in Counter(skill_ids).items() if count > 1
    )
    if duplicate_skill_ids:
        raise ValueError(f"duplicate skill ID: {', '.join(duplicate_skill_ids)}")
    for skill_id in skill_ids:
        if not skill_id:
            raise ValueError("skill ID must be non-empty")
        if "/" in skill_id:
            raise ValueError(f"skill ID must not contain '/': {skill_id}")

    skill_by_id = {skill.id: skill for skill in skills}
    for task in tasks:
        if "/" in task.id:
            raise ValueError(f"task ID must not contain '/': {task.id}")
        for skill_id in task.gold_skills + task.negative_skills:
            if skill_id not in skill_by_id:
                raise ValueError(f"task {task.id} references missing skill: {skill_id}")
        _gold_category(task, skill_by_id)


def _gold_category(task: BenchmarkTask, skill_by_id: dict[str, Skill]) -> str:
    categories = {skill_by_id[skill_id].category for skill_id in task.gold_skills}
    if len(categories) != 1 or None in categories:
        rendered = ", ".join(sorted(str(category) for category in categories))
        raise ValueError(
            f"task {task.id} has mixed gold ecosystem categories: {rendered}"
        )
    return str(next(iter(categories)))


def _validated_output_target(output_dir: Path, repo_root: Path) -> Path:
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError(f"output target already exists: {output_dir}")
    target = output_dir.resolve(strict=False)
    _reject_blind_path(target, "output target")
    parent = target.parent
    if not parent.exists() or not parent.is_dir():
        raise ValueError(
            f"output target parent must be an existing directory: {parent}"
        )
    for protected_text in PROTECTED_DEMO_PATHS:
        protected = (repo_root / protected_text).resolve(strict=False)
        if _overlaps(target, protected):
            raise ValueError(
                f"output target overlaps protected historical evidence: {protected_text}"
            )
    return target


def _atomic_publish(
    target: Path,
    files: dict[str, bytes],
    *,
    input_snapshot: tuple[InputFileSnapshot, ...],
) -> None:
    stage = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=str(target.parent))
    )
    try:
        _publish_staged_pack(stage, files)
        _assert_input_snapshot_unchanged(input_snapshot)
        if target.exists() or target.is_symlink():
            raise ValueError(f"output target appeared during staging: {target}")
        stage.rename(target)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _publish_staged_pack(stage: Path, files: dict[str, bytes]) -> None:
    for name, payload in sorted(files.items()):
        (stage / name).write_bytes(payload)


def _resolve_repository_root(
    supplied: Path | str | None,
    tasks_path: Path,
    skills_index_path: Path,
) -> Path:
    if supplied is not None:
        root = Path(supplied).resolve(strict=True)
        if not root.is_dir():
            raise ValueError(f"repository root is not a directory: {root}")
        return root
    for candidate in (Path.cwd(), tasks_path, skills_index_path):
        start = candidate if candidate.is_dir() else candidate.parent
        for parent in (
            start.resolve(strict=False),
            *start.resolve(strict=False).parents,
        ):
            if (parent / ".git").exists():
                return parent
    raise ValueError("could not discover repository root")


def _logical_path(path: Path, repo_root: Path, label: str) -> str:
    resolved = path.resolve(strict=True)
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise ValueError(f"{label} must be within repository root: {resolved}") from exc


def _reject_blind_path(path: Path, label: str) -> None:
    if "blind-migration-tasks" in {part.strip().lower() for part in path.parts}:
        raise ValueError(f"blind source path is forbidden for {label}: {path}")


def _is_blind_identity(value: str) -> bool:
    return value.strip().lower().startswith("blind-")


def _load_metadata(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed task metadata: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"task metadata must contain a mapping: {path}")
    return raw


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _skill_text(skill: Skill) -> str:
    return " ".join(
        [
            skill.id.replace("-", " "),
            skill.name,
            skill.category or "",
            skill.description,
            " ".join(skill.trigger_terms),
            skill.body,
        ]
    )


def _query_contract_payload() -> dict[str, Any]:
    return {
        key: list(value) if isinstance(value, tuple) else value
        for key, value in QUERY_CONTRACT.items()
    }


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    ).encode("utf-8")


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
