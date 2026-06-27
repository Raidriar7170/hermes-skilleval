import gzip
import json
import shutil
from pathlib import Path

import pytest

from hermes_skilleval.external.skillrouter import SkillRouterAdapter
from hermes_skilleval.external.skillrouter import write_external_validation


FIXTURE = Path(__file__).parent / "fixtures" / "external" / "skillrouter_tiny"
EVAL_CORE_FIXTURE = (
    Path(__file__).parent / "fixtures" / "external" / "skillrouter_eval_core_tiny"
)
FIXTURE_PROVENANCE = {
    "upstream_ref": "fixture-ref",
    "license_note": "fixture-only",
    "acquired_at": "2026-06-27",
}


def _copy_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "skillrouter"
    shutil.copytree(FIXTURE, root)
    return root


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def test_skillrouter_adapter_loads_canonical_records_and_preserves_metadata():
    adapter = SkillRouterAdapter(
        data_root=FIXTURE,
        **FIXTURE_PROVENANCE,
    )

    tasks = adapter.load_tasks()
    easy_skills = list(adapter.iter_skills("easy"))
    hard_skills = list(adapter.iter_skills("hard"))
    validation = adapter.validate()

    assert [task.task_id for task in tasks] == ["task-easy-001", "task-hard-001"]
    assert tasks[0].benchmark_id == "skillrouter"
    assert tasks[0].query == "Need browser automation for a login form"
    assert tasks[0].task_type == "single"
    assert tasks[0].graded_relevance == {"browser-login": 3.0}
    assert tasks[0].metadata["upstream_extra"] == "kept-task"
    assert [skill.skill_id for skill in easy_skills] == ["browser-login"]
    assert [skill.skill_id for skill in hard_skills] == [
        "workflow-debugging",
        "tdd-helper",
    ]
    assert easy_skills[0].metadata["license"] == "fixture-only"
    assert validation["status"] == "PASS"
    assert validation["task_count"] == 2
    assert validation["skill_count_by_tier"] == {"easy": 1, "hard": 2}
    assert validation["relevance_count"] == 3


def test_skillrouter_adapter_loads_official_eval_core_fixture():
    adapter = SkillRouterAdapter(data_root=EVAL_CORE_FIXTURE, **FIXTURE_PROVENANCE)

    tasks = adapter.load_tasks()
    easy_skills = list(adapter.iter_skills("easy"))
    hard_skills = list(adapter.iter_skills("hard"))
    validation = adapter.validate()
    manifest = adapter.provenance(validation)

    task_by_id = {task.task_id: task for task in tasks}
    assert validation["status"] == "PASS"
    assert validation["task_count"] == 4
    assert validation["skill_count_by_tier"] == {"easy": 3, "hard": 3}
    assert validation["relevance_count"] == 6
    assert task_by_id["task-single-easy"].query == (
        "Use browser automation to submit a login form."
    )
    assert task_by_id["task-single-easy"].task_type == "single_skill"
    assert task_by_id["task-single-easy"].tier == "easy"
    assert task_by_id["task-single-easy"].metadata["difficulty"] == "easy"
    assert task_by_id["task-single-easy"].metadata["num_skills"] == 1
    assert task_by_id["task-single-easy"].metadata["skill_names"] == ["Browser Login"]
    assert task_by_id["task-single-easy"].metadata["domain"] == "web"
    assert task_by_id["task-single-easy"].metadata["excluded"] is False
    assert task_by_id["task-single-easy"].graded_relevance == {
        "gt/browser-login": 3,
        "degraded/browser-login": 1,
    }
    assert task_by_id["task-generic-easy"].task_type == "generic_only"
    assert task_by_id["task-generic-easy"].graded_relevance == {}
    assert task_by_id["task-medium-easy-pool"].tier == "medium"
    assert task_by_id["task-medium-easy-pool"].graded_relevance == {
        "gt/medium-easy": 3
    }
    assert [skill.skill_id for skill in easy_skills] == [
        "gt/browser-login",
        "degraded/browser-login",
        "gt/medium-easy",
    ]
    assert {skill.skill_id for skill in hard_skills} == {
        "degraded/workflow-debugging",
        "gt/tdd-helper",
        "gt/workflow-debugging",
    }
    assert {record["path"] for record in manifest["files"]} == {
        "tasks.jsonl",
        "relevance.json",
        "manifest.json",
        "easy/shard-000.jsonl.gz",
        "hard/shard-000.jsonl.gz",
    }
    for record in manifest["files"]:
        assert record["sha256"]
    assert str(EVAL_CORE_FIXTURE.parent) not in json.dumps(manifest)


def test_skillrouter_validation_allows_auxiliary_relevance_absent_from_tier(tmp_path):
    root = tmp_path / "skillrouter_eval_core"
    shutil.copytree(EVAL_CORE_FIXTURE, root)
    easy_shard = root / "easy" / "shard-000.jsonl.gz"
    records = [
        {
            "id": "gt/browser-login",
            "name": "Browser Login",
            "description": "Submit login forms",
            "body": "Use browser automation to fill credentials and submit forms.",
            "tier": "easy",
        }
    ]
    with gzip.open(easy_shard, "wt", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, sort_keys=True) + "\n")
    adapter = SkillRouterAdapter(data_root=root, **FIXTURE_PROVENANCE)

    validation = adapter.validate()

    assert validation["status"] == "PASS"


def test_skillrouter_adapter_manifest_records_hashes_and_mapping():
    adapter = SkillRouterAdapter(
        data_root=FIXTURE,
        **FIXTURE_PROVENANCE,
    )

    manifest = adapter.provenance()

    assert manifest["schema_version"] == "v0.3.external-run-manifest.v1"
    assert manifest["adapter"] == "skillrouter"
    assert manifest["adapter_version"]
    assert manifest["upstream_repo"] == "zhengyanzhao1997/SkillRouter"
    assert manifest["upstream_ref"] == "fixture-ref"
    assert manifest["license_note"] == "fixture-only"
    assert manifest["acquired_at"] == "2026-06-27"
    assert manifest["data_root_label"] == "skillrouter_tiny"
    assert str(FIXTURE.parent) not in json.dumps(manifest)
    assert manifest["mapping"]["task_id"] == ["id", "task_id"]
    assert {record["role"] for record in manifest["files"]} == {
        "tasks",
        "relevance",
        "skills:easy",
        "skills:hard",
    }
    for record in manifest["files"]:
        assert record["sha256"]
        assert record["size_bytes"] > 0
        assert record["record_count"] >= 1


def test_skillrouter_adapter_supports_gzipped_skill_shards(tmp_path):
    root = _copy_fixture(tmp_path)
    hard_dir = root / "skills" / "hard"
    for path in hard_dir.glob("*.jsonl"):
        path.unlink()
    payload = (
        '{"id":"workflow-debugging","name":"Workflow Debugging","description":"Debug workflows","body":"Body","tier":"hard"}\n'
        '{"id":"tdd-helper","name":"TDD Helper","description":"TDD","body":"Body","tier":"hard"}\n'
    )
    with gzip.open(hard_dir / "hard.jsonl.gz", "wt", encoding="utf-8") as file:
        file.write(payload)

    adapter = SkillRouterAdapter(data_root=root, **FIXTURE_PROVENANCE)

    assert [skill.skill_id for skill in adapter.iter_skills("hard")] == [
        "workflow-debugging",
        "tdd-helper",
    ]
    assert adapter.validate()["status"] == "PASS"


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda root: _write_jsonl(
                root / "tasks.jsonl",
                [
                    {
                        "id": "task-easy-001",
                        "query": "first",
                        "tier": "easy",
                        "task_type": "single",
                    },
                    {
                        "id": "task-easy-001",
                        "query": "duplicate",
                        "tier": "easy",
                        "task_type": "single",
                    },
                ],
            ),
            "duplicate task id",
        ),
        (
            lambda root: _write_jsonl(
                root / "tasks.jsonl",
                [
                    {
                        "id": "task-empty",
                        "query": " ",
                        "tier": "easy",
                        "task_type": "single",
                    }
                ],
            ),
            "query must be a non-empty string",
        ),
        (
            lambda root: _write_jsonl(
                root / "tasks.jsonl",
                [
                    {
                        "id": "",
                        "query": "empty id",
                        "tier": "easy",
                        "task_type": "single",
                    }
                ],
            ),
            "task id must be a non-empty string",
        ),
        (
            lambda root: _write_jsonl(
                root / "skills" / "easy.jsonl",
                [
                    {
                        "id": "browser-login",
                        "name": "Browser Login",
                        "description": "A",
                        "body": "A",
                        "tier": "easy",
                    },
                    {
                        "id": "browser-login",
                        "name": "Duplicate Browser Login",
                        "description": "B",
                        "body": "B",
                        "tier": "easy",
                    },
                ],
            ),
            "duplicate skill id",
        ),
        (
            lambda root: (root / "relevance.jsonl").write_text("", encoding="utf-8"),
            "missing relevance",
        ),
        (
            lambda root: _write_jsonl(
                root / "relevance.jsonl",
                [
                    {
                        "task_id": "task-easy-001",
                        "skill_id": "missing-skill",
                        "relevance": 3,
                        "tier": "easy",
                    }
                ],
            ),
            "relevant skill missing from tier",
        ),
        (
            lambda root: _write_jsonl(
                root / "skills" / "easy.jsonl",
                [
                    {
                        "id": "browser-login",
                        "name": "Browser Login",
                        "description": "A",
                        "body": "A",
                        "tier": "hard",
                    }
                ],
            ),
            "tier mismatch",
        ),
    ],
)
def test_skillrouter_adapter_validation_failures(tmp_path, mutate, expected):
    root = _copy_fixture(tmp_path)
    mutate(root)
    adapter = SkillRouterAdapter(data_root=root, **FIXTURE_PROVENANCE)

    validation = adapter.validate()

    assert validation["status"] == "INVALID"
    assert any(expected in error for error in validation["errors"])


def test_skillrouter_adapter_rejects_corrupt_gzip(tmp_path):
    root = _copy_fixture(tmp_path)
    hard_dir = root / "skills" / "hard"
    for path in hard_dir.glob("*.jsonl"):
        path.unlink()
    (hard_dir / "broken.jsonl.gz").write_bytes(b"not gzip")
    adapter = SkillRouterAdapter(data_root=root, **FIXTURE_PROVENANCE)

    validation = adapter.validate()

    assert validation["status"] == "INVALID"
    assert any("broken.jsonl.gz" in error for error in validation["errors"])


def test_skillrouter_adapter_manifest_survives_corrupt_gzip(tmp_path):
    root = _copy_fixture(tmp_path)
    hard_dir = root / "skills" / "hard"
    for path in hard_dir.glob("*.jsonl"):
        path.unlink()
    (hard_dir / "broken.jsonl.gz").write_bytes(b"not gzip")
    adapter = SkillRouterAdapter(data_root=root, **FIXTURE_PROVENANCE)
    validation = adapter.validate()

    manifest = adapter.provenance(validation)

    broken_record = next(
        record for record in manifest["files"] if record["path"].endswith("broken.jsonl.gz")
    )
    assert manifest["validation_status"] == "INVALID"
    assert broken_record["sha256"]
    assert broken_record["record_count"] is None
    assert "read_error" in broken_record
    assert str(tmp_path) not in json.dumps(manifest)
    assert str(tmp_path) not in json.dumps(validation)


def test_skillrouter_adapter_manifest_survives_missing_skill_tier(tmp_path):
    root = _copy_fixture(tmp_path)
    shutil.rmtree(root / "skills" / "hard")
    output_dir = tmp_path / "out"

    with pytest.raises(ValueError, match="external validation failed"):
        write_external_validation(data_root=root, output_dir=output_dir)

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((output_dir / "validation.json").read_text(encoding="utf-8"))
    hard_record = next(record for record in manifest["files"] if record["role"] == "skills:hard")
    assert validation["status"] == "INVALID"
    assert manifest["validation_status"] == "INVALID"
    assert hard_record["path"] is None
    assert hard_record["sha256"] is None
    assert "missing skill shard" in hard_record["read_error"]
    assert str(tmp_path) not in json.dumps(manifest)
    assert str(tmp_path) not in json.dumps(validation)


def test_skillrouter_validation_errors_do_not_persist_absolute_paths(tmp_path):
    root = _copy_fixture(tmp_path)
    (root / "tasks.jsonl").write_text('{"id": ', encoding="utf-8")
    output_dir = tmp_path / "out"

    with pytest.raises(ValueError, match="external validation failed"):
        write_external_validation(
            data_root=root,
            output_dir=output_dir,
            **FIXTURE_PROVENANCE,
        )

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((output_dir / "validation.json").read_text(encoding="utf-8"))
    assert str(tmp_path) not in json.dumps(manifest)
    assert str(tmp_path) not in json.dumps(validation)
    assert any("tasks.jsonl" in error for error in validation["errors"])


def test_skillrouter_adapter_requires_real_provenance_metadata():
    adapter = SkillRouterAdapter(data_root=FIXTURE)

    validation = adapter.validate()

    assert validation["status"] == "INVALID"
    assert any("upstream_ref must be set" in error for error in validation["errors"])
    assert any("license_note must be set" in error for error in validation["errors"])


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda root: _write_jsonl(
                root / "tasks.jsonl",
                [
                    {
                        "id": "task-single-easy",
                        "instruction_text": "first",
                        "difficulty": "easy",
                    },
                    {
                        "id": "task-single-easy",
                        "instruction_text": "duplicate",
                        "difficulty": "easy",
                    },
                ],
            ),
            "duplicate task id",
        ),
        (
            lambda root: _write_jsonl(
                root / "tasks.jsonl",
                [
                    {
                        "id": "task-empty-instruction",
                        "instruction_text": " ",
                        "difficulty": "easy",
                    }
                ],
            ),
            "query must be a non-empty string",
        ),
        (
            lambda root: (root / "relevance.json").write_text("{}", encoding="utf-8"),
            "missing relevance entry",
        ),
        (
            lambda root: shutil.rmtree(root / "hard"),
            "missing skill shard for tier hard",
        ),
        (
            lambda root: (root / "relevance.json").write_text(
                json.dumps(
                    {
                        "task-single-easy": {
                            "task_type": "single_skill",
                            "gt_skill_ids": ["gt/missing"],
                            "core_gt_ids": ["gt/missing"],
                            "auxiliary_gt_ids": [],
                            "relevance": {"gt/missing": 3},
                        },
                        "task-multi-hard": {
                            "task_type": "multi_skill",
                            "gt_skill_ids": ["gt/workflow-debugging"],
                            "core_gt_ids": ["gt/workflow-debugging"],
                            "auxiliary_gt_ids": [],
                            "relevance": {"gt/workflow-debugging": 3},
                        },
                        "task-generic-easy": {
                            "task_type": "generic_only",
                            "gt_skill_ids": [],
                            "core_gt_ids": [],
                            "auxiliary_gt_ids": [],
                            "relevance": {},
                        },
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            ),
            "relevant skill missing from tier easy",
        ),
    ],
)
def test_skillrouter_eval_core_fixture_validation_failures(tmp_path, mutate, expected):
    root = tmp_path / "skillrouter_eval_core"
    shutil.copytree(EVAL_CORE_FIXTURE, root)
    mutate(root)
    adapter = SkillRouterAdapter(data_root=root, **FIXTURE_PROVENANCE)

    validation = adapter.validate()

    assert validation["status"] == "INVALID"
    assert any(expected in error for error in validation["errors"])
