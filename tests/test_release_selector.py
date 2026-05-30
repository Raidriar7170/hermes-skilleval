from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_skilleval.release_selector import (
    DEFAULT_RELEASE_POLICY,
    select_release_router,
    write_release_decision,
)


def _summary(
    *,
    guard_status: str = "REVIEW_REQUIRED",
    regression_count: int = 2,
    improvement_count: int = 0,
    deltas: dict[str, float] | None = None,
    task_ids: list[str] | None = None,
) -> dict[str, object]:
    metric_deltas = {
        "recall_at_5": 0.0,
        "mrr": -0.03125,
        "ndcg_at_5": -0.023067,
        "negative_hit_rate": 0.0625,
        "negative_accepted_rate": 0.0625,
        "selection_rate_at_5": 0.0,
    }
    if deltas:
        metric_deltas.update(deltas)
    task_ids = task_ids or ["task-a", "task-b"]
    return {
        "phase": "Phase 16",
        "artifact_type": "phase16-blind-validation",
        "task_count": len(task_ids),
        "blind_task_ids": task_ids,
        "guard_status": guard_status,
        "baseline_router": "baseline-minilm",
        "candidate_router": "finetuned-embedding",
        "regression_count": regression_count,
        "improvement_count": improvement_count,
        "metric_deltas": metric_deltas,
        "baseline_mean_metrics": {
            "recall_at_5": 1.0,
            "mrr": 1.0,
            "ndcg_at_5": 1.0,
            "negative_hit_rate": 0.75,
            "negative_accepted_rate": 0.75,
            "selection_rate_at_5": 1.0,
        },
        "candidate_mean_metrics": {
            "recall_at_5": 1.0,
            "mrr": 0.96875,
            "ndcg_at_5": 0.976933,
            "negative_hit_rate": 0.8125,
            "negative_accepted_rate": 0.8125,
            "selection_rate_at_5": 1.0,
        },
        "input_paths": {
            "baseline_results": "docs/demo/phase16-blind-validation/baseline-minilm/results.jsonl",
            "candidate_results": "docs/demo/phase16-blind-validation/finetuned-embedding/results.jsonl",
            "task_root": "benchmarks/blind-migration-tasks",
        },
    }


def _diff(task_id: str, *, regression_flags: list[str] | None = None) -> dict[str, object]:
    regression_flags = regression_flags or []
    return {
        "task_id": task_id,
        "before_selected_skill_ids": ["gold"],
        "after_selected_skill_ids": ["gold", "negative"],
        "gold_skills": ["gold"],
        "negative_skills": ["negative"],
        "before_metrics": {
            "recall_at_5": 1.0,
            "mrr": 1.0,
            "ndcg_at_5": 1.0,
            "negative_hit_rate": 0.0,
            "negative_accepted_rate": 0.0,
            "selection_rate_at_5": 1.0,
        },
        "after_metrics": {
            "recall_at_5": 1.0,
            "mrr": 1.0,
            "ndcg_at_5": 1.0,
            "negative_hit_rate": 1.0,
            "negative_accepted_rate": 1.0,
            "selection_rate_at_5": 1.0,
        },
        "metric_deltas": {
            "recall_at_5": 0.0,
            "mrr": 0.0,
            "ndcg_at_5": 0.0,
            "negative_hit_rate": 1.0,
            "negative_accepted_rate": 1.0,
            "selection_rate_at_5": 0.0,
        },
        "selection_changed": True,
        "regression_flags": regression_flags,
        "improvement_flags": [],
        "applied_candidate_ids": [],
    }


def _write_inputs(
    tmp_path: Path,
    summary: dict[str, object],
    route_diffs: list[dict[str, object]],
) -> tuple[Path, Path]:
    summary_path = tmp_path / "regression-summary.json"
    diffs_path = tmp_path / "route-diffs.jsonl"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    diffs_path.write_text(
        "".join(json.dumps(record) + "\n" for record in route_diffs),
        encoding="utf-8",
    )
    return summary_path, diffs_path


def test_select_release_router_keeps_baseline_for_phase16_regression() -> None:
    decision = select_release_router(
        summary=_summary(),
        route_diffs=[
            _diff("task-a", regression_flags=["negative_hit_rate_increased"]),
            _diff("task-b", regression_flags=["mrr_decreased"]),
        ],
    )

    assert decision["decision"] == "KEEP_BASELINE"
    assert decision["selected_router"] == "baseline-minilm"
    assert decision["candidate_router"] == "finetuned-embedding"
    assert decision["approved_for_default"] is False
    assert decision["policy"] == DEFAULT_RELEASE_POLICY
    assert "regression_count exceeds policy" in decision["reasons"]


def test_select_release_router_approves_candidate_when_guard_and_policy_pass() -> None:
    decision = select_release_router(
        summary=_summary(
            guard_status="PASS",
            regression_count=0,
            improvement_count=1,
            deltas={
                "recall_at_5": 0.01,
                "mrr": 0.0,
                "ndcg_at_5": 0.02,
                "negative_hit_rate": -0.05,
                "negative_accepted_rate": 0.0,
            },
        ),
        route_diffs=[_diff("task-a"), _diff("task-b")],
    )

    assert decision["decision"] == "APPROVE_CANDIDATE"
    assert decision["selected_router"] == "finetuned-embedding"
    assert decision["approved_for_default"] is True
    assert decision["task_decisions"][0]["decision"] == "NO_CHANGE"


@pytest.mark.parametrize(
    ("summary", "route_diffs", "expected_reason"),
    [
        (_summary(task_ids=["task-a", "task-c"]), [_diff("task-a"), _diff("task-b")], "task ids mismatch"),
        (_summary(), [_diff("task-a"), _diff("task-a")], "duplicate task ids"),
        ({**_summary(), "artifact_type": "wrong"}, [_diff("task-a"), _diff("task-b")], "wrong artifact_type"),
        (
            _summary(deltas={"mrr": "bad"}),  # type: ignore[dict-item]
            [_diff("task-a"), _diff("task-b")],
            "metric_deltas.mrr must be numeric",
        ),
        (
            {key: value for key, value in _summary().items() if key != "guard_status"},
            [_diff("task-a"), _diff("task-b")],
            "guard_status must be a non-empty string",
        ),
        (
            _summary(),
            [
                {key: value for key, value in _diff("task-a").items() if key != "metric_deltas"},
                _diff("task-b"),
            ],
            "route diff record 0 metric_deltas must be an object",
        ),
        (
            _summary(),
            [
                {
                    **_diff("task-a"),
                    "metric_deltas": {
                        key: value
                        for key, value in _diff("task-a")["metric_deltas"].items()
                        if key != "mrr"
                    },
                },
                _diff("task-b"),
            ],
            "route diff record 0 metric_deltas.mrr must be numeric",
        ),
        (
            _summary(),
            [
                {
                    **_diff("task-a"),
                    "metric_deltas": {
                        **_diff("task-a")["metric_deltas"],
                        "mrr": True,
                    },
                },
                _diff("task-b"),
            ],
            "route diff record 0 metric_deltas.mrr must be numeric",
        ),
        (
            _summary(),
            [
                {
                    **_diff("task-a"),
                    "metric_deltas": {
                        **_diff("task-a")["metric_deltas"],
                        "mrr": "bad",
                    },
                },
                _diff("task-b"),
            ],
            "route diff record 0 metric_deltas.mrr must be numeric",
        ),
        (_summary(), [{"task_id": "task-a"}, "not-a-dict"], "route diff record 1 must be an object"),
    ],
)
def test_select_release_router_returns_review_required_for_invalid_inputs(
    summary: dict[str, object],
    route_diffs: list[object],
    expected_reason: str,
) -> None:
    decision = select_release_router(summary=summary, route_diffs=route_diffs)

    assert decision["decision"] == "REVIEW_REQUIRED"
    assert decision["selected_router"] is None
    assert decision["approved_for_default"] is False
    assert any(expected_reason in reason for reason in decision["reasons"])


def test_select_release_router_returns_review_required_for_missing_input_paths(
    tmp_path: Path,
) -> None:
    decision = select_release_router(
        summary=tmp_path / "missing-summary.json",
        route_diffs=tmp_path / "missing-diffs.jsonl",
    )

    assert decision["decision"] == "REVIEW_REQUIRED"
    assert decision["approved_for_default"] is False
    assert any("missing regression summary" in reason for reason in decision["reasons"])
    assert any("missing route diffs" in reason for reason in decision["reasons"])


def test_select_release_router_raises_value_error_for_malformed_json(tmp_path: Path) -> None:
    summary_path = tmp_path / "regression-summary.json"
    diffs_path = tmp_path / "route-diffs.jsonl"
    summary_path.write_text("{not-json", encoding="utf-8")
    diffs_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError):
        select_release_router(summary=summary_path, route_diffs=diffs_path)


def test_write_release_decision_writes_json_markdown_and_jsonl(tmp_path: Path) -> None:
    summary_path, diffs_path = _write_inputs(
        tmp_path,
        _summary(),
        [
            _diff("task-a", regression_flags=["negative_hit_rate_increased"]),
            _diff("task-b", regression_flags=["mrr_decreased"]),
        ],
    )
    output_dir = tmp_path / "phase17"

    decision = write_release_decision(
        regression_summary_path=summary_path,
        route_diffs_path=diffs_path,
        output_dir=output_dir,
    )

    assert decision["decision"] == "KEEP_BASELINE"
    assert (output_dir / "release-decision.json").is_file()
    assert (output_dir / "release-decision.md").is_file()
    assert (output_dir / "task-decisions.jsonl").is_file()
    written = json.loads((output_dir / "release-decision.json").read_text())
    assert written["artifact_type"] == "phase17-calibrated-release-selector"
    task_lines = (output_dir / "task-decisions.jsonl").read_text().splitlines()
    assert len(task_lines) == decision["task_count"]
    assert "# Phase 17 Calibrated Release Selector" in (
        output_dir / "release-decision.md"
    ).read_text(encoding="utf-8")
