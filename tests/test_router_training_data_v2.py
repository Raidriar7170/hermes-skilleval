from __future__ import annotations

import hashlib
import inspect
import json
import shutil
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import pytest
import yaml

import hermes_skilleval.router_training_data_v2 as qualification
from hermes_skilleval.models import BenchmarkTask
from hermes_skilleval.router_training_data_v2 import (
    BLOCKER_CODES,
    qualify_router_training_data_v2,
)
from hermes_skilleval.task_loader import load_tasks


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_TASKS = REPO_ROOT / "benchmarks/migration-tasks"
CANONICAL_SKILLS = (
    REPO_ROOT / "docs/demo/phase9-real-skill-library-migration/skills.json"
)
EXPECTED_QUERY_CONTRACT = {
    "alternate_query_fields": [],
    "forbidden_primary_query_inputs": [
        "task_id",
        "category",
        "difficulty",
        "robustness_tags",
        "split",
        "family",
    ],
    "formatter": "router_query_text(prompt: str)",
    "hash_algorithm": "sha256",
    "hash_field": "prompt_text_sha256",
    "normalization": "loader_normalized",
    "primary_query_field": "query_text",
    "query_text_policy": "prompt_only",
    "source_field": "task.prompt",
}
EXPECTED_ROW_FIELDS = {
    "accepted_for_training",
    "artifact_version",
    "candidate_type",
    "disposition",
    "label",
    "pair_id",
    "policy_id",
    "prompt_text_sha256",
    "query_text",
    "query_text_policy",
    "schema_version",
    "skill_id",
    "skill_text",
    "source",
    "source_split",
    "task_id",
}
EXPECTED_DIVERSITY_DIAGNOSTICS = {
    "family_independent_count": None,
    "family_metadata_status": "UNAVAILABLE",
    "per_skill_unique_train_positive_prompt_count": {
        "accessibility-tree-inspection": 0,
        "apply-patch-discipline": 1,
        "browser-smoke-testing": 1,
        "evidence-backed-final": 1,
        "form-interaction-flow": 1,
        "mcp-tool-routing": 0,
        "plan-mode": 1,
        "slash-command-workflow": 1,
        "subagent-worker-protocol": 1,
        "systematic-debugging": 1,
        "task-tool-delegation": 0,
        "test-driven-development": 1,
        "using-git-worktrees": 0,
        "verification-before-completion": 1,
        "visual-regression-review": 1,
        "workspace-git-hygiene": 0,
    },
    "train_policy_unique_prompt_count": 8,
    "unique_prompt_count": 12,
    "unique_task_family_count": None,
}


def _independent_diversity_diagnostics(
    rows: list[dict[str, object]],
    skill_ids: set[str],
) -> dict[str, object]:
    train_policy_rows = [
        row
        for row in rows
        if row["source_split"] == "dev"
        and row["candidate_type"] in {"positive", "same_category_negative_candidate"}
    ]
    return {
        "family_independent_count": None,
        "family_metadata_status": "UNAVAILABLE",
        "per_skill_unique_train_positive_prompt_count": {
            skill_id: len(
                {
                    str(row["query_text"])
                    for row in rows
                    if row["source_split"] == "dev"
                    and row["candidate_type"] == "positive"
                    and row["skill_id"] == skill_id
                }
            )
            for skill_id in sorted(skill_ids)
        },
        "train_policy_unique_prompt_count": len(
            {str(row["query_text"]) for row in train_policy_rows}
        ),
        "unique_prompt_count": len({str(row["query_text"]) for row in rows}),
        "unique_task_family_count": None,
    }


def _skill(skill_id: str, category: str) -> dict[str, object]:
    return {
        "id": skill_id,
        "name": skill_id.replace("-", " ").title(),
        "path": f"skills/{skill_id}/SKILL.md",
        "category": category,
        "description": f"Use {skill_id}.",
        "body": f"# {skill_id}\n",
        "trigger_terms": skill_id.split("-"),
        "token_count_estimate": 5,
    }


def _write_task(
    root: Path,
    directory: str,
    *,
    task_id: str | None = None,
    gold_skills: list[str] | None = None,
    negative_skills: list[str] | None = None,
    split: str = "dev",
    prompt: str = "  A normalized prompt.  \n",
) -> Path:
    task_dir = root / directory
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "id": task_id or directory,
                "category": "migration",
                "difficulty": "medium",
                "gold_skills": gold_skills or ["alpha-one"],
                "negative_skills": negative_skills or ["beta-one"],
                "verifier": "skill_selection",
                "split": split,
                "robustness_tags": ["qualification"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (task_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    return task_dir


def _fixture_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    tasks = root / "benchmarks/migration-tasks"
    _write_task(tasks, "task-one")
    skills = root / "skills.json"
    skills.write_text(
        json.dumps([_skill("alpha-one", "alpha"), _skill("beta-one", "beta")]),
        encoding="utf-8",
    )
    return root, tasks, skills


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _copy_canonical_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "copied-repository"
    (root / ".git").mkdir(parents=True)
    tasks = root / "benchmarks/migration-tasks"
    skills = root / "docs/demo/phase9-real-skill-library-migration/skills.json"
    shutil.copytree(CANONICAL_TASKS, tasks)
    skills.parent.mkdir(parents=True)
    shutil.copy2(CANONICAL_SKILLS, skills)
    return root, tasks, skills


def test_blockers_are_exact_and_sorted():
    assert BLOCKER_CODES == sorted(
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


@pytest.mark.parametrize("blind_vector", ["root", "directory", "metadata"])
def test_blind_identity_is_rejected_before_task_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    blind_vector: str,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    if blind_vector == "root":
        tasks.rename(root / "benchmarks/blind-migration-tasks")
        tasks = root / "benchmarks/blind-migration-tasks"
    elif blind_vector == "directory":
        (tasks / "task-one").rename(tasks / "blind-task-one")
    else:
        metadata = tasks / "task-one/task.yaml"
        payload = yaml.safe_load(metadata.read_text(encoding="utf-8"))
        payload["id"] = "blind-task-one"
        metadata.write_text(yaml.safe_dump(payload), encoding="utf-8")

    def forbidden_loader(_: Path) -> object:
        raise AssertionError("load_tasks must not run for blind input")

    monkeypatch.setattr(qualification, "load_tasks", forbidden_loader)
    with pytest.raises(ValueError, match="blind"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
            enforce_canonical=False,
        )
    assert not (root / "pack").exists()


@pytest.mark.parametrize("linked_entry", ["task-directory", "task-yaml", "prompt-md"])
def test_symlinked_task_entry_into_blind_root_is_rejected_before_prompt_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    linked_entry: str,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    blind = root / "benchmarks/blind-migration-tasks/hidden"
    blind.mkdir(parents=True)
    blind_metadata = blind / "task.yaml"
    blind_metadata.write_text(
        (tasks / "task-one/task.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    blind_prompt = blind / "prompt.md"
    blind_prompt.write_text("DO NOT READ", encoding="utf-8")
    if linked_entry == "task-directory":
        for path in (tasks / "task-one").iterdir():
            path.unlink()
        (tasks / "task-one").rmdir()
        (tasks / "task-one").symlink_to(blind, target_is_directory=True)
    elif linked_entry == "task-yaml":
        metadata = tasks / "task-one/task.yaml"
        metadata.unlink()
        metadata.symlink_to(blind_metadata)
    else:
        prompt = tasks / "task-one/prompt.md"
        prompt.unlink()
        prompt.symlink_to(blind_prompt)

    def forbidden_loader(_: Path) -> object:
        raise AssertionError("load_tasks must not run for blind input")

    monkeypatch.setattr(qualification, "load_tasks", forbidden_loader)
    with pytest.raises(ValueError, match="blind"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
            enforce_canonical=False,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate-task", "duplicate task ID"),
        ("duplicate-skill", "duplicate skill ID"),
        ("missing-skill", "missing skill"),
        ("mixed-category", "mixed gold"),
        ("slash-task", "must not contain '/'"),
        ("slash-skill", "must not contain '/'"),
    ],
)
def test_input_identity_and_category_validation_fails_closed(
    tmp_path: Path, mutation: str, message: str
):
    root, tasks, skills = _fixture_repo(tmp_path)
    if mutation == "duplicate-task":
        _write_task(tasks, "task-two", task_id="task-one")
    elif mutation == "duplicate-skill":
        payload = json.loads(skills.read_text(encoding="utf-8"))
        payload.append(_skill("alpha-one", "alpha"))
        skills.write_text(json.dumps(payload), encoding="utf-8")
    elif mutation == "missing-skill":
        metadata = tasks / "task-one/task.yaml"
        payload = yaml.safe_load(metadata.read_text(encoding="utf-8"))
        payload["negative_skills"] = ["missing-skill"]
        metadata.write_text(yaml.safe_dump(payload), encoding="utf-8")
    elif mutation == "mixed-category":
        metadata = tasks / "task-one/task.yaml"
        payload = yaml.safe_load(metadata.read_text(encoding="utf-8"))
        payload["gold_skills"] = ["alpha-one", "beta-one"]
        payload["negative_skills"] = []
        metadata.write_text(yaml.safe_dump(payload), encoding="utf-8")
    elif mutation == "slash-task":
        metadata = tasks / "task-one/task.yaml"
        payload = yaml.safe_load(metadata.read_text(encoding="utf-8"))
        payload["id"] = "task/one"
        metadata.write_text(yaml.safe_dump(payload), encoding="utf-8")
    else:
        payload = json.loads(skills.read_text(encoding="utf-8"))
        payload[0]["id"] = "alpha/one"
        skills.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
            enforce_canonical=False,
        )
    assert not (root / "pack").exists()


def test_candidate_query_equals_loader_normalized_prompt_and_hash(tmp_path: Path):
    output = tmp_path / "pack"
    qualify_router_training_data_v2(
        tasks_path=CANONICAL_TASKS,
        skills_index_path=CANONICAL_SKILLS,
        output_dir=output,
        repository_root=REPO_ROOT,
    )
    rows = _read_jsonl(output / "candidate-pairs.jsonl")
    task_by_id = {task.id: task for task in load_tasks(CANONICAL_TASKS)}

    for row in rows:
        query_text = row["query_text"]
        assert isinstance(query_text, str)
        expected_prompt = task_by_id[str(row["task_id"])].prompt
        assert query_text.encode("utf-8") == expected_prompt.encode("utf-8")
        assert (
            hashlib.sha256(query_text.encode("utf-8")).hexdigest()
            == row["prompt_text_sha256"]
        )


@pytest.mark.parametrize(
    ("field", "changed_value"),
    [
        ("id", "renamed-task"),
        ("category", "changed-category"),
        ("difficulty", "hard"),
        ("robustness_tags", ["changed-tag", "second-tag"]),
    ],
)
def test_candidate_query_is_invariant_to_structured_task_metadata(
    tmp_path: Path,
    field: str,
    changed_value: object,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    before = root / "before"
    qualification._qualify_router_training_data_v2(
        tasks_path=tasks,
        skills_index_path=skills,
        output_dir=before,
        repository_root=root,
        enforce_canonical=False,
    )

    metadata = tasks / "task-one/task.yaml"
    payload = yaml.safe_load(metadata.read_text(encoding="utf-8"))
    payload[field] = changed_value
    metadata.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    after = root / "after"
    qualification._qualify_router_training_data_v2(
        tasks_path=tasks,
        skills_index_path=skills,
        output_dir=after,
        repository_root=root,
        enforce_canonical=False,
    )

    def query_bindings(path: Path) -> list[tuple[object, bytes, object]]:
        return [
            (
                row["skill_id"],
                str(row["query_text"]).encode("utf-8"),
                row["prompt_text_sha256"],
            )
            for row in _read_jsonl(path / "candidate-pairs.jsonl")
        ]

    assert query_bindings(before) == query_bindings(after)
    assert {binding[1] for binding in query_bindings(after)} == {
        b"A normalized prompt."
    }


def test_candidate_v3_schema_policy_and_exact_field_set(tmp_path: Path):
    root, tasks, skills = _fixture_repo(tmp_path)
    output = root / "pack"
    qualification._qualify_router_training_data_v2(
        tasks_path=tasks,
        skills_index_path=skills,
        output_dir=output,
        repository_root=root,
        enforce_canonical=False,
    )
    rows = _read_jsonl(output / "candidate-pairs.jsonl")

    assert all(set(row) == EXPECTED_ROW_FIELDS for row in rows)
    assert {row["schema_version"] for row in rows} == {
        "router-training-data-v2-candidate-v3"
    }
    assert {row["artifact_version"] for row in rows} == {3}
    assert {row["policy_id"] for row in rows} == {
        "router-training-data-v2-qualification-v3"
    }
    assert {row["query_text_policy"] for row in rows} == {"prompt_only"}
    assert all(
        {key for key in row if key.endswith("query_text")} == {"query_text"}
        for row in rows
    )


def test_query_contract_definition_is_runtime_immutable():
    assert hasattr(qualification, "QUERY_CONTRACT")
    contract = qualification.QUERY_CONTRACT

    assert isinstance(contract, MappingProxyType)
    assert dict(contract) == {
        key: tuple(value) if isinstance(value, list) else value
        for key, value in EXPECTED_QUERY_CONTRACT.items()
    }


def test_report_and_manifest_use_exact_v3_query_contract(tmp_path: Path):
    root, tasks, skills = _fixture_repo(tmp_path)
    output = root / "pack"
    qualification._qualify_router_training_data_v2(
        tasks_path=tasks,
        skills_index_path=skills,
        output_dir=output,
        repository_root=root,
        enforce_canonical=False,
    )
    report = json.loads((output / "qualification-report.json").read_text())
    manifest = json.loads((output / "manifest.json").read_text())

    assert {
        "manifest_artifact_version": manifest.get("artifact_version"),
        "manifest_policy_id": manifest.get("policy_id"),
        "manifest_query_contract": manifest.get("query_contract"),
        "manifest_schema_version": manifest.get("schema_version"),
        "report_policy_id": report.get("policy_id"),
        "report_query_contract": report.get("query_contract"),
        "report_schema_version": report.get("schema_version"),
    } == {
        "manifest_artifact_version": 3,
        "manifest_policy_id": "router-training-data-v2-qualification-v3",
        "manifest_query_contract": EXPECTED_QUERY_CONTRACT,
        "manifest_schema_version": "router-training-data-v2-manifest-v3",
        "report_policy_id": "router-training-data-v2-qualification-v3",
        "report_query_contract": EXPECTED_QUERY_CONTRACT,
        "report_schema_version": ("router-training-data-v2-qualification-report-v3"),
    }
    assert report["query_contract"] == manifest["query_contract"]


@pytest.mark.parametrize("mixed_artifact", ["candidate", "report", "manifest"])
def test_mixed_v1_v2_v3_artifacts_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mixed_artifact: str,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    if mixed_artifact == "candidate":
        original: Any = qualification._build_candidate_matrix

        def mixed_candidates(*args: Any, **kwargs: Any) -> Any:
            rows = original(*args, **kwargs)
            rows[0]["schema_version"] = "router-training-data-v2-candidate-v2"
            rows[0]["artifact_version"] = 2
            return rows

        monkeypatch.setattr(qualification, "_build_candidate_matrix", mixed_candidates)
    elif mixed_artifact == "report":
        original = qualification._build_qualification_report

        def mixed_report(*args: Any, **kwargs: Any) -> Any:
            report = original(*args, **kwargs)
            report["schema_version"] = "router-training-data-v2-qualification-report-v1"
            report["artifact_version"] = 1
            return report

        monkeypatch.setattr(qualification, "_build_qualification_report", mixed_report)
    else:
        original = qualification._build_manifest

        def mixed_manifest(*args: Any, **kwargs: Any) -> Any:
            manifest = original(*args, **kwargs)
            manifest["schema_version"] = "router-training-data-v2-manifest-v2"
            manifest["artifact_version"] = 2
            return manifest

        monkeypatch.setattr(qualification, "_build_manifest", mixed_manifest)

    with pytest.raises(ValueError, match="mixed v1/v2/v3"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
            enforce_canonical=False,
        )
    assert not (root / "pack").exists()


def test_jointly_stale_report_and_manifest_counts_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    original_report: Any = qualification._build_qualification_report
    original_manifest: Any = qualification._build_manifest

    def stale_report(*args: Any, **kwargs: Any) -> Any:
        report = original_report(*args, **kwargs)
        report["counts"] = {**report["counts"], "matrix_candidate_count": 999}
        return report

    def stale_manifest(*args: Any, **kwargs: Any) -> Any:
        manifest = original_manifest(*args, **kwargs)
        manifest["counts"] = {**manifest["counts"], "matrix_candidate_count": 999}
        return manifest

    monkeypatch.setattr(qualification, "_build_qualification_report", stale_report)
    monkeypatch.setattr(qualification, "_build_manifest", stale_manifest)

    with pytest.raises(
        ValueError, match="qualification counts do not match tasks, skills, and rows"
    ):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
            enforce_canonical=False,
        )
    assert not (root / "pack").exists()


def test_corrupted_candidate_prompt_hash_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    original: Any = qualification._build_candidate_matrix

    def corrupted_hash(*args: Any, **kwargs: Any) -> Any:
        rows = original(*args, **kwargs)
        rows[0]["prompt_text_sha256"] = "0" * 64
        return rows

    monkeypatch.setattr(qualification, "_build_candidate_matrix", corrupted_hash)

    with pytest.raises(
        ValueError, match="candidate query contract does not match rows"
    ):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
            enforce_canonical=False,
        )
    assert not (root / "pack").exists()


def test_jointly_stale_manifest_output_records_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    original: Any = qualification._build_manifest

    def stale_outputs(*args: Any, **kwargs: Any) -> Any:
        manifest = original(*args, **kwargs)
        for record in manifest["outputs"]:
            stale_payload = f"stale:{record['path']}".encode()
            record["bytes"] = len(stale_payload)
            record["sha256"] = hashlib.sha256(stale_payload).hexdigest()
        return manifest

    monkeypatch.setattr(qualification, "_build_manifest", stale_outputs)

    with pytest.raises(
        ValueError, match="manifest outputs do not match candidate and report bytes"
    ):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
            enforce_canonical=False,
        )
    assert not (root / "pack").exists()


@pytest.mark.parametrize(
    "legacy_policy_id",
    [
        "router-training-data-v2-qualification-v1",
        "router-training-data-v2-qualification-v2",
    ],
)
def test_v3_schemas_with_legacy_policy_id_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    legacy_policy_id: str,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    original_candidates: Any = qualification._build_candidate_matrix
    original_report: Any = qualification._build_qualification_report
    original_manifest: Any = qualification._build_manifest

    def legacy_candidates(*args: Any, **kwargs: Any) -> Any:
        rows = original_candidates(*args, **kwargs)
        for row in rows:
            row["policy_id"] = legacy_policy_id
        return rows

    def legacy_report(*args: Any, **kwargs: Any) -> Any:
        report = original_report(*args, **kwargs)
        report["policy_id"] = legacy_policy_id
        return report

    def legacy_manifest(*args: Any, **kwargs: Any) -> Any:
        manifest = original_manifest(*args, **kwargs)
        manifest["policy_id"] = legacy_policy_id
        return manifest

    monkeypatch.setattr(qualification, "_build_candidate_matrix", legacy_candidates)
    monkeypatch.setattr(qualification, "_build_qualification_report", legacy_report)
    monkeypatch.setattr(qualification, "_build_manifest", legacy_manifest)

    with pytest.raises(ValueError, match="mixed v1/v2/v3 qualification policies"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
            enforce_canonical=False,
        )
    assert not (root / "pack").exists()


def test_jointly_stale_report_and_manifest_query_contract_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    original_report: Any = qualification._build_qualification_report
    original_manifest: Any = qualification._build_manifest
    stale_contract = {**EXPECTED_QUERY_CONTRACT, "query_text_policy": "legacy"}

    def stale_report(*args: Any, **kwargs: Any) -> Any:
        report = original_report(*args, **kwargs)
        report["query_contract"] = stale_contract
        return report

    def stale_manifest(*args: Any, **kwargs: Any) -> Any:
        manifest = original_manifest(*args, **kwargs)
        manifest["query_contract"] = stale_contract
        return manifest

    monkeypatch.setattr(qualification, "_build_qualification_report", stale_report)
    monkeypatch.setattr(qualification, "_build_manifest", stale_manifest)

    with pytest.raises(ValueError, match="mixed v1/v2/v3 query contracts"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
            enforce_canonical=False,
        )
    assert not (root / "pack").exists()


def test_canonical_matrix_schema_counts_dispositions_and_report(tmp_path: Path):
    output = tmp_path / "pack"
    result = qualify_router_training_data_v2(
        tasks_path=CANONICAL_TASKS,
        skills_index_path=CANONICAL_SKILLS,
        output_dir=output,
        repository_root=REPO_ROOT,
    )
    rows = _read_jsonl(output / "candidate-pairs.jsonl")
    report = json.loads((output / "qualification-report.json").read_text())

    assert result == report
    assert len(rows) == 192
    assert [str(row["pair_id"]) for row in rows] == sorted(
        str(row["pair_id"]) for row in rows
    )
    assert len({row["pair_id"] for row in rows}) == 192
    assert set(rows[0]) == EXPECTED_ROW_FIELDS
    assert {row["schema_version"] for row in rows} == {
        "router-training-data-v2-candidate-v3"
    }
    assert {row["artifact_version"] for row in rows} == {3}
    assert {row["policy_id"] for row in rows} == {
        "router-training-data-v2-qualification-v3"
    }
    assert sum(row["candidate_type"] == "positive" for row in rows) == 16
    assert (
        sum(row["candidate_type"] == "same_category_negative_candidate" for row in rows)
        == 32
    )
    assert (
        sum(row["candidate_type"] == "cross_category_easy_negative" for row in rows)
        == 144
    )
    assert all(row["accepted_for_training"] is False for row in rows)
    assert sum(row["disposition"] == "RESERVED_SOURCE_TEST" for row in rows) == 64
    assert {row["disposition"] for row in rows if row["source_split"] == "dev"} == {
        "TRAIN_CANDIDATE_POSITIVE",
        "REVIEW_REQUIRED_NEGATIVE_CANDIDATE",
        "EXCLUDED_EASY_NEGATIVE",
    }
    sample = next(row for row in rows if row["task_id"] == "browser-form-regression")
    assert (
        sample["prompt_text_sha256"]
        == hashlib.sha256(
            (CANONICAL_TASKS / "browser-form-regression/prompt.md")
            .read_text(encoding="utf-8")
            .strip()
            .encode("utf-8")
        ).hexdigest()
    )
    assert report["qualification_status"] == "REVIEW_REQUIRED"
    assert report["router_decision"] == "KEEP_BASELINE"
    assert report["can_start_training"] is False
    assert report["artifact_version"] == 3
    assert report["blocker_codes"] == BLOCKER_CODES
    assert report["counts"] == {
        "accepted_train_pair_count": 0,
        "cross_category_easy_negative_count": 144,
        "matrix_candidate_count": 192,
        "positive_count": 16,
        "reject_example_count": 0,
        "reserved_matrix_row_count": 64,
        "reserved_positive_or_same_category_count": 16,
        "same_category_negative_candidate_count": 32,
        "source_pair_count": 28,
        "target_skill_count": 16,
        "task_count": 12,
        "train_policy_candidate_count": 32,
        "train_positive_skill_coverage_count": 11,
    }
    independently_recomputed = _independent_diversity_diagnostics(
        rows,
        {str(row["skill_id"]) for row in rows},
    )
    assert independently_recomputed == EXPECTED_DIVERSITY_DIAGNOSTICS
    assert report["diversity_diagnostics"] == independently_recomputed
    assert all("family" not in row for row in rows)
    assert not (output / "training-pairs.jsonl").exists()
    assert not (output / "training-pairs-v2.jsonl").exists()


def test_manifest_is_portable_hash_bound_and_regeneration_is_byte_identical(
    tmp_path: Path,
):
    first = tmp_path / "first"
    second = tmp_path / "second"
    third = tmp_path / "third"
    for output in (first, second, third):
        qualify_router_training_data_v2(
            tasks_path=CANONICAL_TASKS,
            skills_index_path=CANONICAL_SKILLS,
            output_dir=output,
            repository_root=REPO_ROOT,
        )

    for name in ("candidate-pairs.jsonl", "qualification-report.json", "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
        assert (first / name).read_bytes() == (third / name).read_bytes()

    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((first / "qualification-report.json").read_text())
    assert manifest["schema_version"] == "router-training-data-v2-manifest-v3"
    assert manifest["artifact_version"] == 3
    assert manifest["policy_id"] == "router-training-data-v2-qualification-v3"
    assert manifest["query_contract"] == EXPECTED_QUERY_CONTRACT
    assert report["query_contract"] == manifest["query_contract"]
    expected_per_skill = cast(
        dict[str, int],
        EXPECTED_DIVERSITY_DIAGNOSTICS["per_skill_unique_train_positive_prompt_count"],
    )
    independently_recomputed = _independent_diversity_diagnostics(
        _read_jsonl(first / "candidate-pairs.jsonl"),
        set(expected_per_skill),
    )
    assert report["diversity_diagnostics"] == independently_recomputed
    assert manifest["diversity_diagnostics"] == independently_recomputed
    assert str(REPO_ROOT) not in (first / "manifest.json").read_text(encoding="utf-8")
    assert manifest["inputs"]["task_root"] == "benchmarks/migration-tasks"
    assert manifest["inputs"]["skills_index"]["path"] == (
        "docs/demo/phase9-real-skill-library-migration/skills.json"
    )
    for record in manifest["inputs"]["files"]:
        path = REPO_ROOT / record["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
    for record in manifest["outputs"]:
        path = first / record["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
    for output in (first, second):
        assert not (output / "training-pairs.jsonl").exists()
        assert not (output / "training-pairs-v2.jsonl").exists()
        assert not (output / "accepted-pairs-v3.jsonl").exists()
        assert not (output / "training-input-manifest-v3.json").exists()


def test_existing_protected_and_symlink_redirected_outputs_are_rejected(tmp_path: Path):
    root, tasks, skills = _fixture_repo(tmp_path)
    protected = root / "docs/demo/phase14-finetuned-embedding-router"
    protected.mkdir(parents=True)
    existing = root / "existing"
    existing.mkdir()

    for output in (existing, protected / "new-pack", protected.parent):
        with pytest.raises(ValueError, match="output target"):
            qualification._qualify_router_training_data_v2(
                tasks_path=tasks,
                skills_index_path=skills,
                output_dir=output,
                repository_root=root,
                enforce_canonical=False,
            )

    redirect = root / "redirect"
    redirect.symlink_to(protected, target_is_directory=True)
    with pytest.raises(ValueError, match="protected"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=redirect / "new-pack",
            repository_root=root,
            enforce_canonical=False,
        )
    assert not (protected / "new-pack").exists()


def test_atomic_failure_cleans_temporary_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root, tasks, skills = _fixture_repo(tmp_path)
    output = root / "pack"

    def fail_after_stage(*_: object, **__: object) -> None:
        raise OSError("simulated write failure")

    monkeypatch.setattr(qualification, "_publish_staged_pack", fail_after_stage)
    with pytest.raises(OSError, match="simulated"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=output,
            repository_root=root,
            enforce_canonical=False,
        )
    assert not output.exists()
    assert not list(root.glob(".pack.tmp-*"))


def test_public_v3_rejects_byte_identical_inputs_from_alternate_logical_task_root(
    tmp_path: Path,
):
    root, tasks, skills = _copy_canonical_inputs(tmp_path)
    alternate_tasks = root / "benchmarks/alternate-migration-tasks"
    tasks.rename(alternate_tasks)
    tasks = alternate_tasks
    output = root / "pack"

    with pytest.raises(ValueError, match="canonical task root"):
        qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=output,
            repository_root=root,
        )
    assert not output.exists()


def test_public_v3_rejects_superset_skill_index_snapshot(
    tmp_path: Path,
):
    root, tasks, skills = _copy_canonical_inputs(tmp_path)
    payload = json.loads(skills.read_text(encoding="utf-8"))
    payload.append(_skill("unexpected-superset-skill", "browser-gui"))
    skills.write_text(json.dumps(payload), encoding="utf-8")
    output = root / "pack"

    with pytest.raises(
        ValueError, match="canonical input snapshot|canonical skill IDs"
    ):
        qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=output,
            repository_root=root,
        )
    assert not output.exists()


def test_public_v3_rejects_changed_canonical_task_snapshot(tmp_path: Path):
    root, tasks, skills = _copy_canonical_inputs(tmp_path)
    prompt = tasks / "browser-form-regression/prompt.md"
    prompt.write_bytes(prompt.read_bytes() + b"\nchanged\n")
    output = root / "pack"

    with pytest.raises(ValueError, match="canonical input snapshot"):
        qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=output,
            repository_root=root,
        )
    assert not output.exists()


def test_public_v3_is_portable_across_byte_identical_clone(tmp_path: Path):
    root, tasks, skills = _copy_canonical_inputs(tmp_path)
    output = root / "pack"

    qualify_router_training_data_v2(
        tasks_path=tasks,
        skills_index_path=skills,
        output_dir=output,
        repository_root=root,
    )

    committed = REPO_ROOT / "docs/demo/router-training-data-v2-qualification-pack"
    for name in (
        "candidate-pairs.jsonl",
        "qualification-report.json",
        "manifest.json",
    ):
        assert (output / name).read_bytes() == (committed / name).read_bytes()


@pytest.mark.parametrize("blind_vector", ["root", "directory", "metadata"])
def test_whitespace_padded_blind_identity_stops_before_loader_and_prompt_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    blind_vector: str,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    if blind_vector == "root":
        padded_root = root / "benchmarks/  BLIND-MIGRATION-TASKS  "
        tasks.rename(padded_root)
        tasks = padded_root
    elif blind_vector == "directory":
        (tasks / "task-one").rename(tasks / "  BLIND-task-one  ")
    else:
        metadata = tasks / "task-one/task.yaml"
        payload = yaml.safe_load(metadata.read_text(encoding="utf-8"))
        payload["id"] = "  BLIND-task-one  "
        metadata.write_text(yaml.safe_dump(payload), encoding="utf-8")

    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name == "prompt.md":
            raise AssertionError("prompt content must not be read")
        return original_read_text(path, *args, **kwargs)

    def forbidden_loader(_: Path) -> object:
        raise AssertionError("load_tasks must not run for blind input")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(qualification, "load_tasks", forbidden_loader)
    with pytest.raises(ValueError, match="blind"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
            enforce_canonical=False,
        )
    assert not (root / "pack").exists()


def test_whitespace_padded_loaded_blind_id_is_rejected_defensively(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root, tasks, skills = _fixture_repo(tmp_path)
    loaded = BenchmarkTask(
        id="  BLIND-task-one  ",
        category="migration",
        difficulty="medium",
        prompt="prompt must already have come from a trusted loader",
        gold_skills=["alpha-one"],
        negative_skills=["beta-one"],
        verifier="skill_selection",
        split="dev",
    )
    monkeypatch.setattr(qualification, "load_tasks", lambda _: [loaded])

    with pytest.raises(ValueError, match="blind loaded task ID"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
            enforce_canonical=False,
        )


def test_input_mutation_after_snapshot_fails_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root, tasks, skills = _fixture_repo(tmp_path)
    output = root / "pack"
    original_build: Any = qualification._build_candidate_matrix

    def mutate_after_build(*args: Any, **kwargs: Any) -> list[dict[str, object]]:
        rows = original_build(*args, **kwargs)
        metadata = tasks / "task-one/task.yaml"
        metadata.write_bytes(metadata.read_bytes() + b"\n")
        return rows

    monkeypatch.setattr(qualification, "_build_candidate_matrix", mutate_after_build)
    with pytest.raises(ValueError, match="input changed during qualification"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=output,
            repository_root=root,
            enforce_canonical=False,
        )
    assert not output.exists()


def test_target_created_during_staging_is_preserved_and_publication_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root, tasks, skills = _fixture_repo(tmp_path)
    output = root / "pack"
    original_publish = qualification._publish_staged_pack

    def create_competing_target(stage: Path, files: dict[str, bytes]) -> None:
        original_publish(stage, files)
        output.mkdir()
        (output / "sentinel.txt").write_text("do not replace\n", encoding="utf-8")

    monkeypatch.setattr(
        qualification,
        "_publish_staged_pack",
        create_competing_target,
    )
    with pytest.raises(ValueError, match="output target appeared during staging"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=output,
            repository_root=root,
            enforce_canonical=False,
        )
    assert (output / "sentinel.txt").read_text(encoding="utf-8") == "do not replace\n"
    assert not list(root.glob(".pack.tmp-*"))


@pytest.mark.parametrize("entry_kind", ["task-yaml", "prompt-md", "skills-index"])
def test_input_symlink_retarget_after_snapshot_fails_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry_kind: str,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    sources = root / "entry-sources"
    sources.mkdir()
    if entry_kind == "task-yaml":
        entry = tasks / "task-one/task.yaml"
        alternate_suffix = b"\n# retargeted metadata\n"
    elif entry_kind == "prompt-md":
        entry = tasks / "task-one/prompt.md"
        alternate_suffix = b"\nRetargeted prompt.\n"
    else:
        entry = skills
        alternate_suffix = b"\n"
    original_target = sources / f"{entry_kind}-original"
    original_target.write_bytes(entry.read_bytes())
    alternate_target = sources / f"{entry_kind}-alternate"
    alternate_target.write_bytes(entry.read_bytes() + alternate_suffix)
    entry.unlink()
    entry.symlink_to(original_target)
    output = root / "pack"
    original_loader = qualification.load_tasks

    def retarget_then_load(tasks_path: Path) -> list[BenchmarkTask]:
        entry.unlink()
        entry.symlink_to(alternate_target)
        return original_loader(tasks_path)

    monkeypatch.setattr(qualification, "load_tasks", retarget_then_load)
    with pytest.raises(ValueError, match="input changed during qualification"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=output,
            repository_root=root,
            enforce_canonical=False,
        )
    assert not output.exists()
    assert not list(root.glob(".pack.tmp-*"))


def test_private_qualification_helper_requires_explicit_canonical_choice():
    parameter = inspect.signature(
        qualification._qualify_router_training_data_v2
    ).parameters["enforce_canonical"]

    assert parameter.default is inspect.Parameter.empty


@pytest.mark.parametrize("via_symlink", [False, True])
def test_blind_skills_index_is_rejected_before_read_hash_or_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    via_symlink: bool,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    blind_dir = root / "benchmarks/  BLIND-MIGRATION-TASKS  "
    blind_dir.mkdir(parents=True)
    blind_skills = blind_dir / "skills.json"
    skills.rename(blind_skills)
    skills_entry = root / "skills-link.json" if via_symlink else blind_skills
    if via_symlink:
        skills_entry.symlink_to(blind_skills)
    output = root / "pack"
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path.resolve(strict=False) == blind_skills.resolve(strict=True):
            raise AssertionError("blind skills index must not be read or hashed")
        return original_read_bytes(path)

    def forbidden_skill_loader(_: Path) -> object:
        raise AssertionError("blind skills index must not be loaded")

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    monkeypatch.setattr(qualification, "load_skill_index", forbidden_skill_loader)
    with pytest.raises(ValueError, match="blind"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills_entry,
            output_dir=output,
            repository_root=root,
            enforce_canonical=False,
        )
    assert not output.exists()
    assert not list(root.glob(".pack.tmp-*"))


@pytest.mark.parametrize(
    "blind_segment",
    ["blind-migration-tasks", "  BLIND-MIGRATION-TASKS  "],
)
def test_resolved_output_inside_blind_tree_is_rejected_before_staging(
    tmp_path: Path,
    blind_segment: str,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    blind_parent = root / "benchmarks" / blind_segment
    blind_parent.mkdir(parents=True)
    output = blind_parent / "pack"

    with pytest.raises(ValueError, match="blind"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=output,
            repository_root=root,
            enforce_canonical=False,
        )
    assert not output.exists()
    assert not list(blind_parent.glob(".pack.tmp-*"))


def test_output_symlink_ancestor_redirected_into_blind_tree_is_rejected(
    tmp_path: Path,
):
    root, tasks, skills = _fixture_repo(tmp_path)
    blind_parent = root / "benchmarks/blind-migration-tasks"
    blind_parent.mkdir(parents=True)
    redirect = root / "output-redirect"
    redirect.symlink_to(blind_parent, target_is_directory=True)
    output = redirect / "pack"

    with pytest.raises(ValueError, match="blind"):
        qualification._qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=output,
            repository_root=root,
            enforce_canonical=False,
        )
    assert not (blind_parent / "pack").exists()
    assert not list(blind_parent.glob(".pack.tmp-*"))
