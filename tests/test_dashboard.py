import json
from pathlib import Path

import pytest

from hermes_skilleval.dashboard import build_dashboard_payload


def test_build_dashboard_payload_loads_child_runs_and_summaries(tmp_path: Path):
    _write_run(
        tmp_path,
        "alpha-router",
        [
            {
                "task_id": "task-001",
                "router": "alpha",
                "split": "test",
                "category": "infra",
                "difficulty": "easy",
                "selected_skill_ids": ["docker"],
                "gold_skills": ["docker"],
                "negative_skills": ["academic-writing"],
                "recall_at_5": 1.0,
                "mrr": 1.0,
                "ndcg_at_5": 1.0,
                "negative_hit_rate": 0.0,
                "abstention_rate": 0.0,
                "selection_rate_at_5": 0.2,
                "latency_ms": 12.0,
                "scores": {"docker": 3.0, "academic-writing": -2.0},
            },
            {
                "task_id": "task-002",
                "router": "alpha",
                "split": "test",
                "category": "infra",
                "difficulty": "hard",
                "selected_skill_ids": ["academic-writing"],
                "gold_skills": ["docker"],
                "negative_skills": ["academic-writing"],
                "recall_at_5": 0.0,
                "mrr": 0.0,
                "ndcg_at_5": 0.0,
                "negative_hit_rate": 1.0,
                "abstention_rate": 0.0,
                "selection_rate_at_5": 0.2,
                "latency_ms": 18.0,
            },
        ],
    )
    _write_run(
        tmp_path,
        "beta-router",
        [
            {
                "task_id": "task-003",
                "router": "beta",
                "split": "dev",
                "category": "writing",
                "difficulty": "medium",
                "selected_skill_ids": [],
                "gold_skills": ["academic-writing"],
                "negative_skills": ["docker"],
                "latency_ms": 20.0,
            }
        ],
    )

    payload = build_dashboard_payload(tmp_path)
    data = payload.to_json_dict()

    assert [run["label"] for run in data["runs"]] == ["alpha-router", "beta-router"]
    assert data["runs"][0]["task_count"] == 2
    assert data["runs"][0]["metrics"]["recall_at_5"] == 0.5
    assert data["runs"][0]["metrics"]["negative_hit_rate"] == 0.5
    assert data["runs"][1]["metrics"]["abstention_rate"] == 1.0
    assert len(data["records"]) == 3
    assert data["records"][1]["failure_tags"] == ["recall-miss", "negative-hit", "low-selection"]
    assert data["records"][2]["failure_tags"] == ["recall-miss", "abstained", "low-selection"]
    assert data["records"][0]["score_ranking"][0] == {"skill_id": "docker", "score": 3.0}
    assert data["filters"]["runs"] == ["alpha-router", "beta-router"]
    assert data["filters"]["splits"] == ["dev", "test"]
    assert data["filters"]["categories"] == ["infra", "writing"]
    assert data["filters"]["difficulties"] == ["easy", "hard", "medium"]
    assert data["filters"]["failure_tags"] == ["abstained", "low-selection", "negative-hit", "recall-miss"]


def test_build_dashboard_payload_requires_run_results(tmp_path: Path):
    with pytest.raises(ValueError, match="no dashboard runs found"):
        build_dashboard_payload(tmp_path)


def test_build_dashboard_payload_failure_tags_follow_spec_thresholds(tmp_path: Path):
    _write_run(
        tmp_path,
        "thresholds",
        [
            {
                "task_id": "partial-recall",
                "router": "alpha",
                "selected_skill_ids": ["docker", "python-packaging"],
                "gold_skills": ["docker", "observability"],
                "negative_skills": [],
                "recall_at_5": 0.5,
                "abstention_rate": 0.0,
                "selection_rate_at_5": 1.0,
                "latency_ms": 10.0,
            },
            {
                "task_id": "partial-abstention",
                "router": "alpha",
                "selected_skill_ids": ["docker", "python-packaging", "observability"],
                "gold_skills": ["docker"],
                "negative_skills": [],
                "recall_at_5": 1.0,
                "abstention_rate": 0.25,
                "selection_rate_at_5": 1.0,
                "latency_ms": 11.0,
            },
            {
                "task_id": "partial-selection",
                "router": "alpha",
                "selected_skill_ids": ["docker", "python-packaging"],
                "gold_skills": ["docker"],
                "negative_skills": [],
                "recall_at_5": 1.0,
                "abstention_rate": 0.0,
                "selection_rate_at_5": 0.4,
                "latency_ms": 12.0,
            },
        ],
    )

    data = build_dashboard_payload(tmp_path).to_json_dict()

    assert data["records"][0]["failure_tags"] == ["recall-miss"]
    assert data["records"][1]["failure_tags"] == ["abstained"]
    assert data["records"][2]["failure_tags"] == ["low-selection"]


def test_build_dashboard_payload_preserves_source_prompt_and_raw(tmp_path: Path):
    _write_run(
        tmp_path,
        "with-context",
        [
            {
                "task_id": "task-context",
                "router": "alpha",
                "prompt": "Use Docker to package the service.",
                "split": "dev",
                "category": "infra",
                "difficulty": "easy",
                "selected_skill_ids": ["docker"],
                "gold_skills": ["docker"],
                "negative_skills": [],
                "latency_ms": 15.0,
                "scores": {"beta": 1.0, "alpha": 1.0, "ignored": "bad"},
            }
        ],
    )

    data = build_dashboard_payload(tmp_path).to_json_dict()

    assert data["source_path"] == str(tmp_path)
    assert data["runs"][0]["source_path"] == str(tmp_path / "with-context" / "results.jsonl")
    assert data["records"][0]["prompt"] == "Use Docker to package the service."
    assert data["records"][0]["raw"]["task_id"] == "task-context"
    assert data["records"][0]["raw"]["prompt"] == "Use Docker to package the service."
    assert data["records"][0]["score_ranking"] == [
        {"skill_id": "alpha", "score": 1.0},
        {"skill_id": "beta", "score": 1.0},
    ]


def test_build_dashboard_payload_rejects_invalid_present_metric(tmp_path: Path):
    _write_run(
        tmp_path,
        "invalid-metric",
        [
            {
                "task_id": "task-invalid",
                "router": "alpha",
                "selected_skill_ids": ["docker"],
                "gold_skills": ["docker"],
                "negative_skills": [],
                "recall_at_5": "1.0",
                "latency_ms": 10.0,
            }
        ],
    )

    with pytest.raises(
        ValueError,
        match=r"field 'recall_at_5' must be finite .*results\.jsonl at line 1",
    ):
        build_dashboard_payload(tmp_path)


def test_build_dashboard_payload_rejects_invalid_skill_list_with_context(tmp_path: Path):
    _write_run(
        tmp_path,
        "invalid-list",
        [
            {
                "task_id": "task-invalid",
                "router": "alpha",
                "selected_skill_ids": ["docker", 42],
                "gold_skills": ["docker"],
                "negative_skills": [],
                "latency_ms": 10.0,
            }
        ],
    )

    with pytest.raises(
        ValueError,
        match=r"field 'selected_skill_ids' must be a list of strings .*results\.jsonl at line 1",
    ):
        build_dashboard_payload(tmp_path)


def test_build_dashboard_payload_reports_physical_line_after_blank_lines(tmp_path: Path):
    run_dir = tmp_path / "blank-lines"
    run_dir.mkdir()
    (run_dir / "results.jsonl").write_text(
        "\n"
        + json.dumps(
            {
                "task_id": "task-invalid",
                "router": "alpha",
                "selected_skill_ids": "docker",
                "gold_skills": ["docker"],
                "negative_skills": [],
                "latency_ms": 10.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"field 'selected_skill_ids' must be a list of strings .*results\.jsonl at line 2",
    ):
        build_dashboard_payload(tmp_path)


def _write_run(root: Path, label: str, records: list[dict[str, object]]) -> None:
    run_dir = root / label
    run_dir.mkdir(parents=True)
    (run_dir / "results.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
