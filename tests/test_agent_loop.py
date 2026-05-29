import json
from pathlib import Path
from typing import Any

import yaml

from hermes_skilleval.agent_loop import run_agent_loop


def test_run_agent_loop_writes_dashboard_compatible_results_and_traces(tmp_path: Path):
    tasks = tmp_path / "tasks"
    _write_task(
        tasks,
        task_id="debug-task",
        gold_skills=["systematic-debugging"],
        negative_skills=["visual-regression-review"],
        expected_evidence=["failing test reproduced", "root cause stated"],
        migration_dimensions=["instruction fidelity", "evidence completeness"],
    )
    skills_index = tmp_path / "skills.json"
    skills_index.write_text(
        json.dumps(
            [
                {
                    "id": "systematic-debugging",
                    "name": "Systematic Debugging",
                    "path": "benchmarks/migrated-skills/superpowers/systematic-debugging/SKILL.md",
                    "category": "superpowers",
                    "description": "Debug failures with evidence.",
                    "body": "Reproduce, isolate, fix, and verify failures.",
                    "trigger_terms": ["debug"],
                    "token_count_estimate": 10,
                }
            ]
        ),
        encoding="utf-8",
    )
    routes = tmp_path / "routes.jsonl"
    routes.write_text(
        json.dumps(
            {
                "task_id": "debug-task",
                "router": "hybrid",
                "selected_skill_ids": ["systematic-debugging"],
                "scores": {"systematic-debugging": 1.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "agent-loop-hybrid"

    summary = run_agent_loop(
        routes_path=routes,
        tasks_path=tasks,
        skills_index_path=skills_index,
        output_dir=output_dir,
    )

    records = _read_jsonl(output_dir / "results.jsonl")
    traces = _read_jsonl(output_dir / "agent-traces.jsonl")

    assert summary["task_count"] == 1
    assert summary["agent_success_rate"] == 1.0
    assert records[0]["router"] == "agent-loop-hybrid"
    assert records[0]["task_id"] == "debug-task"
    assert records[0]["prompt"] == "Debug the failing test and preserve evidence."
    assert records[0]["selected_skill_ids"] == ["systematic-debugging"]
    assert records[0]["agent_success"] is True
    assert records[0]["trace_id"] == "agent-loop-hybrid:debug-task"
    assert records[0]["execution_condition"] == "routed-skill"
    assert records[0]["expected_evidence"] == [
        "failing test reproduced",
        "root cause stated",
    ]
    assert records[0]["dimension_scores"] == {
        "instruction fidelity": 1.0,
        "evidence completeness": 1.0,
    }
    assert records[0]["recall_at_5"] == 1.0
    assert records[0]["negative_hit_rate"] == 0.0
    assert traces[0]["trace_schema_version"] == "phase10.agent-loop.v1"
    assert traces[0]["prompt"] == "Debug the failing test and preserve evidence."
    assert traces[0]["loop_steps"][0]["step"] == "read_task"
    assert traces[0]["loop_steps"][-1]["step"] == "final_handoff"
    assert (output_dir / "report.md").read_text(encoding="utf-8").startswith(
        "# Phase 10 Agent-in-the-loop Report"
    )


def _write_task(
    root: Path,
    *,
    task_id: str,
    gold_skills: list[str],
    negative_skills: list[str],
    expected_evidence: list[str],
    migration_dimensions: list[str],
) -> None:
    task_dir = root / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "id": task_id,
                "category": "migration",
                "difficulty": "medium",
                "gold_skills": gold_skills,
                "negative_skills": negative_skills,
                "verifier": "manual",
                "split": "test",
                "robustness_tags": ["migration-evaluation"],
                "migration_source": "superpowers",
                "expected_evidence": expected_evidence,
                "migration_dimensions": migration_dimensions,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (task_dir / "prompt.md").write_text(
        "Debug the failing test and preserve evidence.",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
