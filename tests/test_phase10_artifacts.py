import json
from pathlib import Path


PHASE10_ROOT = Path("docs/demo/phase10-agent-in-the-loop")
README = Path("README.md")
PHASE10_DOC = Path("docs/phase10.md")
TIMELINE = Path("docs/experiment-timeline.md")

RUNS = {
    "agent-loop-no-skill-hybrid": "no-skill",
    "agent-loop-hybrid": "routed-skill",
    "agent-loop-oracle-skill-hybrid": "oracle-skill",
}


def test_phase10_agent_loop_artifacts_cover_three_conditions():
    for run_label, condition in RUNS.items():
        run_dir = PHASE10_ROOT / run_label
        results = _read_jsonl(run_dir / "results.jsonl")
        traces = _read_jsonl(run_dir / "agent-traces.jsonl")
        summary = json.loads((run_dir / "agent-loop-summary.json").read_text())
        report = (run_dir / "report.md").read_text(encoding="utf-8")

        assert len(results) == 12
        assert len(traces) == 12
        assert summary["phase"] == "Phase 10"
        assert summary["execution_condition"] == condition
        assert summary["task_count"] == 12
        assert report.startswith("# Phase 10 Agent-in-the-loop Report")
        assert {record["execution_condition"] for record in results} == {condition}
        assert all(isinstance(record.get("prompt"), str) and record["prompt"] for record in results)
        assert {trace["execution_condition"] for trace in traces} == {condition}
        assert all(isinstance(trace.get("prompt"), str) and trace["prompt"] for trace in traces)
        assert {
            trace["trace_schema_version"]
            for trace in traces
        } == {
            "phase10.agent-loop.v1"
        }

    no_skill = json.loads(
        (PHASE10_ROOT / "agent-loop-no-skill-hybrid" / "agent-loop-summary.json")
        .read_text(encoding="utf-8")
    )
    oracle = json.loads(
        (PHASE10_ROOT / "agent-loop-oracle-skill-hybrid" / "agent-loop-summary.json")
        .read_text(encoding="utf-8")
    )
    routed = json.loads(
        (PHASE10_ROOT / "agent-loop-hybrid" / "agent-loop-summary.json")
        .read_text(encoding="utf-8")
    )

    assert no_skill["agent_success_rate"] == 0.0
    assert routed["agent_success_rate"] > no_skill["agent_success_rate"]
    assert oracle["agent_success_rate"] == 1.0


def test_phase10_dashboard_and_comparison_are_committed():
    dashboard = (PHASE10_ROOT / "dashboard.html").read_text(encoding="utf-8")
    comparison = (PHASE10_ROOT / "comparison.md").read_text(encoding="utf-8")
    summary = json.loads((PHASE10_ROOT / "phase10-summary.json").read_text())

    assert "Phase 10 Agent-in-the-loop" in dashboard
    assert "agent-loop-no-skill-hybrid" in dashboard
    assert "agent-loop-hybrid" in dashboard
    assert "agent-loop-oracle-skill-hybrid" in dashboard
    assert "Hermes SkillEval Router Comparison" in comparison
    assert summary["phase"] == "Phase 10"
    assert summary["run_labels"] == sorted(RUNS)
    assert summary["conditions"] == [
        "no-skill",
        "oracle-skill",
        "routed-skill",
    ]


def test_phase10_is_documented_in_readme_and_phase_notes():
    readme = README.read_text(encoding="utf-8")
    phase10 = PHASE10_DOC.read_text(encoding="utf-8")
    timeline = TIMELINE.read_text(encoding="utf-8")

    assert "docs/experiment-timeline.md" in readme
    assert "| Phase 10 | Agent-in-the-loop migration evaluation |" in timeline
    assert "- [x] Agent-in-the-loop skill routing evaluation" in readme
    assert "run-agent-loop" in readme
    assert "three execution conditions" in phase10
    assert "agent-traces.jsonl" in phase10
    assert "deterministic" in phase10


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
