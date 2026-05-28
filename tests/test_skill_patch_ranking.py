import json
from pathlib import Path

import yaml

from hermes_skilleval.skill_patch_ranking import rank_skill_patches


def test_rank_skill_patches_generates_ranked_candidates_for_failed_judge_run(
    tmp_path: Path,
):
    _write_task(
        tmp_path / "tasks",
        "task-001",
        gold=["browser-smoke-testing"],
        negative=["systematic-debugging"],
        expected_evidence=["opened URL", "nonblank page"],
    )
    skills_index = tmp_path / "skills.json"
    skills_index.write_text(
        json.dumps(
            [
                _skill("browser-smoke-testing", ["browser", "smoke"], "Open local pages."),
                _skill("systematic-debugging", ["debug"], "Debug failures."),
            ]
        ),
        encoding="utf-8",
    )
    routes = tmp_path / "routes.jsonl"
    routes.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "router": "hybrid",
                "selected_skill_ids": [
                    "browser-smoke-testing",
                    "systematic-debugging",
                ],
                "gold_skills": ["browser-smoke-testing"],
                "negative_skills": ["systematic-debugging"],
                "scores": {
                    "browser-smoke-testing": 30.0,
                    "systematic-debugging": 20.0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    judge = tmp_path / "judge-results.jsonl"
    judge.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "trace_id": "agent-loop-hybrid:task-001",
                "execution_condition": "routed-skill",
                "judge_pass": False,
                "judge_score": 0.0,
                "evidence_score": 0.0,
                "failure_type": "negative_skill_selected",
                "penalties": ["missing-evidence", "negative-skill-failure"],
                "expected_evidence": ["opened URL", "nonblank page"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = rank_skill_patches(
        judge_results_path=judge,
        routes_path=routes,
        tasks_path=tmp_path / "tasks",
        skills_index_path=skills_index,
        output_dir=tmp_path / "phase12",
    )

    candidates = _read_jsonl(tmp_path / "phase12" / "patch-candidates.jsonl")
    ranked = _read_jsonl(tmp_path / "phase12" / "ranked-patches.jsonl")

    assert summary["phase"] == "Phase 12"
    assert summary["failed_task_count"] == 1
    assert summary["candidate_count"] >= 2
    assert ranked[0]["rank"] == 1
    assert {candidate["rank"] for candidate in candidates} == {None}
    assert ranked[0]["source_task_id"] == "task-001"
    assert ranked[0]["target_skill_id"] == "browser-smoke-testing"
    assert ranked[0]["demote_skill_ids"] == ["systematic-debugging"]
    assert ranked[0]["total_score"] >= ranked[-1]["total_score"]
    assert {candidate["patch_field"] for candidate in candidates} >= {
        "trigger_terms",
        "description",
    }
    assert (tmp_path / "phase12" / "ranking-summary.json").exists()
    assert (tmp_path / "phase12" / "ranked-patches.md").exists()


def test_rank_skill_patches_ignores_passing_judge_records(tmp_path: Path):
    _write_task(
        tmp_path / "tasks",
        "task-001",
        gold=["systematic-debugging"],
        negative=["visual-regression-review"],
        expected_evidence=["root cause note"],
    )
    skills_index = tmp_path / "skills.json"
    skills_index.write_text(
        json.dumps([_skill("systematic-debugging", ["debug"], "Debug failures.")]),
        encoding="utf-8",
    )
    routes = tmp_path / "routes.jsonl"
    routes.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "selected_skill_ids": ["systematic-debugging"],
                "gold_skills": ["systematic-debugging"],
                "negative_skills": ["visual-regression-review"],
                "scores": {"systematic-debugging": 40.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    judge = tmp_path / "judge-results.jsonl"
    judge.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "judge_pass": True,
                "failure_type": None,
                "penalties": [],
                "expected_evidence": ["root cause note"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = rank_skill_patches(
        judge_results_path=judge,
        routes_path=routes,
        tasks_path=tmp_path / "tasks",
        skills_index_path=skills_index,
        output_dir=tmp_path / "phase12",
    )

    assert summary["failed_task_count"] == 0
    assert summary["candidate_count"] == 0
    assert _read_jsonl(tmp_path / "phase12" / "patch-candidates.jsonl") == []


def _write_task(
    root: Path,
    task_id: str,
    *,
    gold: list[str],
    negative: list[str],
    expected_evidence: list[str],
) -> None:
    task_dir = root / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "id": task_id,
                "category": "migration",
                "difficulty": "medium",
                "gold_skills": gold,
                "negative_skills": negative,
                "verifier": "manual",
                "split": "test",
                "robustness_tags": ["migration-evaluation"],
                "expected_evidence": expected_evidence,
                "migration_dimensions": ["evidence completeness"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (task_dir / "prompt.md").write_text(
        "Open the local dashboard and verify a nonblank page.",
        encoding="utf-8",
    )


def _skill(skill_id: str, trigger_terms: list[str], description: str) -> dict[str, object]:
    return {
        "id": skill_id,
        "name": skill_id.replace("-", " ").title(),
        "path": f"benchmarks/migrated-skills/test/{skill_id}/SKILL.md",
        "category": "test",
        "description": description,
        "body": description,
        "trigger_terms": trigger_terms,
        "token_count_estimate": 10,
    }


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
