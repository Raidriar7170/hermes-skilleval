import json
from pathlib import Path

import pytest

from hermes_skilleval.agent_judge import judge_agent_loop


def test_judge_agent_loop_scores_trace_evidence_and_writes_artifacts(tmp_path: Path):
    traces = tmp_path / "agent-traces.jsonl"
    traces.write_text(
        json.dumps(
            {
                "trace_schema_version": "phase10.agent-loop.v1",
                "trace_id": "agent-loop-hybrid:task-001",
                "task_id": "task-001",
                "prompt": "Fix the regression and include evidence.",
                "execution_condition": "routed-skill",
                "source_router": "hybrid",
                "selected_skill_ids": ["systematic-debugging"],
                "agent_status": "passed",
                "agent_success": True,
                "expected_evidence": ["failing test reproduced", "fix verified"],
                "evidence_checks": [
                    {"name": "failing test reproduced", "satisfied": True},
                    {"name": "fix verified", "satisfied": True},
                ],
                "failure_type": None,
                "failure_reason": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "judge"

    summary = judge_agent_loop(
        traces_path=traces,
        output_dir=output_dir,
        run_label="judge-agent-loop-hybrid",
    )

    judge_records = _read_jsonl(output_dir / "judge-results.jsonl")
    dashboard_records = _read_jsonl(output_dir / "results.jsonl")

    assert summary["judge_pass_rate"] == 1.0
    assert summary["mean_judge_score"] == 1.0
    assert judge_records[0]["judge_status"] == "passed"
    assert judge_records[0]["judge_score"] == 1.0
    assert judge_records[0]["evidence_score"] == 1.0
    assert judge_records[0]["prompt"] == "Fix the regression and include evidence."
    assert dashboard_records[0]["router"] == "judge-agent-loop-hybrid"
    assert dashboard_records[0]["judge_score"] == 1.0
    assert (output_dir / "judge-summary.json").exists()
    assert (output_dir / "judge-rubric.md").exists()


def test_judge_agent_loop_penalizes_missing_evidence_and_negative_failure(tmp_path: Path):
    traces = tmp_path / "agent-traces.jsonl"
    traces.write_text(
        json.dumps(
            {
                "trace_schema_version": "phase10.agent-loop.v1",
                "trace_id": "agent-loop-hybrid:task-002",
                "task_id": "task-002",
                "prompt": "Route safely without choosing a negative skill.",
                "execution_condition": "routed-skill",
                "source_router": "hybrid",
                "selected_skill_ids": ["visual-regression-review"],
                "agent_status": "failed",
                "agent_success": False,
                "expected_evidence": ["safe skill selected", "final evidence noted"],
                "evidence_checks": [
                    {"name": "safe skill selected", "satisfied": False},
                    {"name": "final evidence noted", "satisfied": False},
                ],
                "failure_type": "negative_skill_selected",
                "failure_reason": "Selected a task negative skill.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = judge_agent_loop(
        traces_path=traces,
        output_dir=tmp_path / "judge",
        run_label="judge-agent-loop-hybrid",
    )

    record = _read_jsonl(tmp_path / "judge" / "judge-results.jsonl")[0]
    assert summary["judge_pass_rate"] == 0.0
    assert record["judge_status"] == "failed"
    assert record["evidence_score"] == 0.0
    assert record["penalties"] == [
        "missing-evidence",
        "negative-skill-failure",
        "agent-loop-failed",
    ]


def test_judge_agent_loop_rejects_unknown_trace_schema(tmp_path: Path):
    traces = tmp_path / "agent-traces.jsonl"
    traces.write_text(
        json.dumps({"trace_schema_version": "wrong", "trace_id": "x", "task_id": "x"}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported trace_schema_version"):
        judge_agent_loop(traces_path=traces, output_dir=tmp_path / "judge")


def test_judge_agent_loop_rejects_evidence_checks_without_expected_names(
    tmp_path: Path,
):
    traces = tmp_path / "agent-traces.jsonl"
    traces.write_text(
        json.dumps(
            _trace(
                expected_evidence=["A", "B"],
                evidence_checks=[
                    {"satisfied": True},
                    {"satisfied": True},
                ],
            )
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="evidence_checks\\[1\\]\\.name"):
        judge_agent_loop(traces_path=traces, output_dir=tmp_path / "judge")


def test_judge_agent_loop_rejects_mismatched_or_duplicate_evidence_checks(
    tmp_path: Path,
):
    mismatched = tmp_path / "mismatched.jsonl"
    mismatched.write_text(
        json.dumps(
            _trace(
                expected_evidence=["A"],
                evidence_checks=[
                    {"name": "A", "satisfied": True},
                    {"name": "extra", "satisfied": True},
                ],
            )
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must match expected_evidence"):
        judge_agent_loop(traces_path=mismatched, output_dir=tmp_path / "mismatched")

    duplicate = tmp_path / "duplicate.jsonl"
    duplicate.write_text(
        json.dumps(
            _trace(
                expected_evidence=["A"],
                evidence_checks=[
                    {"name": "A", "satisfied": True},
                    {"name": "A", "satisfied": True},
                ],
            )
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate evidence check"):
        judge_agent_loop(traces_path=duplicate, output_dir=tmp_path / "duplicate")


def test_judge_agent_loop_scores_are_bounded_by_expected_evidence(tmp_path: Path):
    traces = tmp_path / "agent-traces.jsonl"
    traces.write_text(
        json.dumps(
            _trace(
                expected_evidence=["A"],
                evidence_checks=[
                    {"name": "A", "satisfied": True},
                ],
            )
        )
        + "\n",
        encoding="utf-8",
    )

    summary = judge_agent_loop(traces_path=traces, output_dir=tmp_path / "judge")
    record = _read_jsonl(tmp_path / "judge" / "judge-results.jsonl")[0]

    assert summary["mean_evidence_score"] == 1.0
    assert summary["mean_judge_score"] == 1.0
    assert record["evidence_score"] == 1.0
    assert record["judge_score"] == 1.0


def _trace(
    *,
    expected_evidence: list[str],
    evidence_checks: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "trace_schema_version": "phase10.agent-loop.v1",
        "trace_id": "agent-loop-hybrid:task-malformed",
        "task_id": "task-malformed",
        "prompt": "Judge evidence checks.",
        "execution_condition": "routed-skill",
        "source_router": "hybrid",
        "selected_skill_ids": ["systematic-debugging"],
        "agent_status": "passed",
        "agent_success": True,
        "expected_evidence": expected_evidence,
        "evidence_checks": evidence_checks,
        "failure_type": None,
        "failure_reason": None,
    }


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
