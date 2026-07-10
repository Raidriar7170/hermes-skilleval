from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

import hermes_skilleval.router_training_data_v2 as qualification
from hermes_skilleval.router_training_data_v2 import (
    BLOCKER_CODES,
    qualify_router_training_data_v2,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_TASKS = REPO_ROOT / "benchmarks/migration-tasks"
CANONICAL_SKILLS = (
    REPO_ROOT / "docs/demo/phase9-real-skill-library-migration/skills.json"
)


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


def test_v1_blockers_are_exact_and_sorted():
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
        qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
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
        qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
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
        qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=root / "pack",
            repository_root=root,
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
    assert [row["pair_id"] for row in rows] == sorted(row["pair_id"] for row in rows)
    assert len({row["pair_id"] for row in rows}) == 192
    assert set(rows[0]) == {
        "accepted_for_training",
        "candidate_type",
        "disposition",
        "label",
        "pair_id",
        "prompt_text_sha256",
        "query_text",
        "schema_version",
        "skill_id",
        "skill_text",
        "source",
        "source_split",
        "task_id",
    }
    assert {row["schema_version"] for row in rows} == {
        "router-training-data-v2-candidate-v1"
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
    assert not (output / "training-pairs.jsonl").exists()


def test_manifest_is_portable_hash_bound_and_regeneration_is_byte_identical(
    tmp_path: Path,
):
    first = tmp_path / "first"
    second = tmp_path / "second"
    for output in (first, second):
        qualify_router_training_data_v2(
            tasks_path=CANONICAL_TASKS,
            skills_index_path=CANONICAL_SKILLS,
            output_dir=output,
            repository_root=REPO_ROOT,
        )

    for name in ("candidate-pairs.jsonl", "qualification-report.json", "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()

    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["policy_id"] == "router-training-data-v2-qualification-v1"
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


def test_existing_protected_and_symlink_redirected_outputs_are_rejected(tmp_path: Path):
    root, tasks, skills = _fixture_repo(tmp_path)
    protected = root / "docs/demo/phase14-finetuned-embedding-router"
    protected.mkdir(parents=True)
    existing = root / "existing"
    existing.mkdir()

    for output in (existing, protected / "new-pack", protected.parent):
        with pytest.raises(ValueError, match="output target"):
            qualify_router_training_data_v2(
                tasks_path=tasks,
                skills_index_path=skills,
                output_dir=output,
                repository_root=root,
            )

    redirect = root / "redirect"
    redirect.symlink_to(protected, target_is_directory=True)
    with pytest.raises(ValueError, match="protected"):
        qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=redirect / "new-pack",
            repository_root=root,
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
        qualify_router_training_data_v2(
            tasks_path=tasks,
            skills_index_path=skills,
            output_dir=output,
            repository_root=root,
        )
    assert not output.exists()
    assert not list(root.glob(".pack.tmp-*"))
